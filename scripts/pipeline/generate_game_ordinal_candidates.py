#!/usr/bin/env python3
"""Generate sealed staged candidates for the canonical Games 1–3 tournament."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from omegaconf import OmegaConf

from cks_picks_cfb.data.lake import DatasetRef, read_dataset
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.features.v2_recency import canonical_prediction_regime
from cks_picks_cfb.models.early_season import (
    add_ordinal_shrinkage_features,
    prior_strength_designs,
)
from cks_picks_cfb.models.game_ordinal_training import (
    generate_game_ordinal_candidate_predictions,
)
from cks_picks_cfb.models.predictive_evaluation import evaluate_predictive_candidate
from cks_picks_cfb.models.training_policy import policy_from_mapping

EARLY = ("game_1", "game_2", "game_3")


def _feature_ref(storage, uri: str) -> DatasetRef:
    return DatasetRef(**json.loads(storage.read_bytes(uri).decode()))


def _best_strengths(
    rows: pd.DataFrame, candidate: str
) -> dict[tuple[str, str], dict[str, float]]:
    column = f"{candidate}_prediction"
    result: dict[tuple[str, str], dict[str, float]] = {}
    for target in ("spread", "total"):
        for regime in EARLY:
            route = rows[(rows["target"] == target) & (rows["regime"] == regime)]
            scored = []
            for strength_json, values in route.groupby(
                "prior_strengths_json", observed=True
            ):
                report = evaluate_predictive_candidate(
                    values.rename(columns={column: "candidate_prediction"}),
                    target=target,
                    regime=regime,
                    n_bootstrap=1,
                )
                scored.append((strength_json, report))
            if not scored:
                raise ValueError(f"No Ridge designs for {target}/{regime}/{candidate}")
            strength_json, _ = min(
                scored,
                key=lambda item: (
                    item[1]["metrics"]["candidate_mae"],
                    item[1]["metrics"]["candidate_rmse"],
                    abs(item[1]["metrics"]["candidate_bias"]),
                    item[0],
                ),
            )
            result[(target, regime)] = json.loads(strength_json)
    return result


def _blend_rows(rows: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, dict[str, float]]]:
    """Build frozen canonical blend OOF rows; Game 1 is prior-only."""
    output = []
    weights: dict[str, dict[str, float]] = {}
    for target in ("spread", "total"):
        target_rows = rows[rows["target"] == target].copy()
        prior_column = f"preseason_{target}_prediction"
        current_column = f"current_{target}_prediction"
        if {prior_column, current_column} - set(target_rows):
            raise ValueError("Canonical blend requires baseline component predictions")
        selected: tuple[float, float] | None = None
        best_loss = float("inf")
        for game_2 in np.linspace(0.0, 1.0, 21):
            for game_3 in np.linspace(0.0, game_2, int(round(game_2 * 20)) + 1):
                candidate = target_rows.copy()
                route_weight = candidate["regime"].map(
                    {"game_1": 1.0, "game_2": game_2, "game_3": game_3}
                )
                prediction = (
                    route_weight * candidate[prior_column]
                    + (1.0 - route_weight) * candidate[current_column]
                )
                loss = float((prediction - candidate["actual"]).abs().mean())
                if loss < best_loss:
                    best_loss, selected = loss, (float(game_2), float(game_3))
        assert selected is not None
        weights[target] = {"game_1": 1.0, "game_2": selected[0], "game_3": selected[1]}
        target_rows["blend_prediction"] = (
            target_rows["regime"].map(weights[target]) * target_rows[prior_column]
            + (1.0 - target_rows["regime"].map(weights[target]))
            * target_rows[current_column]
        )
        target_rows["prior_strengths_json"] = "{}"
        output.append(target_rows)
    return pd.concat(output, ignore_index=True), weights


def _selection(
    raw: pd.DataFrame, policy, spec, seed: int
) -> tuple[pd.DataFrame, dict[str, dict[str, float]]]:
    ridge_rows = []
    for strengths in prior_strength_designs():
        frame, features = add_ordinal_shrinkage_features(raw, prior_strengths=strengths)
        ridge_rows.append(
            generate_game_ordinal_candidate_predictions(
                frame,
                policy=policy,
                features=[*features, *list(spec.context_features)],
                baseline_columns=OmegaConf.to_container(
                    spec.baseline_columns, resolve=True
                ),
                random_seed=seed,
                stage="selection",
                candidate_kinds=("direct_ridge", "points_ridge"),
                prior_strengths=strengths,
            )
        )
    ridge = pd.concat(ridge_rows, ignore_index=True)
    selected = {
        candidate: _best_strengths(ridge, candidate)
        for candidate in ("direct_ridge", "points_ridge")
    }
    cat_rows = []
    for candidate, designs in selected.items():
        for strengths in {
            json.dumps(value, sort_keys=True) for value in designs.values()
        }:
            values = json.loads(strengths)
            frame, features = add_ordinal_shrinkage_features(
                raw, prior_strengths=values
            )
            cat_rows.append(
                generate_game_ordinal_candidate_predictions(
                    frame,
                    policy=policy,
                    features=[*features, *list(spec.context_features)],
                    baseline_columns=OmegaConf.to_container(
                        spec.baseline_columns, resolve=True
                    ),
                    random_seed=seed,
                    stage="selection",
                    candidate_kinds=(candidate.replace("ridge", "catboost"),),
                    prior_strengths=values,
                )
            )
    # Use one Ridge design's rows to avoid duplicate baseline-component OOF rows.
    blend, weights = _blend_rows(
        ridge[ridge["prior_strengths_json"] == ridge["prior_strengths_json"].iloc[0]]
    )
    return pd.concat([ridge, *cat_rows, blend], ignore_index=True), weights


def _locked(
    raw: pd.DataFrame, policy, spec, selection: dict, seed: int
) -> pd.DataFrame:
    default_strengths = {"plays": 100.0, "drives": 20.0, "games": 4.0}
    default_frame, default_features = add_ordinal_shrinkage_features(
        raw, prior_strengths=default_strengths
    )
    baseline_rows = generate_game_ordinal_candidate_predictions(
        default_frame,
        policy=policy,
        features=[*default_features, *list(spec.context_features)],
        baseline_columns=OmegaConf.to_container(spec.baseline_columns, resolve=True),
        random_seed=seed,
        stage="locked",
        candidate_kinds=("direct_ridge",),
        prior_strengths=default_strengths,
    )
    rows = []
    for target in ("spread", "total"):
        for regime in EARLY:
            candidate = selection["proposed_routing"][target][regime]
            if candidate == "baseline":
                rows.append(
                    baseline_rows[
                        (baseline_rows["target"] == target)
                        & (baseline_rows["regime"] == regime)
                    ]
                )
                continue
            if candidate == "blend":
                # Add one ordinary candidate frame only to supply the strict lineage columns.
                strengths = {"plays": 100.0, "drives": 20.0, "games": 4.0}
            else:
                strengths = selection["reports"][target][regime][candidate][
                    "selected_prior_strengths"
                ]
            frame, features = add_ordinal_shrinkage_features(
                raw, prior_strengths=strengths
            )
            kinds = (candidate,) if candidate != "blend" else ("direct_ridge",)
            candidate_rows = generate_game_ordinal_candidate_predictions(
                frame,
                policy=policy,
                features=[*features, *list(spec.context_features)],
                baseline_columns=OmegaConf.to_container(
                    spec.baseline_columns, resolve=True
                ),
                random_seed=seed,
                stage="locked",
                candidate_kinds=kinds,
                prior_strengths=strengths,
            )
            candidate_rows = candidate_rows[
                (candidate_rows["target"] == target)
                & (candidate_rows["regime"] == regime)
            ].copy()
            if candidate == "blend":
                weight = float(selection["blend_weights"][target][regime])
                candidate_rows["blend_prediction"] = (
                    weight * candidate_rows[f"preseason_{target}_prediction"]
                    + (1.0 - weight) * candidate_rows[f"current_{target}_prediction"]
                )
            rows.append(candidate_rows)
    return pd.concat(rows, ignore_index=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("selection", "locked"), required=True)
    parser.add_argument("--feature-ref-uri", required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--selection-report-uri")
    parser.add_argument(
        "--environment", choices=("preview", "production"), required=True
    )
    parser.add_argument(
        "--experiment", type=Path, default=Path("conf/experiment/week0_regimes.yaml")
    )
    parser.add_argument("--random-seed", type=int, default=42)
    args = parser.parse_args()
    storage = get_storage(environment=args.environment)
    spec = OmegaConf.load(args.experiment)
    policy = policy_from_mapping(
        OmegaConf.to_container(OmegaConf.load(spec.training_policy), resolve=True)
    )
    raw = read_dataset(storage, _feature_ref(storage, args.feature_ref_uri)).assign(
        prediction_regime=lambda values: values["prediction_regime"].map(
            canonical_prediction_regime
        )
    )
    if args.stage == "selection":
        result, weights = _selection(raw, policy, spec, args.random_seed)
        result.attrs["blend_weights"] = weights
        weights_path = args.output_csv.with_suffix(".blend-weights.json")
        weights_path.write_text(json.dumps(weights, indent=2, sort_keys=True))
    else:
        if not args.selection_report_uri:
            raise ValueError("--selection-report-uri is required for locked generation")
        selection = json.loads(storage.read_bytes(args.selection_report_uri).decode())
        if selection.get("stage") != "selection" or not selection.get(
            "selection_design_sha"
        ):
            raise ValueError("Locked generation requires a sealed selection report")
        result = _locked(raw, policy, spec, selection, args.random_seed)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output_csv, index=False)
    print(
        json.dumps(
            {
                "stage": args.stage,
                "rows": len(result),
                "years": sorted(
                    result["season"].dropna().astype(int).unique().tolist()
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
