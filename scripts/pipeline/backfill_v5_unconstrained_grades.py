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
from dataclasses import dataclass, field
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


LEGACY_QUOTE_POLICY = "model_side_best_quote_v1"
FROZEN_LINE_VERSION = "frozen_line_v2"
SIDES = {"spread": ("home", "away"), "total": ("over", "under")}


@dataclass
class BackfillPlan:
    grades: list[dict] = field(default_factory=list)
    prediction_updates: list[dict] = field(default_factory=list)
    pms_updates: list[dict] = field(default_factory=list)
    tallies: dict = field(
        default_factory=lambda: {
            "spread": {"win": 0, "loss": 0, "push": 0},
            "total": {"win": 0, "loss": 0, "push": 0},
        }
    )
    unresolved: list[tuple[int, str, str]] = field(default_factory=list)


def resolve_side(
    target: str,
    *,
    selection_side: str | None,
    stored_lean: str | None,
    predicted: float | None,
    line: float | None,
    prefer_recomputed: bool,
    allow_recompute: bool,
) -> str | None:
    """The side a game is graded on.

    The side the site already showed (the stored selection, then the stored lean) is the
    side that is graded. The side is recomputed from prediction and line only when asked to
    rewrite leans (``prefer_recomputed``, replay runs outside grades-only mode) or, failing
    any stored side, when ``allow_recompute`` is set. A grades-only run never invents one.
    """
    valid = SIDES[target]
    recomputed = None
    if predicted is not None and line is not None:
        if target == "spread":
            recomputed = "home" if predicted + line > 0 else "away"
        else:
            recomputed = "over" if predicted > line else "under"
    stored = next((x for x in (selection_side, stored_lean) if x in valid), None)
    if prefer_recomputed and recomputed is not None:
        return recomputed
    if stored is not None:
        return stored
    return recomputed if allow_recompute else None


def grading_version(quote_id: object, policy_version: object) -> str:
    """The label a quote-backed grade carries is the policy that selected the quote."""
    if not quote_id:
        return FROZEN_LINE_VERSION
    return str(policy_version) if policy_version else LEGACY_QUOTE_POLICY


def recompute_result(
    target: str,
    side: str | None,
    line: float | None,
    home: float | None,
    away: float | None,
) -> str | None:
    fn = spread_result if target == "spread" else total_result
    return fn(home, away, line, side)


def plan_backfill(rows: list[tuple], *, grades_only: bool) -> BackfillPlan:
    """Plan the missing grades (and, outside grades-only mode, lean rewrites) for ``rows``."""
    plan = BackfillPlan()
    for (
        _week,
        run_id,
        game_id,
        _home_team,
        _away_team,
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
        spread_policy,
        total_policy,
    ) in rows:
        home = float(home_pts) if home_pts is not None else None
        away = float(away_pts) if away_pts is not None else None
        can_mutate = (not grades_only) and (evidence_class == "replay")
        for (
            target,
            line_a,
            pred,
            lean,
            pms_side,
            pms_point,
            quote_id,
            price,
            policy,
            existing,
        ) in (
            (
                "spread",
                home_line,
                pred_spread,
                spread_lean,
                pms_spread_side,
                pms_spread_point,
                spread_quote_id,
                spread_quote_price,
                spread_policy,
                spread_grade,
            ),
            (
                "total",
                total_line,
                pred_total,
                total_lean,
                pms_total_side,
                pms_total_point,
                total_quote_id,
                total_quote_price,
                total_policy,
                total_grade,
            ),
        ):
            eff_line = (
                float(pms_point)
                if pms_point is not None
                else (float(line_a) if line_a is not None else None)
            )
            side = resolve_side(
                target,
                selection_side=pms_side,
                stored_lean=lean,
                predicted=float(pred) if pred is not None else None,
                line=eff_line,
                prefer_recomputed=can_mutate,
                allow_recompute=not grades_only,
            )
            lean_key = "spread_lean" if target == "spread" else "total_lean"
            if can_mutate and side and lean != side:
                plan.prediction_updates.append(
                    {"run_id": run_id, "game_id": int(game_id), lean_key: side}
                )
            if can_mutate and side and pms_side != side and pms_side is not None:
                plan.pms_updates.append(
                    {
                        "run_id": run_id,
                        "game_id": int(game_id),
                        "target": target,
                        "side": side,
                    }
                )
            result = recompute_result(target, side, eff_line, home, away)
            if result is None:
                if (
                    home is not None
                    and away is not None
                    and eff_line is not None
                    and side is None
                ):
                    plan.unresolved.append((int(game_id), target, "no stored side"))
                continue
            plan.tallies[target][result] += 1
            if existing is None:
                plan.grades.append(
                    {
                        "run_id": run_id,
                        "game_id": int(game_id),
                        "target": target,
                        "market_snapshot_id": snapshot_id,
                        "market_quote_id": quote_id,
                        "side": side,
                        "result": result,
                        "profit_units": _profit(
                            result, price=float(price) if price is not None else None
                        ),
                        "grading_version": grading_version(quote_id, policy),
                    }
                )
    return plan


