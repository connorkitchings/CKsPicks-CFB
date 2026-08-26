"""Sealed Phase 3 v2 team-score candidates and tournament helpers.

The module is deliberately independent of V4 and market data.  Both candidates
first forecast the two team scores, then derive margin and total from their
joint predictive distribution.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
import yaml
from scipy.optimize import lsq_linear, minimize
from scipy.special import gammaln

from cks_picks_cfb.ratings.contracts import MeasurementContractError
from cks_picks_cfb.ratings.prediction_evaluation import evaluate_predictions

SCORE_TOURNAMENT_CONFIG_VERSION = "rating_score_tournament_v2"
SCORE_MODEL_DATASET = "rating_score_models"
SCORE_PREDICTION_DATASET = "rating_score_predictions"
SCORE_MODEL_SCHEMA_VERSION = "rating_score_models_v2"
SCORE_PREDICTION_SCHEMA_VERSION = "rating_score_predictions_v2"
SCORE_CANDIDATE_SCHEMA_VERSION = "rating_score_candidate_v2"
SCORE_FAMILIES = ("linear_scores", "negative_binomial_scores")
FEATURE_NAMES = (
    "intercept",
    "home_field",
    "own_offense",
    "opponent_defense",
    "pace_z",
)
Z_SCORES = {"50": 0.6744897501960817, "80": 1.2815515655446004, "95": 1.959963984540054}


def _sha(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@dataclass(frozen=True)
class ScoreTournamentConfig:
    research_prefix: str
    historical_seasons: tuple[int, ...]
    selection_seasons: tuple[int, ...]
    locked_season: int
    state_inputs: Mapping[str, str]
    v4_benchmark: Mapping[str, str]
    pace: Mapping[str, Any]
    candidates: tuple[str, ...]
    nb2: Mapping[str, Any]
    selection: Mapping[str, Any]
    gates: Mapping[str, Any]
    raw_config: Mapping[str, Any]

    @property
    def design_id(self) -> str:
        return _sha(self.raw_config)


def load_score_tournament_config(path: str | Path) -> ScoreTournamentConfig:
    raw = yaml.safe_load(Path(path).read_text())
    if (
        not isinstance(raw, Mapping)
        or raw.get("score_model_tournament_config_version")
        != SCORE_TOURNAMENT_CONFIG_VERSION
    ):
        raise MeasurementContractError("Unsupported Phase 3 score tournament config")
    try:
        config = ScoreTournamentConfig(
            research_prefix=str(raw["research_prefix"]).rstrip("/"),
            historical_seasons=tuple(int(value) for value in raw["historical_seasons"]),
            selection_seasons=tuple(int(value) for value in raw["selection_seasons"]),
            locked_season=int(raw["locked_season"]),
            state_inputs={str(k): str(v) for k, v in raw["state_inputs"].items()},
            v4_benchmark={str(k): str(v) for k, v in raw["v4_benchmark"].items()},
            pace=dict(raw["pace"]),
            candidates=tuple(str(value) for value in raw["candidates"]),
            nb2=dict(raw["nb2"]),
            selection=dict(raw["selection"]),
            gates=dict(raw["gates"]),
            raw_config=raw,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise MeasurementContractError(
            "Incomplete Phase 3 score tournament config"
        ) from exc
    if (
        config.historical_seasons != (2021, 2022, 2023, 2024, 2025)
        or config.selection_seasons != (2022, 2023, 2024)
        or config.locked_season != 2025
        or config.candidates != SCORE_FAMILIES
    ):
        raise MeasurementContractError("Phase 3 v2 chronology or candidates changed")
    return config


@dataclass(frozen=True)
class ScoreModel:
    family: str
    coefficients: np.ndarray
    residual_covariance: np.ndarray
    dispersion: float | None
    training_seasons: tuple[int, ...]
    optimizer_success: bool = True


def _complete_rows(frame: pd.DataFrame) -> pd.DataFrame:
    required = {
        "season",
        "game_id",
        "week",
        "kickoff_utc",
        "home_field",
        "home_offense_mean",
        "away_offense_mean",
        "home_defense_mean",
        "away_defense_mean",
        "pace_z",
        "actual_home_points",
        "actual_away_points",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise MeasurementContractError(f"Score frame missing columns: {missing}")
    rows = frame.dropna(
        subset=[
            "actual_home_points",
            "actual_away_points",
            "home_offense_mean",
            "away_offense_mean",
            "home_defense_mean",
            "away_defense_mean",
            "pace_z",
        ]
    ).copy()
    if rows.empty:
        raise MeasurementContractError("Score model requires completed game outcomes")
    if (rows[["actual_home_points", "actual_away_points"]] < 0).any().any():
        raise MeasurementContractError("Scores must be non-negative")
    return rows


def _side_design(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return a symmetric side-row design and the paired game-side indices."""
    home = np.column_stack(
        [
            np.ones(len(frame)),
            frame["home_field"].to_numpy(float),
            frame["home_offense_mean"].to_numpy(float),
            frame["away_defense_mean"].to_numpy(float),
            frame["pace_z"].to_numpy(float),
        ]
    )
    away = np.column_stack(
        [
            np.ones(len(frame)),
            np.zeros(len(frame)),
            frame["away_offense_mean"].to_numpy(float),
            frame["home_defense_mean"].to_numpy(float),
            frame["pace_z"].to_numpy(float),
        ]
    )
    outcomes = np.concatenate(
        [
            frame["actual_home_points"].to_numpy(float),
            frame["actual_away_points"].to_numpy(float),
        ]
    )
    return np.vstack([home, away]), outcomes, np.stack([home, away], axis=1)


