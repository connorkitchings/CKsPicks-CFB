"""Deterministic Phase 4A EPA-only team-rating tournament."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

from cks_picks_cfb.data.data_first_phase2 import DEVELOPMENT_SEASONS, FORBIDDEN_SEASONS
from cks_picks_cfb.data.data_first_phase4a import (
    ATTRIBUTION_COLUMNS,
    PREDICTION_COLUMNS,
    RATING_CANDIDATES,
    RATING_STATE_COLUMNS,
    TEAM_STATE_COLUMNS,
    Phase4AError,
    candidate_parts,
    select_rating,
)

VALIDATION_SEASONS = (2018, 2019, 2021, 2022, 2023, 2024, 2025)
FEATURES = ("home_offense", "home_defense", "away_offense", "away_defense")


@dataclass(frozen=True)
class Phase4AComputation:
    rating_states: pd.DataFrame
    team_states: pd.DataFrame
    predictions: pd.DataFrame
    attribution: pd.DataFrame
    retained_rating: dict[str, Any]


def _num(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame[column], errors="coerce")


def analytic_posterior(
    prior_mean: float,
    prior_variance: float,
    observed_z: float | None,
    exposure: float,
    *,
    equivalent_exposure: float = 100.0,
) -> tuple[float, float, float, float]:
    """Return posterior mean/variance and the two precisions used to obtain it."""
    if prior_variance <= 0 or equivalent_exposure <= 0 or exposure < 0:
        raise Phase4AError("analytic posterior received invalid variance or exposure")
    prior_precision = 1.0 / prior_variance
    observed_precision = (
        exposure / equivalent_exposure if observed_z is not None else 0.0
    )
    total = prior_precision + observed_precision
    return (
        (prior_precision * prior_mean + observed_precision * (observed_z or 0.0))
        / total,
        1.0 / total,
        prior_precision,
        observed_precision,
    )


def _scales(terminal: pd.DataFrame, season: int) -> dict[str, tuple[float, float]]:
    result: dict[str, tuple[float, float]] = {}
    for role in ("offense", "defense"):
        values = _num(
            terminal[(terminal["season"] < season) & terminal["unit_role"].eq(role)],
            "adjusted_value",
        ).dropna()
        if len(values) >= 2:
            result[role] = (float(values.mean()), max(float(values.std(ddof=1)), 0.05))
        else:
            result[role] = (0.0, 0.15)
    return result


def build_rating_states(
    *,
    adjusted: pd.DataFrame,
    terminal: pd.DataFrame,
    candidate: str,
    identity_sha: str,
    code_sha: str,
    config_sha: str,
) -> pd.DataFrame:
    """Build chronological offense/defense posteriors for one candidate.

    ``adjusted`` must contain only Phase 3 EPA-only iteration-four rows for the
    candidate's updater.  Defense is sign-reversed so larger values always mean
    better football quality.
    """
    prior_family, _ = candidate_parts(candidate)
    current = adjusted.copy()
    current = current[
        current["measurement_id"].eq("epa_per_play")
        & current["adjustment_iteration"].eq(4)
        & current["unit_role"].isin(["offense", "defense"])
    ].copy()
    if current["season"].isin(FORBIDDEN_SEASONS).any():
        raise Phase4AError("Phase 4A adjusted measurements include 2020")
    terminal = terminal[
        terminal["measurement_id"].eq("epa_per_play")
        & terminal["unit_role"].isin(["offense", "defense"])
    ].copy()
    terminal_states: dict[int, dict[tuple[str, str], tuple[float, float]]] = {}
    records: list[dict[str, Any]] = []
    for season in DEVELOPMENT_SEASONS:
        scales = _scales(terminal, season)
        prior_seasons = [value for value in DEVELOPMENT_SEASONS if value < season]
        source_season = prior_seasons[-1] if prior_seasons else None
        source = terminal_states.get(source_season, {}) if source_season else {}
        decay_steps = season - source_season if source_season else 0
        for row in current[current["season"].eq(season)].itertuples(index=False):
            key = (str(row.team), str(row.unit_role))
            prior = source.get(key)
            if prior_family == "neutral" or prior is None:
                prior_mean, prior_variance = 0.0, 1.0
                prior_source, prior_source_season = "neutral", None
                steps = 0
            else:
                decay = 0.60**decay_steps
                prior_mean = decay * prior[0]
                prior_variance = decay**2 * prior[1] + (1 - decay**2)
                prior_source, prior_source_season, steps = (
                    "fixed_rho",
                    source_season,
                    decay_steps,
                )
            center, scale = scales[str(row.unit_role)]
            native = pd.to_numeric(
                pd.Series([row.adjusted_value]), errors="coerce"
            ).iloc[0]
            observed = None if pd.isna(native) else float((native - center) / scale)
            if str(row.unit_role) == "defense" and observed is not None:
                observed *= -1
            exposure = float(row.primary_exposure) if observed is not None else 0.0
            mean, variance, prior_precision, observed_precision = analytic_posterior(
                prior_mean, prior_variance, observed, exposure
            )
            records.append(
                {
                    "candidate": candidate,
                    "season": int(season),
                    "week": int(row.week),
                    "game_id": int(row.as_of_game_id),
                    "kickoff_utc": str(row.as_of_kickoff_utc),
                    "team": str(row.team),
                    "unit_role": str(row.unit_role),
                    "prior_source": prior_source,
                    "prior_source_season": prior_source_season,
                    "annual_decay_steps": steps,
                    "standardization_center": center,
                    "standardization_scale": scale,
                    "observed_adjusted_value": native,
                    "observed_z": observed,
                    "effective_exposure": exposure,
                    "completed_games": int(row.games_exposure),
                    "prior_mean": prior_mean,
                    "prior_variance": prior_variance,
                    "prior_precision": prior_precision,
                    "observed_precision": observed_precision,
                    "posterior_mean": mean,
                    "posterior_variance": variance,
                    "posterior_sd": float(np.sqrt(variance)),
                    "movement": mean - prior_mean,
                    "fallback_used": observed is None,
                    "fallback_reason": "no_prior_week_evidence"
                    if observed is None
                    else None,
                    "fallback_cohort": None,
                    "parent_identity_sha": identity_sha,
                    "code_sha": code_sha,
                    "config_sha": config_sha,
                }
            )
        next_states: dict[tuple[str, str], tuple[float, float]] = {}
        for row in terminal[terminal["season"].eq(season)].itertuples(index=False):
            key = (str(row.team), str(row.unit_role))
            prior = source.get(key)
            if prior_family == "neutral" or prior is None:
                prior_mean, prior_variance = 0.0, 1.0
            else:
                decay = 0.60**decay_steps
                prior_mean = decay * prior[0]
                prior_variance = decay**2 * prior[1] + (1 - decay**2)
            center, scale = scales[str(row.unit_role)]
            observed = (float(row.adjusted_value) - center) / scale
            if str(row.unit_role) == "defense":
                observed *= -1
            next_states[key] = analytic_posterior(
                prior_mean, prior_variance, observed, float(row.primary_exposure)
            )[:2]
        terminal_states[season] = next_states
    return pd.DataFrame.from_records(records, columns=RATING_STATE_COLUMNS)


def build_team_states(states: pd.DataFrame) -> pd.DataFrame:
    """Expose a wide, pregame team state with propagated overall uncertainty."""
    index = ["candidate", "season", "week", "game_id", "kickoff_utc", "team"]
    pivot = states.pivot(
        index=index,
        columns="unit_role",
        values=["posterior_mean", "posterior_sd", "fallback_used"],
    )
    pivot.columns = [f"{metric}_{role}" for metric, role in pivot.columns]
    output = pivot.reset_index().rename(
        columns={
            "posterior_mean_offense": "offense_rating",
            "posterior_sd_offense": "offense_sd",
            "posterior_mean_defense": "defense_rating",
            "posterior_sd_defense": "defense_sd",
            "fallback_used_offense": "offense_fallback",
            "fallback_used_defense": "defense_fallback",
        }
    )
    if output[["offense_rating", "defense_rating"]].isna().any().any():
        raise Phase4AError("rating state lacks an offense or defense row")
    offense_rating = pd.to_numeric(output["offense_rating"], errors="raise")
    defense_rating = pd.to_numeric(output["defense_rating"], errors="raise")
    offense_sd = pd.to_numeric(output["offense_sd"], errors="raise")
    defense_sd = pd.to_numeric(output["defense_sd"], errors="raise")
    output["overall_rating"] = (offense_rating + defense_rating) / 2
    output["overall_sd"] = (
        np.sqrt(
            offense_sd.to_numpy(dtype=float) ** 2
            + defense_sd.to_numpy(dtype=float) ** 2
        )
        / 2
    )
    source = (
        states.groupby(index, sort=False)[
            ["parent_identity_sha", "code_sha", "config_sha"]
        ]
        .first()
        .reset_index()
    )
    output = output.merge(source, on=index, validate="one_to_one")
    return (
        output.loc[:, TEAM_STATE_COLUMNS]
        .sort_values(index, kind="mergesort")
        .reset_index(drop=True)
    )


def fcs_partial_pool(
    history: pd.DataFrame, *, rating_column: str, sd_column: str, cutoff: str
) -> tuple[float, float, str]:
    """Return a strictly preceding named-FCS cohort fallback.

    A named FCS team with no own state is never silently imputed with an FBS
    value.  The cohort is shrunk to the same neutral prior used by every other
    first-game state and retains the maximum cohort uncertainty.
    """
    values = history[
        history["classification"].eq("fcs")
        & (pd.to_datetime(history["kickoff_utc"], utc=True) < pd.Timestamp(cutoff))
    ]
    means = _num(values, rating_column).replace([np.inf, -np.inf], np.nan).dropna()
    if means.empty:
        return 0.0, 1.0, "neutral_no_preceding_fcs_cohort"
    mean, variance, _, _ = analytic_posterior(
        0.0, 1.0, float(means.mean()), float(len(means) * 100)
    )
    max_sd = max(float(np.sqrt(variance)), float(_num(values, sd_column).max()))
    return mean, max_sd, "preceding_fcs_partial_pool"


def _game_features(
    team_states: pd.DataFrame, games: pd.DataFrame, candidate: str
) -> pd.DataFrame:
    columns = ["season", "week", "game_id", "kickoff_utc", "home_team", "away_team"]
    classification_available = {"home_classification", "away_classification"}.issubset(
        games.columns
    )
    if classification_available:
        columns.extend(["home_classification", "away_classification"])
    schedule = games[columns].drop_duplicates(["season", "game_id"])
    values = team_states[team_states["candidate"].eq(candidate)].copy()
    class_rows: list[pd.DataFrame] = []
    if classification_available:
        for side in ("home", "away"):
            class_rows.append(
                schedule[
                    ["season", "game_id", f"{side}_team", f"{side}_classification"]
                ].rename(
                    columns={
                        f"{side}_team": "team",
                        f"{side}_classification": "classification",
                    }
                )
            )
        classes = pd.concat(class_rows, ignore_index=True).drop_duplicates(
            ["season", "game_id", "team"]
        )
        values = values.merge(
            classes, on=["season", "game_id", "team"], how="left", validate="one_to_one"
        )
    else:
        values["classification"] = "fbs"
    result = schedule.copy()
    for side in ("home", "away"):
        subset = values[
            [
                "season",
                "game_id",
                "team",
                "offense_rating",
                "defense_rating",
                "offense_sd",
                "defense_sd",
            ]
        ].rename(
            columns={
                "team": f"{side}_join",
                "offense_rating": f"{side}_offense",
                "defense_rating": f"{side}_defense",
                "offense_sd": f"{side}_offense_sd",
                "defense_sd": f"{side}_defense_sd",
            }
        )
        result = result.merge(
            subset,
            left_on=["season", "game_id", f"{side}_team"],
            right_on=["season", "game_id", f"{side}_join"],
            how="left",
            validate="one_to_one",
        ).drop(columns=[f"{side}_join"])
        if classification_available:
            classification = f"{side}_classification"
            for role in ("offense", "defense"):
                missing = result[f"{side}_{role}"].isna()
                for index in result.index[
                    missing
                    & result[classification].astype(str).str.casefold().eq("fcs")
                ]:
                    mean, sd, _ = fcs_partial_pool(
                        values,
                        rating_column=f"{role}_rating",
                        sd_column=f"{role}_sd",
                        cutoff=str(result.at[index, "kickoff_utc"]),
                    )
                    result.at[index, f"{side}_{role}"] = mean
                    result.at[index, f"{side}_{role}_sd"] = sd
                unresolved = result[f"{side}_{role}"].isna()
                if unresolved.any():
                    raise Phase4AError("missing non-FCS pregame rating state")
    result["candidate"] = candidate
    return result


def _standardize(
    train: pd.DataFrame, validate: pd.DataFrame
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    centers: dict[str, float] = {}
    scales: dict[str, float] = {}
    train_out, validate_out = train.copy(), validate.copy()
    fallback = pd.Series(False, index=validate.index)
    for feature in FEATURES:
        values = _num(train_out, feature).replace([np.inf, -np.inf], np.nan).dropna()
        if values.empty:
            raise Phase4AError(f"fold has no training evidence for {feature}")
        centers[feature] = float(values.mean())
        scales[feature] = max(float(values.std(ddof=0)), 1e-8)
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
    return (
        train_out.loc[:, FEATURES].to_numpy(),
        validate_out.loc[:, FEATURES].to_numpy(),
        {"center": centers, "scale": scales, "fallback": fallback},
    )


def run_rating_tournament(
    team_states: pd.DataFrame,
    games: pd.DataFrame,
    outcomes: pd.DataFrame,
    *,
    ridge_alpha: float = 10,
) -> pd.DataFrame:
    """Fit strictly preceding-season Ridge heads for every fixed rating candidate."""
    outcome = outcomes[["season", "game_id", "home_points", "away_points"]].copy()
    outcome["margin"] = _num(outcome, "home_points") - _num(outcome, "away_points")
    outcome["total"] = _num(outcome, "home_points") + _num(outcome, "away_points")
    records: list[dict[str, Any]] = []
    expected: set[tuple[int, int, str]] | None = None
    for candidate in RATING_CANDIDATES:
        frame = _game_features(team_states, games, candidate).merge(
            outcome[["season", "game_id", "margin", "total"]],
            on=["season", "game_id"],
            validate="one_to_one",
        )
        if frame["season"].isin(FORBIDDEN_SEASONS).any():
            raise Phase4AError("tournament includes 2020")
        candidate_keys: set[tuple[int, int, str]] = set()
        for season in VALIDATION_SEASONS:
            train = frame[frame["season"] < season]
            validate = frame[frame["season"].eq(season)]
            if train.empty or validate.empty:
                raise Phase4AError(
                    f"empty temporal fold for validation season {season}"
                )
            x_train, x_validate, meta = _standardize(train, validate)
            training_seasons = sorted(set(train["season"].astype(int)))
            for target in ("margin", "total"):
                model = Ridge(alpha=ridge_alpha).fit(
                    x_train, _num(train, target).to_numpy()
                )
                predicted = model.predict(x_validate)
                for pos, row in enumerate(validate.itertuples(index=False)):
                    records.append(
                        {
                            "candidate": candidate,
                            "season": season,
                            "week": int(row.week),
                            "game_id": int(row.game_id),
                            "kickoff_utc": str(row.kickoff_utc),
                            "target": target,
                            "actual": float(getattr(row, target)),
                            "prediction": float(predicted[pos]),
                            "absolute_error": abs(
                                float(getattr(row, target)) - float(predicted[pos])
                            ),
                            "fold_id": f"validate-{season}",
                            "training_seasons": json.dumps(training_seasons),
                            "feature_names": json.dumps(FEATURES),
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
        if expected is None:
            expected = candidate_keys
        elif expected != candidate_keys:
            raise Phase4AError("rating candidate population changed")
    return (
        pd.DataFrame.from_records(records, columns=PREDICTION_COLUMNS)
        .sort_values(
            ["candidate", "season", "week", "game_id", "target"], kind="mergesort"
        )
        .reset_index(drop=True)
    )


def evaluate_rating_tournament(predictions: pd.DataFrame) -> pd.DataFrame:
    """Evaluate the fixed reference against every challenger with paired bootstrap."""
    reference = predictions[predictions["candidate"].eq("rho_0_60__exposure")]
    rows: list[dict[str, Any]] = []
    reference_keys = set(
        reference[["season", "game_id", "target"]].itertuples(index=False, name=None)
    )
    reference_mae = float(reference["absolute_error"].mean())
    for candidate in RATING_CANDIDATES:
        current = predictions[predictions["candidate"].eq(candidate)]
        keys = set(
            current[["season", "game_id", "target"]].itertuples(index=False, name=None)
        )
        coverage_equal = keys == reference_keys
        if not coverage_equal:
            raise Phase4AError("rating candidate coverage differs from reference")
        mae = float(current["absolute_error"].mean())
        if candidate == "rho_0_60__exposure":
            mean, lower, upper = 0.0, 0.0, 0.0
        else:
            mean, lower, upper = paired_bootstrap_interval(
                predictions,
                candidate,
                replicates=2000,
                confidence=0.90,
                seed=20260908 + RATING_CANDIDATES.index(candidate),
            )
        season_reference = reference.groupby("season")["absolute_error"].mean()
        season_current = current.groupby("season")["absolute_error"].mean()
        regression = (
            (season_current - season_reference) / season_reference * 100
        ).max()
        prior, updater = candidate_parts(candidate)
        rows.append(
            {
                "candidate": candidate,
                "prior_family": prior,
                "updater": updater,
                "mechanism_count": (0 if prior == "neutral" else 1)
                + (0 if updater == "exposure" else 1),
                "validation_rows": len(current),
                "validation_games": current[["season", "game_id"]]
                .drop_duplicates()
                .shape[0],
                "pooled_mae": mae,
                "reference_mae": reference_mae,
                "improvement_pct": (reference_mae - mae) / reference_mae * 100,
                "bootstrap_mean_improvement": mean,
                "bootstrap_90_lower": lower,
                "bootstrap_90_upper": upper,
                "bootstrap_excludes_zero": bool(lower > 0)
                if candidate != "rho_0_60__exposure"
                else False,
                "coverage_equal": coverage_equal,
                "maximum_seasonal_regression_pct": float(regression),
                "seasonal_gate_passed": bool(regression <= 5),
                "primary_gate_passed": False,
                "selected": False,
            }
        )
    result = pd.DataFrame.from_records(rows, columns=ATTRIBUTION_COLUMNS)
    selected = select_rating(result)
    result["primary_gate_passed"] = (
        (result["candidate"] != "rho_0_60__exposure")
        & (result["improvement_pct"] >= 0.5)
        & result["bootstrap_excludes_zero"]
        & result["coverage_equal"]
        & result["seasonal_gate_passed"]
    )
    result.loc[result["candidate"].eq(selected), "selected"] = True
    return result


def paired_bootstrap_interval(
    predictions: pd.DataFrame,
    candidate: str,
    *,
    replicates: int,
    confidence: float,
    seed: int,
) -> tuple[float, float, float]:
    """Paired season-then-week bootstrap of reference-minus-challenger MAE."""
    if candidate == "rho_0_60__exposure" or replicates <= 0 or not 0 < confidence < 1:
        raise Phase4AError("invalid Phase 4A paired bootstrap request")
    paired = predictions[
        predictions["candidate"].isin(["rho_0_60__exposure", candidate])
    ].pivot_table(
        index=["season", "week", "game_id", "target"],
        columns="candidate",
        values="absolute_error",
        aggfunc="first",
    )
    if paired[["rho_0_60__exposure", candidate]].isna().any().any():
        raise Phase4AError("paired bootstrap population is incomplete")
    paired["improvement"] = paired["rho_0_60__exposure"] - paired[candidate]
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
