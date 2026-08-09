#!/usr/bin/env python3
"""
Backfill game results from scored CSVs into Postgres and refresh system_stats.

Reads:  ephemeral scored working CSVs, or immutable checksummed artifacts when
        --from-artifact is used.
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

from cks_picks_cfb.artifacts import (
    local_scored_path,
    read_csv_artifact,
    read_json_artifact,
    read_verified_csv_artifact,
    scored_artifact_path,
    scored_artifact_prefix,
    scored_run_manifest_path,
)
from cks_picks_cfb.data.storage import get_storage

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
    return prepare_scored(pd.read_csv(csv_path))


def load_scored_artifact(artifact_path: str) -> pd.DataFrame:
    return prepare_scored(read_csv_artifact(artifact_path))


def prepare_scored(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize a scored bets dataframe for DB upsert."""

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
    if "spread_lean" not in df.columns and "Spread Bet" in df.columns:
        df["spread_lean"] = df["Spread Bet"].astype(str).str.lower()
    if "total_lean" not in df.columns and "Total Bet" in df.columns:
        df["total_lean"] = df["Total Bet"].astype(str).str.lower()
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

UPSERT_OBJECTIVE_RESULT_SQL = """
INSERT INTO game_results (
    game_id, home_points, away_points, completion_state, scored_at
) VALUES (
    %(game_id)s, %(home_points)s, %(away_points)s, 'completed', NOW()
)
ON CONFLICT (game_id) DO UPDATE SET
    home_points = EXCLUDED.home_points,
    away_points = EXCLUDED.away_points,
    completion_state = 'completed',
    scored_at = NOW()
"""

RECOMPUTE_STATS_SQL = """
WITH selected_runs AS (
    SELECT DISTINCT ON (season, week) run_id
    FROM prediction_runs
    WHERE season = %(season)s AND state = 'scored'
    ORDER BY season, week, scored_at DESC NULLS LAST, created_at DESC
)
INSERT INTO system_stats (
    season, as_of_week,
    spread_wins, spread_losses, spread_pushes,
    total_wins, total_losses, total_pushes,
    spread_profit_units, total_profit_units,
    updated_at
)
SELECT
    %(season)s AS season,
    COALESCE(MAX(g.week), 0) AS as_of_week,
    COUNT(*) FILTER (WHERE pg.target = 'spread' AND pg.result = 'win') AS spread_wins,
    COUNT(*) FILTER (WHERE pg.target = 'spread' AND pg.result = 'loss') AS spread_losses,
    COUNT(*) FILTER (WHERE pg.target = 'spread' AND pg.result = 'push') AS spread_pushes,
    COUNT(*) FILTER (WHERE pg.target = 'total' AND pg.result = 'win') AS total_wins,
    COUNT(*) FILTER (WHERE pg.target = 'total' AND pg.result = 'loss') AS total_losses,
    COUNT(*) FILTER (WHERE pg.target = 'total' AND pg.result = 'push') AS total_pushes,
    COALESCE(SUM(pg.profit_units) FILTER (WHERE pg.target = 'spread'), 0) AS spread_profit_units,
    COALESCE(SUM(pg.profit_units) FILTER (WHERE pg.target = 'total'), 0) AS total_profit_units,
    NOW()
FROM games g
JOIN prediction_grades pg ON g.game_id = pg.game_id
JOIN selected_runs sr ON sr.run_id = pg.run_id
WHERE g.season = %(season)s
ON CONFLICT (season) DO UPDATE SET
    as_of_week    = EXCLUDED.as_of_week,
    spread_wins   = EXCLUDED.spread_wins,
    spread_losses = EXCLUDED.spread_losses,
    spread_pushes = EXCLUDED.spread_pushes,
    total_wins    = EXCLUDED.total_wins,
    total_losses  = EXCLUDED.total_losses,
    total_pushes  = EXCLUDED.total_pushes,
    spread_profit_units = EXCLUDED.spread_profit_units,
    total_profit_units = EXCLUDED.total_profit_units,
    updated_at    = NOW()
"""

