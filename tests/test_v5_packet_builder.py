import copy

import pytest

from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.ops import v5_packet_builder as builder
from cks_picks_cfb.ops.v5_batch_selection_v2 import (
    V5BatchSelectionError,
    validate_v2_packet,
)
from scripts.pipeline.authorize_v5_intended_update_batch import (
    AuthorizationPacketError,
    validate_packet,
)
from tests.test_v5_batch_selection_v2 import Storage, _ref

CUTOVER = 5


def _manifest(week, *, environment="preview", prefix="new"):
    return {
        "run_id": f"{prefix}-{week}",
        "week": week,
        "evidence_class": "pending" if week == CUTOVER else "replay",
        "model_id": "v5-test",
        "inference_bundle_sha256": "a" * 64,
        "v5_rating_replay_manifest_sha256": "b" * 64,
        "v5_live_forecast_manifest_uri": f"research/forecast/{week}.json",
        "v5_live_forecast_manifest_sha256": "c" * 64,
        "v5_intended_update_serving_manifest_uri": f"research/serving/{week}.json",
        "v5_intended_update_serving_manifest_sha256": "d" * 64,
        "v5_intended_update_verifier_uri": f"research/verifier/{week}.json",
        "v5_intended_update_verifier_sha256": "e" * 64,
        "artifact_uri": f"artifacts/{environment}/predictions/{prefix}-{week}.csv",
        "artifact_sha256": f"{week:x}" * 64,
    }


def _manifests(**kwargs):
    return {week: _manifest(week, **kwargs) for week in range(CUTOVER + 1)}


def _refs(storage):
    row = {
        "season": 2026,
        "as_of_week": 5,
        "team": "Alabama",
        "role": "offense",
        "metric": "m",
        "value": 0.2,
        "n": 1,
        "games": 1,
        "rank": 1,
        "cohort_size": 1,
        "source_versions": {"silver": "v1"},
    }

    def stats(uri, value):
        return _ref(
            storage,
            uri,
            {
                "schema_version": "v5_team_stats_release_payload_v1",
                "environment": "preview",
                "season": 2026,
                "scope": [{"season": 2026, "as_of_week": 5}],
                "rows": [{**row, "value": value}],
            },
        )

    def prospective(uri):
        return _ref(
            storage,
            uri,
            {
                "schema_version": "v5_prospective_records_release_payload_v1",
                "environment": "preview",
                "season": 2026,
                "rows": [],
            },
        )

    before, after = stats("r2://s/before", 0.2), stats("r2://s/after", 0.3)
    verifier = _ref(
        storage,
        "r2://s/verify",
        {
            "state": "verified",
            "before_sha256": before["sha256"],
            "after_sha256": after["sha256"],
            "decision_ref": "decision-x",
        },
    )
    return {
        "team_stats_before": before,
        "team_stats_after": after,
        "team_stats_verifier": verifier,
        "prospective_records_before": prospective("r2://p/before"),
        "prospective_records_after": prospective("r2://p/after"),
    }


def _certs(storage, prefix):
    return [
        _ref(
            storage,
            f"r2://c/{prefix}/{week}",
            {
                "state": "verified",
                "season": 2026,
                "week": week,
                "run_id": f"{prefix}-{week}",
                "finals_complete": True,
                "finals_stabilized_at": "2026-10-01T00:00:00+00:00",
            },
        )
        | {"week": week}
        for week in range(CUTOVER)
    ]


def _selection():
    storage = Storage()
    packet = builder.build_selection_packet(
        _manifests(),
        environment="preview",
        cutover_week=CUTOVER,
        decision_ref="decision-x",
        expected_current_runs={w: f"old-{w}" for w in range(CUTOVER + 1)},
        protected_runs={6: "old-6"},
        certifications=_certs(storage, "new"),
        payload_refs=_refs(storage),
    )
    return packet, storage


