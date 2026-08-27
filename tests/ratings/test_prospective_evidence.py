"""Focused Phase 5 prospective policy and evidence contract tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from cks_picks_cfb.ratings.contracts import MeasurementContractError
from cks_picks_cfb.ratings.prospective import (
    descriptive_metrics,
    load_prospective_policy,
    validate_exact_game_keys,
    validate_freeze_clock,
    validate_parent_manifest,
    validate_source_times,
)


def test_policy_is_deterministic_and_pins_phase4_identities():
    policy = load_prospective_policy("conf/ratings/prospective_evidence_v1.yaml")
    assert (
        policy.policy_sha256
        == load_prospective_policy(
            "conf/ratings/prospective_evidence_v1.yaml"
        ).policy_sha256
    )
    assert policy.season == 2026
    assert policy.first_eligible_week == 1
    assert policy.hard_lead_seconds == 3600
    assert policy.required_eligible_slates == 6


def test_authentic_clock_uses_completion_not_the_requested_cutoff():
    policy = load_prospective_policy("conf/ratings/prospective_evidence_v1.yaml")
    kickoff = datetime(2026, 9, 5, 18, tzinfo=timezone.utc)
    start = kickoff - timedelta(hours=2)
    timing = validate_freeze_clock(
        requested_as_of=start - timedelta(minutes=5),
        freeze_started_at=start,
        freeze_completed_at=kickoff - timedelta(hours=1),
        earliest_kickoff=kickoff,
        policy=policy,
    )
    assert timing["measured_lead_seconds"] == 3600
    with pytest.raises(MeasurementContractError, match="hard lead"):
        validate_freeze_clock(
            requested_as_of=start - timedelta(hours=1),
            freeze_started_at=start,
            freeze_completed_at=kickoff - timedelta(seconds=3599),
            earliest_kickoff=kickoff,
            policy=policy,
        )


def test_parent_manifest_rejects_late_creation_and_cutoff():
    as_of = datetime(2026, 9, 5, 16, tzinfo=timezone.utc)
    ref = {"version_id": "v", "content_sha": "sha"}
    manifest = {
        **ref,
        "as_of": (as_of - timedelta(minutes=1)).isoformat(),
        "created_at": (as_of - timedelta(minutes=1)).isoformat(),
    }
    validate_parent_manifest(manifest, ref=ref, as_of=as_of, freeze_started_at=as_of)
    with pytest.raises(MeasurementContractError, match="created"):
        validate_parent_manifest(
            {**manifest, "created_at": (as_of + timedelta(seconds=1)).isoformat()},
            ref=ref,
            as_of=as_of,
            freeze_started_at=as_of,
        )


def test_source_timestamps_cannot_exceed_the_freeze_cutoff():
    cutoff = datetime(2026, 9, 5, 16, tzinfo=timezone.utc)
    validate_source_times(
        pd.DataFrame({"captured_at": [cutoff - timedelta(seconds=1)]}), as_of=cutoff
    )
    with pytest.raises(MeasurementContractError, match="exceeds"):
        validate_source_times(
            pd.DataFrame({"effective_at": [cutoff + timedelta(seconds=1)]}),
            as_of=cutoff,
        )


def test_exact_game_pairing_and_descriptive_metrics_are_market_free():
    schedule = pd.DataFrame({"game_id": [1, 2]})
    v4 = pd.DataFrame({"game_id": [1, 1, 2, 2], "target": ["margin", "total"] * 2})
    predictions = v4.assign(prediction_mean=0.0)
    assert validate_exact_game_keys(
        schedule=schedule, v4=v4, predictions=predictions
    ) == {1, 2}
    with pytest.raises(MeasurementContractError, match="differ"):
        validate_exact_game_keys(schedule=schedule, v4=v4[v4.game_id.eq(1)])
    metrics = descriptive_metrics(
        pd.DataFrame(
            {
                "target": ["margin", "total"],
                "actual": [3.0, 50.0],
                "prediction_mean": [2.0, 52.0],
                "v4_prediction": [4.0, 49.0],
            }
        )
    )
    assert metrics["rows"] == 2
    assert "market" not in str(metrics).lower()
