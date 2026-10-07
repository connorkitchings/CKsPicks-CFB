import pytest

from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.ops.v5_intended_update_release import AUTH_COLUMNS
from cks_picks_cfb.ratings_lab.artifacts import canonical_json
from scripts.pipeline.authorize_v5_intended_update_batch import (
    AuthorizationPacketError,
    apply_packet,
    validate_packet,
)


def _record(week: int, evidence_class: str) -> dict:
    record = {
        "authorization_id": f"auth-{week}",
        "environment": "preview",
        "season": 2026,
        "week": week,
        "prediction_run_id": f"run-{week}",
        "evidence_class": evidence_class,
        "model_id": "v5-intended-update-2026-v1",
        "inference_bundle_sha256": "a" * 64,
        "rating_manifest_sha256": "b" * 64,
        "forecast_manifest_uri": f"r2://forecast/{week}",
        "forecast_manifest_sha256": "c" * 64,
        "serving_manifest_uri": f"r2://serving/{week}",
        "serving_manifest_sha256": "d" * 64,
        "verifier_uri": f"r2://verify/{week}",
        "verifier_sha256": "e" * 64,
        "prediction_artifact_uri": f"r2://predictions/{week}",
        "prediction_artifact_sha256": "f" * 64,
        "decision_ref": "decision-7a",
    }
    return {
        **record,
        "record_sha256": __import__("hashlib")
        .sha256(canonical_json(record))
        .hexdigest(),
    }


def _packet(cutover=5):
    bundle = {
        "approval_id": "bundle-approval",
        "model_id": "v5-intended-update-2026-v1",
        "inference_bundle_sha256": "a" * 64,
        "first_live_season": 2026,
        "first_live_week": cutover,
        "decision_ref": "decision-7a",
    }
    import hashlib

    bundle["record_sha256"] = hashlib.sha256(canonical_json(bundle)).hexdigest()
    return signed_payload(
        {
            "schema_version": "v5_intended_update_authorization_packet_v1",
            "environment": "preview",
            "season": 2026,
            "cutover_week": cutover,
            "decision_ref": "decision-7a",
            "bundle_approval": bundle,
            "run_authorizations": [
                _record(week, "pending" if week == cutover else "replay")
                for week in range(cutover + 1)
            ],
        }
    )


def test_authorization_packet_binds_bundle_cutover_and_contiguous_runs():
    result = validate_packet(_packet(), environment="preview")
    assert result["cutover_week"] == 5
    assert sorted(result["records"]) == list(range(6))


def test_authorization_packet_rejects_tampering_gaps_and_timing_mismatch():
    packet = _packet()
    packet["run_authorizations"][0]["prediction_run_id"] = "different"
    with pytest.raises(AuthorizationPacketError, match="checksum mismatch"):
        validate_packet(packet, environment="preview")

    packet = _packet()
    packet["run_authorizations"].pop(2)
    packet = signed_payload(
        {key: value for key, value in packet.items() if key != "manifest_sha256"}
    )
    with pytest.raises(AuthorizationPacketError, match="contiguous"):
        validate_packet(packet, environment="preview")

    packet = _packet()
    packet["run_authorizations"][5] = _record(5, "replay")
    packet = signed_payload(
        {key: value for key, value in packet.items() if key != "manifest_sha256"}
    )
    with pytest.raises(AuthorizationPacketError, match="timing class"):
        validate_packet(packet, environment="preview")


class Cursor:
    def __init__(self, packet):
        validated = validate_packet(packet, environment="preview")
        self.rows = [
            tuple(
                validated["bundle"][key]
                for key in (
                    "approval_id",
                    "model_id",
                    "inference_bundle_sha256",
                    "first_live_season",
                    "first_live_week",
                    "decision_ref",
                )
            ),
            *[
                tuple(validated["records"][week][key] for key in AUTH_COLUMNS)
                for week in sorted(validated["records"])
            ],
        ]
        self.executed = []

    def execute(self, sql, params=()):
        self.executed.append((sql, params))

    def fetchone(self):
        return self.rows.pop(0)


def test_authorization_rows_register_under_exclusive_id_locks():
    packet = _packet()
    cur = Cursor(packet)
    apply_packet(cur, packet, environment="preview")
    locks = [sql for sql, _ in cur.executed if "pg_advisory_xact_lock(%s)" in sql]
    inserts = [sql for sql, _ in cur.executed if sql.startswith("INSERT INTO")]
    assert len(locks) == 7
    assert len(inserts) == 7