def _assert_direction(coefficients: np.ndarray) -> None:
    if coefficients[1] < 0 or coefficients[2] <= 0 or coefficients[3] >= 0:
        raise MeasurementContractError(
            "Score model violates frozen football directions"
        )


def _psd_covariance(values: np.ndarray) -> np.ndarray:
    covariance = np.asarray(values, dtype=float)
    if covariance.shape != (2, 2) or not np.isfinite(covariance).all():
        raise MeasurementContractError("Score covariance must be finite 2x2")
    covariance = (covariance + covariance.T) / 2
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    floor = max(1e-6, float(np.max(eigenvalues)) * 1e-9)
    return eigenvectors @ np.diag(np.maximum(eigenvalues, floor)) @ eigenvectors.T


def _paired_residual_covariance(
    frame: pd.DataFrame, coefficients: np.ndarray, *, mean: str
) -> np.ndarray:
    _, _, pair_design = _side_design(frame)
    home_design, away_design = pair_design[:, 0, :], pair_design[:, 1, :]
    if mean == "linear":
        home_mean = home_design @ coefficients
        away_mean = away_design @ coefficients
    else:
        home_mean = np.exp(np.clip(home_design @ coefficients, -20, 20))
        away_mean = np.exp(np.clip(away_design @ coefficients, -20, 20))
    residuals = np.column_stack(
        [
            frame["actual_home_points"].to_numpy(float) - home_mean,
            frame["actual_away_points"].to_numpy(float) - away_mean,
        ]
    )
    return _psd_covariance(np.cov(residuals, rowvar=False, ddof=1))


def _coefficient_bounds() -> tuple[np.ndarray, np.ndarray]:
    """Frozen football-direction constraints for both score families."""
    epsilon = 1e-9
    return (
        np.array([-np.inf, 0.0, epsilon, -np.inf, -np.inf]),
        np.array([np.inf, np.inf, np.inf, -epsilon, np.inf]),
    )


def fit_linear_scores(
    frame: pd.DataFrame, *, training_seasons: Sequence[int]
) -> ScoreModel:
    rows = _complete_rows(frame[frame["season"].isin(training_seasons)])
    matrix, outcomes, _ = _side_design(rows)
    lower, upper = _coefficient_bounds()
    result = lsq_linear(matrix, outcomes, bounds=(lower, upper), tol=1e-12)
    coefficients = result.x
    if not result.success or not np.isfinite(coefficients).all():
        raise MeasurementContractError("Constrained linear score fit failed")
    _assert_direction(coefficients)
    return ScoreModel(
        family="linear_scores",
        coefficients=coefficients,
        residual_covariance=_paired_residual_covariance(
            rows, coefficients, mean="linear"
        ),
        dispersion=None,
        training_seasons=tuple(int(value) for value in training_seasons),
    )


def _nb2_objective(
    parameters: np.ndarray, matrix: np.ndarray, outcomes: np.ndarray
) -> float:
    coefficients = parameters[:-1]
    dispersion = float(np.exp(parameters[-1]))
    mean = np.exp(np.clip(matrix @ coefficients, -20, 20))
    inverse_dispersion = 1.0 / dispersion
    log_likelihood = (
        gammaln(outcomes + inverse_dispersion)
        - gammaln(inverse_dispersion)
        - gammaln(outcomes + 1)
        + inverse_dispersion * (-np.log1p(dispersion * mean))
        + outcomes * (np.log(dispersion * mean) - np.log1p(dispersion * mean))
    )
    return float(-np.sum(log_likelihood))


