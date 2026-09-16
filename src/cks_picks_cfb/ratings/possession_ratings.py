"""Chronological, uncertainty-bearing possession ratings for V5-03.

The module is deliberately frame-oriented: runners own I/O while these pure
operations make a cutoff replay and its evidence independently reproducible.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from math import isfinite
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.linear_model import Ridge

from cks_picks_cfb.data.data_first_possession_rating_v1 import (
    DEFINITIONS,
    PRIOR_FAMILIES,
    UPDATERS,
)


class PossessionRatingError(ValueError):
    """Raised for invalid rating observations, chronology, or selection state."""


@dataclass(frozen=True)
class RatingPrior:
    mean: float
    variance: float
    source: str
    source_season: int | None
    fallback_reason: str | None = None


@dataclass(frozen=True)
class RatingState:
    mean: float
    variance: float
    prior_mean: float
    prior_variance: float
    evidence_weight: float
    process_variance: float
    usable_exposure: float
    completed_games: int
    fallback_reason: str | None = None


CONTEXT_BLOCKS: Mapping[str, tuple[str, ...]] = {
    "recruiting_ridge": ("recruiting_current", "recruiting_4yr", "recruiting_trend"),
    "returning_production_ridge": (
        "return_total_ppa",
        "return_passing_ppa",
        "return_rushing_ppa",
        "return_receiving_ppa",
        "return_percent_ppa",
        "return_passing_usage",
        "return_rushing_usage",
    ),
    "continuity_ridge": (
        "coach_tenure_lower_bound",
        "coach_tenure_censored",
        "coach_new",
        "roster_same_team_return_share",
        "roster_same_team_return_qb_count",
    ),
}
CONTEXT_BLOCKS = CONTEXT_BLOCKS | {
    "all_context_ridge": tuple(
        column for values in CONTEXT_BLOCKS.values() for column in values
    )
}


def standardization(
    terminal: pd.DataFrame, *, season: int, definition: str, role: str
) -> tuple[float, float]:
    """Return prior-season team-equal center/scale; never fit validation season."""
    source = terminal[
        (terminal["season"] < season)
        & terminal["measurement_id"].eq(definition)
        & terminal["unit_role"].eq(role)
    ]
    if source.empty:
        return 0.0, 1.0 if definition == "ppp" else 1.5
    prior_season = int(source["season"].max())
    values = pd.to_numeric(
        source[source["season"].eq(prior_season)]["adjusted_value"], errors="coerce"
    ).dropna()
    floor = 0.30 if definition == "ppp" else 0.50
    fallback = 1.00 if definition == "ppp" else 1.50
    if values.empty:
        return 0.0, fallback
    scale = max(float(values.std(ddof=0)), floor)
    return float(values.mean()), scale if isfinite(scale) and scale > 0 else fallback


def carryover_prior(previous: RatingPrior | None, *, gap: int) -> RatingPrior:
    if previous is None:
        return RatingPrior(0.0, 1.0, "neutral", None, "no_predecessor")
    decay = 0.60**gap
    return RatingPrior(
        decay * previous.mean,
        decay**2 * previous.variance + 1 - decay**2,
        "rho_0_60",
        previous.source_season,
    )


def analytic_update(
    prior: RatingPrior, observation: float | None, exposure: float, *, k: float
) -> RatingState:
    if prior.variance <= 0 or k <= 0 or exposure < 0:
        raise PossessionRatingError("analytic update has invalid precision inputs")
    if observation is None or not isfinite(observation) or exposure == 0:
        return RatingState(
            prior.mean,
            prior.variance,
            prior.mean,
            prior.variance,
            0.0,
            0.0,
            0.0,
            0,
            prior.fallback_reason,
        )
    information = exposure / k
    variance = 1.0 / (1.0 / prior.variance + information)
    mean = variance * (prior.mean / prior.variance + information * observation)
    weight = information / (1.0 / prior.variance + information)
    return RatingState(
        mean,
        variance,
        prior.mean,
        prior.variance,
        weight,
        0.0,
        exposure,
        0,
        prior.fallback_reason,
    )


def recency_observation(
    history: pd.DataFrame, *, half_life: int | None
) -> tuple[float | None, float]:
    """Weight numerator and denominator jointly; no effective-n approximation."""
    usable = history.dropna(subset=["adjusted_z", "usable_exposure"]).copy()
    usable = usable[pd.to_numeric(usable["usable_exposure"], errors="coerce") > 0]
    if usable.empty:
        return None, 0.0
    if half_life is None:
        weights = np.ones(len(usable))
    else:
        age = np.arange(len(usable) - 1, -1, -1, dtype=float)
        weights = np.power(0.5, age / half_life)
    exposure = usable["usable_exposure"].to_numpy(float) * weights
    total = float(exposure.sum())
    return float(np.dot(usable["adjusted_z"].to_numpy(float), exposure) / total), total


def kalman_step(
    state: RatingState,
    *,
    observation: float | None,
    exposure: float,
    elapsed_days: float,
    q: float,
    r: float,
) -> RatingState:
    if not (0 <= q <= 1 and 1e-6 <= r <= 100 and elapsed_days >= 0 and exposure >= 0):
        raise PossessionRatingError("Kalman inputs escape contract bounds")
    prior_variance = state.variance + q * elapsed_days / 7.0
    if observation is None or not isfinite(observation) or exposure == 0:
        return RatingState(
            state.mean,
            prior_variance,
            state.prior_mean,
            state.prior_variance,
            0.0,
            prior_variance - state.variance,
            0.0,
            state.completed_games,
            state.fallback_reason,
        )
    measurement_variance = r / exposure
    gain = prior_variance / (prior_variance + measurement_variance)
    return RatingState(
        state.mean + gain * (observation - state.mean),
        (1 - gain) * prior_variance,
        state.prior_mean,
        state.prior_variance,
        gain,
        prior_variance - state.variance,
        exposure,
        state.completed_games + 1,
        state.fallback_reason,
    )


def fit_kalman_noise(
    observations: Iterable[tuple[float, float, float]], *, minimum_observations: int = 8
) -> tuple[float, float, float, bool]:
    """Fit q/r only on supplied earlier-season innovations with deterministic starts."""
    rows = [
        (float(z), float(n), float(days))
        for z, n, days in observations
        if n > 0 and days >= 0 and isfinite(z)
    ]
    if len(rows) < minimum_observations:
        return 0.0, 1.0, float("nan"), False

    def objective(values: np.ndarray) -> float:
        q, r = values
        mean, variance, total = 0.0, 1.0, 0.0
        for z, n, days in rows:
            predicted = variance + q * days / 7.0
            residual_variance = predicted + r / n
            total += 0.5 * (
                np.log(residual_variance) + (z - mean) ** 2 / residual_variance
            )
            gain = predicted / residual_variance
            mean, variance = mean + gain * (z - mean), (1 - gain) * predicted
        return float(total)

    fits = [
        minimize(
            objective,
            start,
            method="L-BFGS-B",
            bounds=((0, 1), (1e-6, 100)),
            options={"maxiter": 1000, "ftol": 1e-9},
        )
        for start in ((0.0, 1.0), (0.01, 1.0), (0.1, 1.0))
    ]
    valid = [fit for fit in fits if bool(fit.success) and isfinite(float(fit.fun))]
    if not valid:
        return 0.0, 1.0, float("nan"), False
    best = min(valid, key=lambda fit: (float(fit.fun), tuple(float(x) for x in fit.x)))
    return float(best.x[0]), float(best.x[1]), float(best.fun), True


def learned_prior(
    *,
    family: str,
    carryover: RatingPrior,
    training: pd.DataFrame,
    context: pd.DataFrame | None,
    target_season: int,
    team: str,
    role: str,
) -> RatingPrior:
    """Chronologically fit residual Ridge; incomplete context uses carryover unchanged."""
    if family == "neutral":
        return RatingPrior(0.0, 1.0, "neutral", None)
    if family == "rho_0_60":
        return carryover
    if family not in PRIOR_FAMILIES:
        raise PossessionRatingError("unknown prior family")
    if context is None:
        return RatingPrior(
            carryover.mean,
            carryover.variance,
            carryover.source,
            carryover.source_season,
            "context_unavailable",
        )
    columns = CONTEXT_BLOCKS[family]
    context_row = context[
        (context["season"].eq(target_season)) & context["team"].eq(team)
    ]
    if len(context_row) != 1 or context_row.loc[:, list(columns)].isna().any(axis=None):
        return RatingPrior(
            carryover.mean,
            carryover.variance,
            carryover.source,
            carryover.source_season,
            "context_missing_or_ambiguous",
        )
    fitted = training[
        (training["season"] < target_season) & training["unit_role"].eq(role)
    ].merge(context[["season", "team", *columns]], on=["season", "team"], how="inner")
    fitted = fitted.dropna(subset=["terminal_z", "carryover_mean", *columns])
    if fitted["season"].nunique() < 2:
        return RatingPrior(
            carryover.mean,
            carryover.variance,
            carryover.source,
            carryover.source_season,
            "insufficient_prior_history",
        )
    feature_columns = [
        column for column in columns if fitted[column].nunique(dropna=True) > 1
    ]
    if not feature_columns:
        return RatingPrior(
            carryover.mean,
            carryover.variance,
            carryover.source,
            carryover.source_season,
            "constant_context",
        )
    # Earlier-season leave-one-season-out alpha choice. Larger alpha wins within 0.5%.
    candidates: list[tuple[float, float]] = []
    for alpha in (0.1, 1.0, 10.0, 100.0):
        errors = []
        for season in sorted(fitted["season"].unique())[1:]:
            train = fitted[fitted["season"] < season]
            test = fitted[fitted["season"] == season]
            if train["season"].nunique() < 2 or test.empty:
                continue
            model = Ridge(alpha=alpha).fit(
                train[feature_columns], train["terminal_z"] - train["carryover_mean"]
            )
            errors.extend(
                np.abs(
                    model.predict(test[feature_columns])
                    - (test["terminal_z"] - test["carryover_mean"])
                )
            )
        if errors:
            candidates.append((float(np.mean(errors)), alpha))
    if not candidates:
        return RatingPrior(
            carryover.mean,
            carryover.variance,
            carryover.source,
            carryover.source_season,
            "insufficient_inner_fold",
        )
    best_error = min(error for error, _ in candidates)
    alpha = max(value for error, value in candidates if error <= best_error * 1.005)
    model = Ridge(alpha=alpha).fit(
        fitted[feature_columns], fitted["terminal_z"] - fitted["carryover_mean"]
    )
    residuals = (
        fitted["terminal_z"]
        - fitted["carryover_mean"]
        - model.predict(fitted[feature_columns])
    )
    predicted = float(model.predict(context_row[feature_columns])[0])
    return RatingPrior(
        carryover.mean + predicted,
        max(float(np.mean(np.square(residuals))), 1e-6),
        family,
        carryover.source_season,
    )


def replay_states(
    *,
    prior: RatingPrior,
    observations: pd.DataFrame,
    updater: str,
    definition: str,
    cutoff: Any,
) -> RatingState:
    """Replay each prior observation once, strictly before the requested cutoff."""
    if updater not in UPDATERS or definition not in DEFINITIONS:
        raise PossessionRatingError("unsealed updater or definition")
    ordered = observations.copy()
    ordered["kickoff_utc"] = pd.to_datetime(ordered["kickoff_utc"], utc=True)
    cutoff_ts = pd.Timestamp(cutoff)
    ordered = ordered[ordered["kickoff_utc"] < cutoff_ts].sort_values(
        ["kickoff_utc", "game_id"], kind="mergesort"
    )
    k = 8.0 if definition == "ppp" else 20.0
    if updater != "kalman":
        half_life = {
            "exposure": None,
            "half_life_2": 2,
            "half_life_4": 4,
            "half_life_8": 8,
        }[updater]
        z, exposure = recency_observation(ordered, half_life=half_life)
        result = analytic_update(prior, z, exposure, k=k)
        return RatingState(**{**result.__dict__, "completed_games": len(ordered)})
    q, r, _, fitted = fit_kalman_noise(
        (row.adjusted_z, row.usable_exposure, 7.0)
        for row in ordered.itertuples()
        if pd.notna(row.adjusted_z)
    )
    if not fitted:
        fallback = replay_states(
            prior=prior,
            observations=ordered,
            updater="exposure",
            definition=definition,
            cutoff=cutoff_ts,
        )
        return RatingState(
            **{**fallback.__dict__, "fallback_reason": "kalman_cold_start"}
        )
    state = RatingState(
        prior.mean,
        prior.variance,
        prior.mean,
        prior.variance,
        0.0,
        0.0,
        0.0,
        0,
        prior.fallback_reason,
    )
    previous = ordered["kickoff_utc"].iloc[0] if not ordered.empty else cutoff_ts
    for row in ordered.itertuples():
        days = max((row.kickoff_utc - previous).total_seconds() / 86400.0, 0.0)
        state = kalman_step(
            state,
            observation=float(row.adjusted_z) if pd.notna(row.adjusted_z) else None,
            exposure=float(row.usable_exposure)
            if pd.notna(row.usable_exposure)
            else 0.0,
            elapsed_days=days,
            q=q,
            r=r,
        )
        previous = row.kickoff_utc
    return kalman_step(
        state,
        observation=None,
        exposure=0.0,
        elapsed_days=max((cutoff_ts - previous).total_seconds() / 86400.0, 0.0),
        q=q,
        r=r,
    )
