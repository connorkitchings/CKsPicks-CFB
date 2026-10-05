"""Evidence builder/verifier and season-feature populations on synthetic data."""

from __future__ import annotations

import hashlib
import json

import pandas as pd
import pytest

from cks_picks_cfb.metrics import evidence as ev
from cks_picks_cfb.metrics import season_features as sf
from cks_picks_cfb.metrics.contracts import evidence_problems

BUNDLE = json.dumps([{"gameId": 10}, {"gameId": 11}]).encode()
SHA = hashlib.sha256(BUNDLE).hexdigest()
RECORD = {
    "file": "b1.json",
    "sha256": SHA,
    "captured_at_utc": "2026-09-01T00:00:00+00:00",
}


def _read(name):
    assert name == "b1.json"
    return BUNDLE


def _ledger(group="g1", admission="corroborated", ids=None):
    ids = ids if ids is not None else [ev.evidence_id(group, SHA)]
    return pd.DataFrame(
        [
            {
                "season": 2024,
                "game_id": 10,
                "team": "A",
                "source_event_id": f"e{i}",
                "quarter": 2,
                "play_number": i,
                "associated_possession_id": "p1",
                "conversion_for_event_id": None,
                "unit_category": "offense",
                "allocation_group_id": group,
                "admission": admission,
                "evidence_ids": json.dumps(sorted(ids)),
            }
            for i in (1, 2)
        ]
    )


def _decisions(decision="admitted"):
    return pd.DataFrame(
        [
            {
                "group_id": "g1",
                "season": 2024,
                "game_id": 10,
                "team": "A",
                "primary_cause": "dip_restore",
                "net_points": 7.0,
                "decision": decision,
                "event_ids": json.dumps(["e1", "e2"]),
            }
        ]
    )


def test_evidence_id_is_full_digest_tied_to_bundle():
    value = ev.evidence_id("g1", SHA)
    assert value.startswith("cfbd_drives:") and len(value.split(":")[1]) == 64
    assert value != ev.evidence_id("g1", "0" * 64)


def test_bundle_index_verifies_hash_and_rejects_ambiguity():
    index = ev.bundle_index([RECORD], _read)
    assert set(index) == {10, 11}
    with pytest.raises(ev.EvidenceError, match="hash mismatch"):
        ev.bundle_index([{**RECORD, "sha256": "0" * 64}], _read)
    other = {**RECORD, "file": "b2.json", "sha256": "1" * 64}
    with pytest.raises(ev.EvidenceError):
        ev.bundle_index(
            [RECORD, other], lambda n: BUNDLE if n == "b1.json" else b'[{"gameId": 10}]'
        )


def test_build_evidence_rows_satisfy_the_contract_and_resolve():
    index = ev.bundle_index([RECORD], _read)
    frame = ev.build_evidence(_decisions(), _ledger(), index)
    assert len(frame) == 1 and evidence_problems(frame) == []
    row = frame.iloc[0]
    assert row.rights_basis == ev.RIGHTS_BASIS and row.terms_uri == ev.TERMS_URI
    assert json.loads(row.source_locator)["event_ids"] == ["e1", "e2"]
    assert ev.evidence_reference_problems(frame, _ledger(), index, _read) == []


def test_reference_problems_catch_tamper_and_unresolved():
    index = ev.bundle_index([RECORD], _read)
    frame = ev.build_evidence(_decisions(), _ledger(), index)
    assert ev.evidence_reference_problems(
        frame, _ledger(ids=["cfbd_drives:" + "9" * 64]), index, _read
    )
    assert ev.evidence_reference_problems(
        frame, _ledger(admission="reverted_unverified"), index, _read
    )
    assert ev.evidence_reference_problems(
        frame, _ledger(), index, lambda n: b"tampered"
    )
    wrong_group = _ledger(group="other")
    wrong_group["evidence_ids"] = _ledger()["evidence_ids"]
    assert ev.evidence_reference_problems(frame, wrong_group, index, _read)


def test_build_evidence_requires_a_retained_bundle():
    with pytest.raises(ev.EvidenceError, match="no retained bundle"):
        ev.build_evidence(_decisions(), _ledger(), {})


def _games():
    return pd.DataFrame(
        {
            "season": [2024] * 3,
            "game_id": [1, 2, 3],
            "season_type": ["regular", "regular", "postseason"],
            "home_fbs": [True, True, True],
            "away_fbs": [True, False, True],
            "forecast_eligible": [True, True, True],
            "measurement_usable": [True, True, False],
        }
    )


def test_populations_are_distinct_and_explicit():
    games = _games()
    assert sf.population_game_ids(games, "website") == {(2024, 1)}
    assert sf.population_game_ids(games, "v5") == {(2024, 1), (2024, 2)}
    with pytest.raises(ValueError):
        sf.population_game_ids(games, "other")


def test_season_features_aggregates_each_population_separately():
    def row(game, week, num):
        return {
            "season": 2024,
            "week": week,
            "game_id": game,
            "team": "A",
            "role": "offense",
            "metric": "ppp",
            "numerator": num,
            "denominator": 10.0,
            "coverage_status": "observed",
            "missing_reason": None,
        }

    metrics = pd.DataFrame([row(1, 1, 20.0), row(2, 2, 40.0), row(3, 3, 99.0)])
    raw = sf.season_features(metrics, _games())
    assert list(raw.columns) == list(sf.OUTPUT_COLUMNS)
    out = raw.set_index("population")
    assert out.loc["website", "games"] == 1 and out.loc[
        "website", "value"
    ] == pytest.approx(2.0)
    assert out.loc["v5", "games"] == 2 and out.loc["v5", "value"] == pytest.approx(3.0)


def test_season_level_features_schema_matches_the_builder_output():
    from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame

    schema = schema_for("season_level_features", "season_level_features_v1")
    assert tuple(schema.required) == sf.OUTPUT_COLUMNS
    frame = pd.DataFrame(
        [
            {
                "season": 2024,
                "team": "A",
                "role": "offense",
                "metric": "ppp",
                "population": "website",
                "games": 1,
                "games_missing": 0,
                "numerator": 2.0,
                "denominator": 1.0,
                "value": 2.0,
                "coverage_status": "observed",
                "missing_reason": None,
                "as_of_week": 3,
            }
        ]
    )
    validate_frame(frame, schema)


def test_locator_separates_allocated_events_from_replaced_baseline_events():
    index = ev.bundle_index([RECORD], _read)
    decisions = _decisions()
    decisions["event_ids"] = json.dumps(["e1", "e2", "old1"])
    frame = ev.build_evidence(decisions, _ledger(), index)
    locator = json.loads(frame.iloc[0].source_locator)
    assert locator["event_ids"] == ["e1", "e2"]
    assert locator["replaced_baseline_event_ids"] == ["old1"]
    assert ev.evidence_reference_problems(frame, _ledger(), index, _read) == []
    bad = _ledger()
    bad.loc[len(bad)] = {**bad.iloc[0].to_dict(), "source_event_id": "old1"}
    assert ev.evidence_reference_problems(frame, bad, index, _read)
