"""Direct descriptive formulas and the real chart eligibility boundary."""

import numpy as np
import pandas as pd
import pytest

from scripts.research.compare_chart_explosiveness import (
    aggregate,
    compare,
    measures,
    validate_direct,
)


def test_independent_finite_observations_and_successful_yards_formula():
    plays = pd.DataFrame(
        {
            "yards_gained": [25, 5, 30, np.nan, np.inf, -2],
            "success": [1, 1, 0, 1, 1, np.nan],
            "ppa": [1, np.nan, np.inf, 2, 3, 4],
            "ppa_missing": [False, False, False, True, False, False],
        }
    )
    result = measures(plays)
    assert result["yardage_n"] == 4
    assert result["explosive_n"] == 2
    assert result["explosive_rate"] == 0.5
    assert result["successful_yards_n"] == 2
    assert result["successful_yards_sum"] == 30
    assert result["yards_per_success"] == 15  # not all yardage / successes
    assert result["success_n"] == 5
    assert result["success_rate"] == 0.8
    assert result["ppa_n"] == 3
    assert result["ppa_per_play"] == pytest.approx(8 / 3)


def test_zero_explosives_zero_successes_and_zero_exposure():
    result = measures(
        pd.DataFrame(
            {"yards_gained": [2, -4], "success": [0, 0], "ppa": [np.nan, np.inf]}
        )
    )
    assert result["explosive_rate"] == 0
    assert result["yards_per_success"] is None
    assert result["ppa_per_play"] is None
    result = measures(
        pd.DataFrame({"yards_gained": [np.nan], "success": [1], "ppa": [1]})
    )
    assert result["explosive_rate"] is None
    assert result["yards_per_success"] is None
    assert result["success_rate"] == 1


def fixture_frames():
    games = pd.DataFrame(
        [
            {
                "season": 2026,
                "week": week,
                "game_id": game,
                "home_team": home,
                "away_team": away,
                "season_type": "regular",
            }
            for game, week, home, away in (
                (1, 2, "A", "B"),
                (2, 3, "A", "B"),
                (3, 7, "A", "B"),
                (4, 1, "A", "FCS"),
                (5, 1, "A", "B"),
            )
        ]
    )
    finals = pd.DataFrame(
        [
            {"season": 2026, "game_id": game, "home_points": 20, "away_points": 10}
            for game in (1, 2, 3, 4)
        ]
    )
    plays = []
    for game, offense, defense, yards, success in (
        (1, "A", "B", 25, 1),
        (1, "A", "B", 5, 1),
        (1, "B", "A", 1, 0),
        (2, "A", "B", 80, 1),
        (2, "B", "A", 20, 1),
        (3, "A", "B", 99, 1),
        (4, "A", "FCS", 99, 1),
        (5, "A", "B", 99, 1),
    ):
        plays.append(
            {
                "season": 2026,
                "game_id": game,
                "offense": offense,
                "defense": defense,
                "yards_gained": yards,
                "success": success,
                "ppa": 0.2,
                "quarter": 1,
                "st": 0,
                "penalty": 0,
                "twopoint": 0,
                "garbage": 0,
                "play_type": "Rush",
            }
        )
    excluded = {**plays[0], "yards_gained": 99, "quarter": 5}
    plays.extend(
        [
            excluded,
            {**excluded, "quarter": 1, "garbage": 1},
            {**excluded, "quarter": 1, "play_type": "Punt Return"},
        ]
    )
    teams = pd.DataFrame(
        {
            "team": ["A", "B", "C", "FCS"],
            "classification": ["fbs", "fbs", "fbs", "fcs"],
            "conference": ["X"] * 4,
        }
    )
    return {
        "schedule": games,
        "finals": finals,
        "byplay": pd.DataFrame(plays),
        "teams": teams,
    }


def test_windows_mirror_defense_and_exclude_later_uncompleted_fcs_and_ineligible_plays():
    result, contexts, games = compare(fixture_frames(), season=2026, active_week=7)
    assert set(games.game_id) == {1, 2}
    assert set(contexts.game_id) == {1, 2}
    assert set(result.through_week) == {2, 3, 4, 5, 6}
    early = result[result.through_week.eq(2)]
    offense = early[early.side.eq("offense") & early.team.eq("A")].iloc[0]
    defense = early[early.side.eq("defense") & early.team.eq("B")].iloc[0]
    for key in (
        "plays",
        "yardage_n",
        "explosive_n",
        "explosive_rate",
        "successful_yards_n",
        "successful_yards_sum",
        "yards_per_success",
        "success_rate",
        "ppa_per_play",
    ):
        assert offense[key] == defense[key]
    assert offense.plays == 2
    assert offense.yards_per_success == 15
    assert offense.without_longest_yards_per_success == 5
    assert offense.longest_game_id == 1
    late = result[
        result.through_week.eq(3) & result.side.eq("offense") & result.team.eq("A")
    ].iloc[0]
    assert late.plays == 3
    assert late.yards_per_success == pytest.approx(110 / 3)
    assert late.longest_game_id == 2
    absent = early[early.team.eq("C")]
    assert absent.explosive_rate.isna().all()
    assert absent.yards_per_success.isna().all()
    assert absent.yardage_n.eq(0).all()


def test_removing_unsuccessful_longest_gain_preserves_successful_play_denominator():
    frames = fixture_frames()
    frames["byplay"].loc[0, "success"] = 0
    result, _, _ = compare(frames, season=2026, active_week=7)
    point = result[
        result.through_week.eq(2) & result.side.eq("offense") & result.team.eq("A")
    ].iloc[0]
    assert point.yards_per_success == point.without_longest_yards_per_success == 5
    assert point.successful_yards_n == point.without_longest_successful_yards_n == 1
    assert point.without_longest_explosive_rate == 0


def test_aggregate_zero_exposure_stays_null_and_direct_receipt_checks_all_windows():
    frames = fixture_frames()
    result, contexts, _ = compare(frames, season=2026, active_week=7)
    receipt = validate_direct(frames, result, contexts, season=2026, active_week=7)
    assert receipt["direct_formula_values_checked"] == len(result) * 7
    assert receipt["eligible_plays"] == 5
    frames["byplay"]["yards_gained"] = np.nan
    empty, _, _ = compare(frames, season=2026, active_week=7)
    distributions, _ = aggregate(empty)
    assert distributions.pooled.isna().all()
    assert distributions.observed.eq(0).all()
