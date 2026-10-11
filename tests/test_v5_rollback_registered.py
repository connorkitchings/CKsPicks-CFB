"""A rollback carries the runs' registered releases, which may span two bundles.

The currently public runs were released under their own decisions: Weeks 0-4 as replays
and Week 5 pending under the repaired bundle, Week 6 pending under the successor B2
bundle. The rollback packet therefore carries each registered authorization verbatim and
one registered approval per bundle, with no fresh finals certification.
"""

import copy
import os

import psycopg
import pytest

from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.ops import v5_batch_selection_v2 as batch_v2
from cks_picks_cfb.ops import v5_packet_builder as builder
from cks_picks_cfb.ops.v5_batch_selection_v2 import (
    V5BatchSelectionError,
    validate_v2_packet,
)
from tests import test_v5_packet_builder as fixtures
from tests.test_v5_advance_mode import _built_advance

CUTOVER = (
    fixtures.CUTOVER
)  # 5: Weeks 0..4 are restored, Week 5 was opened by the cutover
OLD_SHA, B2_SHA = "a" * 64, "b" * 64
MODEL = "v5-test"


def _prior_manifests():
    """Weeks 0..3 replay under the old bundle, Week 4 pending under the successor."""
    manifests = {}
    for week in range(CUTOVER):
        manifest = fixtures._manifest(week, prefix="old")
        if week == CUTOVER - 1:
            manifest["evidence_class"] = "pending"
            manifest["inference_bundle_sha256"] = B2_SHA
        manifests[week] = manifest
    return manifests


def _registered(manifests):
    """Authorization rows as an export from the database would return them."""
    rows = {}
    for week, manifest in manifests.items():
        record = builder.authorization_record(
            manifest, environment="preview", decision_ref=f"original-decision-{week}"
        )
        rows[week] = {key: record[key] for key in builder.AUTH_COLUMNS}
    return rows


def _bundles():
    return [
        {
            "approval_id": "approval-old",
            "model_id": MODEL,
            "inference_bundle_sha256": OLD_SHA,
            "first_live_season": 2026,
            "first_live_week": 5,
            "decision_ref": "decision-old",
        },
        {
            "approval_id": "approval-b2",
            "model_id": MODEL,
            "inference_bundle_sha256": B2_SHA,
            "first_live_season": 2026,
            "first_live_week": 5,
            "decision_ref": "decision-b2",
        },
    ]


def _swapped_refs(storage):
    refs = fixtures._refs(storage)
    refs["team_stats_before"], refs["team_stats_after"] = (
        refs["team_stats_after"],
        refs["team_stats_before"],
    )
    refs["team_stats_verifier"] = fixtures._ref(
        storage,
        "r2://s/registered-rollback-verify",
        {
            "state": "verified",
            "before_sha256": refs["team_stats_before"]["sha256"],
            "after_sha256": refs["team_stats_after"]["sha256"],
            "decision_ref": "decision-x",
        },
    )
    return refs


def _rollback(**overrides):
    selection, storage, _builder, _fixtures = _built_advance()
    manifests = _prior_manifests()
    kwargs = dict(
        prior_manifests=manifests,
        payload_refs=_swapped_refs(storage),
        registered_bundles=_bundles(),
        registered_authorizations=_registered(manifests),
    )
    kwargs.update(overrides)
    return builder.build_rollback_packet(selection, **kwargs), storage


def _resign(packet):
    return signed_payload(
        {key: value for key, value in packet.items() if key != "manifest_sha256"}
    )


def test_registered_rollback_carries_original_records_and_both_bundles():
    packet, storage = _rollback()
    rows = _registered(_prior_manifests())
    for record in packet["run_authorizations"]:
        original = rows[record["week"]]
        assert all(record[key] == original[key] for key in builder.AUTH_COLUMNS)
        assert record["decision_ref"] == f"original-decision-{record['week']}"
    assert packet["bundle_approval"]["approval_id"] == "approval-old"
    assert [b["approval_id"] for b in packet["additional_bundle_approvals"]] == [
        "approval-b2"
    ]
    assert packet["completed_week_certifications"] == []
    plan = validate_v2_packet(packet, environment="preview", storage=storage)
    assert plan["rollback"] and [b["approval_id"] for b in plan["bundles"]] == [
        "approval-old",
        "approval-b2",
    ]
    # Real classes survive: replays plus a pending run.
    assert {a["evidence_class"] for a in plan["authorizations"].values()} == {
        "replay",
        "pending",
    }


