"""Point-in-time safeguards for retrospectively reconstructed V5 games."""

import pandas as pd

from cks_picks_cfb.forecast.replay import build_replay_application_frame


def _inputs():
    population = pd.DataFrame(
        [
            {
                "season": 2026,
                "week": week,
                "game_id": game_id,
                "kickoff_utc": f"2026-09-{day:02d}T18:00:00Z",
                "home_team": home,
                "away_team": away,
                "forecast_eligible": True,
                "schedule_completed": True,
                "outcome_valid": True,
            }
            for week, game_id, day, home, away in (
                (0, 1, 1, "A", "B"),
                (1, 2, 8, "A", "C"),
                (2, 3, 15, "B", "C"),
            )
        ]
    )
    states = pd.DataFrame(
        [
            {
                "season": 2026,
                "game_id": game_id,
                "cutoff_utc": f"2026-09-{day:02d}T18:00:00Z",
                "team": team,
                "offense_rating": week + 0.1,
                "defense_rating": week + 0.2,
            }
            for week, game_id, day, teams in (
                (0, 1, 1, ("A", "B")),
                (1, 2, 8, ("A", "C")),
                (2, 3, 15, ("B", "C")),
            )
            for team in teams
        ]
    )
    offsets = pd.DataFrame(
        [
            {
                "season": 2026,
                "week": week,
                "game_id": game_id,
                "offset_margin": 0.0,
                "offset_total": 1.0,
            }
            for week, game_id in ((0, 1), (1, 2), (2, 3))
        ]
    )
    return population, states, offsets


def test_replay_uses_opening_priors_and_earlier_games_after_bye():
    population, states, offsets = _inputs()
    result = build_replay_application_frame(population, states, offsets)
    assert result.gaps.empty
    assert result.features["completed_game_stage"].tolist() == [0, 0, 1]
    assert result.features["home_offense"].tolist() == [0.1, 1.1, 2.1]
    assert result.features["offset_total"].tolist() == [1.0, 1.0, 1.0]


def test_replay_reports_missing_and_future_states_without_dropping_games_silently():
    population, states, offsets = _inputs()
    states = states[~((states["game_id"] == 2) & (states["team"] == "C"))]
    states.loc[states["game_id"].eq(3), "cutoff_utc"] = "2026-09-16T18:00:00Z"
    result = build_replay_application_frame(population, states, offsets)
    assert result.features["game_id"].tolist() == [1]
    assert result.gaps.set_index("game_id")["reason"].to_dict() == {
        2: "missing_pregame_state_or_offset",
        3: "late_rating_state",
    }


def test_replay_does_not_accept_an_offset_from_another_week():
    population, states, offsets = _inputs()
    offsets.loc[offsets["game_id"].eq(2), "week"] = 3
    result = build_replay_application_frame(population, states, offsets)
    assert (
        result.gaps.set_index("game_id").loc[2, "reason"]
        == "missing_pregame_state_or_offset"
    )