UPSERT_GRADE_SQL = """
INSERT INTO prediction_grades (
    run_id, game_id, target, market_snapshot_id, side, result,
    profit_units, grading_version, graded_at
) VALUES (
    %(run_id)s, %(game_id)s, %(target)s, %(market_snapshot_id)s,
    %(side)s, %(result)s, %(profit_units)s, %(grading_version)s, NOW()
)
ON CONFLICT (run_id, game_id, target) DO UPDATE SET
    market_snapshot_id = EXCLUDED.market_snapshot_id,
    side = EXCLUDED.side,
    result = EXCLUDED.result,
    profit_units = EXCLUDED.profit_units,
    grading_version = EXCLUDED.grading_version,
    graded_at = NOW()
"""


def _profit(result: str) -> float:
    return {"win": 1.0, "loss": -1.1, "push": 0.0}[result]


def _upsert_run_grades(cur, scored: pd.Series, *, run_id: str) -> None:
    """Store spread and total outcomes against the exact frozen run."""
    game_id = int(scored["game_id"])
    for target, result_column, side_column in (
        ("spread", "spread_result_norm", "spread_lean"),
        ("total", "total_result_norm", "total_lean"),
    ):
        result = scored.get(result_column)
        side = scored.get(side_column)
        if result is None or pd.isna(side):
            continue
        snapshot_id = scored.get("market_snapshot_id")
        if pd.isna(snapshot_id):
            snapshot_id = None
        cur.execute(
            UPSERT_GRADE_SQL,
            {
                "run_id": run_id,
                "game_id": game_id,
                "target": target,
                "market_snapshot_id": snapshot_id,
                "side": str(side).lower(),
                "result": result,
                "profit_units": _profit(result),
                "grading_version": "frozen_line_v2",
            },
        )


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