def fit_negative_binomial_scores(
    frame: pd.DataFrame,
    *,
    training_seasons: Sequence[int],
    nb2: Mapping[str, Any],
) -> ScoreModel:
    rows = _complete_rows(frame[frame["season"].isin(training_seasons)])
    matrix, outcomes, _ = _side_design(rows)
    log_outcomes = np.log(outcomes + 0.5)
    initial_coefficients, _, rank, _ = np.linalg.lstsq(matrix, log_outcomes, rcond=None)
    if rank != len(FEATURE_NAMES):
        raise MeasurementContractError("NB2 score model is rank deficient")
    floor = float(nb2["dispersion_floor"])
    lower, upper = _coefficient_bounds()
    result = minimize(
        _nb2_objective,
        np.concatenate([initial_coefficients, [np.log(0.25)]]),
        args=(matrix, outcomes),
        method="L-BFGS-B",
        bounds=[
            *zip(lower.tolist(), upper.tolist(), strict=True),
            (np.log(floor), np.log(100.0)),
        ],
        options={
            "maxiter": int(nb2["max_iterations"]),
            "ftol": float(nb2["tolerance"]),
        },
    )
    if not result.success or not np.isfinite(result.x).all():
        raise MeasurementContractError(f"NB2 optimizer failed: {result.message}")
    coefficients = result.x[:-1]
    dispersion = max(float(np.exp(result.x[-1])), floor)
    _assert_direction(coefficients)
    return ScoreModel(
        family="negative_binomial_scores",
        coefficients=coefficients,
        residual_covariance=_paired_residual_covariance(rows, coefficients, mean="nb2"),
        dispersion=dispersion,
        training_seasons=tuple(int(value) for value in training_seasons),
        optimizer_success=True,
    )


def fit_score_model(
    family: str,
    frame: pd.DataFrame,
    *,
    training_seasons: Sequence[int],
    config: ScoreTournamentConfig,
) -> ScoreModel:
    if family == "linear_scores":
        return fit_linear_scores(frame, training_seasons=training_seasons)
    if family == "negative_binomial_scores":
        return fit_negative_binomial_scores(
            frame, training_seasons=training_seasons, nb2=config.nb2
        )
    raise MeasurementContractError(f"Unknown score model family: {family}")


def _prediction_covariance(
    model: ScoreModel, home_mean: np.ndarray, away_mean: np.ndarray
) -> np.ndarray:
    if model.family == "linear_scores":
        return np.broadcast_to(model.residual_covariance, (len(home_mean), 2, 2)).copy()
    dispersion = float(model.dispersion)
    home_variance = home_mean + dispersion * home_mean**2
    away_variance = away_mean + dispersion * away_mean**2
    covariance = float(model.residual_covariance[0, 1])
    maximum = 0.99 * np.sqrt(home_variance * away_variance)
    paired_covariance = np.clip(covariance, -maximum, maximum)
    values = np.zeros((len(home_mean), 2, 2), dtype=float)
    values[:, 0, 0] = home_variance
    values[:, 1, 1] = away_variance
    values[:, 0, 1] = paired_covariance
    values[:, 1, 0] = paired_covariance
    return values


