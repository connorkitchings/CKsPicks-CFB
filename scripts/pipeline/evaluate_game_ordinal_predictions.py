#!/usr/bin/env python3
"""Seal result-only Games 1–4 selection, then validate it on locked 2025."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd
from omegaconf import OmegaConf

from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.models.predictive_evaluation import (
    evaluate_predictive_candidate,
    locked_predictive_anti_regression,
    select_predictive_route,
)
from cks_picks_cfb.models.training_policy import (
    policy_from_mapping,
    selection_years,
    validate_feature_lineage,
)
from cks_picks_cfb.ratings.offseason_context import require_admitted_context

EARLY_REGIMES = ("game_1", "game_2", "game_3", "game_4")
CANDIDATE_COLUMNS = {
    "established": "established_prediction",
    "blend": "blend_prediction",
    "direct_ridge": "direct_ridge_prediction",
    "points_ridge": "points_ridge_prediction",
    "direct_catboost": "direct_catboost_prediction",
    "points_catboost": "points_catboost_prediction",
}


def _canonical_sha(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _report_for_rows(
    rows: pd.DataFrame,
    *,
    target: str,
    regime: str,
    prediction_column: str,
    bootstrap: int,
) -> dict[str, Any]:
    return evaluate_predictive_candidate(
        rows.rename(columns={prediction_column: "candidate_prediction"}),
        target=target,
        regime=regime,
        n_bootstrap=bootstrap,
    )


def _design_key(rows: pd.DataFrame) -> str:
    if "prior_strengths_json" not in rows:
        return "{}"
    values = sorted(rows["prior_strengths_json"].dropna().astype(str).unique())
    return values[0] if values else "{}"


def _candidate_reports(
    rows: pd.DataFrame, *, target: str, regime: str, bootstrap: int
) -> dict[str, dict[str, Any]]:
    """Evaluate all available designs and retain a deterministic finalist."""
    reports: dict[str, dict[str, Any]] = {}
    for candidate, column in CANDIDATE_COLUMNS.items():
        if column not in rows:
            continue
        complete = rows.dropna(subset=[column, "baseline_prediction", "actual"])
        if complete.empty:
            continue
        by_design = []
        if "feature_variant" not in complete:
            complete = complete.assign(feature_variant="prior_core")
        if "prior_strengths_json" in complete and candidate != "blend":
            groups = complete.groupby(
                ["feature_variant", "prior_strengths_json"],
                dropna=False,
                observed=True,
            )
        else:
            groups = [
                ((str(variant), "{}"), values)
                for variant, values in complete.groupby(
                    "feature_variant", observed=True
                )
            ]
        for (variant, design), values in groups:
            report = _report_for_rows(
                values,
                target=target,
                regime=regime,
                prediction_column=column,
                bootstrap=bootstrap,
            )
            by_design.append((str(variant), str(design), report))
        variant, design, report = min(
            by_design,
            key=lambda item: (
                float(item[2]["metrics"]["candidate_mae"]),
                float(item[2]["metrics"]["candidate_rmse"]),
                abs(float(item[2]["metrics"]["candidate_bias"])),
                item[0],
                item[1],
            ),
        )
        reports[candidate] = {
            **report,
            "selected_prior_strengths": json.loads(design),
            "selected_feature_variant": variant,
            "design_count": len(by_design),
        }
    return reports


def _read(storage, uri: str) -> dict[str, Any]:
    return json.loads(storage.read_bytes(uri).decode())


def _write_immutable(storage, uri: str, payload: dict[str, Any]) -> None:
    encoded = json.dumps(payload, indent=2, sort_keys=True).encode()
    if storage.exists(uri):
        if storage.read_bytes(uri) != encoded:
            raise FileExistsError(f"Immutable report exists: {uri}")
    else:
        storage.write_bytes(encoded, uri)


def _strength_gap_diagnostics(frame: pd.DataFrame) -> dict[str, Any]:
    """Summarize the extreme non-market pregame baseline segment."""
    values = pd.to_numeric(frame["baseline_prediction"], errors="coerce").abs()
    if values.notna().sum() < 10:
        return {"available": False, "reason": "fewer than ten finite baseline rows"}
    high = values >= values.quantile(0.90)
    return {
        "available": True,
        "basis": "absolute_pregame_baseline_prediction_top_decile",
        "high_gap_rows": int(high.sum()),
        "high_gap_mae": float(
            (frame.loc[high, "baseline_prediction"] - frame.loc[high, "actual"])
            .abs()
            .mean()
        ),
        "all_rows": int(len(frame)),
    }


def _selection(
    frame: pd.DataFrame,
    *,
    policy,
    bootstrap: int,
    feature_ref_uri: str | None,
    blend_weights: dict[str, dict[str, float]] | None,
) -> dict[str, Any]:
    selection = set(selection_years(policy))
    if set(frame["season"].astype(int)) - selection:
        raise ValueError("Selection candidates may contain only 2022-2024 rows")
    reports: dict[str, dict[str, dict[str, Any]]] = {
        target: {} for target in ("spread", "total")
    }
    proposed_routing: dict[str, dict[str, str]] = {target: {} for target in reports}
    for target in reports:
        for regime in EARLY_REGIMES:
            rows = frame[(frame["target"] == target) & (frame["regime"] == regime)]
            if rows.empty:
                raise ValueError(f"Missing selection rows for {target}/{regime}")
            candidate_reports = _candidate_reports(
                rows, target=target, regime=regime, bootstrap=bootstrap
            )
            proposed_routing[target][regime] = select_predictive_route(
                candidate_reports
            )
            reports[target][regime] = candidate_reports
    payload: dict[str, Any] = {
        "schema_version": "game_ordinal_predictive_selection_v2",
        "stage": "selection",
        "selection_basis": "predictive_results_only",
        "betting_validation_status": "not_evaluated",
        "training_policy": policy.schema_version,
        "selection_years": sorted(selection),
        "locked_test_year": policy.locked_test_year,
        "production_refit_years": list(policy.production_refit_years),
        "prior_source_overrides": {"2021": 2019},
        "excluded_years": [2020],
        "feature_ref_uri": feature_ref_uri,
        "feature_track": str(frame.get("feature_track", pd.Series("strict")).iloc[0]),
        "blend_weights": blend_weights or {},
        "feature_variants": sorted(
            frame.get("feature_variant", pd.Series("prior_quality"))
            .dropna()
            .astype(str)
            .unique()
        ),
        "proposed_routing": proposed_routing,
        "reports": reports,
    }
    payload["selection_design_sha"] = _canonical_sha(payload)
    return payload


def _locked(
    frame: pd.DataFrame, *, selection: dict[str, Any], policy, bootstrap: int
) -> dict[str, Any]:
    if selection.get("stage") != "selection" or not selection.get(
        "selection_design_sha"
    ):
        raise ValueError("Locked validation requires an immutable selection report")
    if selection.get("feature_track", "strict") != "strict":
        raise ValueError("Locked validation requires a strict selection report")
    if set(frame["season"].astype(int)) != {policy.locked_test_year}:
        raise ValueError("Locked candidates must contain only the locked 2025 season")
    routing: dict[str, dict[str, str]] = {target: {} for target in ("spread", "total")}
    locked_reports: dict[str, dict[str, dict[str, Any]]] = {
        target: {} for target in routing
    }
    for target in routing:
        for regime in EARLY_REGIMES:
            proposed = selection["proposed_routing"][target][regime]
            rows = frame[(frame["target"] == target) & (frame["regime"] == regime)]
            if rows.empty:
                raise ValueError(f"Missing locked rows for {target}/{regime}")
            if proposed == "baseline":
                routing[target][regime] = "baseline"
                locked_reports[target][regime] = {
                    "candidate": "baseline",
                    "locked_test_pass": True,
                }
                continue
            column = CANDIDATE_COLUMNS[proposed]
            if column not in rows:
                raise ValueError(
                    f"Locked rows are missing proposed {proposed} predictions"
                )
            report = _report_for_rows(
                rows.dropna(subset=[column]),
                target=target,
                regime=regime,
                prediction_column=column,
                bootstrap=bootstrap,
            )
            passed = locked_predictive_anti_regression(report)
            routing[target][regime] = proposed if passed else "baseline"
            locked_reports[target][regime] = {
                "candidate": proposed,
                "locked_test_pass": passed,
                "report": report,
                "fallback": not passed,
            }
    return {
        "schema_version": "game_ordinal_predictive_routing_v2",
        "stage": "finalized",
        "selection_basis": "predictive_results_only",
        "betting_validation_status": "not_evaluated",
        "training_policy": policy.schema_version,
        "selection_report_sha": selection["selection_design_sha"],
        "selection_report": selection,
        "feature_track": "strict",
        "routing": routing,
        "locked_2025_reports": locked_reports,
        "production_refit_years": list(policy.production_refit_years),
        "prior_source_overrides": {"2021": 2019},
        "excluded_years": [2020],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("selection", "locked"), required=True)
    parser.add_argument("--candidates-csv", type=Path, required=True)
    parser.add_argument("--output-uri", required=True)
    parser.add_argument("--selection-report-uri")
    parser.add_argument("--feature-ref-uri")
    parser.add_argument("--blend-weights-json", type=Path)
    parser.add_argument("--context-admission-report-uri")
    parser.add_argument("--research-only", action="store_true")
    parser.add_argument(
        "--environment", choices=("preview", "production"), default="preview"
    )
    parser.add_argument("--bootstrap", type=int, default=2_000)
    parser.add_argument(
        "--training-policy", type=Path, default=Path("conf/training/week0_2026.yaml")
    )
    args = parser.parse_args()
    policy = policy_from_mapping(
        OmegaConf.to_container(OmegaConf.load(args.training_policy), resolve=True)
    )
    frame = pd.read_csv(args.candidates_csv)
    required = {
        "season",
        "target",
        "regime",
        "actual",
        "baseline_prediction",
        "training_max_year",
        "prior_source_season",
        "prior_season_gap",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Candidate file is missing columns: {missing}")
    validate_feature_lineage(frame, policy)
    if set(frame["regime"].dropna()) - set(EARLY_REGIMES):
        raise ValueError("Ordinal evaluator accepts only game_1 through game_4")
    if (frame["training_max_year"].astype(int) >= frame["season"].astype(int)).any():
        raise ValueError(
            "Candidate predictions must train strictly before their season"
        )
    storage = get_storage(environment=args.environment)
    tracks = set(frame.get("feature_track", pd.Series("strict")).dropna().astype(str))
    if tracks == {"reconstructed"} and not args.research_only:
        raise ValueError("Reconstructed V4 candidates require --research-only")
    if args.research_only:
        if tracks != {"reconstructed"}:
            raise ValueError("--research-only accepts only reconstructed V4 candidates")
        if args.stage != "selection":
            raise ValueError(
                "Reconstructed research reports support selection rows only"
            )
        reports = {
            target: {
                regime: _candidate_reports(
                    frame[(frame["target"] == target) & (frame["regime"] == regime)],
                    target=target,
                    regime=regime,
                    bootstrap=args.bootstrap,
                )
                for regime in EARLY_REGIMES
            }
            for target in ("spread", "total")
        }
        context_admission = None
        if args.context_admission_report_uri:
            context_admission = _read(storage, args.context_admission_report_uri)
            require_admitted_context(context_admission, allow_reconstructed=True)
            if context_admission["feature_track"] != "reconstructed":
                raise ValueError("Research-only candidates require reconstructed context")
        payload = {
            "schema_version": "game_ordinal_reconstructed_research_v1",
            "stage": "research",
            "feature_track": "reconstructed",
            "activation_eligible": False,
            "selection_basis": "research_only",
            "feature_ref_uri": args.feature_ref_uri,
            "context_admission": context_admission,
            "strength_gap_diagnostics": _strength_gap_diagnostics(frame),
            "reports": reports,
        }
        _write_immutable(storage, args.output_uri, payload)
        print(json.dumps({"stage": "research", "activation_eligible": False}, indent=2))
        return
    if args.stage == "selection":
        blend_weights = (
            json.loads(args.blend_weights_json.read_text())
            if args.blend_weights_json
            else None
        )
        payload = _selection(
            frame,
            policy=policy,
            bootstrap=args.bootstrap,
            feature_ref_uri=args.feature_ref_uri,
            blend_weights=blend_weights,
        )
    else:
        if not args.selection_report_uri:
            raise ValueError("--selection-report-uri is required for locked validation")
        selection = _read(storage, args.selection_report_uri)
        if selection.get("feature_track", "strict") != "strict":
            raise ValueError("Locked validation requires a strict selection report")
        payload = _locked(
            frame, selection=selection, policy=policy, bootstrap=args.bootstrap
        )
    _write_immutable(storage, args.output_uri, payload)
    print(
        json.dumps(
            {
                "stage": payload["stage"],
                "routing": payload.get("routing") or payload.get("proposed_routing"),
                "selection_design_sha": payload.get("selection_design_sha")
                or payload.get("selection_report_sha"),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
