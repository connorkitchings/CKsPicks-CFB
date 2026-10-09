import pandas as pd

from scripts.analysis.play_order_diagnostic import (
    ordering_comparison,
    period_reset_events,
    prepare,
    summarize_season,
)

COLUMNS = [
    "game_id",
    "period",
    "drive_number",
    "play_number",
    "play_id",
    "clock_minutes",
    "clock_seconds",
    "play_type",
]


def plays(rows):
    return pd.DataFrame(rows, columns=COLUMNS)


def test_reset_to_a_fresh_clock_at_a_drive_boundary_is_counted():
    frame = plays(
        [
            (
                1,
                1,
                1,
                1,
                91,
                14,
                0,
                "Rush",
            ),  # periods 1 and 2 exist, so the game is complete
            (1, 2, 5, 1, 92, 14, 0, "Rush"),
            (1, 3, 17, 10, 1, 0, 28, "Rush"),
            (1, 3, 17, 11, 2, 0, 0, "End Period"),
            (1, 3, 18, 1, 3, 15, 0, "Kickoff"),  # the next period's kickoff, old label
            (1, 3, 18, 2, 4, 14, 50, "Rush"),
            (1, 4, 19, 1, 5, 14, 0, "Rush"),  # the next label does exist
        ]
    )
    events = period_reset_events(prepare(frame))
    assert len(events) == 1
    event = events.iloc[0]
    assert event["prev_type"] == "End Period" and event["play_type"] == "Kickoff"
    assert bool(event["new_drive"]) and bool(event["next_period_present"])
    assert not bool(event["game_lacks_a_regulation_period"])


def test_same_second_plays_and_ordinary_clock_runs_are_not_resets():
    frame = plays(
        [
            (1, 1, 1, 1, 1, 15, 0, "Kickoff"),
            (1, 1, 1, 2, 2, 15, 0, "Rush"),
            (1, 1, 1, 3, 3, 14, 40, "Rush"),
            (1, 1, 2, 1, 4, 14, 40, "Rush"),
        ]
    )
    assert period_reset_events(prepare(frame)).empty


def test_tied_plays_are_left_out_of_the_census():
    frame = plays(
        [
            (1, 1, 5, 6, -217, 3, 41, "Rush"),
            (
                1,
                1,
                5,
                6,
                -218,
                15,
                0,
                "Rush",
            ),  # would look like a reset; the pair is tied
        ]
    )
    assert period_reset_events(prepare(frame)).empty


def test_drive_numbers_that_restart_across_periods_are_an_inversion_game():
    """Period 1 drive 8, then period 2 drive 2: period-first is the coherent order."""
    frame = plays(
        [
            (1, 1, 8, 6, 1, 2, 18, "Rush"),
            (1, 1, 9, 1, 2, 0, 0, "End Period"),
            (1, 2, 2, 2, 3, 15, 0, "Rush"),
            (1, 2, 2, 3, 4, 14, 40, "Rush"),
        ]
    )
    result = ordering_comparison(prepare(frame))
    assert result["inversion_games"] == 1
    assert result["violations_period_first"] == 0
    assert result["violations_drive_first"] > 0
    assert result["inversion_games_period_first_better"] == 1
    assert result["inversion_games_drive_first_better"] == 0


def test_summary_reports_counts_without_excluding_anything():
    frame = plays(
        [
            (1, 3, 17, 11, 1, 0, 0, "End Period"),
            (1, 3, 18, 1, 2, 15, 0, "Kickoff"),
            (2, 1, 1, 1, 3, 15, 0, "Kickoff"),
            (2, 1, 1, 2, 4, 14, 30, "Rush"),
        ]
    )
    summary = summarize_season(frame)
    assert summary["reset_events"] == 1
    assert summary["reset_games"] == 1
    assert summary["reset_in_game_missing_a_regulation_period"] == 1
    assert summary["previous_play_types"] == {"End Period": 1}
    assert summary["reset_play_types"] == {"Kickoff": 1}
