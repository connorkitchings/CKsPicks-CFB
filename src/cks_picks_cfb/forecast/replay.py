"""Point-in-time 2026 V5 replay inputs from certified pregame team states."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class ReplayFrame:
    features: pd.DataFrame
    state_refs: dict[int, str]
    gaps: pd.DataFrame


def build_replay_application_frame(
    population: pd.DataFrame,
    team_states: pd.DataFrame,
    offsets: pd.DataFrame,
) -> ReplayFrame:
    """Build game-specific features without using any same-game outcome.

    Gaps stay explicit so an incomplete historical capture does not silently
    shrink a published season or acquire a fabricated forecast.
    """
    required_population = {
        "season",
        "week",
        "game_id",
        "kickoff_utc",
        "home_team",
        "away_team",
        "forecast_eligible",
        "schedule_completed",
        "outcome_valid",
    }
    required_states = {
        "season",
        "game_id",
        "cutoff_utc",
        "team",
        "offense_rating",
        "defense_rating",
    }
    required_offsets = {"season", "week", "game_id", "offset_margin", "offset_total"}
    for label, frame, required in (
        ("population", population, required_population),
        ("team states", team_states, required_states),
        ("offsets", offsets, required_offsets),
    ):
        if missing := sorted(required - set(frame)):
            raise ValueError(f"replay {label} lacks columns: {missing}")
    games = population[
        population["season"].eq(2026) & population["forecast_eligible"].eq(True)
    ].copy()
    if games.duplicated("game_id").any():
        raise ValueError("replay population duplicates a game")
    games["kickoff_utc"] = pd.to_datetime(games["kickoff_utc"], utc=True)
    games = games.sort_values(["kickoff_utc", "game_id"], kind="mergesort")
    records: list[dict] = []
    gaps: list[dict] = []
    state_refs: dict[int, str] = {}
    for game in games.itertuples(index=False):
        game_id = int(game.game_id)
        if not bool(game.schedule_completed) or not bool(game.outcome_valid):
            gaps.append(
                {
                    "season": 2026,
                    "week": int(game.week),
                    "game_id": game_id,
                    "reason": "unsettled_game",
                }
            )
            continue
        states = team_states[
            team_states["season"].eq(2026) & team_states["game_id"].eq(game_id)
        ]
        home = states[states["team"].eq(str(game.home_team))]
        away = states[states["team"].eq(str(game.away_team))]
        offset = offsets[
            offsets["season"].eq(2026)
            & offsets["week"].eq(int(game.week))
            & offsets["game_id"].eq(game_id)
        ]
        if len(home) != 1 or len(away) != 1 or len(offset) != 1:
            gaps.append(
                {
                    "season": 2026,
                    "week": int(game.week),
                    "game_id": game_id,
                    "reason": "missing_pregame_state_or_offset",
                }
            )
            continue
        cutoff = pd.Timestamp(game.kickoff_utc)
        if any(
            pd.Timestamp(state.iloc[0]["cutoff_utc"]).tz_convert("UTC") > cutoff
            for state in (home, away)
        ):
            gaps.append(
                {
                    "season": 2026,
                    "week": int(game.week),
                    "game_id": game_id,
                    "reason": "late_rating_state",
                }
            )
            continue
        earlier = games[
            games["kickoff_utc"].lt(cutoff)
            & games["schedule_completed"].eq(True)
            & games["outcome_valid"].eq(True)
        ]
        counts = [
            int((earlier["home_team"].eq(team) | earlier["away_team"].eq(team)).sum())
            for team in (str(game.home_team), str(game.away_team))
        ]
        home_row, away_row, offset_row = home.iloc[0], away.iloc[0], offset.iloc[0]
        records.append(
            {
                "season": 2026,
                "week": int(game.week),
                "game_id": game_id,
                "home_offense": float(home_row["offense_rating"]),
                "home_defense": float(home_row["defense_rating"]),
                "away_offense": float(away_row["offense_rating"]),
                "away_defense": float(away_row["defense_rating"]),
                "home_host": 1.0,
                "venue_unknown": True,
                "offset_margin": float(offset_row["offset_margin"]),
                "offset_total": float(offset_row["offset_total"]),
                "completed_game_stage": min(counts),
            }
        )
        state_refs[game_id] = (
            f"team_states/{game_id}#{game.home_team}|team_states/{game_id}#{game.away_team}"
        )
    return ReplayFrame(
        features=pd.DataFrame.from_records(records),
        state_refs=state_refs,
        gaps=pd.DataFrame.from_records(
            gaps, columns=["season", "week", "game_id", "reason"]
        ),
    )
