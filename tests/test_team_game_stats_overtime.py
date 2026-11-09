"""Net success rate includes overtime: ``off_success_ot_*`` columns."""

from __future__ import annotations

import numpy as np
import pandas as pd

from cks_picks_cfb.charts.team_game_stats import (
    TEAM_GAME_COLUMNS,
    build_team_game_stats,
)
from cks_picks_cfb.data.play_filters import eligible_play, scrimmage_play_mask

FBS = {"A", "B", "C"}


def play(game_id, offense, defense, success, **extra):
    return {
        "season": 2026,
        "game_id": game_id,
        "offense": offense,
        "defense": defense,
        "ppa": 0.1,
        "success": success,
        "quarter": 1,
        "st": 0,
        "penalty": 0,
        "twopoint": 0,
        "garbage": 0,
        "play_type": "Rush",
        **extra,
    }


def case():
    plays = [
        # A offense in game 1: two regulation plays (1 success) ...
        play(1, "A", "B", 1),
        play(1, "A", "B", 0),
        # ... plus overtime plays that only the new columns keep.
        play(1, "A", "B", 1, quarter=5),
        play(1, "A", "B", 1, quarter=6),
        # Garbage time is dropped from both, in regulation and in overtime.
        play(1, "A", "B", 1, garbage=1),
        play(1, "A", "B", 1, quarter=5, garbage=1),
        # Rules that stay in force for both masks.
        play(1, "A", "B", 1, st=1),
        play(1, "A", "B", 1, penalty=1),
        play(1, "A", "B", 1, twopoint=1),
        play(1, "A", "B", 1, play_type="Timeout"),
        play(1, "A", "B", 1, play_type="Punt Return"),
        play(1, "A", "B", 1, quarter=np.nan),
        # B offense in game 1: one regulation and one overtime play.
        play(1, "B", "A", 0),
        play(1, "B", "A", 1, quarter=5),
        # Game 2: no overtime.
        play(2, "A", "C", 1),
        play(2, "C", "A", 0),
        play(2, "C", "A", 1, garbage=1),
    ]
    games = pd.DataFrame(
        [
            {"season": 2026, "week": 0, "game_id": g, "home_team": h, "away_team": a}
            for g, h, a in ((1, "A", "B"), (2, "A", "C"))
        ]
    )
    finals = pd.DataFrame(
        [
            {"season": 2026, "game_id": 1, "home_points": 28, "away_points": 7},
            {"season": 2026, "game_id": 2, "home_points": 10, "away_points": 3},
        ]
    )
    return {
        "byplay": pd.DataFrame(plays),
        "games": games,
        "finals": finals,
        "fbs_teams": FBS,
        "neutral_game_ids": set(),
        "season": 2026,
        "active_week": 1,
    }


def row(frame, game_id, team):
    return frame[(frame.game_id == game_id) & (frame.team == team)].iloc[0]


def test_overtime_is_counted_only_in_the_new_columns_and_garbage_time_in_neither():
    out = build_team_game_stats(**case())
    assert list(out.columns) == list(TEAM_GAME_COLUMNS)
    a = row(out, 1, "A")
    assert (a.off_plays, a.off_success_n, a.off_success_sum) == (2, 2, 1.0)
    assert (a.off_success_ot_n, a.off_success_ot_sum) == (4, 3.0)
    b = row(out, 1, "B")
    assert (b.off_plays, b.off_success_n, b.off_success_sum) == (1, 1, 0.0)
    assert (b.off_success_ot_n, b.off_success_ot_sum) == (2, 1.0)


def test_columns_are_equal_when_a_game_has_no_overtime():
    out = build_team_game_stats(**case())
    for team in ("A", "C"):
        found = row(out, 2, team)
        assert found.off_success_ot_n == found.off_success_n
        assert found.off_success_ot_sum == found.off_success_sum


def test_existing_columns_ignore_the_overtime_plays():
    inputs = case()
    full = build_team_game_stats(**inputs)
    byplay = inputs["byplay"]
    regulation = byplay[byplay.quarter.lt(5)]
    trimmed = build_team_game_stats(**{**inputs, "byplay": regulation})
    shared = [c for c in TEAM_GAME_COLUMNS if not c.startswith("off_success_ot")]
    pd.testing.assert_frame_equal(full[shared], trimmed[shared])


def test_default_masks_are_unchanged_and_the_option_only_relaxes_the_period_rule():
    plays = case()["byplay"]
    assert scrimmage_play_mask(plays).sum() == 5  # 2 + 1 + 2 regulation, no garbage
    assert scrimmage_play_mask(plays, keep_overtime=True).sum() == 8
    overtime = next(plays.iloc[[2]].itertuples(index=False))
    garbage = next(plays.iloc[[4]].itertuples(index=False))
    assert not eligible_play(overtime)
    assert eligible_play(overtime, keep_overtime=True)
    assert not eligible_play(garbage, keep_overtime=True)