def mark_run_scored(conn_url: str, run_id: str) -> None:
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE prediction_runs
                SET state = 'scored', scored_at = NOW()
                WHERE run_id = %s AND state = 'frozen'
                """,
                (run_id,),
            )
            if cur.rowcount != 1:
                raise RuntimeError(
                    f"Run {run_id} must exist and be frozen before scoring"
                )
            conn.commit()


def publish_scored_run(
    df: pd.DataFrame, conn_url: str, *, run_id: str, season: int
) -> tuple[int, dict]:
    """Atomically publish results, refresh stats, and mark the frozen run scored."""
    count = 0
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT state FROM prediction_runs WHERE run_id = %s FOR UPDATE",
                (run_id,),
            )
            row = cur.fetchone()
            if not row or row[0] not in {"frozen", "scored"}:
                raise RuntimeError(
                    f"Run {run_id} must exist and be frozen before scoring"
                )
            already_scored = row[0] == "scored"
            if already_scored:
                cur.execute(
                    "SELECT COUNT(DISTINCT game_id) FROM prediction_grades "
                    "WHERE run_id = %s",
                    (run_id,),
                )
                count = int(cur.fetchone()[0])
            else:
                for _, scored in df.iterrows():
                    if pd.isna(scored.get("game_id")):
                        continue
                    home_pts = scored.get("home_points")
                    away_pts = scored.get("away_points")
                    if pd.isna(home_pts) or pd.isna(away_pts):
                        continue
                    cur.execute(
                        UPSERT_OBJECTIVE_RESULT_SQL,
                        {
                            "game_id": int(scored["game_id"]),
                            "home_points": int(home_pts),
                            "away_points": int(away_pts),
                        },
                    )
                    _upsert_run_grades(cur, scored, run_id=run_id)
                    count += 1
                cur.execute(
                    "UPDATE prediction_runs SET state = 'scored', scored_at = NOW() "
                    "WHERE run_id = %s AND state = 'frozen'",
                    (run_id,),
                )
                if cur.rowcount != 1:
                    raise RuntimeError(f"Run {run_id} changed state during scoring")
                cur.execute(
                    "INSERT INTO ops.activation_history "
                    "(environment, season, week, run_id, action, metadata) "
                    "SELECT %s, "
                    "season, week, run_id, 'score', '{}'::jsonb "
                    "FROM prediction_runs WHERE run_id = %s "
                    "ON CONFLICT (run_id, action) DO NOTHING",
                    (os.getenv("CFB_ARTIFACT_ENV", "production"), run_id),
                )
            cur.execute(RECOMPUTE_STATS_SQL, {"season": season})
            cur.execute(
                "SELECT season, as_of_week, spread_wins, spread_losses, spread_pushes, "
                "total_wins, total_losses, total_pushes FROM system_stats WHERE season = %s",
                (season,),
            )
            stats_row = cur.fetchone()
            conn.commit()
    stats = (
        {
            "season": stats_row[0],
            "as_of_week": stats_row[1],
            "spread_wins": stats_row[2],
            "spread_losses": stats_row[3],
            "spread_pushes": stats_row[4],
            "total_wins": stats_row[5],
            "total_losses": stats_row[6],
            "total_pushes": stats_row[7],
        }
        if stats_row
        else {}
    )
    return count, stats


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
WEEK_PARTITION_RE = re.compile(r"week=(\d+)", re.IGNORECASE)


def _find_scored_csvs(season: int) -> list[tuple[int, Path]]:
    pattern = str(local_scored_path(season, 1).parent / "CFB_week*_bets_scored.csv")
    out: list[tuple[int, Path]] = []
    for p in sorted(glob.glob(pattern)):
        m = WEEK_RE.search(Path(p).name)
        if m:
            out.append((int(m.group(1)), Path(p)))
    return out


def _find_scored_artifacts(season: int) -> list[tuple[int, str]]:
    storage = get_storage()
    prefix = scored_artifact_prefix(season)
    out: list[tuple[int, str]] = []
    for path in sorted(storage.list_files(prefix)):
        m = WEEK_PARTITION_RE.search(path)
        if m and path.endswith("/scored.json"):
            out.append((int(m.group(1)), path))
            continue
        m = WEEK_RE.search(Path(path).name)
        if m:
            out.append((int(m.group(1)), path))
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
    parser.add_argument(
        "--from-artifact",
        action="store_true",
        help="Read scored CSVs from durable storage instead of local working copies.",
    )
    parser.add_argument(
        "--artifact-path",
        type=str,
        default=None,
        help="Explicit durable scored CSV path (legacy/backfill only).",
    )
    parser.add_argument("--run-id", help="Exact frozen run ID to publish grades for.")
    args = parser.parse_args()

    conn_url = os.environ.get("DATABASE_URL")
    if not conn_url:
        raise SystemExit("DATABASE_URL not set. Add it to .env.")

    use_artifact = args.from_artifact or args.artifact_path is not None

    if args.backfill_season:
        targets = (
            _find_scored_artifacts(args.year)
            if use_artifact
            else _find_scored_csvs(args.year)
        )
        if not targets:
            print(f"No scored CSVs found for {args.year}")
            return
        print(f"Backfilling {len(targets)} weeks for {args.year}")
        for week, source_path in targets:
            if use_artifact and str(source_path).endswith("/scored.json"):
                manifest = read_json_artifact(str(source_path))
                df = prepare_scored(read_verified_csv_artifact(manifest))
            else:
                df = (
                    load_scored_artifact(source_path)
                    if use_artifact
                    else load_scored(source_path)
                )
            n = upsert_results(df, conn_url) if not args.refresh_stats_only else 0
            source_name = Path(source_path).name
            print(f"  week {week}: {n} results upserted from {source_name}")
    elif args.week:
        csv_path = local_scored_path(args.year, args.week)
        scored_manifest = None
        if use_artifact and not args.artifact_path:
            if not args.run_id:
                raise SystemExit("--run-id is required with --from-artifact")
            scored_manifest = read_json_artifact(
                scored_run_manifest_path(args.year, args.week, args.run_id)
            )
            artifact_path = str(scored_manifest["artifact_uri"])
        else:
            artifact_path = args.artifact_path or scored_artifact_path(
                args.year, args.week
            )
        stats = None
        if not args.refresh_stats_only:
            if scored_manifest:
                df = prepare_scored(read_verified_csv_artifact(scored_manifest))
            elif use_artifact:
                df = load_scored_artifact(artifact_path)
            else:
                df = load_scored(csv_path)
            if scored_manifest:
                n, stats = publish_scored_run(
                    df,
                    conn_url,
                    run_id=str(scored_manifest["run_id"]),
                    season=args.year,
                )
            else:
                n = upsert_results(df, conn_url)
            source_name = Path(artifact_path if use_artifact else csv_path).name
            print(f"Upserted {n} results from {source_name}")
        else:
            print("--refresh-stats-only: skipping game_results")
    else:
        raise SystemExit("Must pass either --week or --backfill-season")

    if "stats" not in locals() or stats is None:
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
