"""Deterministic Phase 4B target-context tournament."""

from __future__ import annotations

import json
import warnings
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

from cks_picks_cfb.data.data_first_phase2 import FORBIDDEN_SEASONS
from cks_picks_cfb.data.data_first_phase4b import (
    ALL_CONTEXT_CANDIDATES,
    CONTEXT_FAMILY_FEATURES,
    NO_CONTEXT_FAMILY,
    TARGETS,
    Phase4BError,
    select_context,
)

VALIDATION_SEASONS = (2018, 2019, 2021, 2022, 2023, 2024, 2025)
RATING_FEATURES = (
    "home_offense",
    "home_defense",
    "away_offense",
    "away_defense",
)

PREDICTION_NUMERIC_COLUMNS = (
    "actual",
    "prediction",
    "absolute_error",
    "ridge_intercept",
)
ATTRIBUTION_NUMERIC_COLUMNS = (
    "feature_count",
    "pooled_mae",
    "baseline_mae",
    "improvement_pct",
    "bootstrap_mean_improvement",
    "bootstrap_90_lower",
    "bootstrap_90_upper",
    "maximum_seasonal_regression_pct",
)


@dataclass(frozen=True)
class Phase4BComputation:
    predictions: pd.DataFrame
    attribution: pd.DataFrame
    coverage: pd.DataFrame
    retained_baseline: dict[str, Any]


def _num(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame[column], errors="coerce")


def _native_float64(values: pd.Series, *, context: str) -> np.ndarray:
    """Materialize nullable pandas numerics as contiguous native floats."""
    try:
        result = np.ascontiguousarray(
            values.to_numpy(dtype=np.float64, na_value=np.nan)
        )
    except (TypeError, ValueError) as exc:
        raise Phase4BError(
            f"could not materialize native float64 values ({context})"
        ) from exc
    return result


def _require_finite_columns(
    frame: pd.DataFrame, columns: tuple[str, ...], *, context: str
) -> None:
    for column in columns:
        values = pd.to_numeric(frame[column], errors="coerce").to_numpy(
            dtype=np.float64
        )
        invalid = ~np.isfinite(values)
        if invalid.any():
            row = frame.iloc[int(np.flatnonzero(invalid)[0])]
            details = ", ".join(
                f"{name}={row[name]}"
                for name in ("family", "target", "season")
                if name in frame.columns
            )
            raise Phase4BError(
                f"{context} contains non-finite {column}"
                + (f" ({details})" if details else "")
            )


def validate_tournament_evidence(
    predictions: pd.DataFrame, attribution: pd.DataFrame | None = None
) -> None:
    """Fail closed before retaining predictions or selection evidence."""
    _require_finite_columns(
        predictions,
        PREDICTION_NUMERIC_COLUMNS,
        context="Phase 4B prediction evidence",
    )
    if attribution is not None:
        _require_finite_columns(
            attribution,
            ATTRIBUTION_NUMERIC_COLUMNS,
            context="Phase 4B attribution evidence",
        )


