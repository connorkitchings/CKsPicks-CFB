"""Synthetic play sequences for the score-attribution repair rules."""

import numpy as np
import pandas as pd
import pytest

from cks_picks_cfb.ratings.observations import true_drive_points
from cks_picks_cfb.ratings_lab import score_attribution as sa

A, B = "Alpha", "Bravo"


def _game(rows):
    """rows: (drive, quarter, offense, a_score, b_score, play_type, scoring)."""
    frame = pd.DataFrame(
        rows,
        columns=[
            "drive_number",
            "quarter",
            "offense",
            "a",
            "b",
            "play_type",
            "scoring",
        ],
    )
    frame["play_number"] = frame.groupby("drive_number").cumcount() + 1
    frame["defense"] = np.where(frame["offense"].eq(A), B, A)
    frame["offense_score"] = np.where(frame["offense"].eq(A), frame["a"], frame["b"])
    frame["defense_score"] = np.where(frame["offense"].eq(A), frame["b"], frame["a"])
    return sa.order_plays(frame)


def _rush(drive, quarter, offense, a, b):
    return (drive, quarter, offense, a, b, "Rush", False)


def _td(drive, quarter, offense, a, b):
    return (drive, quarter, offense, a, b, "Rushing Touchdown", True)


def _result(game, finals, rule, lines=None):
    return sa.repaired_streams(game, finals, rule, lines)


def _points(game, streams, team):
    return {
        drive: pts
        for (drive, off), pts in sa.drive_points(game, streams).items()
        if off == team
    }


def test_drop_to_zero_is_repaired_by_the_scoring_row_rule():
    game = _game(
        [
            _rush(1, 1, A, 0, 0),
            _td(1, 1, A, 7, 0),
            _rush(2, 1, B, 0, 0),  # score wiped to zero
            _rush(2, 1, B, 0, 0),
            _rush(3, 2, A, 0, 0),
            _td(3, 2, A, 14, 0),
        ]
    )
    finals = {A: 14, B: 0}
    drops = sa.find_drops(sa.team_stream(game, A), game)
    assert [d.pattern for d in drops] == ["drop_to_zero"]
    assert drops[0].restored
    streams = _result(game, finals, "r4_scoring_rows")
    assert list(streams[A]) == [0, 7, 7, 7, 7, 14]
    assert _points(game, streams, A) == {1: 7, 3: 7}


def test_point_after_credited_before_the_kick_is_classified_and_repaired():
    game = _game(
        [
            _rush(1, 1, A, 0, 0),
            _td(1, 1, A, 7, 0),
            (2, 1, B, 6, 0, "Kickoff", False),  # PAT not yet credited
            _rush(2, 1, B, 7, 0),
        ]
    )
    drops = sa.find_drops(sa.team_stream(game, A), game)
    assert [d.pattern for d in drops] == ["point_after_before_kick"]
    streams = _result(game, {A: 7, B: 0}, "r4_scoring_rows")
    assert list(streams[A]) == [0, 7, 7, 7]
    assert _points(game, streams, A)[1] == 7


def test_a_drop_that_is_never_restored_is_reported_and_the_cap_resolves_it():
    game = _game(
        [
            _td(1, 1, A, 7, 0),
            _rush(2, 2, B, 7, 0),
            _rush(2, 2, B, 3, 0),  # falls and never comes back
            _rush(3, 3, A, 3, 0),
        ]
    )
    drops = sa.find_drops(sa.team_stream(game, A), game)
    assert [d.restored for d in drops] == [False]
    streams = _result(game, {A: 7, B: 0}, "r1_envelope")
    assert streams[A][-1] == 7


@pytest.mark.parametrize("rule", ["r1_envelope", "r2_isotonic", "r4_scoring_rows"])
def test_no_rule_exceeds_the_game_final(rule):
    game = _game(
        [
            _rush(1, 1, A, 0, 0),
            _td(1, 1, A, 7, 0),
            _rush(2, 2, A, 7, 0),
            _td(2, 2, A, 13, 0),  # phantom touchdown above the final of 7
            _rush(3, 3, B, 13, 0),
        ]
    )
    streams = _result(game, {A: 7, B: 0}, rule)
    assert float(np.max(streams[A])) <= 7
    assert streams[A][-1] == 7


