"""A forward cutover packet needs a passing audit of exactly the runs it selects."""

import copy

import pytest

from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.ops.v5_batch_selection_v2 import (
    V5BatchSelectionError,
    validate_v2_packet,
)
from tests import test_v5_packet_builder as fixtures


def _with_audit(packet, ref):
    body = {k: v for k, v in copy.deepcopy(packet).items() if k != "manifest_sha256"}
    if ref is None:
        body.pop("leakage_audit", None)
    else:
        body["leakage_audit"] = ref
    return signed_payload(body)


def _error(packet, storage):
    with pytest.raises(V5BatchSelectionError) as caught:
        validate_v2_packet(packet, environment="preview", storage=storage)
    return str(caught.value)


def test_a_passing_receipt_for_exactly_the_selected_runs_is_accepted():
    packet, storage = fixtures._selection()
    plan = validate_v2_packet(packet, environment="preview", storage=storage)
    assert plan["after"][fixtures.CUTOVER] == f"new-{fixtures.CUTOVER}"


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"state": "failed"}, "did not pass"),
        (
            {
                "violations": [
                    {"rule": "c_forecast_time", "game_id": 1, "week": 5, "detail": "x"}
                ]
            },
            "did not pass",
        ),
        ({"games_checked": 0}, "checked no games"),
        ({"environment": "production"}, "schema or scope"),
        ({"season": 2025}, "schema or scope"),
        ({"schema_version": "other_v1"}, "schema or scope"),
        ({"runs": {"0": "new-0"}}, "exactly the packet's selected runs"),
        (
            {"runs": {str(w): f"old-{w}" for w in range(fixtures.CUTOVER + 1)}},
            "exactly the packet's selected runs",
        ),
    ],
)
def test_a_receipt_that_does_not_cover_the_packet_refuses_it(overrides, message):
    packet, storage = fixtures._selection()
    ref = fixtures._audit(storage, uri="r2://audit/other", **overrides)
    assert message in _error(_with_audit(packet, ref), storage)


def test_a_missing_or_unverifiable_receipt_refuses_the_packet():
    packet, storage = fixtures._selection()
    assert "reference is incomplete" in _error(_with_audit(packet, None), storage)
    forged = dict(packet["leakage_audit"], sha256="0" * 64)
    assert "checksum differs" in _error(_with_audit(packet, forged), storage)


def test_a_receipt_whose_content_changed_after_signing_is_refused():
    import hashlib

    packet, storage = fixtures._selection()
    original = storage.objects[packet["leakage_audit"]["uri"]]
    # Flip the verdict inside the signed content, then re-point the ref at the raw bytes
    # so only the signature (not the raw checksum) can catch it.
    storage.objects["r2://audit/tampered"] = original.replace(
        b'"games_checked":100', b'"games_checked":999'
    )
    assert storage.objects["r2://audit/tampered"] != original
    ref = {
        "uri": "r2://audit/tampered",
        "sha256": hashlib.sha256(storage.objects["r2://audit/tampered"]).hexdigest(),
    }
    message = _error(_with_audit(packet, ref), storage)
    assert "did not pass" not in message and "checked no games" not in message


def test_a_rollback_packet_is_not_asked_for_one():
    packet, storage = fixtures._selection()
    refs = fixtures._refs(storage)
    refs["team_stats_before"], refs["team_stats_after"] = (
        refs["team_stats_after"],
        refs["team_stats_before"],
    )
    refs["team_stats_verifier"] = fixtures._ref(
        storage,
        "r2://s/gate-rollback-verify",
        {
            "state": "verified",
            "before_sha256": refs["team_stats_before"]["sha256"],
            "after_sha256": refs["team_stats_after"]["sha256"],
            "decision_ref": "decision-x",
        },
    )
    rollback = fixtures.builder.build_rollback_packet(
        packet,
        prior_manifests=fixtures._manifests(prefix="old"),
        certifications=fixtures._certs(storage, "old"),
        payload_refs=refs,
    )
    assert "leakage_audit" not in rollback
    assert validate_v2_packet(rollback, environment="preview", storage=storage)[
        "rollback"
    ]
