"""Fail-closed comparison of successor R1 and legacy comparison evidence."""

from __future__ import annotations

from typing import Mapping

import pandas as pd

HARD_DATASETS = ("games", "game_outcomes", "teams")


def _completed_mask(frame: pd.DataFrame) -> pd.Series:
    return frame["completed"].astype(str).str.strip().str.lower().isin(("true", "1"))


def _column(frame: pd.DataFrame, *candidates: str) -> str:
    for candidate in candidates:
        if candidate in frame.columns:
            return candidate
    raise ValueError(
        f"missing canonical comparison column; expected one of {candidates}"
    )


def _games(frame: pd.DataFrame, season: int) -> dict[int, tuple[str, str]]:
    game_id = _column(frame, "game_id", "id")
    home = _column(frame, "home_team", "home")
    away = _column(frame, "away_team", "away")
    scoped = frame[pd.to_numeric(frame["season"], errors="coerce") == season]
    if (
        scoped.duplicated([game_id]).any()
        or scoped[[game_id, home, away]].isna().any().any()
    ):
        raise ValueError(f"games {season} has duplicate or incomplete identity keys")
    return {
        int(row[0]): (str(row[1]), str(row[2]))
        for row in scoped[[game_id, home, away]].itertuples(index=False, name=None)
    }


def _scores(
    frame: pd.DataFrame, season: int
) -> tuple[dict[int, tuple[float, float]], set[int]]:
    game_id = _column(frame, "game_id", "id")
    home = _column(frame, "home_points", "home_score")
    away = _column(frame, "away_points", "away_score")
    scoped = frame[pd.to_numeric(frame["season"], errors="coerce") == season]
    if scoped.duplicated([game_id]).any():
        raise ValueError(f"outcomes {season} has duplicate game identity keys")
    incomplete_mask = scoped[[home, away]].isna().any(axis=1)
    completed_column = "completed" in scoped.columns
    if completed_column:
        scored_but_unplayed = scoped[incomplete_mask & _completed_mask(scoped)]
        if not scored_but_unplayed.empty:
            raise ValueError(
                f"outcomes {season} has completed games with missing scores: "
                f"{sorted(scored_but_unplayed[game_id].astype(int))}"
            )
    scored = scoped[~incomplete_mask]
    return (
        {
            int(row[0]): (float(row[1]), float(row[2]))
            for row in scored[[game_id, home, away]].itertuples(index=False, name=None)
        },
        set(scoped.loc[incomplete_mask, game_id].astype(int)),
    )


def _teams(frame: pd.DataFrame, season: int) -> set[str]:
    name = _column(frame, "school", "team", "name")
    scoped = frame
    if "season" in frame.columns:
        scoped = frame[pd.to_numeric(frame["season"], errors="coerce") == season]
    values = {str(value) for value in scoped[name].dropna()}
    if not values:
        raise ValueError(f"teams {season} has no canonical team identities")
    return values


def compare_season(
    *,
    season: int,
    successor: Mapping[str, pd.DataFrame],
    legacy: Mapping[str, pd.DataFrame],
) -> dict[str, bool]:
    """Compare hard R1 lineage identities for one historical season."""

    if set(successor) != set(HARD_DATASETS) or set(legacy) != set(HARD_DATASETS):
        raise ValueError("cross-lineage comparison requires exactly the hard datasets")
    current_games = _games(successor["games"], season)
    prior_games = _games(legacy["games"], season)
    current_scored, current_incomplete = _scores(successor["game_outcomes"], season)
    prior_scored, prior_incomplete = _scores(legacy["game_outcomes"], season)
    current_teams = _teams(successor["teams"], season)
    prior_teams = _teams(legacy["teams"], season)
    return {
        # games and game_outcomes carry different scopes by Silver design
        # (games is both-teams-FBS only); each dataset is compared against
        # its own legacy counterpart, never across scopes.
        "season_membership_ok": set(current_games) == set(prior_games)
        and set(current_scored) | current_incomplete
        == set(prior_scored) | prior_incomplete,
        "game_identity_ok": current_games == prior_games,
        "team_identity_ok": current_teams == prior_teams,
        "scores_ok": current_scored == prior_scored
        and current_incomplete == prior_incomplete,
    }