def test_stream_that_never_reaches_the_final_stays_unresolved_under_every_rule():
    game = _game([_td(1, 1, A, 6, 0), _rush(2, 2, B, 6, 0), _td(3, 3, A, 12, 0)])
    outcomes = sa.evaluate_game(game, {A: 18, B: 0}, None)
    for rule in ("r1_envelope", "r2_isotonic", "r4_scoring_rows"):
        assert outcomes[rule][A].reason == "short_of_final"
        assert not outcomes[rule][A].resolved


def test_scoring_row_rule_places_points_where_the_envelope_cannot():
    game = _game(
        [
            _td(1, 1, A, 7, 0),
            _rush(2, 2, B, 7, 0),
            _rush(2, 2, B, 21, 0),  # leaked future score on an ordinary play
            _rush(2, 2, B, 7, 0),
            _td(3, 3, A, 14, 0),
            _td(4, 4, A, 21, 0),
        ]
    )
    finals = {A: 21, B: 0}
    envelope = _result(game, finals, "r1_envelope")
    scoring = _result(game, finals, "r4_scoring_rows")
    # Both reach the final, but the envelope books the later touchdowns as zero-point
    # possessions because the leaked value arrived early.
    assert envelope[A][-1] == scoring[A][-1] == 21
    assert _points(game, envelope, A) == {1: 7, 3: 0, 4: 0}
    assert _points(game, scoring, A) == {1: 7, 3: 7, 4: 7}


def test_a_team_game_the_builder_accepts_is_never_changed():
    game = _game([_td(1, 1, A, 7, 0), _rush(2, 2, B, 7, 0), _td(3, 3, A, 14, 0)])
    for rule in sa.RULES:
        outcome = sa.evaluate_game(game, {A: 14, B: 0}, {A: [7, 0, 7, 0], B: [0] * 4})[
            rule
        ][A]
        assert not outcome.changed
        assert list(outcome.stream) == list(sa.team_stream(game, A))


def test_quarter_anchored_rule_uses_line_scores_as_bounds():
    stream = np.array([0.0, 7.0, 7.0, 14.0, 14.0])
    quarters = np.array([1, 1, 2, 2, 3])
    rebuilt = sa.rule_quarter_anchored(stream, 14, quarters, [7, 7, 0, 0])
    assert rebuilt is not None
    assert list(rebuilt) == [0, 7, 7, 14, 14]
    assert sa.rule_quarter_anchored(stream, 14, quarters, [7, 0, 0, 0]) is None


def test_drive_points_and_rejection_match_the_production_builder():
    game = _game(
        [
            _rush(1, 1, A, 0, 0),
            _td(1, 1, A, 7, 0),
            _rush(2, 2, B, 7, 0),
            _rush(2, 2, B, 3, 0),  # regression: the builder rejects Alpha
            _td(3, 3, A, 10, 0),
        ]
    )
    byplay = game.assign(season=2026, game_id=1)
    games = pd.DataFrame(
        {"season": [2026], "game_id": [1], "home_team": [A], "away_team": [B]}
    )
    outcomes = pd.DataFrame(
        {"season": [2026], "game_id": [1], "home_points": [10], "away_points": [0]}
    )
    built = true_drive_points(byplay=byplay, games=games, outcomes=outcomes)
    assert (2026, 1, A) in built.invalid_offenses
    assert sa.stream_reason(sa.team_stream(game, A), 10, [7, 7]) == "score_regression"

    clean = _game([_td(1, 1, A, 7, 0), _rush(2, 2, B, 7, 0), _td(3, 3, A, 14, 0)])
    clean_built = true_drive_points(
        byplay=clean.assign(season=2026, game_id=1),
        games=games,
        outcomes=outcomes.assign(home_points=14),
    )
    production = {
        (int(r.drive_number), r.offense): int(r.true_points)
        for r in clean_built.drive_points.itertuples()
    }
    mine = sa.drive_points(
        clean, {A: sa.team_stream(clean, A), B: sa.team_stream(clean, B)}
    )
    assert production[(1, A)] == mine[(1, A)] == 7
    assert production[(3, A)] == mine[(3, A)] == 7
