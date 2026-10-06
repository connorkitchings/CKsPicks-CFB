import hashlib

import pytest

from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.ops.v5_batch_selection_v2 import (
    V5BatchSelectionError,
    validate_v2_packet,
)
from cks_picks_cfb.ratings_lab.artifacts import canonical_json


class Storage:
    def __init__(self):
        self.objects = {}

    def read_bytes(self, uri):
        return self.objects[uri]


def _ref(storage, uri, body):
    signed = signed_payload(body)
    raw = canonical_json(signed)
    storage.objects[uri] = raw
    return {"uri": uri, "sha256": hashlib.sha256(raw).hexdigest()}


def _packet():
    storage = Storage()
    before_runs = {str(week): f"old-{week}" for week in range(6)}
    after_runs = {str(week): f"new-{week}" for week in range(6)}
    bundle = {
        "approval_id": "bundle-7a",
        "model_id": "v5-intended-update-2026-v1",
        "inference_bundle_sha256": "a" * 64,
        "first_live_season": 2026,
        "first_live_week": 5,
        "decision_ref": "decision-7a",
    }
    bundle["record_sha256"] = hashlib.sha256(canonical_json(bundle)).hexdigest()
    authorizations = []
    for week in range(6):
        record = {
            "authorization_id": f"auth-{week}",
            "environment": "preview",
            "season": 2026,
            "week": week,
            "prediction_run_id": f"new-{week}",
            "evidence_class": "pending" if week == 5 else "replay",
            "model_id": bundle["model_id"],
            "inference_bundle_sha256": bundle["inference_bundle_sha256"],
            "rating_manifest_sha256": "b" * 64,
            "forecast_manifest_uri": f"r2://forecast/{week}",
            "forecast_manifest_sha256": "c" * 64,
            "serving_manifest_uri": f"r2://serving/{week}",
            "serving_manifest_sha256": "d" * 64,
            "verifier_uri": f"r2://verifier/{week}",
            "verifier_sha256": "e" * 64,
            "prediction_artifact_uri": f"r2://predictions/{week}",
            "prediction_artifact_sha256": "f" * 64,
            "decision_ref": "decision-7a",
        }
        authorizations.append(
            {**record, "record_sha256": hashlib.sha256(canonical_json(record)).hexdigest()}
        )

    row_before = {
        "season": 2026,
        "as_of_week": 5,
        "team": "Alabama",
        "role": "offense",
        "metric": "ppa_per_play",
        "value": 0.2,
        "n": 100,
        "games": 5,
        "rank": 3,
        "cohort_size": 130,
        "source_versions": {"silver": "silver-v1"},
    }
    row_after = {**row_before, "value": 0.25}
    stats_before = _ref(
        storage,
        "r2://stats/before",
        {
            "schema_version": "v5_team_stats_release_payload_v1",
            "environment": "preview",
            "season": 2026,
            "scope": [{"season": 2026, "as_of_week": 5}],
            "rows": [row_before],
        },
    )
    stats_after = _ref(
        storage,
        "r2://stats/after",
        {
            "schema_version": "v5_team_stats_release_payload_v1",
            "environment": "preview",
            "season": 2026,
            "scope": [{"season": 2026, "as_of_week": 5}],
            "rows": [row_after],
        },
    )
    verifier = _ref(
        storage,
        "r2://stats/verify",
        {
            "schema_version": "v5_team_stats_release_verification_v1",
            "state": "verified",
            "before_sha256": stats_before["sha256"],
            "after_sha256": stats_after["sha256"],
            "decision_ref": "decision-7a",
        },
    )
    prospective_before = _ref(
        storage,
        "r2://prospective/before",
        {
            "schema_version": "v5_prospective_records_release_payload_v1",
            "environment": "preview",
            "season": 2026,
            "rows": [],
        },
    )
    prospective_after = _ref(
        storage,
        "r2://prospective/after",
        {
            "schema_version": "v5_prospective_records_release_payload_v1",
            "environment": "preview",
            "season": 2026,
            "rows": [],
        },
    )
    certs = [
        _ref(
            storage,
            f"r2://certs/{week}",
            {
                "schema_version": "v5_replay_certification_v1",
                "state": "verified",
                "season": 2026,
                "week": week,
                "run_id": f"new-{week}",
                "finals_complete": True,
                "finals_stabilized_at": "2026-10-01T00:00:00+00:00",
            },
        )
        | {"week": week}
        for week in range(5)
    ]
    packet = signed_payload(
        {
            "schema_version": "v5_intended_update_batch_selection_v2",
            "environment": "preview",
            "season": 2026,
            "cutover_week": 5,
            "decision_ref": "decision-7a",
            "expected_current_runs": before_runs,
            "replacement_runs": after_runs,
            "certified_completed_weeks": list(range(5)),
            "protected_runs": {"6": "old-6"},
            "expected_current_week": {"season": 2026, "week": 5, "run_id": "old-5"},
            "replacement_current_week": {"season": 2026, "week": 5, "run_id": "new-5"},
            "bundle_approval": bundle,
            "run_authorizations": authorizations,
            "completed_week_certifications": certs,
            "team_stats_before": stats_before,
            "team_stats_after": stats_after,
            "team_stats_verifier": verifier,
            "prospective_records_before": prospective_before,
            "prospective_records_after": prospective_after,
        }
    )
    return packet, storage


