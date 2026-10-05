"""Stage 9 (old_grade_reproduction) and Stage 10 (retrospective_grades) for Stage 6B."""

from __future__ import annotations

import json
import os
from typing import Any

import pandas as pd

from cks_picks_cfb.rebuild.errors import GateError
from cks_picks_cfb.rebuild.legacy import (
    _profit,
    spread_result,
    total_result,
)
from cks_picks_cfb.rebuild.orchestrator import StageContext, StageOutput
from cks_picks_cfb.rebuild.recon_common import (
    EVIDENCE_CLASS,
    SELECTION_POLICY,
    WEEKS,
    frame_digest,
    json_data,
    load_partitioned_gold,
    original_run_id,
    parquet_data,
    read_parquet_data,
    recon_run_id,
    write_partitioned_gold,
)
from cks_picks_cfb.rebuild.recon_markets import FINALS_PARQUET, MARKETS_PARQUET

OLD_REPRO_SUMMARY = "rebuild/6b/{run_id}/old_grade_reproduction/summary.json"

RETRO_GRADES_SUMMARY = "rebuild/6b/{run_id}/retrospective_grades/summary.json"
RETRO_GRADES_PARQUET = "rebuild/6b/{run_id}/retrospective_grades/grades.parquet"
GRADES_DATASET = "reconstruction_grades"
GRADES_SCHEMA_VERSION = "reconstruction_grades_v1"

EXPECTED_TOTAL_GRADES = 541


# ---------------------------------------------------------------------------
# Stage 9: Old Grade Reproduction
# ---------------------------------------------------------------------------


def build_old_grade_reproduction(context: StageContext) -> StageOutput:
    fin_key = FINALS_PARQUET.format(run_id=context.plan.run_id)
    finals = read_parquet_data(context.read_artifact("finals", fin_key)).set_index("game_id")

    preview_url = os.getenv("PREVIEW_DATABASE_URL")
    if not preview_url:
        raise GateError("old grade reproduction requires PREVIEW_DATABASE_URL for Preview DB checks")

    import psycopg

    from cks_picks_cfb.rebuild.targets import assert_preview_database

    runs = [original_run_id(w) for w in WEEKS]
    mismatches: list[dict[str, Any]] = []
    total_checked = 0

    with psycopg.connect(preview_url) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            assert_preview_database(cur)
            # Fetch stored selections and stored grades
            cur.execute(
                "SELECT pms.run_id, pms.game_id, pms.target, pms.side, pms.point, pms.price, "
                "pg.result, pg.profit_units "
                "FROM prediction_market_selections pms "
                "JOIN prediction_grades pg ON (pms.run_id = pg.run_id AND pms.game_id = pg.game_id AND pms.target = pg.target) "
                "WHERE pms.run_id = ANY(%s) ORDER BY pms.run_id, pms.game_id, pms.target",
                (runs,),
            )
            rows = cur.fetchall()
            for run_id, game_id, target, side, point, price, stored_res, stored_profit in rows:
                total_checked += 1
                game = finals.loc[int(game_id)]
                home_pts = float(game["home_points"])
                away_pts = float(game["away_points"])

                if target == "spread":
                    recomputed_res = spread_result(home_pts, away_pts, float(point), side)
                else:
                    recomputed_res = total_result(home_pts, away_pts, float(point), side)

                recomputed_profit = round(_profit(recomputed_res, float(price)), 4)
                stored_profit_f = round(float(stored_profit), 4)

                if recomputed_res != stored_res or abs(recomputed_profit - stored_profit_f) > 1e-4:
                    mismatches.append(
                        {
                            "run_id": run_id,
                            "game_id": int(game_id),
                            "target": target,
                            "side": side,
                            "point": float(point),
                            "price": float(price),
                            "recomputed_res": recomputed_res,
                            "stored_res": stored_res,
                            "recomputed_profit": recomputed_profit,
                            "stored_profit": stored_profit_f,
                        }
                    )

    if total_checked != EXPECTED_TOTAL_GRADES:
        raise GateError(
            f"old grade reproduction: checked {total_checked} grades, expected {EXPECTED_TOTAL_GRADES}"
        )
    if mismatches:
        raise GateError(
            f"old grade reproduction failed: {len(mismatches)} mismatches against stored grades: {mismatches[:5]}"
        )

    summary = {
        "status": "passed",
        "total_grades_checked": total_checked,
        "mismatches_count": len(mismatches),
        "verified_runs": runs,
    }

    prefix_sum = OLD_REPRO_SUMMARY.format(run_id=context.plan.run_id)
    artifacts = [(prefix_sum, json_data(summary))]
    return StageOutput(artifacts=artifacts, metrics={"grades_reproduced": total_checked})


def verify_old_grade_reproduction(context: StageContext) -> list[str]:
    problems: list[str] = []
    prefix_sum = OLD_REPRO_SUMMARY.format(run_id=context.plan.run_id)
    try:
        summary = json.loads(context.read_artifact("old_grade_reproduction", prefix_sum))
    except Exception as exc:
        return [f"failed to read old grade reproduction summary: {exc}"]

    if summary.get("mismatches_count", 0) > 0:
        problems.append("old grade reproduction reported mismatches")
    if summary.get("total_grades_checked") != EXPECTED_TOTAL_GRADES:
        problems.append(f"grades checked {summary.get('total_grades_checked')} != {EXPECTED_TOTAL_GRADES}")
    return problems


