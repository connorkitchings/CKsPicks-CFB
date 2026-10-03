import pandas as pd

from scripts.analysis.audit_score_stream import (
    classify_drop,
    find_drops,
    running_max_vs_final,
    summarize,
    team_game_count,
)


def _plays(rows):
    frame = pd.DataFrame(
        rows,
        columns=[
            "game_id",
            "drive_number",
            "play_number",
            "offense",
            "defense",
            "offense_score",
            "defense_score",
            "play_type",
            "scoring",
        ],
    )
    frame["week"] = 1
    return frame


def test_classify_drop_rules_in_priority_order():
    assert (
        classify_drop(
            to_zero=True, size=7, prev_scoring=True, prev_type="x", cur_type="y"
        )
        == "a_drop_to_zero"
    )
    assert (
        classify_drop(
            to_zero=False,
            size=1,
            prev_scoring=True,
            prev_type="Rush",
            cur_type="Kickoff",
        )
        == "b_pat_or_2pt_credited_early"
    )
    assert (
        classify_drop(
            to_zero=False,
            size=2,
            prev_scoring=True,
            prev_type="Rush",
            cur_type="Kickoff",
        )
        == "b_pat_or_2pt_credited_early"
    )
    assert (
        classify_drop(
            to_zero=False,
            size=3,
            prev_scoring=True,
            prev_type="Rush",
            cur_type="Kickoff",
        )
        == "c_scoring_row_other_size"
    )
    assert (
        classify_drop(
            to_zero=False,
            size=3,
            prev_scoring=False,
            prev_type="Penalty",
            cur_type="Rush",
        )
        == "d_penalty_adjacent"
    )
    assert (
        classify_drop(
            to_zero=False, size=7, prev_scoring=False, prev_type="Rush", cur_type="Punt"
        )
        == "f_other_nonscoring_prev"
    )


def test_find_drops_reads_each_teams_score_from_both_columns():
    # A scores a touchdown credited as 7 (PAT early), the next row shows 6, then 13.
    rows = [
        (1, 1, 1, "A", "B", 0, 0, "Rush", False),
        (1, 1, 2, "A", "B", 7, 0, "Passing Touchdown", True),
        (
            1,
            2,
            1,
            "B",
            "A",
            0,
            6,
            "Rush",
            False,
        ),  # A is now the defense: 6, a decrease of 1
        (1, 2, 2, "B", "A", 0, 6, "Punt", False),
        (1, 3, 1, "A", "B", 13, 0, "Rush", False),
    ]
    drops = find_drops(_plays(rows))
    assert len(drops) == 1
    drop = drops.iloc[0]
    assert (drop["team"], drop["before"], drop["after"], drop["size"]) == (
        "A",
        7.0,
        6.0,
        1.0,
    )
    assert drop.cause == "b_pat_or_2pt_credited_early"
    assert bool(drop.restored) is True
    assert bool(drop.to_zero) is False


def test_drop_to_zero_and_not_restored_are_reported():
    rows = [
        (2, 1, 1, "A", "B", 3, 0, "Rush", False),
        (2, 1, 2, "A", "B", 0, 0, "Rush", False),  # A: 3 -> 0
        (2, 1, 3, "A", "B", 0, 0, "Punt", False),
    ]
    drops = find_drops(_plays(rows))
    assert drops.cause.tolist() == ["a_drop_to_zero"]
    assert bool(drops.iloc[0].restored) is False


def test_summarize_counts_events_flagged_team_games_and_causes():
    rows = [
        (1, 1, 1, "A", "B", 7, 0, "Passing Touchdown", True),
        (1, 1, 2, "A", "B", 6, 0, "Kickoff", False),
        (2, 1, 1, "C", "D", 0, 0, "Rush", False),
        (2, 1, 2, "C", "D", 0, 0, "Rush", False),
    ]
    plays = _plays(rows)
    drops = find_drops(plays)
    summary = summarize(drops, team_game_count(plays))
    assert summary["events"] == 1
    assert summary["team_games"] == 4
    assert summary["flagged_team_games"] == 1
    assert summary["flagged_share"] == 0.25
    assert summary["by_cause"]["b_pat_or_2pt_credited_early"] == 1


def test_clean_game_has_no_drops():
    rows = [
        (3, 1, 1, "A", "B", 0, 0, "Rush", False),
        (3, 1, 2, "A", "B", 7, 0, "Rushing Touchdown", True),
        (3, 2, 1, "B", "A", 0, 7, "Rush", False),
    ]
    assert find_drops(_plays(rows)).empty


def test_running_max_uses_both_columns_and_flags_an_overshoot():
    rows = [
        (4, 1, 1, "A", "B", 7, 0, "Rushing Touchdown", True),
        (4, 2, 1, "B", "A", 0, 7, "Rush", False),
        (4, 2, 2, "B", "A", 14, 7, "Rushing Touchdown", True),
        # A is on defense when it scores a defensive touchdown: 13 on defense_score only
        (4, 3, 1, "B", "A", 14, 13, "Interception Return Touchdown", True),
    ]
    games = pd.DataFrame({"game_id": [4], "home_team": ["A"], "away_team": ["B"]})
    outcomes = pd.DataFrame({"game_id": [4], "home_points": [13], "away_points": [10]})
    out = running_max_vs_final(_plays(rows), games, outcomes)
    # A reaches 13 (matches). B reaches 14 but the final says 10: a real mismatch.
    assert out.to_dict("records") == [
        {"game_id": 4, "team": "B", "final": 10.0, "running_max": 14.0}
    ]
