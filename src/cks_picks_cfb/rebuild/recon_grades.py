"""Stage 9 (old_grade_reproduction) and Stage 10 (retrospective_grades) for Stage 6B."""

from __future__ import annotations

import io
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
    EXPECTED_COUNTS,
    SELECTION_POLICY,
    WEEKS,
    checked_read,
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


def _original_csvs(
    context: StageContext,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    from cks_picks_cfb.rebuild import common

    storage = common.preview_storage(context)
    predictions, selections, grades = [], [], []
    for w in WEEKS:
        pred_manifest = json.loads(context.read_input(f"original_predictions_w{w}"))
        score_manifest = json.loads(context.read_input(f"original_scored_w{w}"))
        run = original_run_id(w)
        if any(
            m["run_id"] != run or m["week"] != w or m["season"] != 2026
            for m in (pred_manifest, score_manifest)
        ):
            raise GateError("original manifest identity changed")
        frames = []
        for manifest in (pred_manifest, score_manifest):
            raw = checked_read(
                storage,
                {
                    "uri": manifest["artifact_uri"],
                    "sha256": manifest["artifact_sha256"],
                },
            )
            frame = pd.read_csv(io.BytesIO(raw))
            if len(frame) != EXPECTED_COUNTS[w] or frame.duplicated("game_id").any():
                raise GateError("original CSV game population changed")
            frames.append(frame)
        pred, scored = frames
        if set(pred.game_id) != set(scored.game_id):
            raise GateError("original prediction/scored keys differ")
        predictions.append(
            pred[
                [
                    "game_id",
                    "Spread Prediction",
                    "Total Prediction",
                    "Spread Bet",
                    "Total Bet",
                ]
            ]
            .rename(
                columns={
                    "Spread Prediction": "predicted_spread",
                    "Total Prediction": "predicted_total",
                    "Spread Bet": "spread_lean",
                    "Total Bet": "total_lean",
                }
            )
            .assign(run_id=run)
        )
        for row in scored.to_dict("records"):
            gid = int(row["game_id"])
            for target, side_col, line_col, price_col, result_col in (
                (
                    "spread",
                    "Spread Bet",
                    "home_team_spread_line",
                    "spread_market_quote_price",
                    "Spread Bet Result",
                ),
                (
                    "total",
                    "Total Bet",
                    "total_line",
                    "total_market_quote_price",
                    "Total Bet Result",
                ),
            ):
                if pd.isna(row[line_col]):
                    continue
                side, result = str(row[side_col]).lower(), str(row[result_col]).lower()
                price = float(row[price_col])
                if result not in ("win", "loss", "push") or side not in (
                    ("home", "away") if target == "spread" else ("over", "under")
                ):
                    raise GateError("original CSV has ungradable selection")
                selections.append(
                    dict(
                        run_id=run,
                        game_id=gid,
                        target=target,
                        side=side,
                        point=float(row[line_col]),
                        price=price,
                        snapshot_id=str(row["market_snapshot_id"]),
                        quote_id=str(row[f"{target}_market_quote_id"]),
                    )
                )
                grades.append(
                    dict(
                        run_id=run,
                        game_id=gid,
                        target=target,
                        side=side,
                        result=result,
                        profit_units=round(_profit(result, price), 4),
                    )
                )
    return (
        pd.concat(predictions, ignore_index=True),
        pd.DataFrame(selections),
        pd.DataFrame(grades),
    )


def build_old_grade_reproduction(context: StageContext) -> StageOutput:
    finals = read_parquet_data(
        context.read_artifact(
            "finals", FINALS_PARQUET.format(run_id=context.plan.run_id)
        )
    ).set_index("game_id")
    predictions, selections, grades = _original_csvs(context)
    keys = ["run_id", "game_id", "target"]
    expected_keys = {
        (original_run_id(int(row.week)), int(gid), target)
        for gid, row in finals.iterrows()
        for target in ("spread", "total")
        if not (int(row.week) == 3 and int(gid) == 401856811 and target == "total")
    }
    for frame in (selections, grades):
        if (
            frame.duplicated(keys).any()
            or set(frame[keys].itertuples(index=False, name=None)) != expected_keys
        ):
            raise GateError("original grade/selection key population changed")
    if (
        set(predictions.game_id) != set(finals.index)
        or predictions.duplicated("game_id").any()
    ):
        raise GateError("original prediction coverage differs from finals")
    preview_url = os.getenv("PREVIEW_DATABASE_URL")
    if not preview_url:
        raise GateError(
            "old grade reproduction requires PREVIEW_DATABASE_URL for Preview DB checks"
        )
    import psycopg

    from cks_picks_cfb.rebuild.targets import assert_preview_database

    with psycopg.connect(preview_url) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            assert_preview_database(cur)
            cur.execute(
                "SELECT pms.run_id, pms.game_id, pms.target, pms.side, pms.point, pms.price, "
                "pg.result, pg.profit_units, pms.snapshot_id, pms.quote_id, pg.market_snapshot_id, pg.market_quote_id, pg.side "
                "FROM prediction_market_selections pms JOIN prediction_grades pg "
                "ON (pms.run_id = pg.run_id AND pms.game_id = pg.game_id AND pms.target = pg.target) "
                "WHERE pms.run_id = ANY(%s) ORDER BY pms.run_id, pms.game_id, pms.target",
                ([original_run_id(w) for w in WEEKS],),
            )
            rows = cur.fetchall()
    if (
        len(rows) != EXPECTED_TOTAL_GRADES
        or len({tuple(r[:3]) for r in rows}) != EXPECTED_TOTAL_GRADES
        or {tuple(r[:3]) for r in rows} != expected_keys
    ):
        raise GateError(
            "Preview original grades have missing, duplicate or unexpected keys"
        )
    sels = selections.set_index(keys)
    csv_grades = grades.set_index(keys)
    for (
        run,
        gid,
        target,
        side,
        point,
        price,
        stored_result,
        stored_profit,
        snap,
        quote,
        grade_snap,
        grade_quote,
        grade_side,
    ) in rows:
        selected, csv_grade = (
            sels.loc[(run, gid, target)],
            csv_grades.loc[(run, gid, target)],
        )
        final = finals.loc[gid]
        result = (spread_result if target == "spread" else total_result)(
            float(final.home_points), float(final.away_points), float(point), str(side)
        )
        profit = round(_profit(result, float(price)), 4)
        if (
            str(side) != selected.side
            or float(point) != selected.point
            or float(price) != selected.price
            or str(snap) != selected.snapshot_id
            or str(quote) != selected.quote_id
            or grade_snap != snap
            or grade_quote != quote
            or grade_side != side
            or result != stored_result
            or result != csv_grade.result
            or abs(profit - float(stored_profit)) > 1e-4
            or abs(profit - csv_grade.profit_units) > 1e-4
        ):
            raise GateError(
                f"old grade reproduction mismatch against Preview/scored CSV: {run} {gid} {target}"
            )
    summary = dict(
        status="passed",
        total_grades_checked=len(rows),
        csv_grades_checked=len(grades),
        mismatches_count=0,
        verified_runs=[original_run_id(w) for w in WEEKS],
    )
    artifacts = [
        (OLD_REPRO_SUMMARY.format(run_id=context.plan.run_id), json_data(summary))
    ]
    for name, frame in (
        ("predictions", predictions),
        ("selections", selections),
        ("grades", grades),
    ):
        artifacts.append(
            (
                f"{context.plan.run_prefix()}old_grade_reproduction/{name}.parquet",
                parquet_data(frame),
            )
        )
    return StageOutput(artifacts=artifacts, metrics={"grades_reproduced": len(rows)})


def verify_old_grade_reproduction(context: StageContext) -> list[str]:
    problems: list[str] = []
    prefix_sum = OLD_REPRO_SUMMARY.format(run_id=context.plan.run_id)
    try:
        summary = json.loads(
            context.read_artifact("old_grade_reproduction", prefix_sum)
        )
    except Exception as exc:
        return [f"failed to read old grade reproduction summary: {exc}"]

    if summary.get("mismatches_count") != 0:
        problems.append("old grade reproduction reported mismatches")
    if summary.get("total_grades_checked") != EXPECTED_TOTAL_GRADES:
        problems.append(
            f"grades checked {summary.get('total_grades_checked')} != {EXPECTED_TOTAL_GRADES}"
        )
    return problems


# ---------------------------------------------------------------------------
# Stage 10: Retrospective Grades
# ---------------------------------------------------------------------------


def build_retrospective_grades(context: StageContext) -> StageOutput:
    old_summary = json.loads(
        context.read_artifact(
            "old_grade_reproduction",
            OLD_REPRO_SUMMARY.format(run_id=context.plan.run_id),
        )
    )
    if (
        old_summary.get("mismatches_count") != 0
        or old_summary.get("total_grades_checked") != EXPECTED_TOTAL_GRADES
        or old_summary.get("csv_grades_checked") != EXPECTED_TOTAL_GRADES
    ):
        raise GateError("new grades require complete original grade reproduction")
    sel_key = MARKETS_PARQUET.format(run_id=context.plan.run_id)
    selections = read_parquet_data(context.read_artifact("markets", sel_key))

    fin_key = FINALS_PARQUET.format(run_id=context.plan.run_id)
    finals = read_parquet_data(context.read_artifact("finals", fin_key)).set_index(
        "game_id"
    )

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
        raise GateError(
            f"retrospective grades count {len(all_grades)} != {EXPECTED_TOTAL_GRADES}"
        )

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
        "results_summary": all_grades.groupby(["target", "result"])
        .size()
        .unstack(fill_value=0)
        .to_dict(),
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
        grades = read_parquet_data(
            context.read_artifact("retrospective_grades", prefix_gr)
        )
    except Exception as exc:
        return [f"failed to read retrospective grades artifacts: {exc}"]

    if len(grades) != EXPECTED_TOTAL_GRADES:
        problems.append(f"grades count {len(grades)} != {EXPECTED_TOTAL_GRADES}")
    if frame_digest(grades) != summary["grades_digest"]:
        problems.append("grades frame digest mismatch")

    try:
        lake_grades = load_partitioned_gold(
            context, "retrospective_grades", summary["lake_gold"]
        )
        if len(lake_grades) != EXPECTED_TOTAL_GRADES:
            problems.append(
                f"lake grades count {len(lake_grades)} != {EXPECTED_TOTAL_GRADES}"
            )
    except Exception as exc:
        problems.append(f"failed to load partitioned lake grades: {exc}")

    return problems
