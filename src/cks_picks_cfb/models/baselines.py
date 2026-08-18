"""Strictly temporal baseline component generation."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from cks_picks_cfb.model_bundle import validate_model_feature_allowlist

TARGETS = {"spread": "spread_target", "total": "total_target"}
SELECTION_FOLDS = (
    ((2021,), 2022),
    ((2021, 2022), 2023),
    ((2021, 2022, 2023), 2024),
)


def _model() -> Pipeline:
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            ("ridge", Ridge(alpha=10.0)),
        ]
    )


def _feature_columns(frame: pd.DataFrame, *, prior: bool) -> list[str]:
    prefixes = (
        ("home_prior_", "away_prior_")
        if prior
        else ("home_current_", "away_current_", "home_adj_", "away_adj_")
    )
    columns = [
        column
        for column in frame.columns
        if column.startswith(prefixes) and pd.api.types.is_numeric_dtype(frame[column])
    ]
    if not columns:
        kind = "prior" if prior else "current"
        raise ValueError(f"Structural Gold has no numeric {kind} features")
    validate_model_feature_allowlist(tuple(columns))
    return columns


def generate_baselines(
    frame: pd.DataFrame, *, include_locked_2025: bool
) -> pd.DataFrame:
    """Generate selection OOF components and optionally the guarded 2025 fold."""
    if 2020 in set(frame["season"].astype(int)):
        raise ValueError("2020 is excluded from baseline generation")
    target_columns = [
        column for column in TARGETS.values() if column in frame.columns
    ]
    if target_columns:
        # A labeled-season row without a final result (canceled or unreported
        # game) is not trainable; exclude it exactly like inference-only rows.
        frame = frame.loc[~frame[target_columns].isna().any(axis=1)].copy()
    prior_features = _feature_columns(frame, prior=True)
    current_features = _feature_columns(frame, prior=False)
    folds = list(SELECTION_FOLDS)
    if include_locked_2025:
        folds.append(((2021, 2022, 2023, 2024), 2025))
    outputs = []
    for train_years, validation_year in folds:
        train = frame[frame["season"].astype(int).isin(train_years)]
        validation = frame[frame["season"].astype(int) == validation_year].copy()
        if train.empty or validation.empty:
            raise ValueError(f"Missing rows for baseline fold ending {validation_year}")
        result = validation[["season", "game_id"]].copy()
        result["training_max_year"] = max(train_years)
        for target, target_column in TARGETS.items():
            if target_column not in frame:
                raise ValueError(f"Structural Gold is missing {target_column}")
            prior_model = _model().fit(train[prior_features], train[target_column])
            established = train[train["prediction_regime"] == "established"]
            if established.empty:
                raise ValueError(f"No established training rows for {validation_year}")
            current_model = _model().fit(
                established[current_features], established[target_column]
            )
            prior_prediction = np.asarray(
                prior_model.predict(validation[prior_features]), dtype=float
            )
            current_prediction = np.asarray(
                current_model.predict(validation[current_features]), dtype=float
            )
            result[f"preseason_{target}_prediction"] = prior_prediction
            result[f"current_{target}_prediction"] = current_prediction
            result[f"baseline_{target}_prediction"] = np.where(
                validation["prediction_regime"].eq("established"),
                current_prediction,
                prior_prediction,
            )
        outputs.append(result)
    return pd.concat(outputs, ignore_index=True).sort_values(["season", "game_id"])
