#!/usr/bin/env python3
"""Evaluate Ridge/CatBoost OOF predictions and freeze a routing report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from omegaconf import OmegaConf

from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.models.promotion import (
    evaluate_promotion,
    locked_test_anti_regression,
    select_regime_candidate,
)
from cks_picks_cfb.models.training_policy import (
    policy_from_mapping,
    selection_years,
    validate_feature_lineage,
)

REGIMES = ("preseason", "one_game", "two_games", "three_games", "established")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oof-csv", type=Path, required=True)
    parser.add_argument("--output-uri", required=True)
    parser.add_argument("--bootstrap", type=int, default=1000)
    parser.add_argument("--blend-weights-json", type=Path, required=True)
    parser.add_argument(
        "--training-policy",
        type=Path,
        default=Path("conf/training/week0_2026.yaml"),
    )
    args = parser.parse_args()
    policy = policy_from_mapping(
        OmegaConf.to_container(OmegaConf.load(args.training_policy), resolve=True)
    )
    blend_weights = json.loads(args.blend_weights_json.read_text(encoding="utf-8"))
    for target in ("spread", "total"):
        weights = {
            int(key): float(value) for key, value in blend_weights[target].items()
        }
        if set(weights) != set(range(5)) or not (
            weights[0] >= weights[1] >= weights[2] >= weights[3] >= weights[4]
        ):
            raise ValueError(f"{target} blend weights are incomplete or non-monotone")
    frame = pd.read_csv(args.oof_csv)
    required = {
        "season",
        "target",
        "regime",
        "actual",
        "market_line",
        "baseline_prediction",
        "direct_ridge_prediction",
        "direct_catboost_prediction",
        "blend_prediction",
        "training_max_year",
        "prior_source_season",
        "prior_season_gap",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"OOF prediction file is missing columns: {missing}")
    if set(frame["season"].astype(int)) - set(policy.labeled_years):
        raise ValueError("OOF file contains an unsupported season")
    validate_feature_lineage(frame, policy)
    oof_years = selection_years(policy)
    oof = frame[frame["season"].isin(oof_years)]
    if (oof["training_max_year"].astype(int) != oof["season"].astype(int) - 1).any():
        raise ValueError("OOF predictions must train only on preceding seasons")
    locked = frame[frame["season"] == policy.locked_test_year]
    if locked.empty or set(locked["training_max_year"].astype(int)) != {2024}:
        raise ValueError("Locked 2025 predictions must train on 2021-2024")

    routing: dict[str, dict[str, str]] = {target: {} for target in ("spread", "total")}
    reports: dict[str, dict[str, dict]] = {target: {} for target in ("spread", "total")}
    for target in ("spread", "total"):
        for regime in REGIMES:
            selection_rows = frame[
                (frame["target"] == target)
                & (frame["regime"] == regime)
                & (frame["season"].isin(oof_years))
            ]
            locked_rows = frame[
                (frame["target"] == target)
                & (frame["regime"] == regime)
                & (frame["season"] == policy.locked_test_year)
            ]
            if selection_rows.empty or locked_rows.empty:
                raise ValueError(f"Missing OOF rows for {target}/{regime}")
            candidate_reports = {}
            candidates = ["direct_ridge", "direct_catboost"]
            if regime in {"one_game", "two_games", "three_games"}:
                candidates.insert(1, "blend")
            for candidate in candidates:
                selection_frame = selection_rows.rename(
                    columns={f"{candidate}_prediction": "candidate_prediction"}
                )
                locked_frame = locked_rows.rename(
                    columns={f"{candidate}_prediction": "candidate_prediction"}
                )
                selection_report = evaluate_promotion(
                    selection_frame,
                    target=target,
                    regime=regime,
                    n_bootstrap=args.bootstrap,
                )
                locked_report = evaluate_promotion(
                    locked_frame,
                    target=target,
                    regime=regime,
                    n_bootstrap=args.bootstrap,
                )
                candidate_reports[candidate] = {
                    **selection_report,
                    "selection_report": selection_report,
                    "locked_2025_report": locked_report,
                    "locked_test_pass": locked_test_anti_regression(locked_report),
                    "promotion_pass": bool(selection_report["promotion_pass"]),
                }
            selected = select_regime_candidate(candidate_reports)
            champion = (
                selected
                if selected and candidate_reports[selected]["locked_test_pass"]
                else None
            )
            routing[target][regime] = champion or "display_fallback"
            reports[target][regime] = candidate_reports
    payload = {
        "schema_version": "regime_routing_v1",
        "training_policy": policy.schema_version,
        "selection_years": list(oof_years),
        "locked_test_year": policy.locked_test_year,
        "production_refit_years": list(policy.production_refit_years),
        "prior_source_overrides": {"2021": 2019},
        "excluded_years": [2020],
        "blend_weights": blend_weights,
        "routing": routing,
        "reports": reports,
        "transition_diagnostics": (
            frame.groupby(["season", "target", "regime"], observed=True)
            .agg(
                games=("actual", "size"),
                direct_ridge_mae=(
                    "direct_ridge_prediction",
                    lambda values: float(
                        (values - frame.loc[values.index, "actual"]).abs().mean()
                    ),
                ),
                direct_catboost_mae=(
                    "direct_catboost_prediction",
                    lambda values: float(
                        (values - frame.loc[values.index, "actual"]).abs().mean()
                    ),
                ),
            )
            .reset_index()
            .to_dict("records")
        ),
    }
    storage = get_storage()
    if storage.exists(args.output_uri):
        raise FileExistsError(f"Immutable routing report exists: {args.output_uri}")
    storage.write_bytes(
        json.dumps(payload, indent=2, sort_keys=True).encode("utf-8"),
        args.output_uri,
    )
    print(json.dumps(routing, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
