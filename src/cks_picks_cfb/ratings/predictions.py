"""Frozen Phase 3 structured margin and total prediction baseline.

This module is deliberately independent from V4 inference and all market
inputs.  It turns certified pregame team states into transparent OLS forecasts.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd
import yaml

from cks_picks_cfb.ratings.contracts import MeasurementContractError

PREDICTION_CONFIG_VERSION = "rating_prediction_baseline_v1"
PREDICTION_MODEL_DATASET = "rating_prediction_models"
PREDICTION_DATASET = "rating_game_predictions"
PREDICTION_MODEL_SCHEMA_VERSION = "rating_prediction_models_v1"
PREDICTION_SCHEMA_VERSION = "rating_game_predictions_v1"
PREDICTION_TARGETS = ("margin", "total")


def _sha(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@dataclass(frozen=True)
class PredictionConfig:
    research_prefix: str
    historical_seasons: tuple[int, ...]
    evaluation_seasons: tuple[int, ...]
    state_inputs: Mapping[str, str]
    v4_benchmark: Mapping[str, str]
    pace: Mapping[str, Any]
    gates: Mapping[str, Any]
    raw_config: Mapping[str, Any]

    @property
    def design_id(self) -> str:
        return _sha(self.raw_config)


def load_prediction_config(path: str | Path) -> PredictionConfig:
    raw = yaml.safe_load(Path(path).read_text())
    if (
        not isinstance(raw, Mapping)
        or raw.get("prediction_baseline_config_version") != PREDICTION_CONFIG_VERSION
    ):
        raise MeasurementContractError("Unsupported Phase 3 prediction configuration")
    try:
        config = PredictionConfig(
            research_prefix=str(raw["research_prefix"]).rstrip("/"),
            historical_seasons=tuple(int(value) for value in raw["historical_seasons"]),
            evaluation_seasons=tuple(int(value) for value in raw["evaluation_seasons"]),
            state_inputs={str(k): str(v) for k, v in raw["state_inputs"].items()},
            v4_benchmark={str(k): str(v) for k, v in raw["v4_benchmark"].items()},
            pace=dict(raw["pace"]),
            gates=dict(raw["gates"]),
            raw_config=raw,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise MeasurementContractError(
            "Incomplete Phase 3 prediction configuration"
        ) from exc
    if config.historical_seasons != (
        2021,
        2022,
        2023,
        2024,
        2025,
    ) or config.evaluation_seasons != (2022, 2023, 2024, 2025):
        raise MeasurementContractError(
            "Phase 3 chronology must remain frozen to 2021-2025"
        )
    return config


def _require(frame: pd.DataFrame, columns: set[str], label: str) -> None:
    missing = sorted(columns - set(frame.columns))
    if missing:
        raise MeasurementContractError(f"{label} missing columns: {missing}")


def _terminal_scale(
    terminal: pd.DataFrame, *, season: int, config: PredictionConfig
) -> tuple[float, float]:
    prior = terminal[
        (terminal["season"].astype(int) == season - 1)
        & (terminal["measurement_id"] == config.pace["measurement_id"])
        & (terminal["unit_role"] == config.pace["role"])
        & (terminal["coverage_status"] == "observed")
    ]
    values = pd.to_numeric(prior["adjusted_value"], errors="coerce").dropna()
    if values.empty:
        return float(config.pace["fallback_center"]), float(
            config.pace["fallback_scale"]
        )
    scale = float(values.std(ddof=1)) if len(values) > 1 else 0.0
    return float(values.mean()), max(scale, float(config.pace["scale_floor"]))


def _pace_values(
    snapshots: pd.DataFrame,
    terminal: pd.DataFrame,
    *,
    season: int,
    game_id: int,
    team: str,
    config: PredictionConfig,
) -> tuple[float, str, float, float]:
    current = snapshots[
        (snapshots["season"].astype(int) == season)
        & (snapshots["as_of_game_id"].astype(int) == game_id)
        & (snapshots["team"] == team)
        & (snapshots["measurement_id"] == config.pace["measurement_id"])
        & (snapshots["unit_role"] == config.pace["role"])
    ]
    if len(current) != 1:
        raise MeasurementContractError(
            f"Expected one pace snapshot for {season}/{game_id}/{team}"
        )
    center, scale = _terminal_scale(terminal, season=season, config=config)
    row = current.iloc[0]
    value = pd.to_numeric(pd.Series([row["adjusted_value"]]), errors="coerce").iloc[0]
    if row["coverage_status"] == "observed" and pd.notna(value):
        return (float(value) - center) / scale, "current_pregame", center, scale
    previous = terminal[
        (terminal["season"].astype(int) == season - 1)
        & (terminal["team"] == team)
        & (terminal["measurement_id"] == config.pace["measurement_id"])
        & (terminal["unit_role"] == config.pace["role"])
        & (terminal["coverage_status"] == "observed")
    ]
    if len(previous) == 1 and pd.notna(previous.iloc[0]["adjusted_value"]):
        return (
            (float(previous.iloc[0]["adjusted_value"]) - center) / scale,
            "previous_terminal",
            center,
            scale,
        )
    return 0.0, "neutral_fallback", center, scale


def prepare_prediction_frame(
    *,
    team_states: pd.DataFrame,
    snapshots: pd.DataFrame,
    terminal_snapshots: pd.DataFrame,
    games: pd.DataFrame,
    outcomes: pd.DataFrame,
    config: PredictionConfig,
) -> pd.DataFrame:
    """Join canonical context to exactly two pregame states without inference leakage."""
    _require(
        team_states,
        {
            "state_kind",
            "season",
            "as_of_game_id",
            "team",
            "state_id",
            "offense_mean",
            "offense_sd",
            "defense_mean",
            "defense_sd",
            "overall_mean",
            "overall_sd",
            "completed_games",
        },
        "team states",
    )
    _require(
        games,
        {
            "season",
            "game_id",
            "week",
            "kickoff_utc",
            "home_team",
            "away_team",
            "neutral_site",
        },
        "games",
    )
    _require(
        outcomes,
        {"season", "game_id", "completed", "home_points", "away_points"},
        "outcomes",
    )
    if set(
        pd.to_numeric(team_states["season"], errors="coerce").dropna().astype(int)
    ) & {2019, 2020}:
        raise MeasurementContractError("Team states contain forbidden seasons")
    state_rows = team_states[team_states["state_kind"] == "pregame"].copy()
    if state_rows.duplicated(["season", "as_of_game_id", "team"]).any():
        raise MeasurementContractError("Duplicate pregame team states")
    if (
        team_states[team_states["state_kind"] != "pregame"].empty is False
        and state_rows.empty
    ):
        raise MeasurementContractError("Pregame states are required")
    game_rows = games[games["season"].isin((*config.historical_seasons, 2026))].copy()
    if game_rows.duplicated(["season", "game_id"]).any():
        raise MeasurementContractError("Duplicate canonical games")
    status = (
        game_rows.get("status", pd.Series("", index=game_rows.index))
        .astype(str)
        .str.lower()
    )
    game_rows = game_rows[~status.isin(("cancelled", "canceled", "postponed"))]
    if game_rows["neutral_site"].isna().any():
        raise MeasurementContractError(
            "Phase 3 rejects games with missing neutral-site status"
        )
    outcome_rows = outcomes.rename(
        columns={
            "completed": "outcome_completed",
            "home_points": "outcome_home_points",
            "away_points": "outcome_away_points",
        }
    )
    outcome_rows = outcome_rows.drop_duplicates(["season", "game_id"])
    if len(outcome_rows) != len(outcomes):
        raise MeasurementContractError("Duplicate canonical outcomes")
    joined = game_rows.merge(
        outcome_rows, on=["season", "game_id"], how="left", validate="one_to_one"
    )
    records: list[dict[str, Any]] = []
    for game in joined.sort_values(
        ["season", "kickoff_utc", "game_id"], kind="mergesort"
    ).itertuples(index=False):
        states = state_rows[
            (state_rows["season"].astype(int) == int(game.season))
            & (state_rows["as_of_game_id"].astype(int) == int(game.game_id))
        ]
        if len(states) != 2 or set(states["team"]) != {game.home_team, game.away_team}:
            raise MeasurementContractError(
                f"Expected home/away pregame states for {game.season}/{game.game_id}"
            )
        home, away = (
            states[states["team"] == game.home_team].iloc[0],
            states[states["team"] == game.away_team].iloc[0],
        )
        home_pace, home_source, center, scale = _pace_values(
            snapshots,
            terminal_snapshots,
            season=int(game.season),
            game_id=int(game.game_id),
            team=str(game.home_team),
            config=config,
        )
        away_pace, away_source, _, _ = _pace_values(
            snapshots,
            terminal_snapshots,
            season=int(game.season),
            game_id=int(game.game_id),
            team=str(game.away_team),
            config=config,
        )
        complete = (
            bool(game.outcome_completed) if pd.notna(game.outcome_completed) else False
        )
        actual_margin = (
            float(game.outcome_home_points - game.outcome_away_points)
            if complete
            and pd.notna(game.outcome_home_points)
            and pd.notna(game.outcome_away_points)
            else np.nan
        )
        actual_total = (
            float(game.outcome_home_points + game.outcome_away_points)
            if complete
            and pd.notna(game.outcome_home_points)
            and pd.notna(game.outcome_away_points)
            else np.nan
        )
        records.append(
            {
                "season": int(game.season),
                "week": int(game.week),
                "game_id": int(game.game_id),
                "kickoff_utc": str(game.kickoff_utc),
                "home_team": str(game.home_team),
                "away_team": str(game.away_team),
                "neutral_site": bool(game.neutral_site),
                "home_state_id": home.state_id,
                "away_state_id": away.state_id,
                "home_completed_games": int(home.completed_games),
                "away_completed_games": int(away.completed_games),
                "quality_gap": float(home.overall_mean - away.overall_mean),
                "home_field": 0.0 if bool(game.neutral_site) else 1.0,
                "offense_sum": float(home.offense_mean + away.offense_mean),
                "defense_sum": float(home.defense_mean + away.defense_mean),
                "pace_z": float((home_pace + away_pace) / 2),
                "home_overall_sd": float(home.overall_sd),
                "away_overall_sd": float(away.overall_sd),
                "home_offense_sd": float(home.offense_sd),
                "away_offense_sd": float(away.offense_sd),
                "home_defense_sd": float(home.defense_sd),
                "away_defense_sd": float(away.defense_sd),
                "pace_center": center,
                "pace_scale": scale,
                "home_pace_source": home_source,
                "away_pace_source": away_source,
                "actual_margin": actual_margin,
                "actual_total": actual_total,
            }
        )
    return pd.DataFrame.from_records(records)


@dataclass(frozen=True)
class OLSModel:
    target: str
    feature_names: tuple[str, ...]
    coefficients: np.ndarray
    covariance: np.ndarray
    residual_variance: float
    rank: int
    training_seasons: tuple[int, ...]


def fit_ols(
    frame: pd.DataFrame, *, target: str, training_seasons: tuple[int, ...]
) -> OLSModel:
    if target == "margin":
        feature_names = ("home_field", "quality_gap")
        outcome = "actual_margin"
    elif target == "total":
        feature_names = ("intercept", "offense_sum", "defense_sum", "pace_z")
        outcome = "actual_total"
    else:
        raise MeasurementContractError(f"Unknown prediction target {target}")
    rows = (
        frame[frame["season"].isin(training_seasons)]
        .dropna(subset=[outcome, *[x for x in feature_names if x != "intercept"]])
        .copy()
    )
    if len(rows) <= len(feature_names):
        raise MeasurementContractError(f"Insufficient rows for {target} OLS")
    matrix = np.column_stack(
        [
            np.ones(len(rows))
            if name == "intercept"
            else rows[name].to_numpy(dtype=float)
            for name in feature_names
        ]
    )
    y = rows[outcome].to_numpy(dtype=float)
    coefficients, _, rank, _ = np.linalg.lstsq(matrix, y, rcond=None)
    if rank != len(feature_names) or not np.isfinite(coefficients).all():
        raise MeasurementContractError(
            f"{target} OLS design is rank deficient or non-finite"
        )
    residuals = y - matrix @ coefficients
    residual_variance = float(np.sum(residuals**2) / (len(rows) - len(feature_names)))
    if not np.isfinite(residual_variance) or residual_variance <= 0:
        raise MeasurementContractError(
            f"{target} OLS residual variance must be positive"
        )
    if (target == "margin" and coefficients[1] <= 0) or (
        target == "total" and (coefficients[1] <= 0 or coefficients[2] >= 0)
    ):
        raise MeasurementContractError(
            f"{target} OLS coefficient signs violate frozen baseline"
        )
    covariance = residual_variance * np.linalg.inv(matrix.T @ matrix)
    return OLSModel(
        target,
        feature_names,
        coefficients,
        covariance,
        residual_variance,
        int(rank),
        training_seasons,
    )


def predict(model: OLSModel, frame: pd.DataFrame, *, fold_id: str) -> pd.DataFrame:
    matrix = np.column_stack(
        [
            np.ones(len(frame))
            if name == "intercept"
            else frame[name].to_numpy(dtype=float)
            for name in model.feature_names
        ]
    )
    mean = matrix @ model.coefficients
    estimation_variance = np.einsum("ij,jk,ik->i", matrix, model.covariance, matrix)
    if model.target == "margin":
        propagated = abs(float(model.coefficients[1])) * (
            frame["home_overall_sd"].to_numpy(float)
            + frame["away_overall_sd"].to_numpy(float)
        )
        actual = frame["actual_margin"].to_numpy(float)
    else:
        propagated = abs(float(model.coefficients[1])) * (
            frame["home_offense_sd"].to_numpy(float)
            + frame["away_offense_sd"].to_numpy(float)
        ) + abs(float(model.coefficients[2])) * (
            frame["home_defense_sd"].to_numpy(float)
            + frame["away_defense_sd"].to_numpy(float)
        )
        actual = frame["actual_total"].to_numpy(float)
    variance = model.residual_variance + estimation_variance + propagated**2
    sd = np.sqrt(variance)
    if not np.isfinite(sd).all() or (sd <= 0).any():
        raise MeasurementContractError(
            "Predictive uncertainty must be finite and positive"
        )
    z = {"50": 0.6744897501960817, "80": 1.2815515655446004, "95": 1.959963984540054}
    result = frame[
        [
            "season",
            "week",
            "game_id",
            "kickoff_utc",
            "home_state_id",
            "away_state_id",
            "home_completed_games",
            "away_completed_games",
            "home_pace_source",
            "away_pace_source",
        ]
    ].copy()
    result["target"] = model.target
    result["fold_id"] = fold_id
    result["actual"] = actual
    result["prediction_mean"] = mean
    result["prediction_sd"] = sd
    result["residual_variance"] = model.residual_variance
    result["coefficient_estimation_variance"] = estimation_variance
    result["state_propagation_sd"] = propagated
    for label, value in z.items():
        result[f"interval_{label}_lower"] = mean - value * sd
        result[f"interval_{label}_upper"] = mean + value * sd
    return result


def expanding_predictions(
    frame: pd.DataFrame, config: PredictionConfig
) -> tuple[pd.DataFrame, list[OLSModel]]:
    predictions: list[pd.DataFrame] = []
    models: list[OLSModel] = []
    for season in config.evaluation_seasons:
        training = tuple(year for year in config.historical_seasons if year < season)
        test = frame[
            (frame["season"] == season)
            & frame["actual_margin"].notna()
            & frame["actual_total"].notna()
        ]
        if test.empty:
            raise MeasurementContractError(
                f"No completed outcomes available for expanding {season} evaluation"
            )
        for target in PREDICTION_TARGETS:
            model = fit_ols(frame, target=target, training_seasons=training)
            models.append(model)
            predictions.append(predict(model, test, fold_id=f"expanding_{season}"))
    return pd.concat(predictions, ignore_index=True), models


def model_records(
    models: list[OLSModel],
    *,
    design_id: str,
    code_sha: str,
    config_sha: str,
    lineage: Mapping[str, Any],
) -> list[dict[str, Any]]:
    records = []
    for model in models:
        fold_id = (
            "final_2026"
            if len(model.training_seasons) == 5
            else f"expanding_{max(model.training_seasons) + 1}"
        )
        records.append(
            {
                "target": model.target,
                "fold_id": fold_id,
                "training_seasons": list(model.training_seasons),
                "feature_names": list(model.feature_names),
                "coefficients": json.dumps(
                    dict(zip(model.feature_names, model.coefficients.tolist())),
                    sort_keys=True,
                ),
                "residual_variance": model.residual_variance,
                "rank": model.rank,
                "state_design_id": design_id,
                "code_sha": code_sha,
                "config_sha": config_sha,
                "certified_input_lineage": json.dumps(lineage, sort_keys=True),
            }
        )
    return records
