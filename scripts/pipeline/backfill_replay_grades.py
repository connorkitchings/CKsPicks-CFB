#!/usr/bin/env python3
"""Grade every replay prediction that has a frozen line and a final score.

The operational scorer writes grades only for above-threshold bets. This
backfills the remaining lean-graded rows (edge below the bet threshold) for
the selection-time 2025 replay runs so the retrospective season record is
complete. It applies the identical frozen-line rule as the pipeline
(grading_version ``frozen_line_v2``) and never overwrites existing grades.
"""

from __future__ import annotations

import argparse
import os
import sys

import psycopg
from dotenv import load_dotenv

sys.path.append(os.getcwd())

from scripts.pipeline.score_to_db import (  # noqa: E402
    UPSERT_GRADE_SQL,
    _profit,
    recompute_stats,
)


def spread_result(
    home_points: float | None,
    away_points: float | None,
    line: float | None,
    lean: str | None,
) -> str | None:
    """Frozen-line spread grade for a lean; None when ungradable."""
    if home_points is None or away_points is None or line is None:
        return None
    if lean not in ("home", "away"):
        return None
    cover_margin = (home_points - away_points) + line
    if cover_margin > 0:
        return "win" if lean == "home" else "loss"
    if cover_margin < 0:
        return "loss" if lean == "home" else "win"
    return "push"


def total_result(
    home_points: float | None,
    away_points: float | None,
    line: float | None,
    lean: str | None,
) -> str | None:
    """Frozen-line total grade for a lean; None when ungradable."""
    if home_points is None or away_points is None or line is None:
        return None
    if lean not in ("over", "under"):
        return None
    score = home_points + away_points
    if score > line:
        return "win" if lean == "over" else "loss"
    if score < line:
        return "loss" if lean == "over" else "win"
    return "push"


def _resolve_db_url(environment: str, confirm_production: bool) -> str:
    if environment == "production":
        if not confirm_production:
            raise SystemExit("Production grade backfills require --confirm-production")
        url = os.getenv("DATABASE_URL")
        if not url:
            raise SystemExit("DATABASE_URL is not set")
        return url
    url = os.getenv("PREVIEW_DATABASE_URL")
    if not url:
        raise SystemExit("PREVIEW_DATABASE_URL must identify an isolated Neon branch")
    if url == os.getenv("DATABASE_URL"):
        raise SystemExit("PREVIEW_DATABASE_URL must not equal DATABASE_URL")
    return url


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument(
        "--environment", choices=("preview", "production"), default="preview"
    )
    parser.add_argument("--model-id", default="v4-locked-test-replay-20260909b")
    parser.add_argument("--confirm-production", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    conn_url = _resolve_db_url(args.environment, args.confirm_production)

    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT g.week, p.run_id, p.game_id,
                       p.home_team_spread_line, p.total_line,
                       p.spread_lean, p.total_lean, p.market_snapshot_id,
                       gr.home_points, gr.away_points,
                       pg_s.result AS spread_grade, pg_t.result AS total_grade
                FROM predictions p
                JOIN prediction_runs pr ON p.run_id = pr.run_id
                JOIN games g ON p.game_id = g.game_id
                LEFT JOIN game_results gr ON g.game_id = gr.game_id
                LEFT JOIN prediction_grades pg_s
                  ON pg_s.run_id = p.run_id AND pg_s.game_id = p.game_id
                 AND pg_s.target = 'spread'
                LEFT JOIN prediction_grades pg_t
                  ON pg_t.run_id = p.run_id AND pg_t.game_id = p.game_id
                 AND pg_t.target = 'total'
                WHERE pr.model_id = %s AND g.season = %s
                ORDER BY g.week, p.game_id
                """,
                (args.model_id, args.year),
            )
            rows = cur.fetchall()
    inserted = {"spread": 0, "total": 0}
    pending: list[dict] = []
    for (
        week,
        run_id,
        game_id,
        spread_line,
        total_line,
        spread_lean,
        total_lean,
        snapshot_id,
        home_points,
        away_points,
        spread_grade,
        total_grade,
    ) in rows:
        home = float(home_points) if home_points is not None else None
        away = float(away_points) if away_points is not None else None
        candidates = (
            (
                "spread",
                spread_grade,
                spread_result(home, away, spread_line, (spread_lean or "").lower()),
                (spread_lean or "").lower(),
            ),
            (
                "total",
                total_grade,
                total_result(home, away, total_line, (total_lean or "").lower()),
                (total_lean or "").lower(),
            ),
        )
        for target, existing, result, side in candidates:
            if existing is not None or result is None:
                continue
            pending.append(
                {
                    "run_id": run_id,
                    "game_id": int(game_id),
                    "target": target,
                    "market_snapshot_id": snapshot_id,
                    "side": side,
                    "result": result,
                    "profit_units": _profit(result),
                    "grading_version": "frozen_line_v2",
                }
            )
            inserted[target] += 1
    print(
        f"{args.year} replay: {len(rows)} predictions scanned, "
        f"backfilling {inserted['spread']} spread + {inserted['total']} total grades"
        + (" (dry run)" if args.dry_run else "")
    )
    if args.dry_run or not pending:
        return
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            for record in pending:
                cur.execute(UPSERT_GRADE_SQL, record)
        conn.commit()
    stats = recompute_stats(conn_url, args.year)
    print(
        f"{args.year} system_stats refreshed: spread "
        f"{stats.get('spread_wins')}-{stats.get('spread_losses')}-{stats.get('spread_pushes')} · "
        f"total {stats.get('total_wins')}-{stats.get('total_losses')}-{stats.get('total_pushes')}"
    )


if __name__ == "__main__":
    main()
