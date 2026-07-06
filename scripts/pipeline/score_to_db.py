#!/usr/bin/env python3
"""
Backfill game results from scored CSVs into Postgres and refresh system_stats.

Reads:  data/production/scored/{year}/CFB_week{N}_bets_scored.csv
Writes: game_results table (upsert), system_stats table (recompute from results)

Usage:
    # Score a single week + refresh YTD stats
    PYTHONPATH=. uv run python scripts/pipeline/score_to_db.py --year 2025 --week 14

    # Backfill all scored weeks for a season (recompute YTD from scratch)
    PYTHONPATH=. uv run python scripts/pipeline/score_to_db.py --year 2025 --backfill-season

    # Just refresh the YTD aggregate without touching game_results
    PYTHONPATH=. uv run python scripts/pipeline/score_to_db.py --year 2025 --refresh-stats-only
"""

from __future__ import annotations

import argparse
import glob
import os
import re
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

try:
    import psycopg
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "psycopg not installed. Run: uv sync  (psycopg[binary] is in pyproject.toml)"
    ) from exc


# ---------------------------------------------------------------------------
# Result parsing
# ---------------------------------------------------------------------------


def _normalize_result(val) -> str | None:
    """Map CSV 'Win'/'Loss'/'Push'/NaN to lower-case enum value or None."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip().lower()
    if s in {"win", "loss", "push"}:
        return s
    return None


def load_scored(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"Scored CSV not found: {csv_path}")
    df = pd.read_csv(csv_path)

    for col in ["game_id", "home_points", "away_points"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Bet result columns vary across pipeline versions; coalesce to canonical names.
    spread_result_col = None
    for cand in ["Spread Bet Result", "spread_result"]:
        if cand in df.columns:
            spread_result_col = cand
            break
    total_result_col = None
    for cand in ["Total Bet Result", "total_result"]:
        if cand in df.columns:
            total_result_col = cand
            break

    df["spread_result_norm"] = (
        df[spread_result_col].apply(_normalize_result) if spread_result_col else None
    )
    df["total_result_norm"] = (
        df[total_result_col].apply(_normalize_result) if total_result_col else None
    )
    return df


# ---------------------------------------------------------------------------
# Postgres upserts
# ---------------------------------------------------------------------------

UPSERT_RESULT_SQL = """
INSERT INTO game_results (
    game_id, home_points, away_points, spread_result, total_result, scored_at
) VALUES (
    %(game_id)s, %(home_points)s, %(away_points)s,
    %(spread_result)s, %(total_result)s, NOW()
)
ON CONFLICT (game_id) DO UPDATE SET
    home_points = EXCLUDED.home_points,
    away_points = EXCLUDED.away_points,
    spread_result = EXCLUDED.spread_result,
    total_result = EXCLUDED.total_result,
    scored_at = NOW()
"""

RECOMPUTE_STATS_SQL = """
INSERT INTO system_stats (
    season, as_of_week,
    spread_wins, spread_losses, spread_pushes,
    total_wins, total_losses, total_pushes,
    updated_at
)
SELECT
    %(season)s AS season,
    COALESCE(MAX(g.week), 0) AS as_of_week,
    COUNT(DISTINCT CASE WHEN gr.spread_result = 'win'  THEN g.game_id END) AS spread_wins,
    COUNT(DISTINCT CASE WHEN gr.spread_result = 'loss' THEN g.game_id END) AS spread_losses,
    COUNT(DISTINCT CASE WHEN gr.spread_result = 'push' THEN g.game_id END) AS spread_pushes,
    COUNT(DISTINCT CASE WHEN gr.total_result  = 'win'  THEN g.game_id END) AS total_wins,
    COUNT(DISTINCT CASE WHEN gr.total_result  = 'loss' THEN g.game_id END) AS total_losses,
    COUNT(DISTINCT CASE WHEN gr.total_result  = 'push' THEN g.game_id END) AS total_pushes,
    NOW()
FROM games g
JOIN game_results gr ON g.game_id = gr.game_id
WHERE g.season = %(season)s
ON CONFLICT (season) DO UPDATE SET
    as_of_week    = EXCLUDED.as_of_week,
    spread_wins   = EXCLUDED.spread_wins,
    spread_losses = EXCLUDED.spread_losses,
    spread_pushes = EXCLUDED.spread_pushes,
    total_wins    = EXCLUDED.total_wins,
    total_losses  = EXCLUDED.total_losses,
    total_pushes  = EXCLUDED.total_pushes,
    updated_at    = NOW()
