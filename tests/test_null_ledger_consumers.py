"""Ledger consumers treat null increments as unknown, never zero; legacy behaviour is unchanged."""

from __future__ import annotations

import pandas as pd
import pytest

from cks_picks_cfb.audit import corpus
from cks_picks_cfb.audit import foundation_blocker_diagnosis as fbd
from cks_picks_cfb.forecast import forecast_verification as fv
from cks_picks_cfb.forecast import offsets

T0 = pd.Timestamp("2026-09-05T19:00:00Z")


def _ev(
    team,
    inc,
    category="regulation_non_offense",
    game=1,
    admission=None,
    period="regulation",
    drive=1,
    event="e",
):
    row = {
        "season": 2026,
        "game_id": game,
        "team": team,
        "period_class": period,
        "scoring_category": category,
        "score_increment": inc,
        "quality_reason": None,
        "source_event_id": f"{event}-{team}-{game}",
        "drive_number": drive,
    }
    if admission is not None:
        row["admission"] = admission
    return row


def _population(games=(1,)):
    return pd.DataFrame(
        [
            {
                "season": 2026,
                "week": 1,
                "game_id": g,
                "kickoff_utc": T0,
                "home_team": "A",
                "away_team": "B",
                "schedule_completed": True,
                "outcome_valid": True,
                "forecast_eligible": True,
                "measurement_usable": True,
            }
            for g in games
        ]
    )


MODULES = [
    pytest.param(offsets.team_game_non_offense, offsets.OffsetError, id="offsets"),
    pytest.param(
        fv._team_game_non_offense, fv.VerificationError, id="independent_verifier"
    ),
]


@pytest.mark.parametrize("fn,error", MODULES)
def test_an_unresolved_marker_makes_the_team_game_unusable_not_a_zero(fn, error):
    events = pd.DataFrame(
        [
            _ev("A", 6, admission="baseline_unchanged"),
            _ev("B", None, category="unresolved", admission="baseline_unchanged"),
        ]
    )
    frame = fn(_population(), events)
    assert not frame["usable"].any()  # both rows use the marked team-game
    assert frame.loc[frame.team == "A", "non_offense_for"].iloc[0] == 6.0


@pytest.mark.parametrize("fn,error", MODULES)
def test_a_complete_v1_ledger_is_usable(fn, error):
    events = pd.DataFrame([_ev("A", 6, admission="baseline_unchanged")])
    frame = fn(_population(), events)
    assert frame["usable"].all()
    assert frame.loc[frame.team == "B", "non_offense_against"].iloc[0] == 6.0


@pytest.mark.parametrize("fn,error", MODULES)
def test_retained_baseline_allocations_count_in_a_v1_ledger(fn, error):
    events = pd.DataFrame(
        [
            _ev("A", 6, admission="baseline_unchanged", event="a"),
            _ev("A", 7, admission="reverted_unverified", event="b"),
            _ev("B", 2, admission="corroborated", event="c"),
            _ev("B", 8, admission="reverted_contradicted", event="d"),
        ]
    )
    frame = fn(_population(), events)
    a = frame[frame.team == "A"].iloc[0]
    assert (a.non_offense_for, a.non_offense_against) == (13.0, 10.0)


@pytest.mark.parametrize("fn,error", MODULES)
def test_a_null_non_offense_increment_is_an_error(fn, error):
    events = pd.DataFrame([_ev("A", None, admission="baseline_unchanged")])
    with pytest.raises(error, match="null increment"):
        fn(_population(), events)


@pytest.mark.parametrize("fn,error", MODULES)
def test_a_legacy_ledger_behaves_exactly_as_before(fn, error):
    # No admission column: an unresolved marker (zero increment) does not change usability.
    events = pd.DataFrame([_ev("A", 6), _ev("B", 0, category="unresolved")])
    frame = fn(_population(), events)
    assert frame["usable"].all()