def readback_mismatches(records: list[dict], stored: list[dict]) -> list[str]:
    """Compare freshly inserted grades with what the database now holds.

    ``stored`` rows carry the persisted grade plus its inputs (selection point and side,
    prediction line, certified final), so the result is recomputed from the database's own
    values rather than from the in-memory plan.
    """
    by_key = {(r["run_id"], r["game_id"], r["target"]): r for r in stored}
    problems: list[str] = []
    for rec in records:
        key = (rec["run_id"], rec["game_id"], rec["target"])
        row = by_key.get(key)
        if row is None:
            problems.append(f"{key}: grade not found after insert")
            continue
        line = row["point"] if row["point"] is not None else row["line"]
        home = float(row["home_points"]) if row["home_points"] is not None else None
        away = float(row["away_points"]) if row["away_points"] is not None else None
        expected = recompute_result(
            rec["target"],
            row["side"],
            float(line) if line is not None else None,
            home,
            away,
        )
        if expected != row["result"]:
            problems.append(f"{key}: stored {row['result']} but inputs give {expected}")
        if (row["result"], row["side"], row["grading_version"]) != (
            rec["result"],
            rec["side"],
            rec["grading_version"],
        ):
            problems.append(f"{key}: stored grade differs from the planned grade")
        if row["selection_side"] is not None and row["selection_side"] != row["side"]:
            problems.append(
                f"{key}: graded side differs from the stored selection side"
            )
    return problems


READBACK_SQL = """
SELECT pg.run_id, pg.game_id, pg.target, pg.side, pg.result, pg.grading_version,
       gr.home_points, gr.away_points, pms.point, pms.side,
       CASE WHEN pg.target = 'spread' THEN p.home_team_spread_line ELSE p.total_line END
FROM prediction_grades pg
JOIN predictions p ON p.run_id = pg.run_id AND p.game_id = pg.game_id
JOIN game_results gr ON gr.game_id = pg.game_id
LEFT JOIN prediction_market_selections pms
  ON pms.run_id = pg.run_id AND pms.game_id = pg.game_id AND pms.target = pg.target
WHERE pg.run_id = ANY(%s)
"""


def fetch_readback(cur, run_ids: list[str]) -> list[dict]:
    cur.execute(READBACK_SQL, (run_ids,))
    return [
        {
            "run_id": r[0],
            "game_id": int(r[1]),
            "target": r[2],
            "side": r[3],
            "result": r[4],
            "grading_version": r[5],
            "home_points": r[6],
            "away_points": r[7],
            "point": float(r[8]) if r[8] is not None else None,
            "selection_side": r[9],
            "line": float(r[10]) if r[10] is not None else None,
        }
        for r in cur.fetchall()
    ]


def snapshot_path(directory: Path, environment: str, scope: str, now: datetime) -> Path:
    """A pre-mutation snapshot file that is unique per environment, scope and run time."""
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    path = directory / f"{environment}_pre_grades_{scope}_{stamp}.json"
    if path.exists():
        raise SystemExit(f"refusing to overwrite an existing snapshot: {path}")
    return path


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
            snapshot["system_stats"] = [dict(zip(cols, r)) for r in cur.fetchall()]

    output_path.write_text(json.dumps(snapshot, indent=2, default=str))
    print(f"Pre-mutation snapshot written to {output_path}")


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument(
        "--max-week", type=int, default=4, help="Max week to scan (inclusive)"
    )
    parser.add_argument(
        "--week",
        type=int,
        default=None,
        help="Specific week to backfill (overrides --max-week)",
    )
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
        default=Path("artifacts/backups")
        / datetime.now(timezone.utc).strftime("%Y-%m-%d"),
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
           pr.evidence_class,
           pms_s.policy_version AS spread_policy, pms_t.policy_version AS total_policy
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

    plan = plan_backfill(rows, grades_only=args.grades_only)
    pending_grades = plan.grades
    pending_prediction_updates = plan.prediction_updates
    pending_pms_updates = plan.pms_updates
    tallies = plan.tallies

    new_spread = sum(1 for g in pending_grades if g["target"] == "spread")
    new_total = sum(1 for g in pending_grades if g["target"] == "total")

    scope_str = (
        f"Week {args.week}" if args.week is not None else f"Weeks 0–{args.max_week}"
    )
    print(f"=== {args.year} ({scope_str}) Unconstrained Grade Backfill Scan ===")
    print(f"Environment: {args.environment}")
    print(f"Grades-only mode: {args.grades_only}")
    print(f"Total games scanned: {len(rows)}")
    print(
        f"New grades to insert: {len(pending_grades)} ({new_spread} spread + {new_total} total)"
    )
    print(f"Predictions lean updates: {len(pending_prediction_updates)}")
    print(f"Market selections side updates: {len(pending_pms_updates)}")
    if plan.unresolved:
        print(
            f"Games with a line and a final but no stored side (not graded): {plan.unresolved}"
        )
    print(
        f"Final full-slate spread record: {tallies['spread']['win']}–{tallies['spread']['loss']}–{tallies['spread']['push']}"
    )
    print(
        f"Final full-slate total record:  {tallies['total']['win']}–{tallies['total']['loss']}–{tallies['total']['push']}"
    )

    if args.dry_run:
        print("\n[DRY RUN] No database changes made.")
        return

    # Take snapshot before mutating
    scope = f"week{args.week}" if args.week is not None else f"weeks0-{args.max_week}"
    snapshot_file = snapshot_path(
        args.snapshot_dir, args.environment, scope, datetime.now(timezone.utc)
    )
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

            # 4. Read the grades back and recompute each from the database's own inputs;
            #    any mismatch aborts the whole transaction (nothing is committed).
            problems = readback_mismatches(
                pending_grades,
                fetch_readback(cur, sorted({g["run_id"] for g in pending_grades})),
            )
            if problems:
                conn.rollback()
                raise SystemExit("grade read-back failed:\n" + "\n".join(problems))

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
