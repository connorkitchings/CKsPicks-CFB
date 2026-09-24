"""Accepted historical bridge features shared by audit and inference export."""

from __future__ import annotations

import pandas as pd

from cks_picks_cfb.data.data_first_forecast_v1 import REQUIRED_RATING_CANDIDATE


def _pregame_completed_counts(games: pd.DataFrame) -> pd.DataFrame:
    """Per-team pregame counts of earlier completed eligible games in-season.

    ``possession_rating_state.completed_games`` counts assimilated
    observations (boundary cutoffs), not completed-game regimes; the regime
    stage must come from the eligible completed schedule itself, ordered by
    ``(kickoff_utc, game_id)`` with the current game excluded.
    """
    rows: list[dict[str, object]] = []
    ordered = games.sort_values(["season", "kickoff_utc", "game_id"], kind="mergesort")
    for season, season_games in ordered.groupby("season", sort=True):
        counts: dict[str, int] = {}
        for row in season_games.itertuples(index=False):
            home, away = str(row.home_team), str(row.away_team)
            for team in (home, away):
                rows.append(
                    {
                        "season": int(season),
                        "game_id": int(row.game_id),
                        "team": team,
                        "completed_games": counts.get(team, 0),
                    }
                )
            counts[home] = counts.get(home, 0) + 1
            counts[away] = counts.get(away, 0) + 1
    frame = pd.DataFrame.from_records(rows)
    if frame.duplicated(subset=["season", "game_id", "team"]).any():
        raise ValueError("pregame completed counts are not unique per team-game")
    return frame


def _feature_frame(
    *,
    population: pd.DataFrame,
    outcomes: pd.DataFrame,
    team_states: pd.DataFrame,
    offsets: pd.DataFrame,
) -> pd.DataFrame:
    games = population[population["forecast_eligible"].astype(bool)].merge(
        outcomes[outcomes["completed"].astype(bool)],
        on=["season", "game_id"],
        how="inner",
        validate="one_to_one",
    )
    selected = team_states[
        team_states["candidate_id"].eq(REQUIRED_RATING_CANDIDATE)
    ].copy()
    home = selected.rename(
        columns={
            "team": "home_team",
            "offense_rating": "home_offense",
            "defense_rating": "home_defense",
        }
    )
    away = selected.rename(
        columns={
            "team": "away_team",
            "offense_rating": "away_offense",
            "defense_rating": "away_defense",
        }
    )
    counts = _pregame_completed_counts(games)
    home_counts = counts.rename(
        columns={"team": "home_team", "completed_games": "home_completed"}
    )
    away_counts = counts.rename(
        columns={"team": "away_team", "completed_games": "away_completed"}
    )
    frame = games.merge(
        home[
            [
                "season",
                "game_id",
                "home_team",
                "home_offense",
                "home_defense",
            ]
        ],
        on=["season", "game_id", "home_team"],
        how="inner",
        validate="one_to_one",
    )
    frame = frame.merge(
        away[
            [
                "season",
                "game_id",
                "away_team",
                "away_offense",
                "away_defense",
            ]
        ],
        on=["season", "game_id", "away_team"],
        how="inner",
        validate="one_to_one",
    )
    frame = frame.merge(
        home_counts[["season", "game_id", "home_team", "home_completed"]],
        on=["season", "game_id", "home_team"],
        how="inner",
        validate="one_to_one",
    )
    frame = frame.merge(
        away_counts[["season", "game_id", "away_team", "away_completed"]],
        on=["season", "game_id", "away_team"],
        how="inner",
        validate="one_to_one",
    )
    frame = frame.merge(
        offsets, on=["season", "week", "game_id"], how="inner", validate="one_to_one"
    )
    frame["home_host"] = 1.0
    frame["venue_unknown"] = True
    frame["actual_margin"] = frame["home_points"].astype(float) - frame[
        "away_points"
    ].astype(float)
    frame["actual_total"] = frame["home_points"].astype(float) + frame[
        "away_points"
    ].astype(float)
    frame["completed_game_stage"] = (
        frame[["home_completed", "away_completed"]]
        .min(axis=1)
        .clip(upper=4)
        .astype(int)
    )
    return frame