"""


def upsert_results(df: pd.DataFrame, conn_url: str) -> int:
    count = 0
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            for _, row in df.iterrows():
                if pd.isna(row.get("game_id")):
                    continue
                home_pts = row.get("home_points")
                away_pts = row.get("away_points")
                if pd.isna(home_pts) or pd.isna(away_pts):
                    # Game not yet played; skip
                    continue
                cur.execute(
                    UPSERT_RESULT_SQL,
                    {
                        "game_id": int(row["game_id"]),
                        "home_points": int(home_pts),
                        "away_points": int(away_pts),
                        "spread_result": row.get("spread_result_norm"),
                        "total_result": row.get("total_result_norm"),
                    },
                )
                count += 1
            conn.commit()
    return count


def recompute_stats(conn_url: str, season: int) -> dict:
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            cur.execute(RECOMPUTE_STATS_SQL, {"season": season})
            cur.execute(
                "SELECT season, as_of_week, spread_wins, spread_losses, spread_pushes, "
                "total_wins, total_losses, total_pushes FROM system_stats WHERE season = %s",
                (season,),
            )
            row = cur.fetchone()
            conn.commit()
    if not row:
        return {}
    return {
        "season": row[0],
        "as_of_week": row[1],
        "spread_wins": row[2],
        "spread_losses": row[3],
        "spread_pushes": row[4],
        "total_wins": row[5],
        "total_losses": row[6],
        "total_pushes": row[7],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

WEEK_RE = re.compile(r"week(\d+)", re.IGNORECASE)


def _find_scored_csvs(season: int) -> list[tuple[int, Path]]:
    pattern = f"data/production/scored/{season}/CFB_week*_bets_scored.csv"
    out: list[tuple[int, Path]] = []
    for p in sorted(glob.glob(pattern)):
        m = WEEK_RE.search(Path(p).name)
        if m:
            out.append((int(m.group(1)), Path(p)))
    return out


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Backfill game_results and refresh system_stats."
    )
    parser.add_argument("--year", type=int, required=True, help="Season year")
    parser.add_argument(
        "--week", type=int, help="Specific week to score (ignored if --backfill-season)"
    )
    parser.add_argument(
        "--backfill-season",
        action="store_true",
        help="Process every scored CSV for the season",
    )
    parser.add_argument(
        "--refresh-stats-only",
        action="store_true",
        help="Skip game_results upsert; just recompute system_stats",
    )
    args = parser.parse_args()

    conn_url = os.environ.get("DATABASE_URL")
    if not conn_url:
        raise SystemExit("DATABASE_URL not set. Add it to .env.")

    if args.backfill_season:
        targets = _find_scored_csvs(args.year)
        if not targets:
            print(f"No scored CSVs found for {args.year}")
            return
        print(f"Backfilling {len(targets)} weeks for {args.year}")
        for week, csv_path in targets:
            df = load_scored(csv_path)
            n = upsert_results(df, conn_url) if not args.refresh_stats_only else 0
            print(f"  week {week}: {n} results upserted from {csv_path.name}")
    elif args.week:
        csv_path = Path(
            f"data/production/scored/{args.year}/CFB_week{args.week}_bets_scored.csv"
        )
        if not args.refresh_stats_only:
            df = load_scored(csv_path)
            n = upsert_results(df, conn_url)
            print(f"Upserted {n} results from {csv_path.name}")
        else:
            print("--refresh-stats-only: skipping game_results")
    else:
        raise SystemExit("Must pass either --week or --backfill-season")

    stats = recompute_stats(conn_url, args.year)
    if stats:
        print(
            f"✅ {args.year} YTD through week {stats['as_of_week']}: "
            f"spread {stats['spread_wins']}-{stats['spread_losses']}-{stats['spread_pushes']} · "
            f"total {stats['total_wins']}-{stats['total_losses']}-{stats['total_pushes']}"
        )
    else:
        print(f"No stats produced for {args.year}")


if __name__ == "__main__":
    main()
