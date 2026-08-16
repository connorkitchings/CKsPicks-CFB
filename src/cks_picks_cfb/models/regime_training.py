"""Temporal candidate generation for the five completed-game regimes."""

from __future__ import annotations

from itertools import product
from typing import Mapping, Sequence

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from cks_picks_cfb.model_bundle import validate_model_feature_allowlist
from cks_picks_cfb.models.training_policy import (
    TrainingPolicy,
    labeled_training_frame,
)

# Football rate/count features should be small. Values outside this envelope
# are malformed upstream values (for example, a sentinel leaking into a rate),
# not meaningful model evidence. Handle them exactly like missing data before
# fold-local imputation so they cannot overflow linear algebra.
MAX_ABS_MODEL_FEATURE = 1_000_000.0


def _model_values(frame: pd.DataFrame, features: Sequence[str]) -> pd.DataFrame:
    values = frame.loc[:, list(features)].replace([np.inf, -np.inf], np.nan).copy()
    numeric = values.select_dtypes(include=[np.number]).columns
    values.loc[:, numeric] = values.loc[:, numeric].mask(
        values.loc[:, numeric].abs() > MAX_ABS_MODEL_FEATURE
    )
    return values

REGIMES = ("preseason", "one_game", "two_games", "three_games", "established")
EARLY_REGIMES = ("one_game", "two_games", "three_games")
TARGET_COLUMNS = {"spread": "spread_target", "total": "total_target"}


def _candidate(kind: str, random_seed: int):
    if kind == "direct_ridge":
        estimator = Ridge(alpha=10.0)
        return Pipeline(
            [
                # Game 1 legitimately has feature columns with no current-season
                # observations in a fold.  Retaining empty columns makes the
                # serialized feature schema stable between train and inference.
                ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
                ("scale", StandardScaler()),
                ("model", estimator),
            ]
        )
    if kind == "direct_catboost":
        return Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
                (
                    "model",
                    CatBoostRegressor(
                        iterations=300,
                        depth=6,
                        learning_rate=0.04,
                        loss_function="MAE",
                        random_seed=random_seed,
                        verbose=False,
                    ),
                ),
            ]
        )
    raise ValueError(f"Unsupported direct candidate: {kind}")


def _fit_predict(
    train: pd.DataFrame,
    validation: pd.DataFrame,
    *,
    features: Sequence[str],
    target_column: str,
    kind: str,
    random_seed: int,
) -> np.ndarray:
    if train.empty or validation.empty:
        raise ValueError(f"No rows available for {kind}/{target_column}")
    model = _candidate(kind, random_seed)
    train_features = _model_values(train, features)
    validation_features = _model_values(validation, features)
    model.fit(train_features, train[target_column])
    prediction = np.asarray(model.predict(validation_features), dtype=float)
    if not np.isfinite(prediction).all():
        raise ValueError(f"{kind}/{target_column} produced non-finite predictions")
    return prediction


def fit_candidate_model(
    frame: pd.DataFrame,
    *,
    features: Sequence[str],
    target_column: str,
    kind: str,
    random_seed: int = 42,
):
    """Fit a serializable production candidate on an already-frozen design."""
    if frame.empty:
        raise ValueError(f"No production refit rows for {kind}/{target_column}")
    validate_model_feature_allowlist(tuple(features))
    model = _candidate(kind, random_seed)
    values = _model_values(frame, features)
    model.fit(values, frame[target_column])
    return model


def select_monotone_blend_weights(
    selection: pd.DataFrame,
    *,
    target: str,
    grid: Sequence[float] = tuple(np.linspace(0.0, 1.0, 21)),
) -> dict[int, float]:
    """Select target-specific weights from selection OOF rows only."""
    if set(selection["season"].astype(int)) - {2022, 2023, 2024}:
        raise ValueError("Blend weights may only use 2022-2024 selection OOF rows")
    actual_column = TARGET_COLUMNS[target]
    required = {
        "prediction_regime",
        actual_column,
        "preseason_component_prediction",
        "current_component_prediction",
    }
    missing = sorted(required - set(selection.columns))
    if missing:
        raise ValueError(f"Blend selection is missing columns: {missing}")
    rows = {
        games: selection[selection["prediction_regime"] == regime]
        for games, regime in enumerate(EARLY_REGIMES, start=1)
    }
    if any(frame.empty for frame in rows.values()):
        raise ValueError("Blend selection requires rows for 1, 2, and 3 games")

    def loss(candidate: tuple[float, float, float]) -> float:
        errors = []
        for games, weight in zip((1, 2, 3), candidate, strict=True):
            frame = rows[games]
            prediction = (
                weight * frame["preseason_component_prediction"]
                + (1.0 - weight) * frame["current_component_prediction"]
            )
            errors.extend((prediction - frame[actual_column]).abs().tolist())
        return float(np.mean(errors))

    candidates = (
        values
        for values in product(grid, repeat=3)
        if values[0] >= values[1] >= values[2]
    )
    selected = min(candidates, key=loss)
    return {
        0: 1.0,
        1: float(selected[0]),
        2: float(selected[1]),
        3: float(selected[2]),
        4: 0.0,
    }


