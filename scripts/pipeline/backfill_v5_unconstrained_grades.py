#!/usr/bin/env python3
"""Backfill unconstrained (threshold 0.0) grades and leans for 2026 V5 runs.

Grades every scheduled game with a model forecast, a market line, and certified
final scores. For sub-1.0/sub-1.5 targets where the pipeline previously marked
leans as null or 'No Bet', this script:
1. Resolves the mathematical model lean.
2. Updates predictions.spread_lean/total_lean where null.
3. Updates prediction_market_selections.side where 'No Bet'.
4. Inserts missing prediction_grades (never overwrites existing grades).
5. Recomputes system_stats for the season.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

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
            raise SystemExit("Production mutations require --confirm-production")
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


def dump_snapshot(conn_url: str, season: int, output_path: Path) -> None:
    """Export pre-mutation state of affected tables for audit and rollback."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "season": season,
        "prediction_grades": [],
        "predictions": [],
        "prediction_market_selections": [],
        "system_stats": [],
    }
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT pg.run_id, pg.game_id, pg.target, pg.side, pg.result, pg.profit_units
                FROM prediction_grades pg
                JOIN site_week_selections sws ON pg.run_id = sws.run_id
                WHERE sws.season = %s
                ORDER BY pg.game_id, pg.target
                """,
                (season,),
            )
            snapshot["prediction_grades"] = [
                {
                    "run_id": r[0],
                    "game_id": r[1],
                    "target": r[2],
                    "side": r[3],
                    "result": r[4],
                    "profit_units": float(r[5]) if r[5] is not None else None,
                }
                for r in cur.fetchall()
            ]

            cur.execute(
                """
                SELECT p.run_id, p.game_id, p.spread_lean, p.total_lean
                FROM predictions p
                JOIN site_week_selections sws ON p.run_id = sws.run_id
                WHERE sws.season = %s
                ORDER BY p.game_id
                """,
                (season,),
            )
            snapshot["predictions"] = [
                {
                    "run_id": r[0],
                    "game_id": r[1],
                    "spread_lean": r[2],
                    "total_lean": r[3],
                }
                for r in cur.fetchall()
            ]

            cur.execute(
                """
                SELECT pms.run_id, pms.game_id, pms.target, pms.side, pms.point
                FROM prediction_market_selections pms
                JOIN site_week_selections sws ON pms.run_id = sws.run_id
                WHERE sws.season = %s
                ORDER BY pms.game_id, pms.target
                """,
                (season,),
            )
            snapshot["prediction_market_selections"] = [
                {
                    "run_id": r[0],
                    "game_id": r[1],
                    "target": r[2],
                    "side": r[3],
                    "point": float(r[4]) if r[4] is not None else None,
                }
                for r in cur.fetchall()
            ]

            cur.execute(
                "SELECT * FROM system_stats WHERE season = %s",
                (season,),
            )
            cols = [desc[0] for desc in cur.description]
            snapshot["system_stats"] = [
                dict(zip(cols, r)) for r in cur.fetchall()
            ]

    output_path.write_text(json.dumps(snapshot, indent=2, default=str))
    print(f"Pre-mutation snapshot written to {output_path}")


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--max-week", type=int, default=4, help="Max week to scan (inclusive)")
    parser.add_argument("--week", type=int, default=None, help="Specific week to backfill (overrides --max-week)")
    parser.add_argument(
        "--grades-only",
        action="store_true",
        help="Only insert prediction_grades; leave predictions and market selections untouched",
    )
    parser.add_argument(
        "--environment", choices=("preview", "production"), default="preview"
    )
    parser.add_argument("--confirm-production", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--snapshot-dir",
        type=Path,
        default=Path("artifacts/backups/2026-10-02"),
    )
    args = parser.parse_args()
    conn_url = _resolve_db_url(args.environment, args.confirm_production)

    week_filter = "sws.week = %s" if args.week is not None else "sws.week <= %s"
    week_param = args.week if args.week is not None else args.max_week

    query = f"""
    SELECT g.week, p.run_id, p.game_id,
           g.home_team, g.away_team,
           p.home_team_spread_line, p.total_line,
           p.predicted_spread, p.predicted_total,
           p.spread_lean, p.total_lean, p.market_snapshot_id,
           gr.home_points, gr.away_points,
           pg_s.result AS spread_grade, pg_t.result AS total_grade,
           pms_s.side AS pms_spread_side, pms_s.point AS pms_spread_point,
           pms_s.quote_id AS spread_quote_id, pms_s.price AS spread_quote_price,
           pms_t.side AS pms_total_side, pms_t.point AS pms_total_point,
           pms_t.quote_id AS total_quote_id, pms_t.price AS total_quote_price,
           pr.evidence_class
    FROM site_week_selections sws
    JOIN predictions p ON p.run_id = sws.run_id
    JOIN prediction_runs pr ON pr.run_id = sws.run_id
    JOIN games g ON p.game_id = g.game_id
    LEFT JOIN game_results gr ON g.game_id = gr.game_id
    LEFT JOIN prediction_grades pg_s
      ON pg_s.run_id = p.run_id AND pg_s.game_id = p.game_id
     AND pg_s.target = 'spread'
    LEFT JOIN prediction_grades pg_t
      ON pg_t.run_id = p.run_id AND pg_t.game_id = p.game_id
     AND pg_t.target = 'total'
    LEFT JOIN prediction_market_selections pms_s
      ON pms_s.run_id = p.run_id AND pms_s.game_id = p.game_id
     AND pms_s.target = 'spread'
    LEFT JOIN prediction_market_selections pms_t
      ON pms_t.run_id = p.run_id AND pms_t.game_id = p.game_id
     AND pms_t.target = 'total'
    WHERE sws.season = %s AND {week_filter}
    ORDER BY g.week, p.game_id
    """

    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (args.year, week_param))
            rows = cur.fetchall()

    pending_grades: list[dict] = []
    pending_prediction_updates: list[dict] = []
    pending_pms_updates: list[dict] = []

    tallies = {
        "spread": {"win": 0, "loss": 0, "push": 0},
        "total": {"win": 0, "loss": 0, "push": 0},
    }

    for (
        week,
        run_id,
        game_id,
        home_team,
        away_team,
        home_line,
        total_line,
        pred_spread,
        pred_total,
        spread_lean,
        total_lean,
        snapshot_id,
        home_pts,
        away_pts,
        spread_grade,
        total_grade,
        pms_spread_side,
        pms_spread_point,
        spread_quote_id,
        spread_quote_price,
        pms_total_side,
        pms_total_point,
        total_quote_id,
        total_quote_price,
        evidence_class,
    ) in rows:
        home = float(home_pts) if home_pts is not None else None
        away = float(away_pts) if away_pts is not None else None
        can_mutate_predictions = (not args.grades_only) and (evidence_class == "replay")

        # Effective spread line
        eff_spread_line = (
            float(pms_spread_point)
            if pms_spread_point is not None
            else (float(home_line) if home_line is not None else None)
        )
        # Mathematical model lean vs market line
        if pred_spread is not None and eff_spread_line is not None:
            eff_spread_lean = "home" if pred_spread + eff_spread_line > 0 else "away"
        else:
            eff_spread_lean = spread_lean if spread_lean in ("home", "away") else None

        if can_mutate_predictions:
            if eff_spread_lean and spread_lean != eff_spread_lean:
                pending_prediction_updates.append(
                    {"run_id": run_id, "game_id": int(game_id), "spread_lean": eff_spread_lean}
                )
            if eff_spread_lean and pms_spread_side != eff_spread_lean and pms_spread_side is not None:
                pending_pms_updates.append(
                    {"run_id": run_id, "game_id": int(game_id), "target": "spread", "side": eff_spread_lean}
                )

        sp_res = spread_result(home, away, eff_spread_line, eff_spread_lean)
        if sp_res is not None:
            tallies["spread"][sp_res] += 1
            if spread_grade is None:
                price = float(spread_quote_price) if spread_quote_price is not None else None
                pending_grades.append(
                    {
                        "run_id": run_id,
                        "game_id": int(game_id),
                        "target": "spread",
                        "market_snapshot_id": snapshot_id,
                        "market_quote_id": spread_quote_id,
                        "side": eff_spread_lean,
                        "result": sp_res,
                        "profit_units": _profit(sp_res, price=price),
                        "grading_version": "model_side_best_quote_v1" if spread_quote_id else "frozen_line_v2",
                    }
                )

        # Effective total line
        eff_total_line = (
            float(pms_total_point)
            if pms_total_point is not None
            else (float(total_line) if total_line is not None else None)
        )
        # Mathematical model lean vs market line
        if pred_total is not None and eff_total_line is not None:
            eff_total_lean = "over" if pred_total > eff_total_line else "under"
        else:
            eff_total_lean = total_lean if total_lean in ("over", "under") else None

        if can_mutate_predictions:
            if eff_total_lean and total_lean != eff_total_lean:
                pending_prediction_updates.append(
                    {"run_id": run_id, "game_id": int(game_id), "total_lean": eff_total_lean}
                )
            if eff_total_lean and pms_total_side != eff_total_lean and pms_total_side is not None:
                pending_pms_updates.append(
                    {"run_id": run_id, "game_id": int(game_id), "target": "total", "side": eff_total_lean}
                )

        tot_res = total_result(home, away, eff_total_line, eff_total_lean)
        if tot_res is not None:
            tallies["total"][tot_res] += 1
            if total_grade is None:
                price = float(total_quote_price) if total_quote_price is not None else None
                pending_grades.append(
                    {
                        "run_id": run_id,
                        "game_id": int(game_id),
                        "target": "total",
                        "market_snapshot_id": snapshot_id,
                        "market_quote_id": total_quote_id,
                        "side": eff_total_lean,
                        "result": tot_res,
                        "profit_units": _profit(tot_res, price=price),
                        "grading_version": "model_side_best_quote_v1" if total_quote_id else "frozen_line_v2",
                    }
                )

    new_spread = sum(1 for g in pending_grades if g["target"] == "spread")
    new_total = sum(1 for g in pending_grades if g["target"] == "total")

    scope_str = f"Week {args.week}" if args.week is not None else f"Weeks 0–{args.max_week}"
    print(f"=== {args.year} ({scope_str}) Unconstrained Grade Backfill Scan ===")
    print(f"Environment: {args.environment}")
    print(f"Grades-only mode: {args.grades_only}")
    print(f"Total games scanned: {len(rows)}")
    print(f"New grades to insert: {len(pending_grades)} ({new_spread} spread + {new_total} total)")
    print(f"Predictions lean updates: {len(pending_prediction_updates)}")
    print(f"Market selections side updates: {len(pending_pms_updates)}")
    print(f"Final full-slate spread record: {tallies['spread']['win']}–{tallies['spread']['loss']}–{tallies['spread']['push']}")
    print(f"Final full-slate total record:  {tallies['total']['win']}–{tallies['total']['loss']}–{tallies['total']['push']}")

    if args.dry_run:
        print("\n[DRY RUN] No database changes made.")
        return

    # Take snapshot before mutating
    snapshot_file = args.snapshot_dir / f"{args.environment}_pre_unconstrained_grades_snapshot.json"
    dump_snapshot(conn_url, args.year, snapshot_file)

    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            # 1. Update predictions leans
            for p in pending_prediction_updates:
                if "spread_lean" in p:
                    cur.execute(
                        "UPDATE predictions SET spread_lean = %s WHERE run_id = %s AND game_id = %s",
                        (p["spread_lean"], p["run_id"], p["game_id"]),
                    )
                if "total_lean" in p:
                    cur.execute(
                        "UPDATE predictions SET total_lean = %s WHERE run_id = %s AND game_id = %s",
                        (p["total_lean"], p["run_id"], p["game_id"]),
                    )

            # 2. Update prediction_market_selections side
            for pms in pending_pms_updates:
                cur.execute(
                    "UPDATE prediction_market_selections SET side = %s WHERE run_id = %s AND game_id = %s AND target = %s",
                    (pms["side"], pms["run_id"], pms["game_id"], pms["target"]),
                )

            # 3. Insert missing prediction_grades
            for record in pending_grades:
                cur.execute(UPSERT_GRADE_SQL, record)

        conn.commit()

    print("\nDatabase records updated successfully. Refreshing system_stats...")
    stats = recompute_stats(conn_url, args.year)
    print(
        f"{args.year} system_stats refreshed: spread "
        f"{stats.get('spread_wins')}-{stats.get('spread_losses')}-{stats.get('spread_pushes')} · "
        f"total {stats.get('total_wins')}-{stats.get('total_losses')}-{stats.get('total_pushes')}"
    )


if __name__ == "__main__":
    main()