def test_forward_packets_still_need_one_bundle_and_the_cutover_decision():
    selection, storage, _b, _f = _built_advance()
    body = copy.deepcopy(selection)
    body["additional_bundle_approvals"] = [selection["bundle_approval"]]
    with pytest.raises(V5BatchSelectionError, match="only valid in a rollback"):
        validate_v2_packet(_resign(body), environment="preview", storage=storage)


def _error(packet, storage):
    with pytest.raises(V5BatchSelectionError) as caught:
        validate_v2_packet(packet, environment="preview", storage=storage)
    return str(caught.value)


def test_controller_rejects_unused_duplicate_or_tampered_approvals():
    packet, storage = _rollback()
    unused = copy.deepcopy(packet)
    extra = dict(unused["additional_bundle_approvals"][0], approval_id="approval-x")
    extra["inference_bundle_sha256"] = "c" * 64
    body = {k: extra[k] for k in builder.BUNDLE_FIELDS}
    extra["record_sha256"] = builder._sha(body)
    unused["additional_bundle_approvals"].append(extra)
    assert "do not match the bundles" in _error(_resign(unused), storage)

    duplicate = copy.deepcopy(packet)
    duplicate["additional_bundle_approvals"].append(packet["bundle_approval"])
    assert "duplicated" in _error(_resign(duplicate), storage)

    tampered = copy.deepcopy(packet)
    tampered["additional_bundle_approvals"][0]["first_live_week"] = 9
    assert "canonical hash" in _error(_resign(tampered), storage)


def test_controller_rejects_a_restored_authorization_for_another_bundle():
    packet, storage = _rollback()
    body = copy.deepcopy(packet)
    record = body["run_authorizations"][0]
    record["inference_bundle_sha256"] = "d" * 64
    record["record_sha256"] = builder._sha(
        {key: record[key] for key in builder.AUTH_COLUMNS}
    )
    assert "another replacement run" in _error(_resign(body), storage)


def test_rollback_gate_applies_to_every_carried_approval():
    bundles = _bundles()
    bundles[1]["first_live_week"] = 9  # after the cutover
    packet, storage = _rollback(registered_bundles=bundles)
    assert _error(packet, storage) == "bundle approval is not bound to cutover N"


def test_builder_requires_exact_registered_inputs():
    manifests = _prior_manifests()
    rows = _registered(manifests)
    with pytest.raises(builder.PacketBuildError, match="need registered bundles"):
        _rollback(registered_bundles=None)
    with pytest.raises(builder.PacketBuildError, match="match the bundles"):
        _rollback(registered_bundles=_bundles()[:1])
    with pytest.raises(builder.PacketBuildError, match="match the bundles"):
        _rollback(registered_bundles=[*_bundles(), {**_bundles()[0], "model_id": "x"}])
    missing = {week: row for week, row in rows.items() if week != 2}
    with pytest.raises(builder.PacketBuildError, match="must cover the prior weeks"):
        _rollback(registered_authorizations=missing)
    wrong_run = copy.deepcopy(rows)
    wrong_run[1]["prediction_run_id"] = "someone-else"
    with pytest.raises(builder.PacketBuildError, match="another run"):
        _rollback(registered_authorizations=wrong_run)
    wrong_class = copy.deepcopy(rows)
    wrong_class[1]["evidence_class"] = "pending"
    with pytest.raises(builder.PacketBuildError, match="another run"):
        _rollback(registered_authorizations=wrong_class)
    extra_column = copy.deepcopy(rows)
    extra_column[0]["extra"] = 1
    with pytest.raises(builder.PacketBuildError, match="exactly the authorization"):
        _rollback(registered_authorizations=extra_column)


