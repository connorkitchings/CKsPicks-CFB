"""Preseason model fitting, evaluation, and early-season blending."""

from __future__ import annotations

from itertools import product
from pathlib import Path
from typing import Any, Mapping, Sequence

import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from cks_picks_cfb.preseason_features import (
    PRESEASON_FEATURES,
    PRIOR_QUALITY_FEATURES,
    SNAPSHOT_SCHEMA_VERSION,
)


def _fit_models(
    train_df: pd.DataFrame, features: Sequence[str], alpha: float
) -> dict[str, Any]:
    bundle: dict[str, Any] = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "features": list(features),
        "models": {},
    }
    for target in ("spread_target", "total_target"):
        rows = train_df.dropna(subset=[target])
        if rows.empty:
            raise ValueError(f"No training rows for {target}")
        model = Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
                ("scaler", StandardScaler()),
                ("ridge", Ridge(alpha=alpha, solver="lsqr")),
            ]
        )
        model.fit(rows[list(features)], rows[target])
        bundle["models"][target] = model
    return bundle


def fit_preseason_models(
    train_df: pd.DataFrame, *, alpha: float = 10.0
) -> dict[str, Any]:
    return _fit_models(train_df, PRESEASON_FEATURES, alpha)


def save_preseason_models(bundle: Mapping[str, Any], path: Path | str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(dict(bundle), path)


def load_preseason_models(path: Path | str) -> dict[str, Any]:
    bundle = joblib.load(path)
    if bundle.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
        raise ValueError("Unsupported preseason model schema")
    return bundle


def predict_preseason(
    bundle: Mapping[str, Any], matchups: pd.DataFrame
) -> tuple[np.ndarray, np.ndarray]:
    features = list(bundle["features"])
    missing = [feature for feature in features if feature not in matchups]
    if missing:
        raise ValueError(f"Preseason matchup schema missing features: {missing}")
    x = matchups[features]

    def predict(model: Pipeline) -> np.ndarray:
        transformed = np.asarray(model[:-1].transform(x), dtype=float)
        ridge = model.named_steps["ridge"]
        with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
            values = transformed @ np.asarray(ridge.coef_, dtype=float) + float(
                ridge.intercept_
            )
        if not np.isfinite(values).all():
            raise ValueError("Preseason model produced non-finite predictions")
        return np.asarray(values, dtype=float)

    return predict(bundle["models"]["spread_target"]), predict(
        bundle["models"]["total_target"]
    )


def evaluate_preseason_predictions(
    df: pd.DataFrame, spread_predictions: np.ndarray, total_predictions: np.ndarray
) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for target, predictions, label in (
        ("spread_target", spread_predictions, "spread"),
        ("total_target", total_predictions, "total"),
    ):
        valid = df[target].notna()
        actual = df.loc[valid].reset_index(drop=True)[target].to_numpy()
        pred = np.asarray(predictions)[valid.to_numpy()]
        metrics[f"{label}_mae"] = float(mean_absolute_error(actual, pred))
        metrics[f"{label}_rmse"] = float(mean_squared_error(actual, pred) ** 0.5)
        metrics[f"{label}_calibration_bias"] = float(np.mean(pred - actual))
    return metrics


def evaluate_preseason_candidate(
    train_df: pd.DataFrame,
    holdout_df: pd.DataFrame,
    shadow_df: pd.DataFrame | None = None,
    *,
    alpha: float = 10.0,
    max_shadow_mae_regression: float = 0.25,
) -> tuple[dict[str, Any], dict[str, Any]]:
    candidate = fit_preseason_models(train_df, alpha=alpha)
    baseline = _fit_models(train_df, PRIOR_QUALITY_FEATURES, alpha)

    def score(frame: pd.DataFrame, bundle: Mapping[str, Any]) -> dict[str, float]:
        return evaluate_preseason_predictions(frame, *predict_preseason(bundle, frame))

    candidate_holdout, baseline_holdout = (
        score(holdout_df, candidate),
        score(holdout_df, baseline),
    )
    holdout_pass = all(
        candidate_holdout[f"{target}_mae"] < baseline_holdout[f"{target}_mae"]
        for target in ("spread", "total")
    )
    result: dict[str, Any] = {
        "candidate_holdout": candidate_holdout,
        "baseline_holdout": baseline_holdout,
        "holdout_pass": holdout_pass,
        "shadow_pass": None,
        "promotion_pass": False,
    }
    if shadow_df is not None:
        candidate_shadow, baseline_shadow = (
            score(shadow_df, candidate),
            score(shadow_df, baseline),
        )
        shadow_pass = all(
            candidate_shadow[f"{target}_mae"]
            <= baseline_shadow[f"{target}_mae"] + max_shadow_mae_regression
            for target in ("spread", "total")
        )
        result.update(
            {
                "candidate_shadow": candidate_shadow,
                "baseline_shadow": baseline_shadow,
                "shadow_pass": shadow_pass,
            }
        )
    result["promotion_pass"] = (
        bool(result["holdout_pass"]) and result["shadow_pass"] is not False
    )
    candidate["validation"] = result
    return candidate, result


def select_blend_weights(
    validation_df: pd.DataFrame,
    *,
    target: str | None = None,
    grid: Sequence[float] = tuple(np.linspace(0.0, 1.0, 21)),
) -> dict[int, float]:
    if target not in {None, "spread", "total"}:
        raise ValueError("target must be 'spread', 'total', or None")
    required = {
        "home_current_season_games",
        "away_current_season_games",
        "spread_target",
        "total_target",
        "preseason_spread",
        "recency_spread",
        "preseason_total",
        "recency_total",
    }
    missing = sorted(required - set(validation_df.columns))
    if missing:
        raise ValueError(f"Blend validation is missing columns: {missing}")
    counts = (
        pd.concat(
            [
                pd.to_numeric(
                    validation_df["home_current_season_games"], errors="coerce"
                ),
                pd.to_numeric(
                    validation_df["away_current_season_games"], errors="coerce"
                ),
            ],
            axis=1,
        )
        .min(axis=1)
        .fillna(0)
        .astype(int)
    )
    rows_by_count = {games: validation_df[counts == games] for games in (1, 2, 3)}
    for games, rows in rows_by_count.items():
        if rows.empty:
            raise ValueError(
                f"Blend validation has no rows with {games} completed games"
            )

    def loss(candidate: tuple[float, float, float]) -> float:
        total = 0.0
        for games, weight in zip((1, 2, 3), candidate, strict=True):
            for selected_target in (target,) if target else ("spread", "total"):
                rows = rows_by_count[games]
                total += mean_absolute_error(
                    rows[f"{selected_target}_target"],
                    weight * rows[f"preseason_{selected_target}"]
                    + (1.0 - weight) * rows[f"recency_{selected_target}"],
                )
        return float(total)

    selected = min(
        (
            candidate
            for candidate in product(grid, repeat=3)
            if candidate[0] >= candidate[1] >= candidate[2]
        ),
        key=loss,
    )
    return {games: float(weight) for games, weight in zip((1, 2, 3), selected)}


def preseason_blend_weight(
    min_current_games: int, weights: Mapping[int, float]
) -> float:
    if min_current_games <= 0:
        return 1.0
    if min_current_games >= 4:
        return 0.0
    return float(weights.get(min_current_games, 0.0))


def blend_early_season_predictions(
    preseason_predictions: np.ndarray,
    recency_predictions: np.ndarray,
    home_games: Sequence[Any],
    away_games: Sequence[Any],
    weights: Mapping[int, float],
) -> np.ndarray:
    result = np.asarray(recency_predictions, dtype=float).copy()
    for index, (home, away) in enumerate(zip(home_games, away_games, strict=True)):
        home_count, away_count = (
            pd.to_numeric(home, errors="coerce"),
            pd.to_numeric(away, errors="coerce"),
        )
        home_count = 0 if pd.isna(home_count) else int(home_count)
        away_count = 0 if pd.isna(away_count) else int(away_count)
        weight = preseason_blend_weight(min(home_count, away_count), weights)
        result[index] = (
            weight * preseason_predictions[index] + (1.0 - weight) * result[index]
        )
    return result
