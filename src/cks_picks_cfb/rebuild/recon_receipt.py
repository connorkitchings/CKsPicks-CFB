"""Stage 12: signed 6B receipt and served-format weekly artifacts.

Emits and independently re-derives rebuild_6b_receipt_v1, including per-week lineage,
rollback targets, hashes, and served-format predictions/scored CSVs and manifests.
Verify re-derives the whole receipt and fails if anything differs.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import pandas as pd

from cks_picks_cfb.artifacts import dataframe_csv_bytes
from cks_picks_cfb.data.data_first_phase2d import signed_payload, verify_signed_payload
from cks_picks_cfb.inference.v5_serving import build_v5_serving_rows
from cks_picks_cfb.rebuild import common
from cks_picks_cfb.rebuild.errors import GateError
from cks_picks_cfb.rebuild.legacy import score_bets
from cks_picks_cfb.rebuild.orchestrator import StageContext, StageOutput
from cks_picks_cfb.rebuild.published import PublishedRun
from cks_picks_cfb.rebuild.recon_common import (
    EXPECTED_COUNTS,
    TOTAL_2026_GAMES,
    WEEK_AS_OF,
    WEEKS,
    json_data,
    original_run_id,
    read_parquet_data,
    recon_run_id,
)
from cks_picks_cfb.rebuild.recon_forecast import PREDICTIONS_PARQUET
from cks_picks_cfb.rebuild.recon_foundation import FOUNDATION_SCHEDULE
from cks_picks_cfb.rebuild.recon_markets import (
    FINALS_PARQUET,
    _load_market_data,
)

RECEIPT_JSON = "rebuild/6b/{run_id}/receipt/receipt.json"
RECEIPT_MD = "rebuild/6b/{run_id}/receipt/receipt.md"
SCHEMA = "rebuild_6b_receipt_v1"
SERVING_MANIFEST_SCHEMA = "v5_intended_update_2026_serving_manifest_v1"

NON_CLAIMS = (
    "Production activation is not authorized and did not occur.",
    "This is Preview-only retrospective evidence; nothing here is certified for live serving or production.",
    "Weeks 0-5 are retrospective reconstructions; the original frozen Week 5 run remains unchanged.",
    "Cutover week N belongs exclusively to Stage 7B.",
    "Signing is canonical-content checksum signing, not cryptographic signer authentication.",
    "No serving, selection, authorization or production tables/prefixes were written.",
)

EXPECTED_6A_RECEIPT_SHA = "efcedf3e67dd85055782474b5022bf73d7f53d80c630264ca7c491699309d15e"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _build_weekly_served_artifacts(
    context: StageContext,
) -> tuple[dict[int, dict[str, Any]], list[tuple[str, bytes]]]:
    """Build served-format predictions.csv, scored.csv and manifest.json for weeks 0..5."""
    storage = common.preview_storage(context)
    sched_key = FOUNDATION_SCHEDULE.format(run_id=context.plan.run_id)
    schedule = read_parquet_data(context.read_artifact("foundation", sched_key))

    preds_key = PREDICTIONS_PARQUET.format(run_id=context.plan.run_id)
    predictions = read_parquet_data(context.read_artifact("predictions", preds_key))

    fin_key = FINALS_PARQUET.format(run_id=context.plan.run_id)
    finals = read_parquet_data(context.read_artifact("finals", fin_key))

    artifacts: list[tuple[str, bytes]] = []
    weeks_info: dict[int, dict[str, Any]] = {}

    for w in WEEKS:
        snaps, quotes = _load_market_data(context, w, storage)
        quotes_df = pd.DataFrame(quotes)
        w_schedule = schedule[schedule["week"].eq(w)].copy()
        w_schedule["start_date"] = w_schedule["kickoff_utc"].astype(str)

        w_preds = predictions[predictions["week"].eq(w)].copy()
        run_id_w = recon_run_id(w)
        orig_run_id_w = original_run_id(w)
        as_of_w = WEEK_AS_OF[w]

        # Build serving rows
        serving = build_v5_serving_rows(
            forecasts=w_preds,
            schedule=w_schedule,
            forecast_schedule=w_schedule,
            markets=snaps,
            forecast_run_id=run_id_w,
            forecast_manifest_sha256=_sha(json_data(w_preds.to_dict("records"))),
            year=2026,
            week=w,
            as_of=as_of_w,
            run_id=run_id_w,
            spread_threshold=0.0,
            spread_threshold_high=0.0,
            total_threshold=0.0,
            timing_class="replay",
            market_quotes=quotes_df,
        )

        serving = serving.sort_values("game_id", kind="mergesort").reset_index(drop=True)

        # Build scored rows
        w_finals = finals[finals["week"].eq(w)].rename(columns={"game_id": "id"})
        scored = score_bets(serving, w_finals)
        scored = scored.sort_values("game_id", kind="mergesort").reset_index(drop=True)

        pred_raw = dataframe_csv_bytes(serving)
        score_raw = dataframe_csv_bytes(scored)

        pred_key = f"rebuild/6b/{context.plan.run_id}/served/week={w}/predictions.csv"
        score_key = f"rebuild/6b/{context.plan.run_id}/served/week={w}/scored.csv"
        manifest_key = f"rebuild/6b/{context.plan.run_id}/served/week={w}/manifest.json"

        manifest_payload = signed_payload(
            {
                "schema_version": SERVING_MANIFEST_SCHEMA,
                "state": "candidate",
                "evidence_class": "retrospective_reconstruction",
                "identity": {
                    "run_id": run_id_w,
                    "original_run_id": orig_run_id_w,
                    "season": 2026,
                    "week": w,
                    "code_sha": context.code_sha,
                },
                "prediction_ref": {
                    "uri": pred_key,
                    "raw_sha256": _sha(pred_raw),
                    "rows": len(serving),
                },
                "scored_ref": {
                    "uri": score_key,
                    "raw_sha256": _sha(score_raw),
                    "rows": len(scored),
                },
                "quote_count": int(
                    serving.spread_market_quote_id.notna().sum()
                    + serving.total_market_quote_id.notna().sum()
                ),
                "game_count": len(serving),
                "data_as_of": as_of_w,
                "production_activation_authorized": False,
            }
        )
        manifest_raw = json_data(manifest_payload)

        artifacts.append((pred_key, pred_raw))
        artifacts.append((score_key, score_raw))
        artifacts.append((manifest_key, manifest_raw))

        weeks_info[w] = {
            "week": w,
            "recon_run_id": run_id_w,
            "original_run_id": orig_run_id_w,
            "as_of": as_of_w,
            "game_count": len(serving),
            "quote_count": int(
                serving.spread_market_quote_id.notna().sum()
                + serving.total_market_quote_id.notna().sum()
            ),
            "artifacts": {
                "predictions_csv": {"uri": pred_key, "raw_sha256": _sha(pred_raw), "rows": len(serving)},
                "scored_csv": {"uri": score_key, "raw_sha256": _sha(score_raw), "rows": len(scored)},
                "manifest_json": {"uri": manifest_key, "raw_sha256": _sha(manifest_raw)},
            },
        }

    return weeks_info, artifacts


def derive_receipt(
    context: StageContext,
    weekly_served_info: dict[int, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Derive the complete Stage 6B signed receipt payload."""
    plan = context.plan

    # Predecessor 6A info
    run_6a = PublishedRun(context, root_input="root_manifest_6a")
    raw_task4_receipt = context.read_input("task4_receipt")
    task4_receipt = json.loads(raw_task4_receipt)
    verify_signed_payload(task4_receipt, label="Task 4 signed receipt")
    if task4_receipt.get("manifest_sha256") != EXPECTED_6A_RECEIPT_SHA:
        raise GateError(f"6A receipt checksum mismatch: {task4_receipt.get('manifest_sha256')}")

    # Stage summaries
    fnd_sum = json.loads(
        context.read_artifact("foundation", f"rebuild/6b/{plan.run_id}/foundation/summary.json")
    )
    events_sum = json.loads(
        context.read_artifact("scoring_events_2026", f"rebuild/6b/{plan.run_id}/scoring_events_2026/summary.json")
    )
    off_sum = json.loads(
        context.read_artifact("offsets_2026", f"rebuild/6b/{plan.run_id}/offsets_2026/summary.json")
    )
    states_sum = json.loads(
        context.read_artifact("states_at_cutoff", f"rebuild/6b/{plan.run_id}/states_at_cutoff/summary.json")
    )
    frames_sum = json.loads(
        context.read_artifact("application_frames", f"rebuild/6b/{plan.run_id}/application_frames/summary.json")
    )
    preds_sum = json.loads(
        context.read_artifact("predictions", f"rebuild/6b/{plan.run_id}/predictions/summary.json")
    )
    markets_sum = json.loads(
        context.read_artifact("markets", f"rebuild/6b/{plan.run_id}/markets/summary.json")
    )
    finals_sum = json.loads(
        context.read_artifact("finals", f"rebuild/6b/{plan.run_id}/finals/summary.json")
    )
    old_repro_sum = json.loads(
        context.read_artifact("old_grade_reproduction", f"rebuild/6b/{plan.run_id}/old_grade_reproduction/summary.json")
    )
    retro_grades_sum = json.loads(
        context.read_artifact("retrospective_grades", f"rebuild/6b/{plan.run_id}/retrospective_grades/summary.json")
    )
    comp_sum = json.loads(
        context.read_artifact("comparison", f"rebuild/6b/{plan.run_id}/comparison/summary.json")
    )

    # Weekly served info (if not provided, rederive)
    if weekly_served_info is None:
        weekly_served_info, _ = _build_weekly_served_artifacts(context)

    # 5 Gold datasets registered in catalog
    gold_datasets = [
        off_sum["lake_gold"],
        frames_sum["lake_gold"],
        preds_sum["lake_gold"],
        markets_sum["lake_gold"],
        retro_grades_sum["lake_gold"],
    ]

    body = {
        "schema_version": SCHEMA,
        "kind": "stage_6b_exit_receipt",
        "production_activation_authorized": False,
        "identity": {
            "run_id": plan.run_id,
            "plan_sha256": plan.plan_sha(),
            "code_sha": context.code_sha,
            "storage_identity": plan.storage_identity,
            "predecessor_6a": {
                "main_run_id": run_6a.root["run_id"],
                "main_root_raw_sha256": _sha(context.read_input("root_manifest_6a")),
                "task4_root_raw_sha256": _sha(context.read_input("root_manifest_task4")),
                "receipt_sha256": EXPECTED_6A_RECEIPT_SHA,
            },
        },
        "inputs": {
            "plan_pins": [
                {"name": p.name, "kind": p.kind, "uri": p.uri, "sha256": p.sha256}
                for p in plan.inputs
            ],
            "decisions": dict(plan.decisions),
            "policies": dict(plan.policies),
        },
        "coverage": {
            "games_total": TOTAL_2026_GAMES,
            "weeks": list(WEEKS),
            "weekly_counts": EXPECTED_COUNTS,
            "selections_total": markets_sum["selections_count"],
            "grades_total": retro_grades_sum["grades_count"],
            "unusable_team_games": off_sum["unusable_team_games"],
        },
        "weeks": {str(w): weekly_served_info[w] for w in WEEKS},
        "outputs": {
            "gold_datasets": gold_datasets,
            "comparison_summary": comp_sum,
        },
        "validation": {
            "foundation_passed": fnd_sum.get("status") == "passed",
            "scoring_events_passed": events_sum.get("status") == "passed",
            "offset_freeze_passed": off_sum.get("offset_freeze_gate") == "passed",
            "states_identity_passed": states_sum.get("pregame_teams_identity_gate") == "passed",
            "frames_coverage_passed": frames_sum.get("status") == "passed",
            "bundle_compatibility_passed": preds_sum.get("bundle_compatibility") == "passed",
            "markets_coverage_passed": markets_sum.get("status") == "passed",
            "finals_coverage_passed": finals_sum.get("status") == "passed",
            "old_grade_reproduction_passed": old_repro_sum.get("status") == "passed" and old_repro_sum.get("mismatches_count") == 0,
            "retrospective_grades_passed": retro_grades_sum.get("status") == "passed",
            "comparison_passed": comp_sum.get("status") == "passed",
        },
        "non_claims": list(NON_CLAIMS),
    }

    return signed_payload(body)


