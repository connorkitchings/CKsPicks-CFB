"""Temporal candidate generation for first-, second-, and third-game routes."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd

from cks_picks_cfb.models.regime_training import TARGET_COLUMNS, _fit_predict
from cks_picks_cfb.models.training_policy import TrainingPolicy, labeled_training_frame

EARLY_REGIMES = ("game_1", "game_2", "game_3", "game_4")
POINT_TARGETS = {"home": "home_points", "away": "away_points"}
CANDIDATE_KINDS = (
    "direct_ridge",
    "points_ridge",
    "direct_catboost",
    "points_catboost",
)


def generate_game_ordinal_candidate_predictions(
    frame: pd.DataFrame,
    *,
    policy: TrainingPolicy,
    features: Sequence[str],
    baseline_columns: Mapping[str, str],
    random_seed: int = 42,
    stage: str = "selection",
    candidate_kinds: Sequence[str] = CANDIDATE_KINDS,
    prior_strengths: Mapping[str, float] | None = None,
    established_features: Sequence[str] | None = None,
    feature_variant: str = "prior_quality",
) -> pd.DataFrame:
    """Generate one sealed stage of direct and points-derived candidates.

    The caller supplies an already reviewed feature list containing no bookmaker
    values. Each fold only trains on seasons preceding its validation season.
    """
    frame = labeled_training_frame(frame, policy)
    if {"home_points", "away_points"} - set(frame.columns):
        target_columns = {"spread_target", "total_target"}
        if target_columns - set(frame.columns):
            raise ValueError(
                "Points-derived candidates require spread and total targets"
            )
        frame = frame.copy()
        frame["home_points"] = (frame["total_target"] + frame["spread_target"]) / 2.0
        frame["away_points"] = (frame["total_target"] - frame["spread_target"]) / 2.0
    required = {
        "season",
        "game_id",
        "prediction_regime",
        "home_points",
        "away_points",
        *TARGET_COLUMNS.values(),
        *features,
        *baseline_columns.values(),
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Ordinal candidate frame is missing columns: {missing}")
    unknown = (
        set(frame["prediction_regime"].dropna()) - set(EARLY_REGIMES) - {"established"}
    )
    if unknown:
        raise ValueError(
            f"Ordinal candidate frame has unsupported routes: {sorted(unknown)}"
        )
    unknown_kinds = set(candidate_kinds) - set(CANDIDATE_KINDS)
    if unknown_kinds:
        raise ValueError(
            f"Unsupported ordinal candidate kinds: {sorted(unknown_kinds)}"
        )
    if established_features:
        missing_established = sorted(set(established_features) - set(frame.columns))
        if missing_established:
            raise ValueError(
                f"Ordinal candidate frame is missing established features: {missing_established}"
            )
    if stage == "selection":
        folds = list(policy.selection_folds)
    elif stage == "locked":
        folds = [
            type(policy.selection_folds[0])(
                policy.locked_test_train_years, policy.locked_test_year
            )
        ]
    else:
        raise ValueError("Ordinal candidate stage must be selection or locked")
    outputs: list[pd.DataFrame] = []
    for fold in folds:
        train = frame[frame["season"].isin(fold.train_years)]
        validation = frame[frame["season"] == fold.validation_year]
        for target, target_column in TARGET_COLUMNS.items():
            for regime in EARLY_REGIMES:
                train_route = train[train["prediction_regime"] == regime]
                validation_route = validation[
                    validation["prediction_regime"] == regime
                ].copy()
                if train_route.empty or validation_route.empty:
                    continue
                for kind in ("direct_ridge", "direct_catboost"):
                    if kind not in candidate_kinds:
                        continue
                    validation_route[f"{kind}_prediction"] = _fit_predict(
                        train_route,
                        validation_route,
                        features=features,
                        target_column=target_column,
                        kind=kind,
                        random_seed=random_seed,
                    )
                point_predictions: dict[str, dict[str, np.ndarray]] = {}
                for kind in ("direct_ridge", "direct_catboost"):
                    point_kind = f"points_{kind.removeprefix('direct_')}"
                    if point_kind not in candidate_kinds:
                        continue
                    point_predictions[kind] = {}
                    for side, points_column in POINT_TARGETS.items():
                        point_predictions[kind][side] = np.clip(
                            _fit_predict(
                                train_route,
                                validation_route,
                                features=features,
                                target_column=points_column,
                                kind=kind,
                                random_seed=random_seed,
                            ),
                            0,
                            None,
                        )
                    home = point_predictions[kind]["home"]
                    away = point_predictions[kind]["away"]
                    validation_route[f"{point_kind}_prediction"] = (
                        home - away if target == "spread" else home + away
                    )
                validation_route["target"] = target
                validation_route["regime"] = regime
                validation_route["actual"] = validation_route[target_column]
                validation_route["baseline_prediction"] = validation_route[
                    baseline_columns[target]
                ]
                if regime == "game_4" and established_features:
                    established_train = train[
                        train["prediction_regime"] == "established"
                    ]
                    validation_route["established_prediction"] = _fit_predict(
                        established_train,
                        validation_route,
                        features=established_features,
                        target_column=target_column,
                        kind="direct_ridge",
                        random_seed=random_seed,
                    )
                validation_route["training_max_year"] = max(fold.train_years)
                validation_route["candidate_stage"] = stage
                validation_route["feature_variant"] = feature_variant
                validation_route["prior_strengths_json"] = json.dumps(
                    dict(prior_strengths or {}), sort_keys=True
                )
                outputs.append(validation_route)
    if not outputs:
        raise ValueError("No ordinal candidate rows were generated")
    return pd.concat(outputs, ignore_index=True)
