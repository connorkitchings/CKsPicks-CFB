"""The Week 7 packet shape: advance mode, Week 5 prospective evidence, nothing protected.

At the Week 7 cutover every existing selection (Weeks 0-6) is replaced and no other week
is selected, so ``protected_runs`` is empty. Week 5 is the only prospective record
(display-only Week 6 may not carry one).
"""

import copy
import hashlib
import json
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
from cks_picks_cfb.ratings_lab.artifacts import canonical_json
from tests import test_v5_packet_builder as fixtures
from tests.test_v5_batch_selection_v2 import Storage

CUTOVER = 7
FROZEN_AT = "2026-10-02T11:00:00+00:00"
FIRST_KICKOFF = "2026-10-03T00:00:00+00:00"


@pytest.fixture(autouse=True)
def _week7(monkeypatch):
    monkeypatch.setattr(fixtures, "CUTOVER", CUTOVER)


def _freeze_row(storage, *, week=5, run_id="old-5", frozen_at=FROZEN_AT):
    receipt = signed_payload(
        {
            "schema_version": "v5_prospective_freeze_receipt_v1",
            "state": "frozen",
            "environment": "preview",
            "season": 2026,
            "week": week,
            "run_id": run_id,
            "decision_ref": "decision-week5",
            "frozen_at": frozen_at,
            "first_kickoff_utc": FIRST_KICKOFF,
        }
    )
    raw = canonical_json(receipt)
    sha = hashlib.sha256(raw).hexdigest()
    uri = f"artifacts/prospective/v5/season=2026/week={week}/{run_id}/freeze-{sha}.json"
    storage.objects[uri] = raw
    return {
        "season": 2026,
        "week": week,
        "run_id": run_id,
        "freeze_receipt_uri": uri,
        "freeze_receipt_sha256": sha,
        "frozen_at": frozen_at,
        "first_kickoff_utc": FIRST_KICKOFF,
        "decision_ref": "decision-week5",
    }


def _prospective_ref(storage, uri, rows):
    return fixtures._ref(
        storage,
        uri,
        {
            "schema_version": "v5_prospective_records_release_payload_v1",
            "environment": "preview",
            "season": 2026,
            "rows": rows,
        },
    )


def _selection(rows=None, *, storage=None):
    storage = storage or Storage()
    rows = [_freeze_row(storage)] if rows is None else rows
    refs = fixtures._refs(storage)
    refs["prospective_records_before"] = _prospective_ref(storage, "r2://p/b", rows)
    refs["prospective_records_after"] = _prospective_ref(storage, "r2://p/a", rows)
    packet = builder.build_selection_packet(
        fixtures._manifests(),
        environment="preview",
        cutover_week=CUTOVER,
        decision_ref="decision-x",
        expected_current_runs={w: f"old-{w}" for w in range(CUTOVER)},
        protected_runs={},
        certifications=fixtures._certs(storage, "new"),
        payload_refs=refs,
        leakage_audit=fixtures._audit(storage),
        advance=True,
    )
    return packet, storage, refs


def test_week7_advance_packet_with_the_week5_record_and_nothing_protected_validates():
    packet, storage, _refs = _selection()
    assert packet["protected_runs"] == {} and packet["opens_week"] == CUTOVER
    plan = validate_v2_packet(packet, environment="preview", storage=storage)
    assert sorted(plan["before"]) == list(range(CUTOVER))
    assert sorted(plan["after"]) == list(range(CUTOVER + 1))
    assert plan["opens_week"] == CUTOVER and not plan["rollback"]


def test_week7_advance_rollback_validates_and_restores_weeks_0_to_6():
    packet, storage, refs = _selection()
    swapped = dict(refs)
    swapped["team_stats_before"], swapped["team_stats_after"] = (
        refs["team_stats_after"],
        refs["team_stats_before"],
    )
    swapped["team_stats_verifier"] = fixtures._ref(
        storage,
        "r2://s/week7-rollback-verify",
        {
            "state": "verified",
            "before_sha256": swapped["team_stats_before"]["sha256"],
            "after_sha256": swapped["team_stats_after"]["sha256"],
            "decision_ref": "decision-x",
        },
    )
    prior = {w: m for w, m in fixtures._manifests(prefix="old").items() if w < CUTOVER}
    rollback = builder.build_rollback_packet(
        packet, prior_manifests=prior, payload_refs=swapped
    )
    plan = validate_v2_packet(rollback, environment="preview", storage=storage)
    assert plan["rollback"] and sorted(plan["after"]) == list(range(CUTOVER))
    assert plan["pending_run"] == "new-7"
    assert rollback["protected_runs"] == {}


def _error(packet, storage):
    with pytest.raises(V5BatchSelectionError) as caught:
        validate_v2_packet(packet, environment="preview", storage=storage)
    return str(caught.value)