def test_v2_packet_verifies_signed_refs_complete_keys_and_cutover_bindings():
    packet, storage = _packet()
    result = validate_v2_packet(packet, environment="preview", storage=storage)
    assert result["cutover_week"] == 5
    assert result["after"][5] == "new-5"
    assert result["payloads"]["team_stats_after"]["rows"][0]["value"] == 0.25


def test_v2_packet_fails_closed_on_tampered_bytes_normalized_duplicate_or_key_drift():
    packet, storage = _packet()
    storage.objects["r2://stats/after"] += b" "
    with pytest.raises(V5BatchSelectionError, match="checksum"):
        validate_v2_packet(packet, environment="preview", storage=storage)

    packet, storage = _packet()
    packet["expected_current_runs"]["05"] = packet["expected_current_runs"].pop("5")
    packet["expected_current_runs"]["5"] = "duplicate-week-5"
    packet = signed_payload({key: value for key, value in packet.items() if key != "manifest_sha256"})
    with pytest.raises(V5BatchSelectionError, match="duplicate"):
        validate_v2_packet(packet, environment="preview", storage=storage)

    packet, storage = _packet()
    packet["team_stats_after"] = _ref(
        storage,
        "r2://stats/after-missing-row",
        {
            "schema_version": "v5_team_stats_release_payload_v1",
            "environment": "preview",
            "season": 2026,
            "scope": [{"season": 2026, "as_of_week": 5}],
            "rows": [],
        },
    )
    packet = signed_payload({key: value for key, value in packet.items() if key != "manifest_sha256"})
    with pytest.raises(V5BatchSelectionError, match="identical complete keys"):
        validate_v2_packet(packet, environment="preview", storage=storage)


def test_v2_packet_rejects_prospective_record_drift():
    packet, storage = _packet()
    packet["prospective_records_after"] = _ref(
        storage,
        "r2://prospective/drift",
        {
            "schema_version": "v5_prospective_records_release_payload_v1",
            "environment": "preview",
            "season": 2026,
            "rows": [{
                "season": 2026,
                "week": 5,
                "run_id": "live-5",
                "freeze_receipt_uri": "r2://receipt",
                "freeze_receipt_sha256": "a" * 64,
                "frozen_at": "2026-10-01T00:00:00+00:00",
                "first_kickoff_utc": "2026-10-10T00:00:00+00:00",
                "decision_ref": "decision",
            }],
        },
    )
    packet = signed_payload({key: value for key, value in packet.items() if key != "manifest_sha256"})
    with pytest.raises(V5BatchSelectionError, match="preserve prospective records exactly"):
        validate_v2_packet(packet, environment="preview", storage=storage)


def test_v2_packet_current_pointer_must_bind_to_the_exact_expected_run():
    packet, storage = _packet()
    packet["expected_current_week"] = {"season": 2026, "week": 5, "run_id": "old-4"}
    packet = signed_payload({key: value for key, value in packet.items() if key != "manifest_sha256"})
    with pytest.raises(V5BatchSelectionError, match="current-week before/after bindings"):
        validate_v2_packet(packet, environment="preview", storage=storage)
