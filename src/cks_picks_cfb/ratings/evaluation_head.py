"""Fixed Gaussian evaluation head for R2/R3 fold evidence generation.

This module implements a minimal OLS team-score model that converts pregame
team states into margin and total predictions.  It is deliberately independent
of V4 inference, market inputs, and team-identity features.

The head is re-fitted inside each fold on training seasons only; it never
sees game outcomes from the target season.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


class EvaluationHeadError(ValueError):
    """Raised for invalid inputs to the evaluation head."""


EVALUATION_HEAD_VERSION = "gaussian_head_v1"

# State input columns used as features — no team ID, no market data
_OFFENSE_FEATURE = "offense_mean"
_DEFENSE_FEATURE = "defense_mean"
_REQUIRED_TEAM_STATE_COLS = {
    "team",
    "season",
    "game_id",
    "offense_mean",
    "defense_mean",
}
_REQUIRED_OUTCOME_COLS = {
    "game_id",
    "home_team",
    "away_team",
    "home_points",
    "away_points",
}


@dataclass(frozen=True)
class GaussianHead:
    """Fitted OLS coefficients for home/away score prediction."""

    margin_coef: np.ndarray  # shape (4,): home_off, home_def, away_off, away_def
    margin_intercept: float
    total_coef: np.ndarray
    total_intercept: float
    train_seasons: tuple[int, ...]
    n_train_games: int
    version: str = EVALUATION_HEAD_VERSION


def _build_matchup_features(
    team_states: pd.DataFrame,
    outcomes: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[int]]:
    """Join team states onto outcomes and return (X, y_margin, y_total, game_ids)."""
    # Keep only one state per (season, game_id, team) — use the pregame state
    states = team_states.copy()
    if "state_kind" in states.columns:
        states = states[states["state_kind"] == "pregame"]
    # Deduplicate: keep the last pregame state before each game
    states = states.sort_values(["season", "game_id", "team"]).drop_duplicates(
        subset=["season", "game_id", "team"], keep="last"
    )

    X: list[np.ndarray] = []  # noqa: N806
    y_margin: list[float] = []
    y_total: list[float] = []
    game_ids: list[int] = []

    for row in outcomes.itertuples(index=False):
        gid = int(row.game_id)
        home = str(row.home_team)
        away = str(row.away_team)
        home_pts = float(row.home_points)
        away_pts = float(row.away_points)
        if not (np.isfinite(home_pts) and np.isfinite(away_pts)):
            continue

        home_state = states[
            (states["game_id"].astype(str) == str(gid))
            & (states["team"].astype(str) == home)
        ]
        away_state = states[
            (states["game_id"].astype(str) == str(gid))
            & (states["team"].astype(str) == away)
        ]
        if home_state.empty or away_state.empty:
            continue

        ho = float(home_state[_OFFENSE_FEATURE].iloc[0])
        hd = float(home_state[_DEFENSE_FEATURE].iloc[0])
        ao = float(away_state[_OFFENSE_FEATURE].iloc[0])
        ad = float(away_state[_DEFENSE_FEATURE].iloc[0])
        if not np.isfinite([ho, hd, ao, ad]).all():
            continue

        X.append(np.array([ho, hd, ao, ad]))
        y_margin.append(home_pts - away_pts)
        y_total.append(home_pts + away_pts)
        game_ids.append(gid)

    if not X:
        return np.empty((0, 4)), np.array([]), np.array([]), []

    return np.array(X), np.array(y_margin), np.array(y_total), game_ids


def fit_gaussian_head(
    *,
    team_states: pd.DataFrame,
    game_outcomes: pd.DataFrame,
    train_seasons: tuple[int, ...],
) -> GaussianHead:
    """Fit the OLS head on training-fold team states and outcomes.

    Parameters
    ----------
    team_states:
        Pregame team states for all training seasons. Must contain
        ``team``, ``season``, ``game_id``, ``offense_mean``, ``defense_mean``.
    game_outcomes:
        Completed game outcomes for all training seasons. Must contain
        ``game_id``, ``home_team``, ``away_team``, ``home_points``, ``away_points``.
    train_seasons:
        The seasons used for fitting — must all precede the target fold season.
    """
    missing_state = _REQUIRED_TEAM_STATE_COLS - set(team_states.columns)
    missing_outcome = _REQUIRED_OUTCOME_COLS - set(game_outcomes.columns)
    if missing_state:
        raise EvaluationHeadError(
            f"team_states missing columns: {sorted(missing_state)}"
        )
    if missing_outcome:
        raise EvaluationHeadError(
            f"game_outcomes missing columns: {sorted(missing_outcome)}"
        )
    if 2020 in train_seasons or 2025 in train_seasons or 2026 in train_seasons:
        raise EvaluationHeadError("Forbidden seasons in train_seasons")

    # Filter to training seasons only
    state_mask = pd.to_numeric(team_states["season"], errors="coerce").isin(
        train_seasons
    )
    outcome_mask = pd.to_numeric(
        game_outcomes.get("season", pd.Series(dtype=float)), errors="coerce"
    ).isin(train_seasons)
    train_states = team_states[state_mask]
    train_outcomes = (
        game_outcomes[outcome_mask]
        if "season" in game_outcomes.columns
        else game_outcomes
    )

    X, y_margin, y_total, _ = _build_matchup_features(train_states, train_outcomes)  # noqa: N806
    if len(X) < 4:
        raise EvaluationHeadError(
            f"Insufficient training games ({len(X)}) for evaluation head fit"
        )

    # OLS with intercept: solve (X'X)^{-1} X'y
    X_aug = np.column_stack([X, np.ones(len(X))])  # noqa: N806
    coef_margin, *_ = np.linalg.lstsq(X_aug, y_margin, rcond=None)
    coef_total, *_ = np.linalg.lstsq(X_aug, y_total, rcond=None)

    return GaussianHead(
        margin_coef=coef_margin[:4],
        margin_intercept=float(coef_margin[4]),
        total_coef=coef_total[:4],
        total_intercept=float(coef_total[4]),
        train_seasons=tuple(sorted(train_seasons)),
        n_train_games=len(X),
    )


def predict_gaussian_head(
    *,
    head: GaussianHead,
    team_states: pd.DataFrame,
    game_outcomes: pd.DataFrame,
    target_season: int,
) -> pd.DataFrame:
    """Generate margin and total predictions for the target fold season.

    Parameters
    ----------
    head:
        The fitted GaussianHead from ``fit_gaussian_head``.
    team_states:
        Pregame team states for the target season.
    game_outcomes:
        Game outcomes (used for game_id / home_team / away_team linkage and
        completed_games count; actual scores are recorded but not used for
        prediction).
    target_season:
        The target fold season being evaluated.
    """
    if target_season in (2020, 2025, 2026):
        raise EvaluationHeadError(f"Forbidden target season {target_season}")
    if target_season in head.train_seasons:
        raise EvaluationHeadError(
            f"Target season {target_season} appeared in training; data leakage risk"
        )

    state_mask = pd.to_numeric(team_states["season"], errors="coerce") == target_season
    target_states = team_states[state_mask]
    outcome_mask = (
        pd.to_numeric(
            game_outcomes.get("season", pd.Series(dtype=float)), errors="coerce"
        )
        == target_season
        if "season" in game_outcomes.columns
        else pd.Series([True] * len(game_outcomes))
    )
    target_outcomes = game_outcomes[outcome_mask]

    X, y_margin, y_total, game_ids = _build_matchup_features(  # noqa: N806
        target_states, target_outcomes
    )
    if len(X) == 0:
        return pd.DataFrame(
            columns=[
                "game_id",
                "season",
                "predicted_margin",
                "predicted_total",
                "actual_margin",
                "actual_total",
                "completed_games",
            ]
        )

    X_aug = np.column_stack([X, np.ones(len(X))])  # noqa: N806
    pred_margin = X_aug @ np.append(head.margin_coef, head.margin_intercept)
    pred_total = X_aug @ np.append(head.total_coef, head.total_intercept)

    # Look up completed_games from team states
    states_by_gid: dict[int, int] = {}
    if "completed_games" in target_states.columns:
        for gid, grp in target_states.groupby("game_id"):
            states_by_gid[int(gid)] = int(grp["completed_games"].max())

    rows: list[dict[str, Any]] = []
    for i, gid in enumerate(game_ids):
        rows.append(
            {
                "game_id": gid,
                "season": target_season,
                "predicted_margin": float(pred_margin[i]),
                "predicted_total": float(pred_total[i]),
                "actual_margin": float(y_margin[i]),
                "actual_total": float(y_total[i]),
                "completed_games": states_by_gid.get(gid, 0),
            }
        )

    return pd.DataFrame(rows)


def fold_metrics(
    predictions: pd.DataFrame, candidate_id: str, season: int
) -> dict[str, Any]:
    """Compute early/full MAE and bias metrics from a predictions DataFrame.

    Returns a dict compatible with ``successor_tournaments.select_from_fold_metrics``.
    """
    if predictions.empty:
        raise EvaluationHeadError(f"No predictions for {candidate_id} season {season}")

    required = {
        "predicted_margin",
        "predicted_total",
        "actual_margin",
        "actual_total",
        "completed_games",
    }
    missing = required - set(predictions.columns)
    if missing:
        raise EvaluationHeadError(f"predictions missing columns: {sorted(missing)}")

    if (
        predictions["season"].astype(int).eq(2020).any()
        or predictions["season"].astype(int).eq(2025).any()
    ):
        raise EvaluationHeadError("Forbidden season in predictions")

    # Early season = completed_games in 1..3
    early = predictions[predictions["completed_games"].astype(int).between(1, 3)]
    full = predictions[predictions["completed_games"].astype(int) >= 1]

    def _mae(df: pd.DataFrame, pred_col: str, actual_col: str) -> float:
        if df.empty:
            return float("nan")
        return float(
            np.abs(df[pred_col].to_numpy(float) - df[actual_col].to_numpy(float)).mean()
        )

    return {
        "candidate_id": candidate_id,
        "season": season,
        "early_margin_mae": _mae(early, "predicted_margin", "actual_margin"),
        "early_total_mae": _mae(early, "predicted_total", "actual_total"),
        "full_margin_mae": _mae(full, "predicted_margin", "actual_margin"),
        "full_total_mae": _mae(full, "predicted_total", "actual_total"),
        "early_n": len(early),
        "full_n": len(full),
    }