# ---------------------------------------------------------------------------
# Database: restored runs are checked structurally; registered rows must match.
# ---------------------------------------------------------------------------

requires_db = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="requires disposable PostgreSQL via TEST_DATABASE_URL",
)


@requires_db
def test_restored_runs_must_be_complete_public_runs_without_fresh_finals():
    from tests.test_v5_batch_selection_v2 import _packet, _prepare_database

    conn_url = os.environ["TEST_DATABASE_URL"]
    _packet_obj, storage = _packet()
    _prepare_database(conn_url, storage)
    plan = {"after": {week: f"old-{week}" for week in range(6)}}
    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        # The seeded Week 5 run is published and pending with no game_results at all:
        # a forward packet would refuse it, a rollback accepts it.
        batch_v2._verify_restored_runs(cur, plan)
        cur.execute(
            "UPDATE prediction_runs SET state = 'preview' WHERE run_id = 'old-3'"
        )
        with pytest.raises(V5BatchSelectionError, match="Week 3 restored run"):
            batch_v2._verify_restored_runs(cur, plan)
        cur.execute(
            "UPDATE prediction_runs SET state = 'scored' WHERE run_id = 'old-3'"
        )
        cur.execute(
            "UPDATE prediction_runs SET predicted_games = 0 WHERE run_id = 'old-2'"
        )
        with pytest.raises(V5BatchSelectionError, match="Week 2 restored run"):
            batch_v2._verify_restored_runs(cur, plan)
        cur.execute(
            "UPDATE prediction_runs SET predicted_games = 1 WHERE run_id = 'old-2'"
        )
        cur.execute("DELETE FROM predictions WHERE run_id = 'old-1'")
        with pytest.raises(V5BatchSelectionError, match="Week 1 restored run"):
            batch_v2._verify_restored_runs(cur, plan)
        conn.rollback()


@requires_db
def test_export_reads_exactly_the_registered_rows_and_refuses_gaps():
    from scripts.pipeline.export_v5_registered_releases import ExportError, export
    from tests.test_v5_batch_selection_v2 import _packet, _prepare_database

    conn_url = os.environ["TEST_DATABASE_URL"]
    _prepared, storage = _packet()
    _prepare_database(conn_url, storage)
    manifest = fixtures._manifest(1, prefix="old")
    row = {
        key: builder.authorization_record(
            manifest, environment="preview", decision_ref="original-decision"
        )[key]
        for key in builder.AUTH_COLUMNS
    }
    row["model_id"] = "v5-intended-update-test"
    bundle = {
        "approval_id": "approval-exported",
        "model_id": "v5-intended-update-test",
        "inference_bundle_sha256": OLD_SHA,
        "first_live_season": 2026,
        "first_live_week": 5,
        "decision_ref": "decision-exported",
    }
    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM v5_model_bundle_approvals WHERE inference_bundle_sha256 = %s",
            (OLD_SHA,),
        )
        cur.execute(
            "INSERT INTO v5_model_bundle_approvals ("
            + ", ".join(bundle)
            + ") VALUES ("
            + ", ".join(["%s"] * len(bundle))
            + ")",
            tuple(bundle.values()),
        )
        cur.execute(
            "INSERT INTO v5_intended_update_release_authorizations ("
            + ", ".join(builder.AUTH_COLUMNS)
            + ") VALUES ("
            + ", ".join(["%s"] * len(builder.AUTH_COLUMNS))
            + ")",
            tuple(row[key] for key in builder.AUTH_COLUMNS),
        )
        result = export(cur, environment="preview", runs={1: "old-1"})
        assert result["registered_authorizations"] == {"1": row}
        assert result["registered_bundles"] == [bundle]
        with pytest.raises(ExportError, match="expected one registered authorization"):
            export(cur, environment="preview", runs={2: "old-2"})
        with pytest.raises(ExportError, match="expected one registered authorization"):
            export(cur, environment="production", runs={1: "old-1"})
        conn.rollback()
