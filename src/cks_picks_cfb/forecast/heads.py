"""Chronological bounded Ridge bridge registry for V5-04A."""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.special import ndtr
from sklearn.linear_model import Ridge

from cks_picks_cfb.forecast.horizons import fitting_seasons, paired_bootstrap_lower


class HeadError(ValueError):
    """Raised when a bridge fit cannot preserve the sealed population."""


FEATURES = (
    "home_offense",
    "home_defense",
    "away_offense",
    "away_defense",
    "home_host",
    "venue_unknown",
)

# Sentinel season marking through-development-window final-fit rows. There is
# no held-out validation season for a final fit, and 2026 must never appear as
# a season label; 0 is outside every development/forbidden/outer registry and
# keeps the integer schema contracts intact. The full training window is
# recorded explicitly in each final row's training_seasons.
FINAL_FIT_SEASON = 0


@dataclass(frozen=True)
class HeadComputation:
    predictions: pd.DataFrame
    reporting_predictions: pd.DataFrame
    models: pd.DataFrame
    retained: dict[str, str]


def gaussian_crps(actual: np.ndarray, mean: np.ndarray, variance: float) -> np.ndarray:
    """Analytical Gaussian CRPS used only for head comparison, not calibration."""
    sigma = max(float(variance), 1e-6) ** 0.5
    z = (actual - mean) / sigma
    phi = np.exp(-0.5 * z * z) / np.sqrt(2.0 * np.pi)
    return sigma * (z * (2.0 * ndtr(z) - 1.0) + 2.0 * phi - 1.0 / np.sqrt(np.pi))


def _design(
    train: pd.DataFrame, test: pd.DataFrame, *, floor: float
) -> tuple[np.ndarray, np.ndarray, tuple[str, ...]]:
    center = train.loc[:, FEATURES].mean()
    scale = train.loc[:, FEATURES].std(ddof=0).clip(lower=floor)
    x_train = (train.loc[:, FEATURES] - center) / scale
    x_test = (test.loc[:, FEATURES] - center) / scale
    varying = tuple(
        column for column in FEATURES if x_train[column].nunique(dropna=False) > 1
    )
    if not varying:
        raise HeadError("bridge fit has no varying feature")
    return (
        x_train.loc[:, varying].to_numpy(float),
        x_test.loc[:, varying].to_numpy(float),
        varying,
    )


def _target(frame: pd.DataFrame, target: str) -> pd.Series:
    if target == "margin":
        return frame["actual_margin"] - frame["offset_margin"]
    if target == "total":
        return frame["actual_total"] - frame["offset_total"]
    raise HeadError(f"unknown target: {target}")


def select_inner_alpha(
    frame: pd.DataFrame,
    *,
    target: str,
    seasons: tuple[int, ...],
    alpha_grid: tuple[float, ...],
    floor: float,
) -> tuple[float, bool]:
    """Choose alpha on earlier nested folds; ties within 0.5% use larger alpha."""
    scores: list[tuple[float, float]] = []
    for alpha in alpha_grid:
        errors: list[float] = []
        for season in seasons:
            train = frame[
                frame["season"].isin(
                    tuple(value for value in seasons if value < season)
                )
            ]
            test = frame[frame["season"].eq(season)]
            if train.empty or test.empty:
                continue
            try:
                x_train, x_test, _ = _design(train, test, floor=floor)
            except HeadError:
                continue
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=RuntimeWarning)
                fitted = Ridge(alpha=alpha).fit(x_train, _target(train, target))
                values = fitted.predict(x_test)
            errors.extend(np.abs(values - _target(test, target).to_numpy(float)))
        if errors:
            scores.append((float(np.mean(errors)), float(alpha)))
    if not scores:
        return 10.0, True
    best = min(score for score, _ in scores)
    return max(alpha for score, alpha in scores if score <= best * 1.005), False


def _fit_one(
    train: pd.DataFrame, test: pd.DataFrame, *, target: str, alpha: float, floor: float
) -> tuple[np.ndarray, float]:
    x_train, x_test, _ = _design(train, test, floor=floor)
    y_train = _target(train, target)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=RuntimeWarning)
        model = Ridge(alpha=alpha).fit(x_train, y_train)
        values = model.predict(x_test)
        residual_variance = max(
            float(np.mean(np.square(model.predict(x_train) - y_train))), 1e-6
        )
    return values, residual_variance


