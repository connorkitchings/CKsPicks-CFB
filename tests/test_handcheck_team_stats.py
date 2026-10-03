import pandas as pd

from cks_picks_cfb.data.play_filters import scrimmage_play_mask
from scripts.analysis.handcheck_team_stats import (
    build_drives,
    compare,
    eligible_scrimmage,
    recompute,
)

COLUMNS = [
    "game_id",
    "week",
    "drive_number",
    "play_number",
    "quarter",
    "offense",
    "defense",
    "offense_score",
    "defense_score",
    "yards_to_goal",
    "eckel",
    "st",
    "penalty",
    "twopoint",
    "garbage",
    "play_type",
]


def _plays(rows):
    return pd.DataFrame(rows, columns=COLUMNS)


def _fixture():
    # Columns: game, week, drive, play, quarter, offense, defense, off_score,
    # def_score, yards_to_goal, eckel, st, penalty, twopoint, garbage, play_type.
    # A: drive 1 starts at its own 25 (ytg 75), scores a touchdown (6) and the PAT (7),
    # a scoring opportunity; drive 3 starts at ytg 60 and goes nowhere.
    # B: drive 2 starts at ytg 70 and punts. The kickoff row is its own group.
    return _plays(
        [
            (1, 1, 1, 1, 1, "B", "A", 0, 0, 65, 0, 1, 0, 0, 0, "Kickoff"),
            (1, 1, 1, 2, 1, "A", "B", 0, 0, 75, 0, 0, 0, 0, 0, "Rush"),
            (1, 1, 1, 3, 1, "A", "B", 0, 0, 45, 1, 0, 0, 0, 0, "Pass Reception"),
            (1, 1, 1, 4, 1, "A", "B", 6, 0, 5, 1, 0, 0, 0, 0, "Passing Touchdown"),
            (1, 1, 1, 5, 1, "A", "B", 7, 0, 3, 1, 1, 0, 0, 0, "Extra Point Good"),
            (1, 1, 2, 1, 1, "B", "A", 0, 7, 70, 0, 0, 0, 0, 0, "Rush"),
            (1, 1, 2, 2, 1, "B", "A", 0, 7, 68, 0, 1, 0, 0, 0, "Punt"),
            (1, 1, 3, 1, 2, "A", "B", 7, 0, 60, 0, 0, 0, 0, 0, "Rush"),
            (1, 1, 3, 2, 2, "A", "B", 7, 0, 58, 0, 0, 0, 0, 0, "Pass Incompletion"),
        ]
    )


def test_eligible_scrimmage_matches_the_shared_filter_on_mixed_play_types():
    types = [
        "Rush",
        "Pass Reception",
        "Punt",
        "Punt Return",
        "Kickoff",
        "Field Goal Good",
        "Extra Point Good",
        "Timeout",
        "End of Half",
        "Penalty",
        "Sack",
    ]
    rows = []
    for number, play_type in enumerate(types, start=1):
        rows.append(
            (
                1,
                1,
                1,
                number,
                1,
                "A",
                "B",
                0,
                0,
                50,
                0,
                0,
                1 if play_type == "Penalty" else 0,
                0,
                0,
                play_type,
            )
        )
    rows.append((1, 1, 1, 99, 5, "A", "B", 0, 0, 25, 0, 0, 0, 0, 0, "Rush"))  # overtime
    rows.append((1, 1, 1, 100, 4, "A", "B", 0, 0, 50, 0, 0, 0, 0, 1, "Rush"))  # garbage
    plays = _plays(rows)
    mine = eligible_scrimmage(plays)
    theirs = scrimmage_play_mask(plays)
    assert mine.tolist() == theirs.tolist()
    assert mine.sum() == 3  # Rush, Pass Reception, Sack


def test_kickoff_group_is_not_a_drive_and_starts_come_from_the_first_row():
    drives = build_drives(_fixture())
    assert sorted(zip(drives.offense, drives.drive_number)) == [
        ("A", 1),
        ("A", 3),
        ("B", 2),
    ]
    a1 = drives[(drives.offense == "A") & (drives.drive_number == 1)].iloc[0]
    assert a1.start_yards_to_goal == 75
    assert bool(a1.opportunity) is True


def test_recompute_matches_hand_calculation():
    drives = build_drives(_fixture())
    offense = recompute(drives, "A", "offense")
    # drives start at ytg 75 and 60 => field positions 25 and 40 => mean 32.5
    assert offense["avg_start_field_pos"] == (32.5, 2)
    # one of two drives is a scoring opportunity
    assert offense["scoring_opp_rate"] == (0.5, 2)
    # the touchdown drive scored 7 (running score 7 at its last row, 0 before it)
    assert offense["pts_per_scoring_opp"] == (7.0, 1)
    defense = recompute(drives, "A", "defense")  # B's single drive against A
    assert defense["avg_start_field_pos"] == (30.0, 1)
    assert defense["scoring_opp_rate"] == (0.0, 1)
    assert defense["pts_per_scoring_opp"] == (None, 0)


def test_a_team_whose_score_decreases_is_skipped_for_points():
    plays = _fixture()
    # make A's score fall from 7 to 6 on the row after the touchdown drive
    plays.loc[(plays.drive_number == 2) & (plays.play_number == 1), "defense_score"] = 6
    drives = build_drives(plays)
    offense = recompute(drives, "A", "offense")
    assert offense["pts_per_scoring_opp"] == (None, 0)
    assert offense["avg_start_field_pos"] == (32.5, 2)  # the other metrics still count


def test_compare_flags_differences_and_accepts_matching_or_both_null():
    drives = build_drives(_fixture())
    published = pd.DataFrame(
        [
            ("A", "offense", "avg_start_field_pos", 32.5),
            ("A", "offense", "scoring_opp_rate", 0.75),  # wrong on purpose
            ("A", "offense", "pts_per_scoring_opp", 7.0),
            ("A", "defense", "pts_per_scoring_opp", None),
        ],
        columns=["team", "role", "metric", "value"],
    )
    results = {(c.role, c.metric): c for c in compare(drives, published, ["A"])}
    assert results[("offense", "avg_start_field_pos")].ok
    assert not results[("offense", "scoring_opp_rate")].ok
    assert results[("offense", "pts_per_scoring_opp")].ok
    assert results[("defense", "pts_per_scoring_opp")].ok  # both null