def render_markdown(receipt: dict[str, Any]) -> str:
    ident = receipt["identity"]
    cov = receipt["coverage"]
    comp = receipt["outputs"]["comparison_summary"]
    records = comp["retrospective_records"]

    lines = [
        "# Stage 6B Exit Receipt",
        "",
        f"- **Receipt Checksum:** `{receipt['manifest_sha256']}`",
        f"- **Run ID:** `{ident['run_id']}`",
        f"- **Code SHA:** `{ident['code_sha'][:8]}`",
        f"- **Plan SHA:** `{ident['plan_sha256'][:8]}`",
        f"- **Predecessor 6A Receipt:** `{ident['predecessor_6a']['receipt_sha256'][:16]}…`",
        "",
        "## Reconstructed Coverage (2026 Weeks 0-5)",
        "",
        f"- **Games:** {cov['games_total']} (8/43/49/57/58/56)",
        f"- **Selections:** {cov['selections_total']} (model_side_best_quote_v2)",
        f"- **Retrospective Grades:** {cov['grades_total']} (0 mismatches on old grades first)",
        f"- **Unusable Team-Games:** {cov['unusable_team_games']} (6A scoring semantics)",
        "",
        "## Retrospective Performance Records vs 52.4%",
        "",
        "| Target | Record (W-L-P) | Win % | Profit Units | vs 52.4% |",
        "|---|---|---|---|---|",
        f"| Spread | {records['spread']['wins']}-{records['spread']['losses']}-{records['spread']['pushes']} | {records['spread']['win_pct']:.1%} | {records['spread']['profit_units']:+.2f}u | {records['spread']['vs_52_4']:+.1%} |",
        f"| Total | {records['total']['wins']}-{records['total']['losses']}-{records['total']['pushes']} | {records['total']['win_pct']:.1%} | {records['total']['profit_units']:+.2f}u | {records['total']['vs_52_4']:+.1%} |",
        f"| Overall | {records['overall']['wins']}-{records['overall']['losses']}-{records['overall']['pushes']} | {records['overall']['win_pct']:.1%} | {records['overall']['profit_units']:+.2f}u | {records['overall']['vs_52_4']:+.1%} |",
        "",
        "## Weekly Reconstruction and Rollback Targets",
        "",
        "| Week | Games | Reconstructed Run ID | Original Served Run ID (Rollback) | Predictions CSV | Scored CSV |",
        "|---|---|---|---|---|---|",
    ]

    weeks = receipt["weeks"]
    for w in sorted(int(k) for k in weeks):
        winfo = weeks[str(w)]
        lines.append(
            f"| {w} | {winfo['game_count']} | `{winfo['recon_run_id']}` | `{winfo['original_run_id']}` | "
            f"`{winfo['artifacts']['predictions_csv']['raw_sha256'][:8]}…` | `{winfo['artifacts']['scored_csv']['raw_sha256'][:8]}…` |"
        )

    lines.extend(["", "## Non-claims", ""])
    for nc in receipt["non_claims"]:
        lines.append(f"- {nc}")

    return "\n".join(lines) + "\n"