# ---------------------------------------------------------------------------
# Stage 10: Retrospective Grades
# ---------------------------------------------------------------------------


def build_retrospective_grades(context: StageContext) -> StageOutput:
    sel_key = MARKETS_PARQUET.format(run_id=context.plan.run_id)
    selections = read_parquet_data(context.read_artifact("markets", sel_key))

    fin_key = FINALS_PARQUET.format(run_id=context.plan.run_id)
    finals = read_parquet_data(context.read_artifact("finals", fin_key)).set_index("game_id")

    weekly_grades: dict[int, pd.DataFrame] = {}
    grade_rows: list[dict[str, Any]] = []

    for w in WEEKS:
        w_sels = selections[selections["week"].eq(w)].copy()
        w_rows: list[dict[str, Any]] = []

        for row in w_sels.itertuples(index=False):
            game_id = int(row.game_id)
            target = str(row.target)
            side = str(row.side)
            point = float(row.point)
            price = float(row.price)

            fin = finals.loc[game_id]
            home_pts = float(fin["home_points"])
            away_pts = float(fin["away_points"])
            finals_ref = str(fin["finals_ref"])

            if target == "spread":
                result = spread_result(home_pts, away_pts, point, side)
            else:
                result = total_result(home_pts, away_pts, point, side)

            if result is None:
                raise GateError(f"ungradable selection: game {game_id} {target}")

            profit = round(_profit(result, price), 4)

            rec = {
                "run_id": recon_run_id(w),
                "season": 2026,
                "week": w,
                "game_id": game_id,
                "target": target,
                "market_snapshot_id": str(row.snapshot_id),
                "market_quote_id": str(row.quote_id),
                "side": side,
                "result": result,
                "profit_units": profit,
                "grading_version": SELECTION_POLICY,
                "evidence_class": EVIDENCE_CLASS,
                "finals_ref": finals_ref,
            }
            w_rows.append(rec)
            grade_rows.append(rec)

        weekly_grades[w] = pd.DataFrame.from_records(w_rows)

    all_grades = pd.DataFrame.from_records(grade_rows)
    if len(all_grades) != EXPECTED_TOTAL_GRADES:
        raise GateError(f"retrospective grades count {len(all_grades)} != {EXPECTED_TOTAL_GRADES}")

    lake_summary, lake_files = write_partitioned_gold(
        context,
        dataset=GRADES_DATASET,
        schema_version=GRADES_SCHEMA_VERSION,
        frames_by_week=weekly_grades,
        parent_refs=[
            {"dataset": "markets", "version_id": context.plan.run_id},
            {"dataset": "finals", "version_id": context.plan.run_id},
        ],
    )

    summary = {
        "status": "passed",
        "total_grades": len(all_grades),
        "weekly_counts": {str(w): len(weekly_grades[w]) for w in WEEKS},
        "results_summary": all_grades.groupby(["target", "result"]).size().unstack(fill_value=0).to_dict(),
        "grades_digest": frame_digest(all_grades),
        "lake_gold": lake_summary,
    }

    prefix_gr = RETRO_GRADES_PARQUET.format(run_id=context.plan.run_id)
    prefix_sum = RETRO_GRADES_SUMMARY.format(run_id=context.plan.run_id)

    artifacts = [
        (prefix_gr, parquet_data(all_grades)),
        (prefix_sum, json_data(summary)),
        *lake_files,
    ]
    return StageOutput(artifacts=artifacts, metrics={"grades": len(all_grades)})


def verify_retrospective_grades(context: StageContext) -> list[str]:
    problems: list[str] = []
    prefix_sum = RETRO_GRADES_SUMMARY.format(run_id=context.plan.run_id)
    prefix_gr = RETRO_GRADES_PARQUET.format(run_id=context.plan.run_id)
    try:
        summary = json.loads(context.read_artifact("retrospective_grades", prefix_sum))
        grades = read_parquet_data(context.read_artifact("retrospective_grades", prefix_gr))
    except Exception as exc:
        return [f"failed to read retrospective grades artifacts: {exc}"]

    if len(grades) != EXPECTED_TOTAL_GRADES:
        problems.append(f"grades count {len(grades)} != {EXPECTED_TOTAL_GRADES}")
    if frame_digest(grades) != summary["grades_digest"]:
        problems.append("grades frame digest mismatch")

    try:
        lake_grades = load_partitioned_gold(context, "retrospective_grades", summary["lake_gold"])
        if len(lake_grades) != EXPECTED_TOTAL_GRADES:
            problems.append(f"lake grades count {len(lake_grades)} != {EXPECTED_TOTAL_GRADES}")
    except Exception as exc:
        problems.append(f"failed to load partitioned lake grades: {exc}")

    return problems
