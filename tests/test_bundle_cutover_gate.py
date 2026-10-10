"""A bundle approval registered at a display-only week stays valid for a later cutover.

The registry keeps one approval row per model and bundle, so the Week 6 approval of the
B2 bundle cannot be re-registered at Week 7. These tests pin the shared rule and its
three call sites (packet builder, authorization validator, selection controller).
"""

import pytest

from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.ops import v5_packet_builder as builder
from cks_picks_cfb.ops.v5_batch_selection_v2 import (
    V5BatchSelectionError,
    bundle_covers_cutover,
    validate_v2_packet,
)
from scripts.pipeline.authorize_v5_intended_update_batch import (
    AuthorizationPacketError,
    validate_packet,
)
from tests import test_v5_packet_builder as fixtures
from tests.test_v5_batch_selection_v2 import Storage

CUTOVER = 7
MODEL = "v5-test"
BUNDLE_SHA = "a" * 64


@pytest.fixture(autouse=True)
def _week7_fixtures(monkeypatch):
    monkeypatch.setattr(fixtures, "CUTOVER", CUTOVER)


def _registered(first_live_week=6, decision_ref="decision-week6"):
    return {
        "approval_id": "approval-registered-at-week6",
        "model_id": MODEL,
        "inference_bundle_sha256": BUNDLE_SHA,
        "first_live_season": 2026,
        "first_live_week": first_live_week,
        "decision_ref": decision_ref,
    }


def _authorization(**kwargs):
    return builder.build_authorization_packet(
        fixtures._manifests(),
        environment="preview",
        cutover_week=CUTOVER,
        decision_ref="decision-cutover",
        **kwargs,
    )


def _selection(**kwargs):
    storage = Storage()
    packet = builder.build_selection_packet(
        fixtures._manifests(),
        environment="preview",
        cutover_week=CUTOVER,
        decision_ref="decision-cutover",
        expected_current_runs={w: f"old-{w}" for w in range(CUTOVER + 1)},
        protected_runs={8: "old-8"},
        certifications=fixtures._certs(storage, "new"),
        payload_refs=fixtures._refs(storage),
        **kwargs,
    )
    return packet, storage


@pytest.mark.parametrize(
    ("first_live_week", "cutover", "expected"),
    [
        (7, 7, True),  # registered at the cutover
        (6, 7, True),  # display-only week before the cutover
        (6, 8, True),
        (6, 6, True),
        (5, 7, False),  # a prospective week is not display-only
        (8, 7, False),  # first live after the cutover
        (7, 8, False),
        (None, 7, False),
        ("6", 7, False),
        (True, 1, False),
    ],
)
def test_shared_rule(first_live_week, cutover, expected):
    assert bundle_covers_cutover(first_live_week, cutover) is expected


@pytest.mark.parametrize(
    ("first_live_week", "cutover", "expected"),
    [
        (5, 7, True),  # a bundle that was live before the cutover
        (6, 7, True),
        (7, 7, True),
        (4, 7, False),  # before the first live V5 slate
        (8, 7, False),  # first live after the cutover
        (None, 7, False),
        (True, 7, False),
    ],
)
def test_rollback_rule_accepts_any_registered_week_from_five_to_the_cutover(
    first_live_week, cutover, expected
):
    assert bundle_covers_cutover(first_live_week, cutover, rollback=True) is expected


def _rollback(first_live_week, *, season=2026):
    selection, storage = _selection(registered_bundle=_registered())
    packet = builder.build_rollback_packet(
        selection,
        prior_manifests=fixtures._manifests(prefix="old"),
        certifications=fixtures._certs(storage, "old"),
        payload_refs=fixtures._refs(storage),
        registered_bundle={
            **_registered(first_live_week),
            "approval_id": "approval-of-the-prior-bundle",
            "first_live_season": season,
        },
    )
    return packet, storage


def test_rollback_packet_accepts_the_prior_bundle_registered_at_week_five():
    packet, storage = _rollback(5)
    assert packet["bundle_approval"]["first_live_week"] == 5
    # The bundle gate passes; the fixture omits the completed-prospective evidence.
    assert "prospective" in _bundle_error(packet, storage)


