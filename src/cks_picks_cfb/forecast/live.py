"""Pure application of the frozen V5 bridge to outcome-free live games."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

FEATURES = (
    "home_offense",
    "home_defense",
    "away_offense",
    "away_defense",
    "home_host",
    "venue_unknown",
)
DEVELOPMENT_SEASONS = (2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024, 2025)
SCALING_FLOOR = 0.05


class LiveForecastError(ValueError):
    """Raised when a live application frame violates the frozen bridge."""


@dataclass(frozen=True)
class LiveForecastComputation:
    predictions: pd.DataFrame
    recipes: Mapping[str, Mapping[str, object]]


def build_live_application_frame(
    schedule: pd.DataFrame,
    completed_games: pd.DataFrame,
    team_states: pd.DataFrame,
    offsets: pd.DataFrame,
    *,
    as_of: str,
    target_week: int | None = None,
) -> tuple[pd.DataFrame, dict[int, str]]:
    """Join each scheduled 2026 game to only the latest earlier team state.

    Games at or before ``as_of`` are omitted from prospective output. A team
    without an eligible earlier state fails closed for readiness to report.
    """
    schedule_columns = {
        "season",
        "week",
        "game_id",
        "kickoff_utc",
        "home_team",
        "away_team",
    }
    completed_columns = {
        "season",
        "kickoff_utc",
        "home_team",
        "away_team",
        "schedule_completed",
        "outcome_valid",
    }
    state_columns = {
        "season",
        "game_id",
        "cutoff_utc",
        "team",
        "offense_rating",
        "defense_rating",
    }
    if missing := sorted(schedule_columns - set(schedule)):
        raise LiveForecastError(f"live schedule lacks columns: {missing}")
    if missing := sorted(completed_columns - set(completed_games)):
        raise LiveForecastError(f"completed game history lacks columns: {missing}")
    if missing := sorted(state_columns - set(team_states)):
        raise LiveForecastError(f"live team states lack columns: {missing}")
    if not offsets.empty and not {
        "season",
        "week",
        "game_id",
        "offset_margin",
        "offset_total",
    } <= set(offsets):
        raise LiveForecastError("live offsets lack required columns")
    cutoff = pd.Timestamp(as_of)
    if cutoff.tzinfo is None:
        raise LiveForecastError("live forecast as-of must be timezone-aware")
    cutoff = cutoff.tz_convert("UTC")
    games = schedule[schedule["season"].eq(2026)].copy()
    games["kickoff_utc"] = pd.to_datetime(
        games["kickoff_utc"], utc=True, errors="raise"
    )
    games = games[games["kickoff_utc"].gt(cutoff)].copy()
    if target_week is not None:
        games = games[games["week"].eq(target_week)].copy()
    if games.empty:
        raise LiveForecastError("no future eligible 2026 games remain after as-of")
    if games.duplicated(["season", "game_id"]).any():
        raise LiveForecastError("live schedule duplicates a game")
    states = team_states[team_states["season"].eq(2026)].copy()
    states["cutoff_utc"] = pd.to_datetime(
        states["cutoff_utc"], utc=True, errors="raise"
    )
    states = states.sort_values(["team", "cutoff_utc", "game_id"], kind="mergesort")
    state_refs: dict[int, str] = {}
    records: list[dict[str, object]] = []
    completed = completed_games[
        completed_games["season"].eq(2026)
        & completed_games["schedule_completed"].astype(bool)
        & completed_games["outcome_valid"].astype(bool)
    ].copy()
    completed["kickoff_utc"] = pd.to_datetime(
        completed["kickoff_utc"], utc=True, errors="raise"
    )
    if completed["kickoff_utc"].gt(cutoff).any():
        raise LiveForecastError(
            "completed-game source contains outcomes after the forecast cutoff"
        )
    for game in games.sort_values(
        ["kickoff_utc", "game_id"], kind="mergesort"
    ).itertuples(index=False):
        side_rows: dict[str, pd.Series] = {}
        state_ref_parts: dict[str, str] = {}
        counts: dict[str, int] = {}
        for side, team in (
            ("home", str(game.home_team)),
            ("away", str(game.away_team)),
        ):
            candidates = states[
                states["team"].astype(str).eq(team)
                & states["cutoff_utc"].le(cutoff)
                & states["cutoff_utc"].lt(game.kickoff_utc)
            ]
            if candidates.empty:
                raise LiveForecastError(
                    f"no pregame live rating state for {team} before game {game.game_id}"
                )
            state = candidates.iloc[-1]
            side_rows[side] = state
            state_ref_parts[side] = f"team_states/{state['game_id']}#{team}"
            previous = completed[
                completed["kickoff_utc"].lt(game.kickoff_utc)
                & (
                    completed["home_team"].astype(str).eq(team)
                    | completed["away_team"].astype(str).eq(team)
                )
            ]
            counts[side] = int(len(previous))
        keyed_offsets = offsets[
            offsets["season"].eq(2026)
            & offsets["week"].eq(int(game.week))
            & offsets["game_id"].eq(int(game.game_id))
        ]
        if len(keyed_offsets) != 1:
            raise LiveForecastError(
                f"game {game.game_id} lacks exactly one earlier-only offset"
            )
        offset = keyed_offsets.iloc[0]
        state_refs[int(game.game_id)] = (
            f"{state_ref_parts['home']}|{state_ref_parts['away']}"
        )
        records.append(
            {
                "season": 2026,
                "week": int(game.week),
                "game_id": int(game.game_id),
                "home_offense": float(side_rows["home"]["offense_rating"]),
                "home_defense": float(side_rows["home"]["defense_rating"]),
                "away_offense": float(side_rows["away"]["offense_rating"]),
                "away_defense": float(side_rows["away"]["defense_rating"]),
                "home_host": 1.0,
                "venue_unknown": True,
                "offset_margin": float(offset["offset_margin"]),
                "offset_total": float(offset["offset_total"]),
                "completed_game_stage": min(counts.values()),
            }
        )
    return pd.DataFrame.from_records(records), state_refs


def _design(train: pd.DataFrame, test: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    center = train.loc[:, FEATURES].mean()
    scale = train.loc[:, FEATURES].std(ddof=0).clip(lower=SCALING_FLOOR)
    x_train = (train.loc[:, FEATURES] - center) / scale
    x_test = (test.loc[:, FEATURES] - center) / scale
    varying = tuple(c for c in FEATURES if x_train[c].nunique(dropna=False) > 1)
    if not varying:
        raise LiveForecastError("frozen bridge has no varying feature")
    return x_train.loc[:, varying].to_numpy(float), x_test.loc[:, varying].to_numpy(
        float
    )


def export_frozen_bridge(
    historical_features: pd.DataFrame,
    *,
    recipes: Mapping[str, Mapping[str, object]],
    calibration_variances: Mapping[str, float],
) -> dict[str, object]:
    """Fit only the accepted through-2025 recipes for immutable inference."""
    required = {
        "season",
        "actual_margin",
        "actual_total",
        "offset_margin",
        "offset_total",
        *FEATURES,
    }
    if required - set(historical_features):
        raise LiveForecastError("historical bundle training frame is incomplete")
    if historical_features["season"].isin((2020, 2026)).any() or set(
        historical_features["season"].astype(int)
    ) - set(DEVELOPMENT_SEASONS):
        raise LiveForecastError("bundle training includes a forbidden season")
    if set(recipes) != {"margin", "total"} or set(calibration_variances) != {
        "margin",
        "total",
    }:
        raise LiveForecastError("bundle needs both frozen target recipes and variances")
    training = historical_features[
        historical_features["season"].isin(DEVELOPMENT_SEASONS)
    ]
    if training.empty:
        raise LiveForecastError("bundle training population is empty")
    targets: dict[str, object] = {}
    for target in ("margin", "total"):
        recipe = recipes[target]
        if recipe.get("head") not in {"reference", "challenger"}:
            raise LiveForecastError("bundle recipe has an unknown head")
        alpha = float(recipe.get("final_alpha", recipe.get("alpha", float("nan"))))
        variance = float(calibration_variances[target])
        if (
            not np.isfinite(alpha)
            or alpha <= 0
            or not np.isfinite(variance)
            or variance <= 0
        ):
            raise LiveForecastError("bundle recipe has invalid alpha or variance")
        actual = f"actual_{target}"
        offset = f"offset_{target}"
        clean = training.replace([np.inf, -np.inf], np.nan).dropna(
            subset=[actual, offset, *FEATURES]
        )
        center = clean.loc[:, FEATURES].mean()
        scale = clean.loc[:, FEATURES].std(ddof=0).clip(lower=SCALING_FLOOR)
        standardized = (clean.loc[:, FEATURES] - center) / scale
        varying = [
            name for name in FEATURES if standardized[name].nunique(dropna=False) > 1
        ]
        if not varying:
            raise LiveForecastError("bundle has no varying feature")
        model = Ridge(alpha=alpha).fit(
            standardized.loc[:, varying].to_numpy(float),
            clean[actual].to_numpy(float) - clean[offset].to_numpy(float),
        )
        targets[target] = {
            "head": str(recipe["head"]),
            "alpha": alpha,
            "feature_names": varying,
            "center": {name: float(center[name]) for name in varying},
            "scale": {name: float(scale[name]) for name in varying},
            "coefficients": [float(value) for value in model.coef_],
            "intercept": float(model.intercept_),
            "calibration_variance": variance,
            "training_rows": int(len(clean)),
        }
    return {
        "schema_version": "v5_inference_bundle_v1",
        "development_seasons": list(DEVELOPMENT_SEASONS),
        "feature_order": list(FEATURES),
        "targets": targets,
    }


def apply_exported_bridge(
    bundle: Mapping[str, object],
    live_features: pd.DataFrame,
    *,
    run_id: str,
    model_ref: str,
    state_refs: Mapping[int, str],
    source_ref: str,
    timing_class: str = "live",
) -> LiveForecastComputation:
    """Predict with exported coefficients, with no historical refit."""
    if bundle.get("schema_version") != "v5_inference_bundle_v1" or bundle.get(
        "feature_order"
    ) != list(FEATURES):
        raise LiveForecastError("inference bundle schema or feature order changed")
    if bundle.get("development_seasons") != list(DEVELOPMENT_SEASONS):
        raise LiveForecastError("inference bundle training window changed")
    if (
        live_features.empty
        or not live_features["season"].eq(2026).all()
        or live_features.duplicated(["season", "game_id"]).any()
    ):
        raise LiveForecastError("bundle application requires unique live 2026 games")
    if not all((run_id, model_ref, source_ref)):
        raise LiveForecastError("bundle application lacks lineage refs")
    if timing_class not in {"live", "replay"}:
        raise LiveForecastError("bundle application timing class is invalid")
    targets = bundle.get("targets")
    if not isinstance(targets, Mapping) or set(targets) != {"margin", "total"}:
        raise LiveForecastError("bundle lacks paired target models")
    predictions: list[pd.DataFrame] = []
    used_recipes: dict[str, Mapping[str, object]] = {}
    for target in ("margin", "total"):
        spec = targets[target]
        if not isinstance(spec, Mapping):
            raise LiveForecastError("bundle target is malformed")
        names = list(spec["feature_names"])
        if (
            not names
            or any(name not in FEATURES for name in names)
            or len(names) != len(spec["coefficients"])
        ):
            raise LiveForecastError("bundle coefficients or features are malformed")
        offset_column = f"offset_{target}"
        required = {"season", "week", "game_id", offset_column, *names}
        if required - set(live_features):
            raise LiveForecastError("bundle application frame is incomplete")
        clean = live_features.replace([np.inf, -np.inf], np.nan).dropna(
            subset=[offset_column, *names]
        )
        if len(clean) != len(live_features):
            raise LiveForecastError("bundle application has incomplete model inputs")
        x = np.column_stack(
            [
                (clean[name].to_numpy(float) - float(spec["center"][name]))
                / float(spec["scale"][name])
                for name in names
            ]
        )
        mean = (
            x @ np.asarray(spec["coefficients"], dtype=float)
            + float(spec["intercept"])
            + clean[offset_column].to_numpy(float)
        )
        variance = float(spec["calibration_variance"])
        sigma = float(np.sqrt(variance))
        output = clean.loc[:, ["season", "week", "game_id"]].copy()
        output["run_id"] = run_id
        output["target"] = target
        output["mean"] = mean
        output["variance"] = variance
        output["interval_lower_95"] = mean - 1.959963984540054 * sigma
        output["interval_upper_95"] = mean + 1.959963984540054 * sigma
        output["offset"] = clean[offset_column].to_numpy(float)
        output["completed_game_stage"] = (
            pd.to_numeric(
                clean.get("completed_game_stage", pd.Series(0, index=clean.index)),
                errors="raise",
            )
            .clip(upper=4)
            .astype(int)
            .to_numpy()
        )
        output["timing_class"] = timing_class
        output["model_ref"] = (
            f"{model_ref}#{target}:{spec['head']}:{float(spec['alpha']):g}"
        )
        output["state_ref"] = (
            clean["game_id"]
            .map(lambda game_id: state_refs.get(int(game_id), ""))
            .to_numpy()
        )
        output["source_ref"] = source_ref
        if output["state_ref"].eq("").any():
            raise LiveForecastError("bundle application lacks a state reference")
        predictions.append(output)
        used_recipes[target] = {
            "head": spec["head"],
            "alpha": float(spec["alpha"]),
            "training_seasons": list(DEVELOPMENT_SEASONS),
            "calibration_variance": variance,
        }
    result = pd.concat(predictions, ignore_index=True)
    columns = [
        "run_id",
        "season",
        "week",
        "game_id",
        "target",
        "mean",
        "variance",
        "interval_lower_95",
        "interval_upper_95",
        "offset",
        "completed_game_stage",
        "timing_class",
        "model_ref",
        "state_ref",
        "source_ref",
    ]
    ordered = (
        result.loc[:, columns]
        .sort_values(["season", "week", "game_id", "target"], kind="mergesort")
        .reset_index(drop=True)
    )
    return LiveForecastComputation(ordered, used_recipes)


def apply_frozen_bridge(
    historical_features: pd.DataFrame,
    live_features: pd.DataFrame,
    *,
    recipes: Mapping[str, Mapping[str, object]],
    calibration_variances: Mapping[str, float],
    run_id: str,
    model_ref: str,
    state_refs: Mapping[int, str],
    source_ref: str,
) -> LiveForecastComputation:
    """Apply fixed 11C recipes using pre-2026 training labels only.

    The selected head and alpha are inputs from the signed 11C final-fit rows.
    This function fits coefficients on the established through-2025 corpus but
    performs no selection, calibration, or fitting with 2026 outcomes.
    """
    required_historical = {
        "season",
        "actual_margin",
        "actual_total",
        "offset_margin",
        "offset_total",
        *FEATURES,
    }
    required_live = {
        "season",
        "week",
        "game_id",
        "offset_margin",
        "offset_total",
        *FEATURES,
    }
    if missing := sorted(required_historical - set(historical_features)):
        raise LiveForecastError(f"historical fit frame missing columns: {missing}")
    if missing := sorted(required_live - set(live_features)):
        raise LiveForecastError(f"live application frame missing columns: {missing}")
    if historical_features["season"].isin((2020, 2026)).any():
        raise LiveForecastError("historical final fit contains a forbidden season")
    if set(historical_features["season"].astype(int)) - set(DEVELOPMENT_SEASONS):
        raise LiveForecastError("historical final fit differs from the frozen window")
    if live_features.empty or not live_features["season"].eq(2026).all():
        raise LiveForecastError("application frame must contain 2026 live games")
    if live_features.duplicated(["season", "game_id"]).any():
        raise LiveForecastError("live application frame duplicates a game")
    if not set(recipes) == {"margin", "total"} or not set(calibration_variances) == {
        "margin",
        "total",
    }:
        raise LiveForecastError("both frozen target recipes and variances are required")
    if not all((run_id, model_ref, source_ref)):
        raise LiveForecastError("forecast lineage refs are required")

    training = historical_features[
        historical_features["season"].isin(DEVELOPMENT_SEASONS)
    ].copy()
    if training.empty:
        raise LiveForecastError("frozen development training population is empty")
    predictions: list[pd.DataFrame] = []
    used_recipes: dict[str, Mapping[str, object]] = {}
    for target in ("margin", "total"):
        recipe = recipes[target]
        if recipe.get("head") not in ("reference", "challenger"):
            raise LiveForecastError(f"unknown frozen head for {target}")
        alpha = float(recipe.get("final_alpha", recipe.get("alpha", float("nan"))))
        if not np.isfinite(alpha) or alpha <= 0:
            raise LiveForecastError(f"invalid frozen alpha for {target}")
        variance = float(calibration_variances[target])
        if not np.isfinite(variance) or variance <= 0:
            raise LiveForecastError(f"invalid frozen calibration variance for {target}")
        actual_column = "actual_margin" if target == "margin" else "actual_total"
        offset_column = "offset_margin" if target == "margin" else "offset_total"
        clean_train = training.replace([np.inf, -np.inf], np.nan).dropna(
            subset=[actual_column, offset_column, *FEATURES]
        )
        clean_live = live_features.replace([np.inf, -np.inf], np.nan).dropna(
            subset=[offset_column, *FEATURES]
        )
        if len(clean_live) != len(live_features):
            raise LiveForecastError(f"{target} live frame has incomplete model inputs")
        x_train, x_live = _design(clean_train, clean_live)
        estimator = Ridge(alpha=alpha).fit(
            x_train,
            clean_train[actual_column].to_numpy(float)
            - clean_train[offset_column].to_numpy(float),
        )
        mean = estimator.predict(x_live) + clean_live[offset_column].to_numpy(float)
        sigma = float(np.sqrt(variance))
        output = clean_live.loc[:, ["season", "week", "game_id"]].copy()
        output["run_id"] = run_id
        output["target"] = target
        output["mean"] = mean
        output["variance"] = variance
        output["interval_lower_95"] = mean - 1.959963984540054 * sigma
        output["interval_upper_95"] = mean + 1.959963984540054 * sigma
        output["offset"] = clean_live[offset_column].to_numpy(float)
        output["completed_game_stage"] = (
            pd.to_numeric(
                clean_live.get(
                    "completed_game_stage", pd.Series(0, index=clean_live.index)
                ),
                errors="raise",
            )
            .clip(upper=4)
            .astype(int)
            .to_numpy()
        )
        output["timing_class"] = "live"
        output["model_ref"] = f"{model_ref}#{target}:{recipe['head']}:{alpha:g}"
        output["state_ref"] = (
            clean_live["game_id"]
            .map(lambda game_id: state_refs.get(int(game_id), ""))
            .to_numpy()
        )
        output["source_ref"] = source_ref
        if output["state_ref"].eq("").any():
            raise LiveForecastError("one or more live games lack a state reference")
        predictions.append(output)
        used_recipes[target] = {
            "head": recipe["head"],
            "alpha": alpha,
            "training_seasons": list(DEVELOPMENT_SEASONS),
            "calibration_variance": variance,
        }
    result = (
        pd.concat(predictions, ignore_index=True)
        .loc[
            :,
            [
                "run_id",
                "season",
                "week",
                "game_id",
                "target",
                "mean",
                "variance",
                "interval_lower_95",
                "interval_upper_95",
                "offset",
                "completed_game_stage",
                "timing_class",
                "model_ref",
                "state_ref",
                "source_ref",
            ],
        ]
        .sort_values(["season", "week", "game_id", "target"], kind="mergesort")
        .reset_index(drop=True)
    )
    return LiveForecastComputation(result, used_recipes)
