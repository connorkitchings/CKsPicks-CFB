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
EXPECTED_CSV_ACTIVE_GRADES = 455
EXPECTED_CSV_POLICY_EXCEPTIONS = 86
LEGACY_SPREAD_GRADE_THRESHOLD = 1.0
LEGACY_TOTAL_LEAN_THRESHOLD = 1.0
LEGACY_TOTAL_GRADE_THRESHOLD = 1.5


# ---------------------------------------------------------------------------
# Stage 9: Old Grade Reproduction
# ---------------------------------------------------------------------------


def _original_csvs(
    context: StageContext,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    from cks_picks_cfb.rebuild import common

    storage = common.preview_storage(context)
    predictions, csv_rows = [], []
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
        pred_by_game = pred.set_index("game_id")
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
                if line_col not in row or pd.isna(row[line_col]):
                    continue
                line = float(row[line_col])
                price = float(row[price_col])
                side = str(row[side_col]).strip().lower()
                result = str(row[result_col]).strip().lower()
                pred_col = (
                    "Spread Prediction" if target == "spread" else "Total Prediction"
                )
                prediction = float(pred_by_game.loc[gid, pred_col])
                edge = (
                    abs(prediction + line)
                    if target == "spread"
                    else abs(prediction - line)
                )
                if target == "spread":
                    expected_active = edge >= LEGACY_SPREAD_GRADE_THRESHOLD
                    expected_side = "home" if prediction + line > 0 else "away"
                else:
                    expected_active = edge >= LEGACY_TOTAL_GRADE_THRESHOLD
                    expected_side = "over" if prediction > line else "under"
                valid_sides = (
                    ("home", "away") if target == "spread" else ("over", "under")
                )
                expected_csv_side = (
                    expected_side
                    if (target == "spread" and edge >= LEGACY_SPREAD_GRADE_THRESHOLD)
                    or (target == "total" and edge >= LEGACY_TOTAL_LEAN_THRESHOLD)
                    else "no bet"
                )
                if side != expected_csv_side:
                    raise GateError(
                        f"served CSV side violates September 29 threshold policy: {run} {gid} {target}"
                    )
                if expected_active:
                    if side not in valid_sides or result not in ("win", "loss", "push"):
                        raise GateError(
                            "served CSV active selection has invalid side/result"
                        )
                elif result != "no bet":
                    raise GateError(
                        "served CSV sub-threshold row is not labeled No Bet"
                    )
                csv_rows.append(
                    dict(
                        run_id=run,
                        game_id=gid,
                        target=target,
                        side=side,
                        result=result,
                        point=line,
                        price=price,
                        snapshot_id=str(row["market_snapshot_id"]),
                        quote_id=str(row[f"{target}_market_quote_id"]),
                        expected_active=bool(expected_active),
                        edge=edge,
                        prediction=prediction,
                    )
                )
    return (
        pd.concat(predictions, ignore_index=True),
        pd.DataFrame(csv_rows),
    )


def build_old_grade_reproduction(context: StageContext) -> StageOutput:
    finals = read_parquet_data(
        context.read_artifact(
            "finals", FINALS_PARQUET.format(run_id=context.plan.run_id)
        )
    ).set_index("game_id")
    predictions, csv_rows = _original_csvs(context)
    keys = ["run_id", "game_id", "target"]
    expected_keys = {
        (original_run_id(int(row.week)), int(gid), target)
        for gid, row in finals.iterrows()
        for target in ("spread", "total")
        if not (int(row.week) == 3 and int(gid) == 401856811 and target == "total")
    }
    if (
        csv_rows.duplicated(keys).any()
        or set(csv_rows[keys].itertuples(index=False, name=None)) != expected_keys
    ):
        raise GateError("served CSV target key population changed")
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
    csv_by_key = csv_rows.set_index(keys)
    db_selections, db_grades = [], []
    csv_grade_checks = 0
    policy_exceptions = []
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
        csv_row = csv_by_key.loc[(run, gid, target)]
        final = finals.loc[gid]
        result = (spread_result if target == "spread" else total_result)(
            float(final.home_points), float(final.away_points), float(point), str(side)
        )
        profit = round(_profit(result, float(price)), 4)
        if (
            float(point) != float(csv_row.point)
            or float(price) != float(csv_row.price)
            or str(snap) != str(csv_row.snapshot_id)
            or str(quote) != str(csv_row.quote_id)
            or grade_snap != snap
            or grade_quote != quote
            or grade_side != side
            or result != stored_result
            or abs(profit - float(stored_profit)) > 1e-4
        ):
            raise GateError(
                f"Preview grade reproduction or source identity mismatch: {run} {gid} {target}"
            )
        expected_db_side = (
            ("home" if float(csv_row.prediction) + float(point) > 0 else "away")
            if target == "spread"
            else ("over" if float(csv_row.prediction) > float(point) else "under")
        )
        if str(side) != expected_db_side:
            raise GateError(
                f"Preview selection is not the unconstrained model side: {run} {gid} {target}"
            )
        if bool(csv_row.expected_active):
            csv_result = (spread_result if target == "spread" else total_result)(
                float(final.home_points),
                float(final.away_points),
                float(csv_row.point),
                str(csv_row.side),
            )
            if (
                csv_result != csv_row.result
                or str(side) != str(csv_row.side)
                or result != csv_result
            ):
                raise GateError(
                    f"active served CSV grade reproduction mismatch: {run} {gid} {target}"
                )
            csv_grade_checks += 1
        else:
            policy_exceptions.append((run, gid, target))
        db_selections.append(
            dict(
                run_id=run,
                game_id=gid,
                target=target,
                side=str(side),
                point=float(point),
                price=float(price),
                snapshot_id=str(snap),
                quote_id=str(quote),
            )
        )
        db_grades.append(
            dict(
                run_id=run,
                game_id=gid,
                target=target,
                side=str(grade_side),
                result=str(stored_result),
                profit_units=float(stored_profit),
            )
        )

    if csv_grade_checks != EXPECTED_CSV_ACTIVE_GRADES:
        raise GateError(
            f"served CSV active grades {csv_grade_checks} != {EXPECTED_CSV_ACTIVE_GRADES}"
        )
    if len(policy_exceptions) != EXPECTED_CSV_POLICY_EXCEPTIONS:
        raise GateError(
            f"served CSV threshold exceptions {len(policy_exceptions)} != {EXPECTED_CSV_POLICY_EXCEPTIONS}"
        )
    summary = dict(
        status="passed",
        total_grades_checked=len(rows),
        csv_rows_checked=len(csv_rows),
        csv_grades_checked=csv_grade_checks,
        csv_policy_exceptions=len(policy_exceptions),
        mismatches_count=0,
        gates={
            "preview_db_recomputed": True,
            "served_csv_active_grades_recomputed": True,
            "served_csv_threshold_policy_validated": True,
            "db_csv_differences_limited_to_threshold_exceptions": True,
        },
        exception_keys_digest=frame_digest(
            pd.DataFrame(policy_exceptions, columns=keys)
        ),
        verified_runs=[original_run_id(w) for w in WEEKS],
    )
    artifacts = [
        (OLD_REPRO_SUMMARY.format(run_id=context.plan.run_id), json_data(summary))
    ]
    for name, frame in (
        ("predictions", predictions),
        ("selections", pd.DataFrame(db_selections)),
        ("grades", pd.DataFrame(db_grades)),
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
    if summary.get("csv_rows_checked") != EXPECTED_TOTAL_GRADES:
        problems.append("served CSV rows do not cover the complete target population")
    if summary.get("csv_grades_checked") != EXPECTED_CSV_ACTIVE_GRADES:
        problems.append(
            "served CSV active grade count differs from the legacy baseline"
        )
    if summary.get("csv_policy_exceptions") != EXPECTED_CSV_POLICY_EXCEPTIONS:
        problems.append(
            "served CSV threshold exception count differs from the legacy baseline"
        )
    expected_gates = {
        "preview_db_recomputed": True,
        "served_csv_active_grades_recomputed": True,
        "served_csv_threshold_policy_validated": True,
        "db_csv_differences_limited_to_threshold_exceptions": True,
    }
    if summary.get("gates") != expected_gates:
        problems.append("dual-baseline verification gates are missing or failed")
    if not problems:
        try:
            derived = build_old_grade_reproduction(context)
            for key, expected in derived.artifacts:
                if context.read_artifact("old_grade_reproduction", key) != expected:
                    problems.append(
                        f"persisted old-grade artifact differs from rederived evidence: {key}"
                    )
        except Exception as exc:
            problems.append(f"independent old-grade rederivation failed: {exc}")
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
        or old_summary.get("csv_rows_checked") != EXPECTED_TOTAL_GRADES
        or old_summary.get("csv_grades_checked") != EXPECTED_CSV_ACTIVE_GRADES
        or old_summary.get("csv_policy_exceptions") != EXPECTED_CSV_POLICY_EXCEPTIONS
        or old_summary.get("gates", {}).get(
            "db_csv_differences_limited_to_threshold_exceptions"
        )
        is not True
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
