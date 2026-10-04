"""Silver invariants and gate 6: fixture-driven, no cloud or database access."""

from __future__ import annotations

import pandas as pd

from cks_picks_cfb.quality import checks as q
from cks_picks_cfb.quality import silver as sv


def _run(ctx):
    return {r.check_id: r for r in q.run_stage("silver", ctx).results}


def test_all_silver_checks_register_at_warn_and_skip_without_inputs():
    specs = [s for s in q.REGISTRY.values() if s.stage == "silver"]
    assert len(specs) >= 7 and {s.severity for s in specs} == {q.WARN}
    run = q.run_stage("silver", {})
    assert all(r.skipped for r in run.results) and not run.blocked


def test_reconciliation_summary_counts_blocking_and_classes():
    rec = pd.DataFrame(
        {
            "game_id": [1, 2, 3],
            "classification": ["exact_match"] * 2 + ["blocking_conflict"],
            "blocking": [False, False, True],
        }
    )
    res = sv.reconciliation_summary(rec)
    assert res == {
        "games": 3,
        "blocking": 1,
        "by_classification": {"exact_match": 2, "blocking_conflict": 1},
    }
    assert not _run({"source_reconciliation": rec})[
        "silver.reconciliation_recorded"
    ].passed


def _plays(rows):
    return pd.DataFrame(
        rows,
        columns=[
            "game_id",
            "offense",
            "defense",
            "offense_score",
            "defense_score",
            "drive_number",
            "play_number",
        ],
    )


def test_score_stream_orders_by_drive_then_play_and_flags_a_decrease():
    # play_number restarts in every drive, so drive must come first.
    clean = _plays(
        [
            (1, "A", "B", 0, 0, 1, 1),
            (1, "B", "A", 0, 7, 1, 2),
            (1, "A", "B", 7, 7, 2, 1),
            (1, "A", "B", 7, 7, 2, 2),
        ]
    )
    assert sv.score_stream_regressions(clean)["regressed"] == 0
    # Team A's score goes 7 then 3 across drives: a regression (the October score-stream defect).
    bad = _plays(
        [
            (1, "A", "B", 7, 0, 1, 1),
            (1, "B", "A", 0, 7, 1, 2),
            (1, "A", "B", 3, 0, 2, 1),
        ]
    )
    res = sv.score_stream_regressions(bad)
    assert (
        res["regressed"] == 1 and res["team_games"] == 2 and res["games_affected"] == 1
    )
    assert not _run({"byplay": bad})["silver.score_stream_monotone"].passed


def test_drive_numbers_are_one_sequence_per_game_and_unique_per_offense():
    # Number 2 appears under both teams (possession changed inside the drive): allowed.
    ok = pd.DataFrame(
        {
            "game_id": [1] * 4,
            "offense": ["A", "A", "B", "B"],
            "drive_number": [1, 2, 2, 3],
        }
    )
    assert sv.drive_numbering_problems(ok) == {
        "games": 1,
        "duplicate_keys": 0,
        "gap_games": [],
    }
    gap = pd.DataFrame(
        {"game_id": [1, 1], "offense": ["A", "B"], "drive_number": [1, 3]}
    )
    assert sv.drive_numbering_problems(gap)["gap_games"] == [1]
    dup = pd.DataFrame(
        {"game_id": [2, 2], "offense": ["A", "A"], "drive_number": [1, 1]}
    )
    res = sv.drive_numbering_problems(dup)
    assert res["duplicate_keys"] == 1
    assert not _run({"drives": dup})["silver.drive_numbering"].passed


def test_plays_and_drives_must_cover_the_same_games():
    byplay = _plays([(1, "A", "B", 0, 0, 1, 1), (2, "A", "B", 0, 0, 1, 1)])
    drives = pd.DataFrame({"game_id": [1, 3]})
    res = sv.play_drive_game_coverage(byplay, drives)
    assert res == {"plays_without_drives": [2], "drives_without_plays": [3]}


