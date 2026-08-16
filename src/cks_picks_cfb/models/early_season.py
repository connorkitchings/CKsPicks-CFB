"""Leakage-safe primitives for the first three scheduled team games."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from itertools import product

import pandas as pd

PRIOR_STRENGTH_GRID = {
    "plays": (50.0, 100.0, 200.0, 400.0),
    "drives": (5.0, 10.0, 20.0, 40.0),
    "games": (1.0, 2.0, 4.0, 8.0),
}

ORDINAL_SHRINKAGE_FEATURES = {
    "plays": (
        "adj_off_epa_pp",
        "adj_def_epa_pp",
        "adj_off_sr",
        "adj_def_sr",
        "adj_off_rush_ypp",
        "adj_def_rush_ypp",
        "adj_off_pass_ypp",
        "adj_def_pass_ypp",
    ),
    "drives": (
        "off_points_per_drive",
        "def_points_per_drive_allowed",
    ),
    "games": ("luck_factor",),
}


def prior_strength_designs() -> tuple[dict[str, float], ...]:
    """Return the reviewed Cartesian shrinkage grid in deterministic order."""
    return tuple(
        {"plays": plays, "drives": drives, "games": games}
        for plays, drives, games in product(
            PRIOR_STRENGTH_GRID["plays"],
            PRIOR_STRENGTH_GRID["drives"],
            PRIOR_STRENGTH_GRID["games"],
        )
    )


def add_ordinal_shrinkage_features(
    frame: pd.DataFrame, *, prior_strengths: Mapping[str, float]
) -> tuple[pd.DataFrame, tuple[str, ...]]:
    """Add the canonical team-side empirical-Bayes feature family.

    Defensive play exposure is the opposing offense's play count in the same
    point-in-time matchup row.  This avoids borrowing the other team's own
    exposure while preserving the actual defensive opportunity count.
    """
    require_frozen_prior_strengths(prior_strengths)
    result = frame.copy()
    required_exposure = {
        "home_n_off_plays",
        "away_n_off_plays",
        "home_off_drives",
        "away_off_drives",
        "home_def_drives_allowed",
        "away_def_drives_allowed",
        "home_completed_games",
        "away_completed_games",
    }
    missing = sorted(required_exposure - set(result.columns))
    if missing:
        raise ValueError(f"Ordinal shrinkage is missing exposure columns: {missing}")
    result["home_n_def_plays"] = result["away_n_off_plays"]
    result["away_n_def_plays"] = result["home_n_off_plays"]
    features: list[str] = []
    for side in ("home", "away"):
        for metric in ORDINAL_SHRINKAGE_FEATURES["plays"]:
            exposure = f"{side}_n_off_plays" if "_off_" in metric else f"{side}_n_def_plays"
            result = add_team_side_shrinkage(
                result,
                side=side,
                metrics=(metric,),
                exposure_column=exposure,
                prior_strength=float(prior_strengths["plays"]),
            )
            features.extend((f"{side}_shrunk_{metric}", f"{side}_{metric}_current_weight"))
        for metric in ORDINAL_SHRINKAGE_FEATURES["drives"]:
            exposure = f"{side}_off_drives" if metric.startswith("off_") else f"{side}_def_drives_allowed"
            result = add_team_side_shrinkage(
                result,
                side=side,
                metrics=(metric,),
                exposure_column=exposure,
                prior_strength=float(prior_strengths["drives"]),
            )
            features.extend((f"{side}_shrunk_{metric}", f"{side}_{metric}_current_weight"))
        for metric in ORDINAL_SHRINKAGE_FEATURES["games"]:
            result = add_team_side_shrinkage(
                result,
                side=side,
                metrics=(metric,),
                exposure_column=f"{side}_completed_games",
                prior_strength=float(prior_strengths["games"]),
            )
            features.extend((f"{side}_shrunk_{metric}", f"{side}_{metric}_current_weight"))
    return result, tuple(features)


def shrink_to_prior(
    prior: pd.Series,
    current: pd.Series,
    exposure: pd.Series,
    *,
    prior_strength: float,
) -> tuple[pd.Series, pd.Series]:
    """Return empirical-Bayes values and their current-evidence weights.

    Missing current measurements retain the prior; a missing prior retains the
    current value.  The returned weight is zero when only the prior is usable
    and one when only the current measurement is usable.
    """
    if prior_strength <= 0:
        raise ValueError("prior_strength must be positive")
    prior = pd.to_numeric(prior, errors="coerce")
    current = pd.to_numeric(current, errors="coerce")
    exposure = pd.to_numeric(exposure, errors="coerce").fillna(0).clip(lower=0)
    current_weight = exposure / (prior_strength + exposure)
    value = (1.0 - current_weight) * prior + current_weight * current
    value = value.where(prior.notna() & current.notna(), current.combine_first(prior))
    current_weight = current_weight.where(prior.notna() & current.notna())
    current_weight = current_weight.where(prior.notna(), 1.0)
    current_weight = current_weight.where(current.notna(), 0.0)
    return value.astype(float), current_weight.astype(float)


def add_team_side_shrinkage(
    frame: pd.DataFrame,
    *,
    side: str,
    metrics: Sequence[str],
    exposure_column: str,
    prior_strength: float,
) -> pd.DataFrame:
    """Add independently shrunken features for one side of a matchup.

    ``metrics`` are unprefixed current feature names, e.g.
    ``adj_off_epa_pp``.  The input therefore needs ``home_adj_off_epa_pp`` and
    ``home_prior_adj_off_epa_pp`` when ``side='home'``.
    """
    if side not in {"home", "away"}:
        raise ValueError("side must be home or away")
    if exposure_column not in frame:
        raise ValueError(f"Missing exposure column: {exposure_column}")
    result = frame.copy()
    for metric in metrics:
        current_column = f"{side}_{metric}"
        prior_column = f"{side}_prior_{metric}"
        if prior_column not in result and metric.startswith("adj_"):
            prior_column = f"{side}_prior_{metric.removeprefix('adj_')}"
        missing = [
            column
            for column in (current_column, prior_column)
            if column not in result
        ]
        if missing:
            raise ValueError(f"Missing shrinkage columns: {missing}")
        value, weight = shrink_to_prior(
            result[prior_column],
            result[current_column],
            result[exposure_column],
            prior_strength=prior_strength,
        )
        result[f"{side}_shrunk_{metric}"] = value
        result[f"{side}_{metric}_current_weight"] = weight
    return result


def add_points_derived_predictions(
    frame: pd.DataFrame,
    *,
    home_column: str,
    away_column: str,
    prefix: str = "points_derived",
) -> pd.DataFrame:
    """Derive nonnegative point, spread, and total predictions consistently."""
    missing = [column for column in (home_column, away_column) if column not in frame]
    if missing:
        raise ValueError(f"Missing point prediction columns: {missing}")
    result = frame.copy()
    home = pd.to_numeric(result[home_column], errors="coerce").clip(lower=0)
    away = pd.to_numeric(result[away_column], errors="coerce").clip(lower=0)
    result[f"{prefix}_home_points"] = home
    result[f"{prefix}_away_points"] = away
    result[f"{prefix}_spread_prediction"] = home - away
    result[f"{prefix}_total_prediction"] = home + away
    return result


def require_frozen_prior_strengths(selection: Mapping[str, float]) -> None:
    """Reject strengths outside the reviewed, reproducible candidate grids."""
    for unit, value in selection.items():
        if unit not in PRIOR_STRENGTH_GRID:
            raise ValueError(f"Unknown shrinkage unit: {unit}")
        if float(value) not in PRIOR_STRENGTH_GRID[unit]:
            raise ValueError(f"{unit} prior strength is not in the frozen grid")
