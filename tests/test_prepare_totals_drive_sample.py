import pandas as pd

from scripts.research.prepare_totals_drive_sample import (
    COUNTS,
    load_point_in_time_data,
    measure_drives,
    reconcile_and_count,
)


def test_drive_measurements_distinguish_no_opportunities_and_excluded_scoring():
    play = {
        "season": 2025,
        "game_id": 1,
        "offense": "Ohio State",
        "quarter": 1,
        "play_number": 1,
        "st": 0,
        "penalty": 0,
        "twopoint": 0,
        "garbage": 0,
        "play_type": "Rush",
        "down": 1,
    }
    plays = pd.DataFrame(
        [
            dict(play, drive_number=1, yards_to_goal=27),
            dict(play, drive_number=2, yards_to_goal=70),
            dict(play, drive_number=3, yards_to_goal=10, garbage=1),
            dict(play, drive_number=4, yards_to_goal=None),
        ]
    )
    possessions = plays[["season", "game_id", "offense", "drive_number"]].assign(
        possession_eligible=[True, True, False, True],
        defense="Michigan",
        period_class="regulation",
        quality_reason=None,
    )
    scoring = pd.DataFrame(
        [
            (2025, 1, "Ohio State", "eligible_regulation_offense", "2025:1:1:1", 7),
            (2025, 1, "Ohio State", "excluded_regulation_offense", "2025:1:3:1", 7),
        ],
        columns=[
            "season",
            "game_id",
            "team",
            "scoring_category",
            "associated_possession_id",
            "score_increment",
        ],
    )
    result = measure_drives(plays, possessions, scoring).set_index("drive_number")
    assert result.index.tolist() == [1, 2, 4]
    assert result["known"].tolist() == [True, True, False]
    assert result["created"].tolist() == [True, False, False]
    assert result["points"].sum() == 7
    finals = pd.DataFrame(
        [(2025, 1, "Ohio State", "Michigan", 14, 0)],
        columns=[
            "season",
            "game_id",
            "home_team",
            "away_team",
            "home_points",
            "away_points",
        ],
    )
    matched = reconcile_and_count(result.reset_index(), scoring, finals)
    assert matched["opportunity_points"].sum() == 7
    assert matched["finals_reconciled"].all()
    finals.loc[0, "home_points"] = 21
    mismatched = reconcile_and_count(result.reset_index(), scoring, finals)
    assert mismatched["opportunities_with_known_points"].sum() == 0
    assert mismatched["opportunities"].sum() == 1


def test_pregame_sample_uses_only_prior_week_available_games():
    source = pd.DataFrame(
        [
            (2025, 1, 1, "2025-09-01T16:00Z"),
            (2025, 2, 2, "2025-09-06T12:00Z"),
            (2025, 1, 3, "2025-09-06T17:00Z"),
            (2025, 2, 4, "2025-09-06T23:00Z"),
        ],
        columns=["season", "week", "game_id", "kickoff_utc"],
    )
    forecasts = (
        source.loc[source["week"].eq(2)]
        .assign(home_team="Ohio State", away_team="Michigan")
        .reset_index(drop=True)
    )
    counts = pd.DataFrame(
        [(2025, n, "Ohio State", "Michigan", 1, 1, 0, 0, 0, 1, 68) for n in (1, 2, 3)],
        columns=["season", "game_id", "offense", "defense", *COUNTS],
    )
    result = load_point_in_time_data(forecasts, source, counts)
    assert result["home_off_eligible_drives"].tolist() == [1, 1]
    assert result["home_off_opportunities_per_eligible_drive"].tolist() == [0, 0]
    assert result["home_off_points_per_opportunity"].isna().all()
    assert result["away_off_opportunities_per_eligible_drive"].isna().all()
    assert result["away_def_starting_yards_to_goal"].tolist() == [68, 68]