@pytest.mark.parametrize("first_live_week", [4, 8])
def test_rollback_packet_rejects_out_of_range_first_live_weeks(first_live_week):
    packet, storage = _rollback(first_live_week)
    assert _bundle_error(packet, storage) == "bundle approval is not bound to cutover N"


def test_the_forward_packet_still_refuses_what_a_rollback_accepts():
    packet, storage = _selection(registered_bundle=_registered(5))
    assert _bundle_error(packet, storage) == "bundle approval is not bound to cutover N"


def test_default_builder_still_registers_at_the_cutover():
    packet = _authorization()
    validated = validate_packet(packet, environment="preview")
    assert validated["bundle"]["first_live_week"] == CUTOVER
    assert validated["bundle"]["decision_ref"] == "decision-cutover"


def test_registered_week6_approval_passes_the_authorization_validator_unchanged():
    packet = _authorization(registered_bundle=_registered())
    validated = validate_packet(packet, environment="preview")
    assert validated["bundle"] == {
        key: _registered()[key] for key in builder.BUNDLE_FIELDS
    }
    # The retained approval keeps its own decision reference; the runs carry the cutover's.
    assert {r["decision_ref"] for r in validated["records"].values()} == {
        "decision-cutover"
    }


@pytest.mark.parametrize("first_live_week", [5, 8, 4])
def test_authorization_validator_rejects_other_first_live_weeks(first_live_week):
    packet = _authorization(registered_bundle=_registered(first_live_week))
    with pytest.raises(AuthorizationPacketError, match="cutover binding"):
        validate_packet(packet, environment="preview")


def test_bundle_registered_at_the_cutover_must_carry_the_packet_decision_ref():
    packet = _authorization(registered_bundle=_registered(CUTOVER, "another-decision"))
    with pytest.raises(AuthorizationPacketError, match="cutover binding"):
        validate_packet(packet, environment="preview")


def test_builder_refuses_a_registered_approval_for_another_bundle_or_shape():
    other_bundle = {**_registered(), "inference_bundle_sha256": "b" * 64}
    with pytest.raises(builder.PacketBuildError, match="another bundle"):
        _authorization(registered_bundle=other_bundle)
    other_model = {**_registered(), "model_id": "another-model"}
    with pytest.raises(builder.PacketBuildError, match="another bundle"):
        _authorization(registered_bundle=other_model)
    other_season = {**_registered(), "first_live_season": 2025}
    with pytest.raises(builder.PacketBuildError, match="another bundle"):
        _authorization(registered_bundle=other_season)
    with pytest.raises(builder.PacketBuildError, match="exactly"):
        _authorization(registered_bundle={"approval_id": "x"})
    with pytest.raises(builder.PacketBuildError, match="exactly"):
        _authorization(registered_bundle={**_registered(), "extra": 1})


def _bundle_error(packet, storage):
    """The controller's verdict on the bundle gate, ignoring the later evidence checks."""
    with pytest.raises(V5BatchSelectionError) as caught:
        validate_v2_packet(packet, environment="preview", storage=storage)
    return str(caught.value)


def test_controller_accepts_week6_approval_at_week7_and_stops_at_later_checks():
    packet, storage = _selection(registered_bundle=_registered())
    # The bundle gate passes; the packet then fails on the completed-prospective
    # evidence this fixture deliberately omits (Week 5 onward).
    assert "prospective" in _bundle_error(packet, storage)


@pytest.mark.parametrize("first_live_week", [5, 8])
def test_controller_rejects_other_first_live_weeks(first_live_week):
    packet, storage = _selection(registered_bundle=_registered(first_live_week))
    assert _bundle_error(packet, storage) == "bundle approval is not bound to cutover N"


def test_controller_rejects_a_tampered_registered_bundle():
    packet, storage = _selection(registered_bundle=_registered())
    packet["bundle_approval"]["first_live_week"] = 5
    packet = signed_payload(
        {key: value for key, value in packet.items() if key != "manifest_sha256"}
    )
    assert "canonical hash" in _bundle_error(packet, storage)
