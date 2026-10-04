"""Known issue 7: the reconciliation's score comparison runs, records mismatches, never blocks."""

from __future__ import annotations

import json

import pandas as pd

from cks_picks_cfb.data import reconciliation as rc
from cks_picks_cfb.quality import checks as q
from cks_picks_cfb.quality import silver as sv


def _games():
    return pd.DataFrame(
        [
            {
                "season": 2026,
                "game_id": 1,
                "home_team": "A",
                "away_team": "B",
                "completed": True,
                "home_points": 24,
                "away_points": 17,
            }
        ]
    )


def _team_game(**stream):
    frame = pd.DataFrame(
        [
            {"game_id": 1, "team": "A", "off_points_scored": 20},
            {"game_id": 1, "team": "B", "off_points_scored": 14},
        ]
    )
    if stream:
        frame["stream_points"] = [stream["a"], stream["b"]]
    return frame


def _details(result):
    return (
        json.loads(result.iloc[0]["details"])
        if isinstance(result.iloc[0]["details"], str)
        else result.iloc[0]["details"]
    )


def test_stream_points_are_each_teams_highest_running_score():
    byplay = pd.DataFrame(
        [
            {
                "game_id": 1,
                "offense": "A",
                "defense": "B",
                "offense_score": 0,
                "defense_score": 0,
            },
            {
                "game_id": 1,
                "offense": "A",
                "defense": "B",
                "offense_score": 7,
                "defense_score": 0,
            },
            {
                "game_id": 1,
                "offense": "B",
                "defense": "A",
                "offense_score": 3,
                "defense_score": 7,
            },
            {
                "game_id": 1,
                "offense": "A",
                "defense": "B",
                "offense_score": 4,
                "defense_score": 3,
            },  # a dip: max still 7
        ]
    )
    out = rc.stream_points_by_team_game(byplay).set_index("team").stream_points
    assert out.to_dict() == {"A": 7.0, "B": 3.0}


def test_matching_stream_scores_are_compared_and_recorded_without_mismatches():
    result = rc.reconcile_completed_games(_games(), _team_game(a=24, b=17))
    assert (
        result.iloc[0]["classification"] == "exact_match"
        and not result.iloc[0]["blocking"]
    )
    details = _details(result)
    assert (
        details["stream_scores_compared"] == 2
        and "score_stream_mismatches" not in details
    )


def test_a_stream_mismatch_is_recorded_but_does_not_block_the_build():
    result = rc.reconcile_completed_games(_games(), _team_game(a=30, b=17))
    assert (
        result.iloc[0]["classification"] == "exact_match"
        and not result.iloc[0]["blocking"]
    )
    assert _details(result)["score_stream_mismatches"] == [
        {"team": "A", "schedule": 24.0, "stream": 30.0}
    ]
    rc.require_reconciled(result)  # must not raise


def test_a_missing_stream_score_is_not_compared_and_not_counted():
    frame = _team_game(a=24, b=float("nan"))
    details = _details(rc.reconcile_completed_games(_games(), frame))
    assert details["stream_scores_compared"] == 1


def test_without_stream_points_the_output_is_unchanged_from_before():
    details = _details(rc.reconcile_completed_games(_games(), _team_game()))
    assert (
        "stream_scores_compared" not in details
        and "score_stream_mismatches" not in details
    )


def test_the_legacy_points_column_still_blocks_a_conflict():
    frame = _team_game().assign(points=[30, 17])
    result = rc.reconcile_completed_games(_games(), frame)
    assert (
        result.iloc[0]["classification"] == "blocking_conflict"
        and result.iloc[0]["blocking"]
    )


def _recon(compared, mismatch):
    details = {"stream_scores_compared": compared}
    if mismatch:
        details["score_stream_mismatches"] = [
            {"team": "A", "schedule": 1.0, "stream": 2.0}
        ] * mismatch
    return pd.DataFrame([{"details": json.dumps(details)}])


def test_the_quality_checks_see_the_recorded_comparison():
    run = lambda ctx: {r.check_id: r for r in q.run_stage("silver", ctx).results}  # noqa: E731
    skipped = run({"team_game": _team_game(), "source_reconciliation": _recon(0, 0)})
    assert not skipped[
        "silver.reconciliation_compares_scores"
    ].passed  # nothing compared: known issue 7
    assert skipped["silver.stream_scores_match_finals"].skipped
    ran = run({"team_game": _team_game(), "source_reconciliation": _recon(2, 0)})
    assert (
        ran["silver.reconciliation_compares_scores"].passed
        and ran["silver.stream_scores_match_finals"].passed
    )
    bad = run({"team_game": _team_game(), "source_reconciliation": _recon(2, 1)})
    assert (
        bad["silver.reconciliation_compares_scores"].passed
        and not bad["silver.stream_scores_match_finals"].passed
    )
    legacy = run(
        {
            "team_game": _team_game().assign(points=[1, 2]),
            "source_reconciliation": _recon(0, 0),
        }
    )
    assert legacy["silver.reconciliation_compares_scores"].passed


def test_score_comparison_evidence_counts_games_and_mismatches():
    evidence = sv.score_comparison_evidence(
        None, pd.concat([_recon(2, 1), _recon(2, 0), _recon(0, 0)], ignore_index=True)
    )
    assert (
        evidence["games_compared"] == 2
        and evidence["stream_team_scores_compared"] == 4
        and evidence["stream_mismatches"] == 1
    )
