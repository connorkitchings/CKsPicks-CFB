"""Fixed alpha-10 through-2025 bridge for the V5 intended-update successor."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

from cks_picks_cfb.forecast.heads import FEATURES, _fit_one
from cks_picks_cfb.forecast.live import (
    DEVELOPMENT_SEASONS,
    export_frozen_bridge,
)

ALPHA = 10.0
SCALING_FLOOR = 0.05
RATING_FEATURES = ("home_offense", "home_defense", "away_offense", "away_defense")


class IntendedBundleError(ValueError):
    """Historical rating or calibration evidence is incomplete."""


def replace_historical_ratings(
    accepted_features: pd.DataFrame, repaired_states: pd.DataFrame
) -> pd.DataFrame:
    """Change only the four rating means in the accepted feature population."""
    states = repaired_states.copy()
    if "role" not in states and "unit_role" in states:
        states = states.rename(columns={"unit_role": "role", "rating_mean": "mean"})
    required = {"season", "week", "game_id", "team", "role", "mean"}
    if required - set(states):
        raise IntendedBundleError("historical repaired states lack required keys")
    if states.duplicated(["season", "game_id", "team", "role"]).any():
        raise IntendedBundleError("historical repaired states duplicate a key")
    frame = accepted_features.copy()
    if frame.duplicated(["season", "game_id"]).any():
        raise IntendedBundleError("accepted historical features duplicate a game")
    for side in ("home", "away"):
        for role in ("offense", "defense"):
            name = f"{side}_{role}"
            selected = states.loc[
                states.role.eq(role), ["season", "game_id", "team", "mean"]
            ].rename(columns={"team": f"{side}_team", "mean": name})
            frame = frame.drop(columns=name).merge(
                selected,
                on=["season", "game_id", f"{side}_team"],
                how="left",
                validate="one_to_one",
            )
    if frame[list(RATING_FEATURES)].isna().any().any():
        raise IntendedBundleError(
            "repaired states do not cover the forecast population"
        )
    if set(frame.season.astype(int)) != set(DEVELOPMENT_SEASONS):
        raise IntendedBundleError(
            "bridge training seasons differ from the accepted window"
        )
    stable_columns = [name for name in accepted_features if name not in RATING_FEATURES]
    if not frame[stable_columns].equals(accepted_features[stable_columns]):
        raise IntendedBundleError(
            "rating replacement changed nonrating forecast inputs"
        )
    return frame


def earlier_only_calibration(frame: pd.DataFrame, *, target: str) -> tuple[float, int]:
    """Calibrate on rolling prior-season predictions; never use 2026 labels."""
    if target not in {"margin", "total"}:
        raise IntendedBundleError("unknown forecast target")
    if 2020 in set(frame.season) or 2026 in set(frame.season):
        raise IntendedBundleError("calibration includes a forbidden season")
    errors: list[float] = []
    for validation in (season for season in DEVELOPMENT_SEASONS if season >= 2017):
        train = frame[frame.season.lt(validation)]
        test = frame[frame.season.eq(validation)]
        if train.empty or test.empty:
            raise IntendedBundleError("calibration season lacks train or test games")
        fitted, _ = _fit_one(
            train, test, target=target, alpha=ALPHA, floor=SCALING_FLOOR
        )
        residual = (
            test[f"actual_{target}"].to_numpy(float)
            - test[f"offset_{target}"].to_numpy(float)
            - fitted
        )
        errors.extend(residual.tolist())
    if not errors:
        raise IntendedBundleError("earlier-only calibration has no residuals")
    return max(float(np.mean(np.square(errors))), 1e-6), len(errors)


def assert_pre2026_frame(
    frame: pd.DataFrame, *, seasons: tuple[int, ...] = DEVELOPMENT_SEASONS
) -> None:
    """Reject any frame that is not exactly the development seasons (no 2020, no 2026)."""
    present = {int(season) for season in frame["season"]}
    if present & {2020, 2026}:
        raise IntendedBundleError("fit frame includes a forbidden season")
    if present != set(seasons):
        raise IntendedBundleError(
            f"fit frame seasons {sorted(present)} differ from {sorted(seasons)}"
        )


def fit_bundle_from_frame(
    frame: pd.DataFrame,
) -> tuple[dict[str, object], Mapping[str, int]]:
    """Calibrate and export the fixed alpha-10 bridge from a complete historical frame."""
    assert_pre2026_frame(frame)
    variances = {}
    counts = {}
    for target in ("margin", "total"):
        variances[target], counts[target] = earlier_only_calibration(
            frame, target=target
        )
    recipes = {
        target: {"head": "reference", "final_alpha": ALPHA}
        for target in ("margin", "total")
    }
    bundle = export_frozen_bridge(
        frame,
        recipes=recipes,
        calibration_variances=variances,
    )
    if bundle.get("feature_order") != list(FEATURES):
        raise IntendedBundleError("bridge feature order changed")
    return bundle, counts


def fit_intended_update_bundle(
    accepted_features: pd.DataFrame, repaired_states: pd.DataFrame
) -> tuple[dict[str, object], pd.DataFrame, Mapping[str, int]]:
    """Export a fixed inference bundle and its precise historical fit frame."""
    frame = replace_historical_ratings(accepted_features, repaired_states)
    bundle, counts = fit_bundle_from_frame(frame)
    return bundle, frame, counts


def replace_2026_ratings(
    features: pd.DataFrame,
    schedule: pd.DataFrame,
    pregame_team_states: pd.DataFrame,
) -> pd.DataFrame:
    """Apply certified repaired pregame states without changing other inputs."""
    if features.empty or not features.season.eq(2026).all():
        raise IntendedBundleError("successor application requires 2026 feature rows")
    if features.duplicated(["season", "game_id"]).any():
        raise IntendedBundleError("successor feature frame duplicates a game")
    names = schedule[["season", "game_id", "home_team", "away_team"]]
    if names.duplicated(["season", "game_id"]).any():
        raise IntendedBundleError("successor schedule duplicates a game")
    frame = features.merge(names, on=["season", "game_id"], validate="one_to_one")
    if len(frame) != len(features):
        raise IntendedBundleError("successor schedule does not cover all features")
    states = pregame_team_states
    if states.duplicated(["season", "game_id", "team"]).any():
        raise IntendedBundleError("successor pregame team states duplicate a key")
    for side in ("home", "away"):
        selected = states[
            ["season", "game_id", "team", "offense_rating", "defense_rating"]
        ].rename(
            columns={
                "team": f"{side}_team",
                "offense_rating": f"{side}_offense",
                "defense_rating": f"{side}_defense",
            }
        )
        frame = frame.drop(columns=[f"{side}_offense", f"{side}_defense"]).merge(
            selected,
            on=["season", "game_id", f"{side}_team"],
            how="left",
            validate="one_to_one",
        )
    if frame[list(RATING_FEATURES)].isna().any().any():
        raise IntendedBundleError("successor states do not cover every forecast team")
    frame = frame.drop(columns=["home_team", "away_team"])
    stable_columns = [name for name in features if name not in RATING_FEATURES]
    if not frame[stable_columns].equals(features[stable_columns]):
        raise IntendedBundleError("successor application changed nonrating features")
    return frame