def generate_temporal_candidate_predictions(
    frame: pd.DataFrame,
    *,
    policy: TrainingPolicy,
    prior_features: Sequence[str],
    current_features: Sequence[str],
    baseline_columns: Mapping[str, str],
    market_line_columns: Mapping[str, str],
    random_seed: int = 42,
) -> tuple[pd.DataFrame, dict[str, dict[int, float]]]:
    """Generate selection OOF plus locked-2025 candidate predictions.

    The returned frame is long by target and is the sole accepted input to the
    regime evaluator. Production refitting happens only after that report is frozen.
    """
    frame = labeled_training_frame(frame, policy)
    for features in (prior_features, current_features):
        validate_model_feature_allowlist(tuple(features))
    required = {
        "season",
        "game_id",
        "prediction_regime",
        "home_completed_games",
        "away_completed_games",
        *TARGET_COLUMNS.values(),
        *prior_features,
        *current_features,
        *baseline_columns.values(),
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Regime feature dataset is missing columns: {missing}")
    hybrid_features = tuple(dict.fromkeys([*prior_features, *current_features]))
    folds = [
        *policy.selection_folds,
        type(policy.selection_folds[0])(
            policy.locked_test_train_years, policy.locked_test_year
        ),
    ]
    outputs: list[pd.DataFrame] = []
    for fold in folds:
        train = frame[frame["season"].isin(fold.train_years)].copy()
        validation = frame[frame["season"] == fold.validation_year].copy()
        if validation.empty:
            raise ValueError(f"No validation rows for {fold.validation_year}")
        for target, target_column in TARGET_COLUMNS.items():
            prior_prediction = _fit_predict(
                train,
                validation,
                features=prior_features,
                target_column=target_column,
                kind="direct_ridge",
                random_seed=random_seed,
            )
            established_train = train[train["prediction_regime"] == "established"]
            current_prediction = _fit_predict(
                established_train,
                validation,
                features=current_features,
                target_column=target_column,
                kind="direct_ridge",
                random_seed=random_seed,
            )
            for regime in REGIMES:
                valid_regime = validation[
                    validation["prediction_regime"] == regime
                ].copy()
                train_regime = train[train["prediction_regime"] == regime]
                if valid_regime.empty:
                    continue
                features = (
                    prior_features
                    if regime == "preseason"
                    else current_features
                    if regime == "established"
                    else hybrid_features
                )
                for kind in ("direct_ridge", "direct_catboost"):
                    valid_regime[f"{kind}_prediction"] = _fit_predict(
                        train_regime,
                        valid_regime,
                        features=features,
                        target_column=target_column,
                        kind=kind,
                        random_seed=random_seed,
                    )
                indexes = validation.index.get_indexer(valid_regime.index)
                valid_regime["preseason_component_prediction"] = prior_prediction[
                    indexes
                ]
                valid_regime["current_component_prediction"] = current_prediction[
                    indexes
                ]
                valid_regime["target"] = target
                valid_regime["regime"] = regime
                valid_regime["actual"] = valid_regime[target_column]
                valid_regime["baseline_prediction"] = valid_regime[
                    baseline_columns[target]
                ]
                market_column = market_line_columns[target]
                valid_regime["market_line"] = (
                    valid_regime[market_column]
                    if market_column in valid_regime
                    else np.nan
                )
                valid_regime["training_max_year"] = max(fold.train_years)
                outputs.append(valid_regime)
    predictions = pd.concat(outputs, ignore_index=True)
    weights: dict[str, dict[int, float]] = {}
    predictions["blend_prediction"] = np.nan
    for target in TARGET_COLUMNS:
        selection = predictions[
            (predictions["target"] == target)
            & (predictions["season"].isin([2022, 2023, 2024]))
        ]
        weights[target] = select_monotone_blend_weights(selection, target=target)
        for games, regime in enumerate(EARLY_REGIMES, start=1):
            mask = (predictions["target"] == target) & (
                predictions["prediction_regime"] == regime
            )
            weight = weights[target][games]
            predictions.loc[mask, "blend_prediction"] = (
                weight * predictions.loc[mask, "preseason_component_prediction"]
                + (1.0 - weight) * predictions.loc[mask, "current_component_prediction"]
            )
    return predictions, weights