def test_offsets_and_the_verifier_agree_on_a_mixed_ledger():
    events = pd.DataFrame(
        [
            _ev("A", 6, admission="baseline_unchanged", game=1, event="a"),
            _ev(
                "B",
                None,
                category="unresolved",
                admission="baseline_unchanged",
                game=2,
                event="m",
            ),
            _ev("B", 2, admission="corroborated", game=2, event="b"),
        ]
    )
    pop = _population((1, 2))
    pd.testing.assert_frame_equal(
        offsets.team_game_non_offense(pop, events),
        fv._team_game_non_offense(pop, events),
    )


def test_category_totals_keep_all_null_groups_null_and_count_unresolved_separately():
    events = pd.DataFrame(
        [
            _ev("A", 7, category="eligible_regulation_offense", event="a"),
            _ev("A", 3, category="eligible_regulation_offense", event="b"),
            _ev("B", None, category="unresolved", event="m1"),
            _ev("B", None, category="unresolved", event="m2"),
        ]
    )
    totals = corpus.scoring_category_totals(events).set_index(
        ["team", "scoring_category"]
    )
    assert totals.loc[("A", "eligible_regulation_offense"), "score_increment"] == 10
    assert totals.loc[("A", "eligible_regulation_offense"), "unresolved_events"] == 0
    assert pd.isna(totals.loc[("B", "unresolved"), "score_increment"])  # not 0
    assert totals.loc[("B", "unresolved"), "unresolved_events"] == 2


def test_the_increment_check_counts_unresolved_nulls_but_fails_a_resolved_null():
    ok = pd.DataFrame(
        [
            _ev("A", 7, category="eligible_regulation_offense"),
            _ev("B", None, category="unresolved"),
        ]
    )
    (check,) = corpus.check_scoring_increments(ok, "uri")
    assert (
        check["status"] == "pass" and "unresolved_null_markers=1" in check["observed"]
    )
    bad = pd.DataFrame([_ev("A", None, category="eligible_regulation_offense")])
    (failed,) = corpus.check_scoring_increments(bad, "uri")
    assert (
        failed["status"] == "fail" and "non_integer_increments=1" in failed["observed"]
    )


def test_score_reconciliation_reports_unresolved_team_games_not_a_full_shortfall():
    events = pd.DataFrame(
        [
            _ev("A", 7, category="eligible_regulation_offense"),
            _ev("B", None, category="unresolved"),
        ]
    )
    repair = pd.DataFrame(
        [
            {
                "season": 2026,
                "game_id": 1,
                "outcome_valid": "True",
                "home_team": "A",
                "away_team": "B",
                "home_points": 7,
                "away_points": 10,
            }
        ]
    )
    (check,) = corpus.check_score_reconciliation(events, repair, "e", "r")
    assert (
        '"unresolved_team_games": 1' in check["observed"]
        and '"shortfall_count": 0' in check["observed"]
    )
    # Without nulls (legacy ledger) the same team-game is a shortfall, as before.
    legacy = pd.DataFrame(
        [
            _ev("A", 7, category="eligible_regulation_offense"),
            _ev("B", 0, category="unresolved"),
        ]
    )
    (old,) = corpus.check_score_reconciliation(legacy, repair, "e", "r")
    assert (
        '"shortfall_count": 1' in old["observed"]
        and '"unresolved_team_games": 0' in old["observed"]
    )


def test_blocker_diagnosis_ignores_null_increments_in_its_arithmetic():
    events = pd.DataFrame(
        [
            _ev("A", 7, category="eligible_regulation_offense", drive=1, event="a"),
            _ev("A", None, category="unresolved", drive=1, event="m"),
        ]
    )
    # The classifier must not raise or treat the null as a number; it still sees the 7.
    key = {
        "season": 2026,
        "game_id": 1,
        "team": "A",
        "ledger": 7.0,
        "final": 14.0,
        "diff": 7.0,
    }
    result = fbd.classify_key(key, events)
    assert result.ledger_points == 7.0 and result.cause


@pytest.mark.parametrize("fn,error", MODULES)
def test_candidate_disposition_is_rejected(fn, error):
    events = pd.DataFrame([_ev("A", 6, admission="candidate")])
    with pytest.raises(error, match="candidate"):
        fn(_population(), events)
