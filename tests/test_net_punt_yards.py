"""Net punt yards pair a punt with the next drive (contract 2026-10-09/01, Task 4.7).

No test covered this calculation before provider-keyed identity. v1 behaviour is pinned by the
golden digest in ``test_v1_play_order_invariance``; these tests pin what v2 does beside it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from cks_picks_cfb.features.aggregations.drives import aggregate_drives
from cks_picks_cfb.features.aggregations.team_game import (
    _pair_punts_by_drive_number,
    _pair_punts_in_collided_game,
    calculate_st_analytics_agg,
)
from cks_picks_cfb.features.byplay.enrichment import allplays_to_byplay
from tests.test_possession_v2 import p

PUNT = dict(kind="Punt")


def frame(rows):
    return pd.DataFrame(rows)


def v1_and_v2(rows):
    plays = frame(rows)
    v1 = allplays_to_byplay(plays, nullable_ppa=True)
    v2 = allplays_to_byplay(plays, nullable_ppa=True, play_identity="byplay_v2")
    return (
        calculate_st_analytics_agg(v1, aggregate_drives(v1)),
        calculate_st_analytics_agg(
            v2, aggregate_drives(v2, schema_version="drives_v2")
        ),
    )


def clean_game():
    return [
        p(1, 1, 11, 0, 0, yards_to_goal=75),
        p(1, 2, 12, 0, 0, yards_to_goal=70),
        p(1, 3, 13, 0, 0, kind="Punt", yards_to_goal=60),
        p(2, 1, 21, 0, 0, offense="B", yards_to_goal=45),
        p(2, 2, 22, 0, 0, offense="B", kind="Punt", yards_to_goal=50),
        p(3, 1, 31, 0, 0, yards_to_goal=80),
    ]


def test_a_punt_is_paired_with_the_next_drives_start():
    out, _ = v1_and_v2(clean_game())
    punts = out.set_index("team")["off_avg_net_punt_yards"]
    # A punts from 60 yards to goal; B then starts at 45 (55 from its own goal): 60 - 55
    assert punts["A"] == 60 - (100 - 45)
    assert punts["B"] == 50 - (100 - 80)


def test_v2_matches_v1_on_a_game_without_collisions():
    old, new = v1_and_v2(clean_game())
    pd.testing.assert_frame_equal(old, new)


def test_v2_matches_v1_where_the_provider_restarts_drive_numbers_but_nothing_collides():
    """Backwards drive numbers (known issue 17) are not reuse, so v1 and v2 agree."""
    rows = [
        p(1, 1, 11, 0, 0, yards_to_goal=75),
        p(1, 2, 12, 0, 0, kind="Punt", yards_to_goal=60),
        p(2, 1, 21, 0, 0, offense="B", yards_to_goal=45),
        p(3, 1, 31, 0, 0, yards_to_goal=80),
        # period 2 restarts the drive number at 2 (a second drive 2, different provider drive)
        p(
            2,
            3,
            23,
            0,
            0,
            offense="B",
            quarter=2,
            kind="Punt",
            yards_to_goal=52,
            drive_id=2001,
        ),
        p(3, 4, 32, 0, 0, quarter=2, yards_to_goal=66, drive_id=2002),
    ]
    old, new = v1_and_v2(rows)
    pd.testing.assert_frame_equal(old, new)


def collision_rows(unorderable=False):
    """An overtime drive reuses regulation drive 4's number AND its first play number.

    Pairing by displayed drive number would collapse the two drives, and the overtime row (offense
    A sorts first) would supply the next start; pairing by provider drive must not.
    """
    rows = [
        p(1, 1, 11, 0, 0, yards_to_goal=75),
        p(3, 1, 31, 0, 0, yards_to_goal=70, drive_id=1003),
        p(3, 2, 32, 0, 0, kind="Punt", yards_to_goal=62, drive_id=1003),
        p(4, 1, 41, 0, 0, offense="B", yards_to_goal=55, drive_id=1004),
        p(4, 1, 93, 0, 0, quarter=5, yards_to_goal=75, drive_id=-999),
    ]
    if unorderable:
        # a second regulation drive tied with the punting drive on every ordering key
        rows.append(
            p(3, 1, 94, 0, 0, offense="B", quarter=1, yards_to_goal=40, drive_id=1999)
        )
    return rows


def v2_tables(rows):
    plays = allplays_to_byplay(
        frame(rows), nullable_ppa=True, play_identity="byplay_v2"
    )
    return plays, aggregate_drives(plays, schema_version="drives_v2")


def test_a_collision_game_is_paired_by_provider_drive_and_chronological_order():
    plays, drives = v2_tables(collision_rows())
    assert plays.duplicated(
        ["game_id", "drive_number", "play_number"], keep=False
    ).any()
    punts = plays[plays["st_punt"] == 1]
    # Pairing by displayed number collapses regulation drive 4 with the overtime drive that
    # reuses it, and the overtime row (offense A) supplies a start of 75.
    assert (
        _pair_punts_by_drive_number(punts, drives)["next_drive_start_ytg"].iloc[0] == 75
    )
    out = calculate_st_analytics_agg(plays, drives)
    # Pairing by provider drive follows regulation drive 3 with regulation drive 4 (start 55).
    assert out.set_index("team")["off_avg_net_punt_yards"]["A"] == 62 - (100 - 55)


def test_drives_that_cannot_be_ordered_leave_the_punt_without_a_next_drive():
    plays, drives = v2_tables(collision_rows(unorderable=True))
    punts = plays[plays["st_punt"] == 1]
    paired = _pair_punts_in_collided_game(punts, plays, drives)
    assert paired["next_drive_start_ytg"].isna().all()
    out = calculate_st_analytics_agg(plays, drives)
    assert (
        out.empty
        or out.get("off_avg_net_punt_yards", pd.Series(dtype=float)).isna().all()
    )


def test_games_are_paired_independently_of_each_other():
    """A collision elsewhere must not change a clean game's values."""
    other = [
        {
            **r,
            "game_id": 2,
            "play_id": r["play_id"] + 1000,
            "drive_id": r["drive_id"] + 5000,
        }
        for r in clean_game()
    ]
    plays, drives = v2_tables(
        clean_game() + [dict(r, game_id=9) for r in collision_rows()] + other
    )
    mixed = calculate_st_analytics_agg(plays, drives).set_index(["game_id", "team"])
    alone, _ = v1_and_v2(clean_game())
    assert (
        mixed.loc[(1, "A"), "off_avg_net_punt_yards"]
        == alone.set_index("team").loc["A", "off_avg_net_punt_yards"]
    )
    assert (
        mixed.loc[(2, "B"), "off_avg_net_punt_yards"]
        == alone.set_index("team").loc["B", "off_avg_net_punt_yards"]
    )
    assert not np.isnan(mixed.loc[(9, "A"), "off_avg_net_punt_yards"])


def test_the_comparison_flags_only_differences_outside_the_collision_games():
    from scripts.analysis.net_punt_yards_comparison import VALUE, compare_net_punt

    def agg(rows):
        return pd.DataFrame(rows, columns=["game_id", "team", VALUE])

    v1 = agg([(1, "A", 10.0), (2, "A", 5.0), (3, "B", np.nan)])
    same = compare_net_punt(v1, v1.copy(), frozenset())
    assert same["team_games_differing"] == 0 and same["team_games_compared"] == 3
    v2 = agg([(1, "A", 10.0), (2, "A", 7.0), (3, "B", np.nan)])
    inside = compare_net_punt(v1, v2, frozenset({2}))
    assert (
        inside["differing_games"] == [2]
        and inside["differing_outside_collision_games"] == 0
    )
    outside = compare_net_punt(v1, v2, frozenset())
    assert outside["differing_outside_collision_games"] == 1
    assert outside["differing_detail"] == [
        {"game_id": 2, "team": "A", "v1": 5.0, "v2": 7.0}
    ]
    assert compare_net_punt(v1, agg([]), frozenset())["team_games_differing"] == 2