def _games():
    return pd.DataFrame(
        {
            "game_id": [1],
            "home_team": ["A"],
            "away_team": ["B"],
            "home_points": [24],
            "away_points": [17],
            "completed": [True],
        }
    )


def test_points_identity_allows_non_offense_points_but_flags_excess():
    ok = pd.DataFrame(
        {"game_id": [1, 1, 1], "offense": ["A", "A", "B"], "points": [7, 14, 17]}
    )  # A: 21 < 24
    assert sv.points_identity(ok, _games())["excess"] == []
    excess = pd.DataFrame(
        {"game_id": [1, 1], "offense": ["A", "B"], "points": [28, 17]}
    )
    res = sv.points_identity(excess, _games())
    assert res["excess"] == [{"game_id": 1, "team": "A", "drive": 28.0, "final": 24.0}]
    assert not _run({"drives": excess, "games": _games()})[
        "silver.points_identity"
    ].passed


def test_ppa_flag_requires_the_column_and_never_a_zero_fill():
    zero_filled = pd.DataFrame({"ppa": [0.0, 0.5]})
    r = _run({"byplay": zero_filled})["silver.ppa_missing_flag"]
    assert not r.passed and "no ppa_missing flag" in r.detail
    good = pd.DataFrame({"ppa": [None, 0.0, 0.5], "ppa_missing": [True, False, False]})
    assert _run({"byplay": good})["silver.ppa_missing_flag"].passed
    unflagged = pd.DataFrame({"ppa": [None, 0.5], "ppa_missing": [False, False]})
    assert sv.ppa_flag_problems(unflagged)["null_not_flagged"] == 1
    zero_flagged = pd.DataFrame({"ppa": [0.0], "ppa_missing": [True]})
    assert sv.ppa_flag_problems(zero_flagged)["flagged_with_value"] == 1


def _versions():
    prev = pd.DataFrame(
        {
            "game_id": [1, 2, 3],
            "completed": [True, True, False],
            "home_points": [10, 20, None],
            "away_points": [7, 17, None],
        }
    )
    cur = pd.DataFrame(
        {
            "game_id": [1, 2, 3],
            "completed": [True, True, True],
            "home_points": [
                10,
                21,
                14,
            ],  # game 2 corrected after completion; game 3 newly completed
            "away_points": [7, 17, 3],
            "__capture_id": ["c1", "c2", "c3"],
        }
    )
    return prev, cur


def test_completed_game_changes_include_corrections_and_new_completions():
    prev, cur = _versions()
    changes = sv.completed_game_changes(prev, cur)
    assert sorted(changes["game_id"]) == [2, 3]
    # Game 2 was already completed (a correction); game 3 is a new completion.
    assert dict(zip(changes["game_id"], changes["previously_completed"])) == {
        2: True,
        3: False,
    }


def test_unpinned_refreshes_require_a_catalogued_capture_with_a_full_pin():
    prev, cur = _versions()
    changes = sv.completed_game_changes(prev, cur)
    full = pd.DataFrame(
        {
            "capture_id": ["c2", "c3"],
            "content_sha": ["a", "b"],
            "object_sha": ["a", "b"],
            "uri": ["u", "u"],
            "captured_at": ["t", "t"],
        }
    )
    assert sv.unpinned_refreshes(changes, full) == {}
    missing = full.iloc[:1]
    assert sv.unpinned_refreshes(changes, missing) == {"not_in_catalog": [3]}
    partial = full.copy()
    partial.loc[0, "object_sha"] = None
    assert sv.unpinned_refreshes(changes, partial) == {"incomplete_pin": [2]}
    nocap = changes.drop(columns="__capture_id")
    assert sv.unpinned_refreshes(nocap, full) == {"no_capture_id": [2, 3]}
    ctx = {"games": cur, "games_previous": prev, "capture_index": missing}
    assert not _run(ctx)["silver.completed_game_refresh_pinned"].passed