def test_authorization_packet_passes_the_applying_validator():
    packet = builder.build_authorization_packet(
        _manifests(),
        environment="preview",
        cutover_week=CUTOVER,
        decision_ref="decision-x",
    )
    validated = validate_packet(packet, environment="preview")
    assert sorted(validated["records"]) == list(range(6))
    assert validated["bundle"]["first_live_week"] == CUTOVER
    with pytest.raises(AuthorizationPacketError):
        validate_packet(packet, environment="production")


def test_selection_packet_passes_the_v2_validator():
    packet, storage = _selection()
    plan = validate_v2_packet(packet, environment="preview", storage=storage)
    assert plan["after"][CUTOVER] == "new-5"
    assert plan["before"][0] == "old-0"


def test_rollback_packet_is_the_exact_inverse_and_validates():
    packet, storage = _selection()
    refs = _refs(storage)
    refs["team_stats_before"], refs["team_stats_after"] = (
        refs["team_stats_after"],
        refs["team_stats_before"],
    )
    verifier = _ref(
        storage,
        "r2://s/rollback-verify",
        {
            "state": "verified",
            "before_sha256": refs["team_stats_before"]["sha256"],
            "after_sha256": refs["team_stats_after"]["sha256"],
            "decision_ref": "decision-x",
        },
    )
    refs["team_stats_verifier"] = verifier
    rollback = builder.build_rollback_packet(
        packet,
        prior_manifests=_manifests(prefix="old"),
        certifications=_certs(storage, "old"),
        payload_refs=refs,
    )
    plan = validate_v2_packet(rollback, environment="preview", storage=storage)
    assert plan["rollback"] is True
    assert plan["after"][0] == "old-0"
    assert plan["before"][0] == "new-0"
    assert rollback["expected_current_runs"] == packet["replacement_runs"]


def test_builder_refuses_wrong_namespace_gaps_and_wrong_timing_class():
    with pytest.raises(builder.PacketBuildError, match="namespace"):
        builder.build_authorization_packet(
            _manifests(environment="preview"),
            environment="production",
            cutover_week=CUTOVER,
            decision_ref="d",
        )
    gap = _manifests()
    del gap[3]
    with pytest.raises(builder.PacketBuildError, match="contiguous"):
        builder.build_authorization_packet(
            gap, environment="preview", cutover_week=CUTOVER, decision_ref="d"
        )
    wrong = copy.deepcopy(_manifests())
    wrong[CUTOVER]["evidence_class"] = "replay"
    with pytest.raises(builder.PacketBuildError, match="expected pending"):
        builder.build_authorization_packet(
            wrong, environment="preview", cutover_week=CUTOVER, decision_ref="d"
        )
    mixed = _manifests()
    mixed[2]["inference_bundle_sha256"] = "9" * 64
    with pytest.raises(builder.PacketBuildError, match="one model"):
        builder.build_authorization_packet(
            mixed, environment="preview", cutover_week=CUTOVER, decision_ref="d"
        )


def test_selection_builder_refuses_reused_runs_and_missing_evidence():
    storage = Storage()
    common = dict(
        environment="preview",
        cutover_week=CUTOVER,
        decision_ref="decision-x",
        protected_runs={6: "old-6"},
        certifications=_certs(storage, "new"),
        payload_refs=_refs(storage),
    )
    with pytest.raises(builder.PacketBuildError, match="reuse"):
        builder.build_selection_packet(
            _manifests(),
            expected_current_runs={w: f"new-{w}" for w in range(6)},
            **common,
        )
    with pytest.raises(builder.PacketBuildError, match="certifications"):
        builder.build_selection_packet(
            _manifests(),
            expected_current_runs={w: f"old-{w}" for w in range(6)},
            **{**common, "certifications": common["certifications"][:3]},
        )


def test_tampering_a_built_packet_breaks_its_signature():
    packet, storage = _selection()
    forged = signed_payload({**packet, "decision_ref": "other"}) | {
        "manifest_sha256": packet["manifest_sha256"]
    }
    with pytest.raises(V5BatchSelectionError):
        validate_v2_packet(forged, environment="preview", storage=storage)