def evaluate_heads(
    frame: pd.DataFrame,
    *,
    horizon: str,
    development_seasons: tuple[int, ...],
    outer_seasons: tuple[int, ...],
    alpha_grid: tuple[float, ...],
    floor: float,
    bootstrap_seed: int,
    bootstrap_samples: int,
    reporting_seasons: tuple[int, ...] = (),
) -> HeadComputation:
    """Evaluate alpha-10 and an inner-selected challenger with earlier-only fits.

    Reporting seasons are evaluated with the identical procedure but their rows
    are returned separately; they never enter retention gates, the bootstrap,
    model recipes, or any selection population.
    """
    if set(reporting_seasons) & set(outer_seasons):
        raise HeadError("reporting seasons may not overlap the selection population")
    required = {
        "season",
        "week",
        "game_id",
        "actual_margin",
        "actual_total",
        "offset_margin",
        "offset_total",
        *FEATURES,
        "completed_game_stage",
    }
    if missing := sorted(required - set(frame)):
        raise HeadError(f"forecast frame lacks columns: {missing}")
    clean = (
        frame.replace([np.inf, -np.inf], np.nan).dropna(subset=list(required)).copy()
    )
    rows: list[dict[str, object]] = []
    reporting_rows: list[dict[str, object]] = []
    models: list[dict[str, object]] = []
    evaluation_seasons = tuple(outer_seasons) + tuple(reporting_seasons)
    for target in ("margin", "total"):
        for season in evaluation_seasons:
            is_reporting = season in reporting_seasons
            test = clean[clean["season"].eq(season)].copy()
            seasons = fitting_seasons(season, development_seasons, horizon)
            train = clean[clean["season"].isin(seasons)].copy()
            if test.empty or train.empty:
                raise HeadError(
                    f"{horizon}/{target}/{season} lacks scoreable train or test rows"
                )
            selected_alpha, inner_fallback = select_inner_alpha(
                train,
                target=target,
                seasons=seasons,
                alpha_grid=alpha_grid,
                floor=floor,
            )
            for head, alpha in (("reference", 10.0), ("challenger", selected_alpha)):
                try:
                    predicted, variance = _fit_one(
                        train, test, target=target, alpha=alpha, floor=floor
                    )
                except (HeadError, ValueError) as exc:
                    raise HeadError(
                        f"invalid {horizon}/{target}/{season}/{head} bridge"
                    ) from exc
                offset = test[f"offset_{target}"].to_numpy(float)
                actual = test[f"actual_{target}"].to_numpy(float)
                final = predicted + offset
                if not np.isfinite(final).all():
                    raise HeadError("bridge emitted a non-finite forecast")
                crps = gaussian_crps(actual, final, variance)
                for source, value, actual_value, error, score in zip(
                    test.itertuples(index=False),
                    final,
                    actual,
                    np.abs(final - actual),
                    crps,
                    strict=True,
                ):
                    record = {
                        "horizon": horizon,
                        "head": head,
                        "target": target,
                        "season": int(source.season),
                        "week": int(source.week),
                        "game_id": int(source.game_id),
                        "actual": float(actual_value),
                        "prediction": float(value),
                        "absolute_error": float(error),
                        "gaussian_crps": float(score),
                        "offset": float(getattr(source, f"offset_{target}")),
                        "training_seasons": ",".join(map(str, seasons)),
                        "completed_game_stage": int(source.completed_game_stage),
                        "venue_unknown": bool(source.venue_unknown),
                    }
                    (reporting_rows if is_reporting else rows).append(record)
                if not is_reporting:
                    models.append(
                        {
                            "horizon": horizon,
                            "target": target,
                            "outer_season": season,
                            "head": head,
                            "alpha": alpha,
                            "training_seasons": ",".join(map(str, seasons)),
                            "inner_fallback": inner_fallback,
                            "retained": False,
                            "fallback_reason": "insufficient_inner_fold"
                            if inner_fallback
                            else None,
                        }
                    )
    predictions = pd.DataFrame.from_records(rows)
    reporting_predictions = pd.DataFrame.from_records(reporting_rows)
    model_frame = pd.DataFrame.from_records(models)
    retained: dict[str, str] = {}
    for target in ("margin", "total"):
        reference = predictions[
            (predictions["target"].eq(target)) & (predictions["head"].eq("reference"))
        ]
        challenger = predictions[
            (predictions["target"].eq(target)) & (predictions["head"].eq("challenger"))
        ]
        _, lower, _ = paired_bootstrap_lower(
            challenger, reference, seed=bootstrap_seed, samples=bootstrap_samples
        )
        ref_mae, challenger_mae = (
            float(reference.absolute_error.mean()),
            float(challenger.absolute_error.mean()),
        )
        ref_crps, challenger_crps = (
            float(reference.gaussian_crps.mean()),
            float(challenger.gaussian_crps.mean()),
        )
        improvement = 100.0 * (ref_mae - challenger_mae) / ref_mae if ref_mae else 0.0
        regressions_ok = True
        for _, values in pd.concat(
            [reference.assign(kind="reference"), challenger.assign(kind="challenger")]
        ).groupby(["season", "completed_game_stage"], sort=True):
            base, other = (
                values[values.kind.eq("reference")],
                values[values.kind.eq("challenger")],
            )
            if (
                len(base) != len(other)
                or float(other.absolute_error.mean())
                > float(base.absolute_error.mean()) * 1.05
            ):
                regressions_ok = False
        keep = (
            challenger_mae <= ref_mae * 1.01
            and challenger_crps <= ref_crps * 1.01
            and regressions_ok
            and improvement >= 0.5
            and lower > 0
        )
        retained[target] = "challenger" if keep else "reference"
        model_frame.loc[
            (model_frame["target"].eq(target))
            & (model_frame["head"].eq(retained[target])),
            "retained",
        ] = True
    return HeadComputation(
        predictions=predictions,
        reporting_predictions=reporting_predictions,
        models=model_frame,
        retained=retained,
    )