def test_the_week5_prospective_record_is_required_and_week6_may_not_have_one():
    packet, storage, _ = _selection(rows=[])
    assert "prospective Week 5 onward evidence is missing" in _error(packet, storage)

    storage = Storage()
    both = [_freeze_row(storage), _freeze_row(storage, week=6, run_id="old-6")]
    packet, storage, _ = _selection(rows=both, storage=storage)
    assert "display-only weeks cannot carry a prospective record" in _error(
        packet, storage
    )


def test_a_receipt_frozen_after_kickoff_or_for_another_run_is_refused():
    from cks_picks_cfb.ops.prospective_records import ProspectiveRecordError

    storage = Storage()
    late = _freeze_row(storage, frozen_at="2026-10-03T01:00:00+00:00")
    packet, storage, _ = _selection(rows=[late], storage=storage)
    with pytest.raises(ProspectiveRecordError, match="precede kickoff"):
        validate_v2_packet(packet, environment="preview", storage=storage)

    storage = Storage()
    row = _freeze_row(storage)
    row["run_id"] = "another-run"
    packet, storage, _ = _selection(rows=[row], storage=storage)
    with pytest.raises(ProspectiveRecordError):
        validate_v2_packet(packet, environment="preview", storage=storage)


def test_a_prospective_record_that_changes_between_before_and_after_is_refused():
    storage = Storage()
    packet, storage, refs = _selection(storage=storage)
    refs["prospective_records_after"] = _prospective_ref(storage, "r2://p/a2", [])
    body = {k: v for k, v in copy.deepcopy(packet).items() if k != "manifest_sha256"}
    body["prospective_records_after"] = refs["prospective_records_after"]
    assert "preserve prospective records exactly" in _error(
        signed_payload(body), storage
    )


def test_an_empty_protected_map_must_still_be_a_map():
    packet, storage, _ = _selection()
    body = {k: v for k, v in copy.deepcopy(packet).items() if k != "manifest_sha256"}
    del body["protected_runs"]
    assert "protected_runs must be a nonempty week map" in _error(
        signed_payload(body), storage
    )


requires_db = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="requires disposable PostgreSQL via TEST_DATABASE_URL",
)


@pytest.fixture
def database(monkeypatch):
    """The cutover-5 fixture opened as Week 5 with every other selection removed."""
    from tests.test_v5_advance_mode import _advance_packet, _resign
    from tests.test_v5_batch_selection_v2 import _prepare_database

    conn_url = os.environ["TEST_DATABASE_URL"]
    packet, storage = _advance_packet()
    body = json.loads(json.dumps(packet))
    body["protected_runs"] = {}
    packet = _resign(body)
    _prepare_database(conn_url, storage)
    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM site_week_selections WHERE season = 2026 AND week >= 5"
        )
        cur.execute(
            "UPDATE current_week SET season = 2026, week = 4, active_run_id = 'old-4' "
            "WHERE id = 1"
        )
    monkeypatch.setattr(batch_v2, "assert_v5_database_environment", lambda *_a: None)
    monkeypatch.setattr(batch_v2, "_verify_registered_authorizations", lambda *_a: None)
    monkeypatch.setattr(batch_v2, "_verify_week_evidence", lambda *_a: None)
    from cks_picks_cfb.ops import v5_release

    monkeypatch.setattr(v5_release, "assert_v5_database_environment", lambda *_a: None)
    return conn_url, packet, storage


@requires_db
def test_nothing_protected_applies_when_no_other_selection_exists(database):
    conn_url, packet, storage = database
    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        assert (
            batch_v2.apply_v2_packet(
                cur, packet, environment="preview", storage=storage
            )["state"]
            == "selected"
        )
    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        cur.execute("SELECT week, run_id FROM site_week_selections ORDER BY week")
        assert cur.fetchall() == [(week, f"new-{week}") for week in range(6)]


@requires_db
def test_an_unexpected_selection_outside_the_replaced_weeks_blocks_the_packet(database):
    conn_url, packet, storage = database
    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO site_week_selections (season, week, run_id, reason) "
            "VALUES (2026, 6, 'old-6', 'appeared after the packet was built')"
        )
    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        with pytest.raises(V5BatchSelectionError, match="protected public selections"):
            batch_v2.preflight_v2_packet(
                cur, packet, environment="preview", storage=storage
            )
    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        with pytest.raises(V5BatchSelectionError, match="protected public selections"):
            batch_v2.apply_v2_packet(
                cur, packet, environment="preview", storage=storage
            )
    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        cur.execute("SELECT week, run_id FROM site_week_selections ORDER BY week")
        assert cur.fetchall() == [(week, f"old-{week}") for week in range(5)] + [
            (6, "old-6")
        ]
