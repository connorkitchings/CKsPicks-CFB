"""Step 5C: per-group admission and the independent v1 admitted-ledger verifier."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from cks_picks_cfb.ratings import admission as adm
from cks_picks_cfb.ratings import possession_verification as pv
from cks_picks_cfb.ratings import score_envelope_r1 as r1


def _play(drive, number, quarter, offense, off_score, def_score):
    return dict(
        season=2024,
        week=1,
        game_id=1,
        drive_number=drive,
        play_number=number,
        quarter=quarter,
        offense=offense,
        defense="B" if offense == "A" else "A",
        offense_score=off_score,
        defense_score=def_score,
        st=0,
        penalty=0,
        twopoint=0,
        garbage=0,
        ppa=0.1,
        play_type="Rush",
    )


@pytest.fixture
def game():
    # A scores 7, a glitch reports A back at 0, then A is reported at 7 again. The baseline
    # rolls the first seven back and re-credits it later; R1 keeps the first seven.
    byplay = pd.DataFrame(
        [
            _play(1, 1, 1, "A", 0, 0),
            _play(1, 2, 1, "A", 7, 0),
            _play(2, 1, 2, "B", 0, 0),
            _play(3, 1, 3, "A", 7, 0),
        ]
    )
    population = pd.DataFrame(
        [
            dict(
                season=2024,
                game_id=1,
                home_team="A",
                away_team="B",
                home_points=7.0,
                away_points=0.0,
                outcome_valid=True,
            )
        ]
    )
    plays, _, baseline = pv._reconstruct_ledgers(
        byplay=byplay, population=population, outcomes=None
    )
    _, _, candidate = pv._reconstruct_ledgers(
        byplay=pv._independent_envelope(plays, pv._certified_finals(population, None)),
        population=population,
        outcomes=None,
    )
    return byplay, population, baseline, candidate


def _decisions(baseline, candidate, decision):
    members: dict[str, list[str]] = {}
    groups = r1.changed_groups(baseline, candidate, members_out=members)
    assert len(groups) == 1
    status = groups.assign(
        status="corroborated" if decision == adm.ADMITTED else "game_unusable"
    )
    return adm.build_decisions(status, members), members


def test_decide_fails_closed():
    assert adm.decide("corroborated") == adm.ADMITTED
    assert adm.decide("game_unusable") == adm.REVERTED_UNVERIFIED
    assert adm.decide("indistinguishable_at_drive_level") == adm.REVERTED_UNVERIFIED
    assert adm.decide("no_cfbd_data") == adm.REVERTED_UNVERIFIED
    assert adm.decide("cfbd_supports_baseline") == adm.REVERTED_CONTRADICTED
    assert adm.decide("cfbd_matches_neither") == adm.REVERTED_CONTRADICTED
    assert adm.decide("anything_new") == adm.REVERTED_UNVERIFIED


def test_fixture_changes_attribution_not_points(game):
    _, _, baseline, candidate = game
    assert baseline["score_increment"].sum() == candidate["score_increment"].sum() == 7
    assert len(baseline) == 2 and len(candidate) == 1


def _verify(game, decisions, admitted, **kw):
    byplay, population, baseline, _ = game
    return pv.verify_admitted_ledger(
        byplay=byplay,
        population=population,
        outcomes=None,
        baseline_events=baseline,
        admitted_events=admitted,
        decisions=decisions,
        **kw,
    )


@pytest.mark.parametrize("decision", [adm.ADMITTED, adm.REVERTED_UNVERIFIED])
def test_verifier_accepts_correct_admission(game, decision):
    _, _, baseline, candidate = game
    decisions, members = _decisions(baseline, candidate, decision)
    admitted = adm.build_admitted_events(baseline, candidate, decisions, members)
    report = _verify(game, decisions, admitted)
    assert report["ok"], report["problems"]
    if decision == adm.ADMITTED:
        assert len(admitted) == 1 and set(admitted["admission"]) == {"corroborated"}
    else:
        assert len(admitted) == 2 and set(admitted["admission"]) == {decision}
        assert (
            admitted[baseline.columns]
            .reset_index(drop=True)
            .equals(
                baseline.sort_values(
                    ["game_id", "team", "source_event_id"]
                ).reset_index(drop=True)
            )
        )


def test_verifier_rejects_candidate_events_under_a_reverted_decision(game):
    _, _, baseline, candidate = game
    decisions, members = _decisions(baseline, candidate, adm.REVERTED_UNVERIFIED)
    admitted_decisions, _ = _decisions(baseline, candidate, adm.ADMITTED)
    tampered = adm.build_admitted_events(
        baseline, candidate, admitted_decisions, members
    ).assign(admission="baseline_unchanged")
    report = _verify(game, decisions, tampered)
    assert not report["ok"]
    assert any("admitted ledger event set differs" in p for p in report["problems"])


def test_verifier_rejects_uncovered_changed_events(game):
    _, _, baseline, candidate = game
    decisions, members = _decisions(baseline, candidate, adm.ADMITTED)
    admitted = adm.build_admitted_events(baseline, candidate, decisions, members)
    report = _verify(game, decisions.iloc[0:0], admitted)
    assert not report["ok"]
    assert any("belong to no decision group" in p for p in report["problems"])


def test_verifier_rejects_a_changed_baseline(game):
    _, _, baseline, candidate = game
    decisions, members = _decisions(baseline, candidate, adm.ADMITTED)
    admitted = adm.build_admitted_events(baseline, candidate, decisions, members)
    broken = baseline.copy()
    broken.loc[broken.index[0], "score_increment"] = 6
    byplay, population, _, _ = game
    report = pv.verify_admitted_ledger(
        byplay=byplay,
        population=population,
        outcomes=None,
        baseline_events=broken,
        admitted_events=admitted,
        decisions=decisions,
    )
    assert not report["ok"]
    assert any("baseline reproduction failed" in p for p in report["problems"])


def test_verifier_rejects_a_phantom_group_event(game):
    _, _, baseline, candidate = game
    decisions, members = _decisions(baseline, candidate, adm.ADMITTED)
    admitted = adm.build_admitted_events(baseline, candidate, decisions, members)
    bad = decisions.copy()
    bad["event_ids"] = [
        json.dumps(json.loads(bad["event_ids"].iloc[0]) + ["2024:1:9:9"])
    ]
    report = _verify(game, bad, admitted)
    assert not report["ok"]


def test_expected_admitted_count_is_enforced(game):
    _, _, baseline, candidate = game
    decisions, members = _decisions(baseline, candidate, adm.ADMITTED)
    admitted = adm.build_admitted_events(baseline, candidate, decisions, members)
    assert _verify(game, decisions, admitted, expected_admitted_groups=1)["ok"]
    assert not _verify(game, decisions, admitted, expected_admitted_groups=2)["ok"]