def fit_final(
    frame: pd.DataFrame,
    *,
    target: str,
    head: str,
    development_seasons: tuple[int, ...],
    alpha_grid: tuple[float, ...],
    floor: float,
) -> dict[str, object]:
    """Fit the retained head recipe on the full development window.

    There is no test season and no prediction emitted: the final fit is a
    through-window model recipe for downstream use, recorded as a single
    ``forecast_model`` row with ``outer_season == FINAL_FIT_SEASON``.  Alpha
    follows the head recipe: ``reference`` uses fixed 10.0, ``challenger``
    re-runs inner-alpha selection over the full window.  A proof Ridge fit on
    the training window must succeed (fail closed otherwise); its in-sample
    outputs are discarded and never persisted or calibrated.
    """
    if head not in ("reference", "challenger"):
        raise HeadError(f"final fit has an unknown head: {head!r}")
    if target not in ("margin", "total"):
        raise HeadError(f"final fit has an unknown target: {target!r}")
    required = {
        "season",
        "actual_margin",
        "actual_total",
        "offset_margin",
        "offset_total",
        *FEATURES,
    }
    if missing := sorted(required - set(frame)):
        raise HeadError(f"final-fit frame lacks columns: {missing}")
    if set(development_seasons) & {FINAL_FIT_SEASON}:
        raise HeadError("final-fit training window contains the sentinel season")
    clean = (
        frame.replace([np.inf, -np.inf], np.nan).dropna(subset=list(required)).copy()
    )
    train = clean[clean["season"].isin(tuple(development_seasons))].copy()
    if train.empty:
        raise HeadError("final fit has no training rows on the development window")
    if head == "reference":
        alpha, inner_fallback = 10.0, False
    else:
        alpha, inner_fallback = select_inner_alpha(
            train,
            target=target,
            seasons=tuple(development_seasons),
            alpha_grid=alpha_grid,
            floor=floor,
        )
    try:
        _fit_one(train, train, target=target, alpha=alpha, floor=floor)
    except (HeadError, ValueError) as exc:
        raise HeadError(f"final fit failed on the full window: {target}") from exc
    return {
        "target": target,
        "head": head,
        "alpha": float(alpha),
        "training_seasons": tuple(int(season) for season in development_seasons),
        "inner_fallback": bool(inner_fallback),
    }