def _standardize(
    train: pd.DataFrame,
    validate: pd.DataFrame,
    features: tuple[str, ...],
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Fold-local z-score standardization with training-fold mean imputation."""
    centers: dict[str, float] = {}
    scales: dict[str, float] = {}
    train_out, validate_out = train.copy(), validate.copy()
    fallback = pd.Series(False, index=validate.index)
    for feature in features:
        values = _num(train_out, feature).replace([np.inf, -np.inf], np.nan).dropna()
        if values.empty:
            raise Phase4BError(f"fold has no training evidence for {feature}")
        max_abs = float(values.abs().max())
        safe_reduction_bound = np.sqrt(np.finfo(float).max) / max(len(values), 1)
        if max_abs > safe_reduction_bound:
            raise Phase4BError(
                f"fold feature is numerically unstable ({feature}: max_abs={max_abs})"
            )
        centers[feature] = float(values.mean())
        scales[feature] = max(float(values.std(ddof=0)), 0.05)
        if not np.isfinite(centers[feature]) or not np.isfinite(scales[feature]):
            raise Phase4BError(
                f"fold feature is numerically unstable ({feature}: max_abs={max_abs})"
            )
        validate_missing = ~np.isfinite(_num(validate_out, feature))
        fallback |= validate_missing
        for frame in (train_out, validate_out):
            missing = ~np.isfinite(_num(frame, feature))
            frame.loc[missing, feature] = centers[feature]
        train_out[feature] = (_num(train_out, feature) - centers[feature]) / scales[
            feature
        ]
        validate_out[feature] = (
            _num(validate_out, feature) - centers[feature]
        ) / scales[feature]
    x_train = np.ascontiguousarray(
        train_out.loc[:, features].to_numpy(dtype=np.float64)
    )
    x_validate = np.ascontiguousarray(
        validate_out.loc[:, features].to_numpy(dtype=np.float64)
    )
    if not np.isfinite(x_train).all() or not np.isfinite(x_validate).all():
        raise Phase4BError("fold standardization produced non-finite features")
    return (
        x_train,
        x_validate,
        {"center": centers, "scale": scales, "fallback": fallback},
    )


def _fit_predict_ridge(
    *,
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_validate: np.ndarray,
    family: str,
    validation_season: int,
    target: str,
    ridge_alpha: float,
) -> tuple[Ridge, np.ndarray]:
    """Run the fixed Ridge head while treating numerical warnings as fatal."""
    context = f"family={family}, validation_season={validation_season}, target={target}"
    if not (
        x_train.dtype == np.float64
        and x_validate.dtype == np.float64
        and y_train.dtype == np.float64
        and x_train.flags.c_contiguous
        and x_validate.flags.c_contiguous
        and y_train.flags.c_contiguous
        and np.isfinite(x_train).all()
        and np.isfinite(x_validate).all()
        and np.isfinite(y_train).all()
    ):
        raise Phase4BError(f"Ridge received invalid native-float inputs ({context})")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            model = Ridge(alpha=ridge_alpha).fit(x_train, y_train)
    except (RuntimeWarning, FloatingPointError, ValueError) as exc:
        raise Phase4BError(f"Ridge fit numerical failure ({context}): {exc}") from exc
    coefficients = np.ascontiguousarray(model.coef_, dtype=np.float64)
    intercept = float(model.intercept_)
    if not np.isfinite(coefficients).all() or not np.isfinite(intercept):
        raise Phase4BError(
            f"Ridge fit produced non-finite coefficients ({context}): "
            f"coef_max={np.abs(coefficients).max()}, intercept={intercept}"
        )
    coef_max = float(np.abs(coefficients).max())
    if coef_max > 1000.0:
        raise Phase4BError(
            f"Ridge coefficients are numerically explosive ({context}): "
            f"coef_max={coef_max}, intercept={intercept}"
        )
    feature_max = float(np.abs(x_validate).max())
    if feature_max > 100.0:
        raise Phase4BError(
            f"validation features are numerically unstable ({context}): "
            f"feature_max={feature_max}"
        )
    if x_validate.shape[1] != coefficients.shape[0]:
        raise Phase4BError(
            f"shape mismatch ({context}): x_validate.shape={x_validate.shape}, "
            f"coefficients.shape={coefficients.shape}"
        )
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=RuntimeWarning)
        products = np.matmul(x_validate, coefficients)
    if not np.isfinite(products).all():
        non_finite_mask = ~np.isfinite(products)
        sample_vals = products[non_finite_mask][:5] if non_finite_mask.any() else []
        raise Phase4BError(
            f"matmul produced non-finite products ({context}): "
            f"count={non_finite_mask.sum()}, sample={sample_vals.tolist()}"
        )
    predicted = np.ascontiguousarray(products + intercept, dtype=np.float64)
    if (
        not np.isfinite(coefficients).all()
        or not np.isfinite(intercept)
        or not np.isfinite(predicted).all()
    ):
        raise Phase4BError(f"Ridge produced non-finite output ({context})")
    return model, predicted


def _build_game_frame(
    team_states: pd.DataFrame,
    games: pd.DataFrame,
    outcomes: pd.DataFrame,
) -> pd.DataFrame:
    """Build the base game frame with rating features and outcomes."""
    outcome = outcomes[["season", "game_id", "home_points", "away_points"]].copy()
    outcome["margin"] = _num(outcome, "home_points") - _num(outcome, "away_points")
    outcome["total"] = _num(outcome, "home_points") + _num(outcome, "away_points")
    columns = ["season", "week", "game_id", "kickoff_utc", "home_team", "away_team"]
    schedule = games[columns].drop_duplicates(["season", "game_id"])
    values = team_states[team_states["candidate"].eq("rho_0_60__exposure")].copy()
    result = schedule.copy()
    for side in ("home", "away"):
        subset = values[
            [
                "season",
                "game_id",
                "team",
                "offense_rating",
                "defense_rating",
            ]
        ].rename(
            columns={
                "team": f"{side}_join",
                "offense_rating": f"{side}_offense",
                "defense_rating": f"{side}_defense",
            }
        )
        result = result.merge(
            subset,
            left_on=["season", "game_id", f"{side}_team"],
            right_on=["season", "game_id", f"{side}_join"],
            how="left",
            validate="one_to_one",
        ).drop(columns=[f"{side}_join"])
        unresolved = result[[f"{side}_offense", f"{side}_defense"]].isna().any(axis=1)
        if unresolved.any():
            raise Phase4BError("missing non-FCS pregame rating state")
    result = result.merge(
        outcome[["season", "game_id", "margin", "total"]],
        on=["season", "game_id"],
        validate="one_to_one",
    )
    return result


def _add_context_features(
    game_frame: pd.DataFrame,
    context_datasets: dict[str, pd.DataFrame],
    family: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Add context features for one family. Returns (frame, coverage_info)."""
    if family == NO_CONTEXT_FAMILY:
        return game_frame.copy(), pd.DataFrame()
    features = CONTEXT_FAMILY_FEATURES[family]
    result = game_frame.copy()
    coverage_rows: list[dict[str, Any]] = []
    if family in ("field_position", "pace", "turnovers"):
        context = context_datasets[family]
        for side in ("home", "away"):
            side_context = context.copy()
            side_context = side_context.rename(columns={"team": f"{side}_team"})
            for feature in features:
                measurement, role = feature.rsplit("_", 1)
                col_name = f"{side}_{feature}"
                subset = side_context[side_context["unit_role"].eq(role)][
                    ["season", "game_id", f"{side}_team", "raw_value"]
                ].rename(columns={"raw_value": col_name})
                result = result.merge(
                    subset,
                    on=["season", "game_id", f"{side}_team"],
                    how="left",
                    validate="one_to_one",
                )
    elif family == "lagged_rankings":
        context = context_datasets[family]
        for side in ("home", "away"):
            side_context = context.copy()
            side_context = side_context.rename(columns={"team": f"{side}_team"})
            for feature in features:
                col_name = f"{side}_{feature}"
                subset = side_context[
                    ["season", "week", "game_id", f"{side}_team", feature]
                ].rename(columns={feature: col_name})
                result = result.merge(
                    subset,
                    on=["season", "week", "game_id", f"{side}_team"],
                    how="left",
                    validate="one_to_one",
                )
    else:
        context = context_datasets[family]
        for side in ("home", "away"):
            side_context = context.copy()
            side_context = side_context.rename(columns={"team": f"{side}_team"})
            for feature in features:
                col_name = f"{side}_{feature}"
                subset = side_context[["season", f"{side}_team", feature]].rename(
                    columns={feature: col_name}
                )
                result = result.merge(
                    subset,
                    on=["season", f"{side}_team"],
                    how="left",
                    validate="many_to_one",
                )
    return result, pd.DataFrame(coverage_rows)


def run_context_tournament(
    team_states: pd.DataFrame,
    games: pd.DataFrame,
    outcomes: pd.DataFrame,
    context_datasets: dict[str, pd.DataFrame],
    *,
    ridge_alpha: float = 10,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Fit strictly preceding-season Ridge heads for every context family × target."""
    base_frame = _build_game_frame(team_states, games, outcomes)
    if base_frame["season"].isin(FORBIDDEN_SEASONS).any():
        raise Phase4BError("tournament includes 2020")
    records: list[dict[str, Any]] = []
    coverage_records: list[dict[str, Any]] = []
    expected: set[tuple[int, int, str]] | None = None
    for family in ALL_CONTEXT_CANDIDATES:
        frame, _ = _add_context_features(base_frame, context_datasets, family)
        if family == NO_CONTEXT_FAMILY:
            features = RATING_FEATURES
        else:
            context_features = tuple(
                f"{side}_{f}"
                if family in ("field_position", "pace", "turnovers")
                else f"{side}_{f}"
                if family == "lagged_rankings"
                else f"{side}_{f}"
                for side in ("home", "away")
                for f in CONTEXT_FAMILY_FEATURES[family]
            )
            if family == "pace":
                context_features = (f"home_{CONTEXT_FAMILY_FEATURES[family][0]}",)
            features = RATING_FEATURES + context_features
        candidate_keys: set[tuple[int, int, str]] = set()
        for season in VALIDATION_SEASONS:
            train = frame[frame["season"] < season]
            validate = frame[frame["season"].eq(season)]
            if train.empty or validate.empty:
                raise Phase4BError(
                    f"empty temporal fold for validation season {season}"
                )
            x_train, x_validate, meta = _standardize(train, validate, features)
            training_seasons = sorted(set(train["season"].astype(int)))
            imputed_count = int(meta["fallback"].sum())
            for target in TARGETS:
                y_train = _native_float64(
                    _num(train, target),
                    context=(
                        f"family={family}, validation_season={season}, target={target}"
                    ),
                )
                actual = _native_float64(
                    _num(validate, target),
                    context=(
                        f"family={family}, validation_season={season}, target={target}"
                    ),
                )
                model, predicted = _fit_predict_ridge(
                    x_train=x_train,
                    y_train=y_train,
                    x_validate=x_validate,
                    family=family,
                    validation_season=season,
                    target=target,
                    ridge_alpha=ridge_alpha,
                )
                if not np.isfinite(actual).all():
                    raise Phase4BError(
                        f"validation outcome is non-finite "
                        f"(family={family}, validation_season={season}, target={target})"
                    )
                for pos, row in enumerate(validate.itertuples(index=False)):
                    records.append(
                        {
                            "family": family,
                            "target": target,
                            "season": season,
                            "week": int(row.week),
                            "game_id": int(row.game_id),
                            "kickoff_utc": str(row.kickoff_utc),
                            "actual": float(actual[pos]),
                            "prediction": float(predicted[pos]),
                            "absolute_error": abs(
                                float(actual[pos]) - float(predicted[pos])
                            ),
                            "fold_id": f"validate-{season}",
                            "training_seasons": json.dumps(training_seasons),
                            "feature_names": json.dumps(features),
                            "standardization_center": json.dumps(
                                meta["center"], sort_keys=True
                            ),
                            "standardization_scale": json.dumps(
                                meta["scale"], sort_keys=True
                            ),
                            "ridge_coefficients": json.dumps(model.coef_.tolist()),
                            "ridge_intercept": float(model.intercept_),
                            "feature_fallback": bool(meta["fallback"].iloc[pos]),
                            "fallback_count": int(meta["fallback"].iloc[pos]),
                        }
                    )
                    candidate_keys.add((season, int(row.game_id), target))
                coverage_records.append(
                    {
                        "family": family,
                        "target": target,
                        "season": season,
                        "total_rows": len(validate),
                        "complete_rows": len(validate) - imputed_count,
                        "imputed_rows": imputed_count,
                        "coverage_fraction": (len(validate) - imputed_count)
                        / len(validate)
                        if len(validate) > 0
                        else 0.0,
                        "fallback_reason": ""
                        if imputed_count == 0
                        else "training_fold_mean_imputation",
                    }
                )
        if expected is None:
            expected = candidate_keys
        elif expected != candidate_keys:
            raise Phase4BError("context family population changed")
    predictions = (
        pd.DataFrame.from_records(records)
        .sort_values(
            ["family", "target", "season", "week", "game_id"], kind="mergesort"
        )
        .reset_index(drop=True)
    )
    coverage = pd.DataFrame.from_records(coverage_records)
    validate_tournament_evidence(predictions)
    return predictions, coverage


def evaluate_context_tournament(
    predictions: pd.DataFrame,
) -> pd.DataFrame:
    """Evaluate the no-context baseline against every context family with paired bootstrap."""
    validate_tournament_evidence(predictions)
    rows: list[dict[str, Any]] = []
    for target in TARGETS:
        target_predictions = predictions[predictions["target"] == target]
        baseline = target_predictions[target_predictions["family"] == NO_CONTEXT_FAMILY]
        baseline_keys = set(
            baseline[["season", "game_id"]].itertuples(index=False, name=None)
        )
        baseline_mae = float(baseline["absolute_error"].mean())
        for family in ALL_CONTEXT_CANDIDATES:
            current = target_predictions[target_predictions["family"] == family]
            keys = set(
                current[["season", "game_id"]].itertuples(index=False, name=None)
            )
            coverage_equal = keys == baseline_keys
            if not coverage_equal:
                raise Phase4BError("context family coverage differs from baseline")
            mae = float(current["absolute_error"].mean())
            if family == NO_CONTEXT_FAMILY:
                mean, lower, upper = 0.0, 0.0, 0.0
            else:
                mean, lower, upper = paired_bootstrap_interval(
                    target_predictions,
                    family,
                    replicates=2000,
                    confidence=0.90,
                    seed=20260908 + ALL_CONTEXT_CANDIDATES.index(family),
                )
            season_baseline = baseline.groupby("season")["absolute_error"].mean()
            season_current = current.groupby("season")["absolute_error"].mean()
            regression = (
                (season_current - season_baseline) / season_baseline * 100
            ).max()
            feature_count = (
                len(RATING_FEATURES)
                if family == NO_CONTEXT_FAMILY
                else len(RATING_FEATURES) + len(CONTEXT_FAMILY_FEATURES[family])
            )
            rows.append(
                {
                    "target": target,
                    "family": family,
                    "feature_count": feature_count,
                    "validation_rows": len(current),
                    "validation_games": current[["season", "game_id"]]
                    .drop_duplicates()
                    .shape[0],
                    "pooled_mae": mae,
                    "baseline_mae": baseline_mae,
                    "improvement_pct": (baseline_mae - mae) / baseline_mae * 100,
                    "bootstrap_mean_improvement": mean,
                    "bootstrap_90_lower": lower,
                    "bootstrap_90_upper": upper,
                    "bootstrap_excludes_zero": bool(lower > 0)
                    if family != NO_CONTEXT_FAMILY
                    else False,
                    "coverage_equal": coverage_equal,
                    "maximum_seasonal_regression_pct": float(regression),
                    "seasonal_gate_passed": bool(regression <= 5),
                    "primary_gate_passed": False,
                    "selected": False,
                }
            )
    result = pd.DataFrame.from_records(rows)
    for target in TARGETS:
        target_attribution = result[result["target"] == target]
        selected = select_context(target_attribution, target=target)
        result.loc[
            (result["target"] == target) & (result["family"] == selected),
            "selected",
        ] = True
        result.loc[
            (result["target"] == target) & (result["family"] != NO_CONTEXT_FAMILY),
            "primary_gate_passed",
        ] = (
            (result.loc[result["target"] == target, "improvement_pct"] >= 0.5)
            & result.loc[result["target"] == target, "bootstrap_excludes_zero"]
            & result.loc[result["target"] == target, "coverage_equal"]
            & result.loc[result["target"] == target, "seasonal_gate_passed"]
        )
    validate_tournament_evidence(predictions, result)
    return result


def paired_bootstrap_interval(
    predictions: pd.DataFrame,
    family: str,
    *,
    replicates: int,
    confidence: float,
    seed: int,
) -> tuple[float, float, float]:
    """Paired season-then-week bootstrap of baseline-minus-challenger MAE."""
    if family == NO_CONTEXT_FAMILY or replicates <= 0 or not 0 < confidence < 1:
        raise Phase4BError("invalid Phase 4B paired bootstrap request")
    paired = predictions[
        predictions["family"].isin([NO_CONTEXT_FAMILY, family])
    ].pivot_table(
        index=["season", "week", "game_id"],
        columns="family",
        values="absolute_error",
        aggfunc="first",
    )
    if paired[[NO_CONTEXT_FAMILY, family]].isna().any().any():
        raise Phase4BError("paired bootstrap population is incomplete")
    paired["improvement"] = paired[NO_CONTEXT_FAMILY] - paired[family]
    cells = (
        paired.reset_index()
        .groupby(["season", "week"], sort=True)["improvement"]
        .agg(["mean", "count"])
        .reset_index()
    )
    seasons = sorted(cells["season"].astype(int).unique())
    rng = np.random.default_rng(seed)
    draws = np.empty(replicates)
    for index in range(replicates):
        numerator, denominator = 0.0, 0
        for season in rng.choice(seasons, size=len(seasons), replace=True):
            options = cells[cells["season"].eq(season)].reset_index(drop=True)
            sampled = options.iloc[rng.integers(0, len(options), size=len(options))]
            numerator += float((sampled["mean"] * sampled["count"]).sum())
            denominator += int(sampled["count"].sum())
        draws[index] = numerator / denominator
    alpha = (1 - confidence) / 2
    return (
        float(paired["improvement"].mean()),
        float(np.quantile(draws, alpha)),
        float(np.quantile(draws, 1 - alpha)),
    )