def build_receipt(context: StageContext) -> StageOutput:
    weeks_info, served_artifacts = _build_weekly_served_artifacts(context)
    receipt = derive_receipt(context, weekly_served_info=weeks_info)

    prefix_json = RECEIPT_JSON.format(run_id=context.plan.run_id)
    prefix_md = RECEIPT_MD.format(run_id=context.plan.run_id)

    receipt_bytes = json_data(receipt)
    md_bytes = render_markdown(receipt).encode()

    all_artifacts = served_artifacts + [
        (prefix_json, receipt_bytes),
        (prefix_md, md_bytes),
    ]

    return StageOutput(
        artifacts=all_artifacts,
        metrics={
            "receipt_sha256": receipt["manifest_sha256"],
            "served_artifacts_count": len(served_artifacts),
        },
    )


def verify_receipt(context: StageContext) -> list[str]:
    problems: list[str] = []
    prefix_json = RECEIPT_JSON.format(run_id=context.plan.run_id)

    try:
        raw_receipt = context.read_artifact("receipt", prefix_json)
        receipt = json.loads(raw_receipt)
    except Exception as exc:
        return [f"failed to read receipt: {exc}"]

    # 1. Verify signature
    try:
        verify_signed_payload(receipt, label="Stage 6B exit receipt")
    except Exception as exc:
        problems.append(f"receipt signature verification failed: {exc}")

    # 2. Check production authorization flag
    if receipt.get("production_activation_authorized") is not False:
        problems.append("receipt must state that production activation is not authorized")

    # 3. Check non-claims
    if len(receipt.get("non_claims", [])) != len(NON_CLAIMS):
        problems.append("the non-claims were altered")

    # 4. Check validation booleans
    val = receipt.get("validation", {})
    for check_name, passed in val.items():
        if not passed:
            problems.append(f"validation check '{check_name}' did not pass")

    # 5. Check served weekly artifacts
    weeks = receipt.get("weeks", {})
    if set(weeks.keys()) != {str(w) for w in WEEKS}:
        problems.append("receipt weeks missing from coverage")

    for w_str, winfo in weeks.items():
        w = int(w_str)
        pred_key = winfo["artifacts"]["predictions_csv"]["uri"]
        score_key = winfo["artifacts"]["scored_csv"]["uri"]
        manifest_key = winfo["artifacts"]["manifest_json"]["uri"]

        try:
            pred_bytes = context.read_artifact("receipt", pred_key)
            if _sha(pred_bytes) != winfo["artifacts"]["predictions_csv"]["raw_sha256"]:
                problems.append(f"week {w} predictions.csv sha256 mismatch")
        except Exception as exc:
            problems.append(f"missing week {w} predictions.csv artifact: {exc}")

        try:
            score_bytes = context.read_artifact("receipt", score_key)
            if _sha(score_bytes) != winfo["artifacts"]["scored_csv"]["raw_sha256"]:
                problems.append(f"week {w} scored.csv sha256 mismatch")
        except Exception as exc:
            problems.append(f"missing week {w} scored.csv artifact: {exc}")

        try:
            manifest_bytes = context.read_artifact("receipt", manifest_key)
            if _sha(manifest_bytes) != winfo["artifacts"]["manifest_json"]["raw_sha256"]:
                problems.append(f"week {w} manifest.json sha256 mismatch")
        except Exception as exc:
            problems.append(f"missing week {w} manifest.json artifact: {exc}")

    # 6. Re-derivation equality
    try:
        rederived = derive_receipt(context)
        if rederived != receipt:
            problems.append("re-derived receipt differs from staged receipt")
    except Exception as exc:
        problems.append(f"failed to re-derive receipt: {exc}")

    return problems