def predict_score_model(
    model: ScoreModel, frame: pd.DataFrame, *, fold_id: str
) -> pd.DataFrame:
    rows = frame.copy()
    _, _, pair_design = _side_design(rows)
    home_design, away_design = pair_design[:, 0, :], pair_design[:, 1, :]
    if model.family == "linear_scores":
        home_mean = home_design @ model.coefficients
        away_mean = away_design @ model.coefficients
    else:
        home_mean = np.exp(np.clip(home_design @ model.coefficients, -20, 20))
        away_mean = np.exp(np.clip(away_design @ model.coefficients, -20, 20))
    if (
        not np.isfinite(home_mean).all()
        or not np.isfinite(away_mean).all()
        or (home_mean <= 0).any()
        or (away_mean <= 0).any()
    ):
        raise MeasurementContractError(
            "Score model emitted non-positive or non-finite score means"
        )
    covariance = _prediction_covariance(model, home_mean, away_mean)
    if not np.isfinite(covariance).all() or (np.linalg.eigvalsh(covariance) < 0).any():
        raise MeasurementContractError("Score covariance must be finite and PSD")
    home_variance, away_variance = covariance[:, 0, 0], covariance[:, 1, 1]
    paired_covariance = covariance[:, 0, 1]
    margin_mean, total_mean = home_mean - away_mean, home_mean + away_mean
    margin_variance = home_variance + away_variance - 2 * paired_covariance
    total_variance = home_variance + away_variance + 2 * paired_covariance
    if (margin_variance <= 0).any() or (total_variance <= 0).any():
        raise MeasurementContractError("Derived target variance must be positive")
    common = rows[
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
    common["fold_id"] = fold_id
    common["score_model_family"] = model.family
    common["predicted_home_score"] = home_mean
    common["predicted_away_score"] = away_mean
    common["home_score_sd"] = np.sqrt(home_variance)
    common["away_score_sd"] = np.sqrt(away_variance)
    common["score_covariance"] = paired_covariance
    common["distribution_family"] = (
        "bivariate_normal" if model.family == "linear_scores" else "nb2_moment_normal"
    )
    predictions: list[pd.DataFrame] = []
    for target, mean, variance, actual in (
        ("margin", margin_mean, margin_variance, rows["actual_margin"].to_numpy(float)),
        ("total", total_mean, total_variance, rows["actual_total"].to_numpy(float)),
    ):
        values = common.copy()
        sd = np.sqrt(variance)
        values["target"] = target
        values["actual"] = actual
        values["prediction_mean"] = mean
        values["prediction_sd"] = sd
        for label, z_score in Z_SCORES.items():
            values[f"interval_{label}_lower"] = mean - z_score * sd
            values[f"interval_{label}_upper"] = mean + z_score * sd
        predictions.append(values)
    return pd.concat(predictions, ignore_index=True)


def expanding_score_predictions(
    family: str, frame: pd.DataFrame, *, config: ScoreTournamentConfig
) -> tuple[pd.DataFrame, list[ScoreModel]]:
    predictions: list[pd.DataFrame] = []
    models: list[ScoreModel] = []
    for season in config.selection_seasons:
        training = tuple(year for year in config.historical_seasons if year < season)
        test = _complete_rows(frame[frame["season"] == season])
        model = fit_score_model(family, frame, training_seasons=training, config=config)
        models.append(model)
        predictions.append(
            predict_score_model(model, test, fold_id=f"expanding_{season}")
        )
    return pd.concat(predictions, ignore_index=True), models


def locked_score_predictions(
    family: str, frame: pd.DataFrame, *, config: ScoreTournamentConfig
) -> tuple[pd.DataFrame, ScoreModel]:
    training = tuple(
        year for year in config.historical_seasons if year < config.locked_season
    )
    model = fit_score_model(family, frame, training_seasons=training, config=config)
    test = _complete_rows(frame[frame["season"] == config.locked_season])
    return predict_score_model(
        model, test, fold_id=f"locked_{config.locked_season}"
    ), model


def tournament_selection(
    *,
    frame: pd.DataFrame,
    v4: pd.DataFrame,
    config: ScoreTournamentConfig,
) -> tuple[str | None, dict[str, Any], dict[str, list[ScoreModel]]]:
    report: dict[str, Any] = {
        "report_schema_version": "rating_score_tournament_v2",
        "selection_seasons": list(config.selection_seasons),
        "candidates": {},
    }
    models_by_family: dict[str, list[ScoreModel]] = {}
    eligible: list[tuple[float, str]] = []
    for family in config.candidates:
        try:
            predictions, models = expanding_score_predictions(
                family, frame, config=config
            )
            evaluation = evaluate_predictions(
                predictions=predictions, v4=v4, gates=config.gates
            )
        except MeasurementContractError as exc:
            report["candidates"][family] = {
                "selection_error": str(exc),
                "all_checks_passed": False,
            }
            models_by_family[family] = []
            continue
        ratio = float(
            np.mean(
                [
                    evaluation["targets"][target]["candidate"]["mae"]
                    / evaluation["targets"][target]["v4"]["mae"]
                    for target in ("margin", "total")
                ]
            )
        )
        report["candidates"][family] = {
            "selection_evaluation": evaluation,
            "mean_mae_ratio_to_v4": ratio,
            "all_checks_passed": evaluation["all_checks_passed"],
        }
        models_by_family[family] = models
        if evaluation["all_checks_passed"]:
            eligible.append((ratio, family))
    if not eligible:
        report["winner"] = None
        report["all_selection_checks_passed"] = False
        return None, report, models_by_family
    eligible.sort()
    winner_ratio, winner = eligible[0]
    if len(eligible) > 1 and eligible[1][0] - winner_ratio <= float(
        config.selection["mae_ratio_tie"]
    ):
        winner = str(config.selection["tie_winner"])
    report["winner"] = winner
    report["all_selection_checks_passed"] = True
    return winner, report, models_by_family


def model_record(model: ScoreModel) -> dict[str, Any]:
    return {
        "family": model.family,
        "training_seasons": list(model.training_seasons),
        "feature_names": list(FEATURE_NAMES),
        "coefficients": json.dumps(
            dict(zip(FEATURE_NAMES, model.coefficients.tolist())), sort_keys=True
        ),
        "residual_covariance": json.dumps(model.residual_covariance.tolist()),
        "dispersion": model.dispersion,
        "optimizer_success": model.optimizer_success,
    }
