"""Advance mode: a cutover that opens a brand-new Week N (no public selection yet).

The selection packet starts from Weeks 0..N-1 with the site at Week N-1 and ends at
Weeks 0..N with the site at Week N; its rollback is the exact inverse and deletes the
Week N selection, which only an owner or migrator login may do.
"""

import json
import os

import psycopg
import pytest

from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.ops import v5_batch_selection_v2 as batch_v2
from cks_picks_cfb.ops.public_selection import PublicSelectionError, deselect_week_run
from cks_picks_cfb.ops.v5_batch_selection_v2 import (
    V5BatchSelectionError,
    validate_v2_packet,
)
from tests.test_v5_batch_selection_v2 import (
    _make_rollback_packet,
    _packet,
    _prepare_database,
)

OPENS = 5  # the fixture's cutover week; Weeks 0..4 are selected, Week 5 is new


def _resign(packet):
    return signed_payload(
        {key: value for key, value in packet.items() if key != "manifest_sha256"}
    )


def _advance_packet():
    """The existing cutover-5 fixture, re-expressed as opening Week 5."""
    packet, storage = _packet()
    body = json.loads(json.dumps(packet))
    body["opens_week"] = OPENS
    del body["expected_current_runs"][str(OPENS)]
    body["expected_current_week"] = {
        "season": 2026,
        "week": OPENS - 1,
        "run_id": f"old-{OPENS - 1}",
    }
    return _resign(body), storage


def test_validator_accepts_the_advance_shape_and_reports_it():
    packet, storage = _advance_packet()
    plan = validate_v2_packet(packet, environment="preview", storage=storage)
    assert plan["opens_week"] == OPENS
    assert sorted(plan["before"]) == list(range(OPENS))
    assert sorted(plan["after"]) == list(range(OPENS + 1))
    assert plan["pending_run"] == plan["after"][OPENS]


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda p: p.update(opens_week=OPENS + 1), "opens_week must equal"),
        (lambda p: p.update(opens_week=True), "opens_week must equal"),
        (
            lambda p: p["expected_current_runs"].update({str(OPENS): "old-5"}),
            "Weeks 0 through N exactly",
        ),
        (
            lambda p: p["expected_current_week"].update(week=OPENS),
            "current-week before/after bindings",
        ),
        (
            lambda p: p["expected_current_week"].update(run_id="old-0"),
            "current-week before/after bindings",
        ),
        (
            lambda p: p["replacement_current_week"].update(week=OPENS - 1),
            "current-week before/after bindings",
        ),
    ],
)
def test_validator_rejects_inconsistent_advance_packets(mutate, message):
    packet, storage = _advance_packet()
    body = json.loads(json.dumps(packet))
    mutate(body)
    with pytest.raises(V5BatchSelectionError, match=message):
        validate_v2_packet(_resign(body), environment="preview", storage=storage)


def test_a_normal_packet_cannot_claim_to_be_missing_its_cutover_week():
    packet, storage = _packet()
    body = json.loads(json.dumps(packet))
    del body["expected_current_runs"][str(OPENS)]
    with pytest.raises(V5BatchSelectionError, match="Weeks 0 through N exactly"):
        validate_v2_packet(_resign(body), environment="preview", storage=storage)


def test_advance_rollback_is_the_inverse_and_validates():
    packet, storage = _advance_packet()
    rollback = _make_rollback_packet(packet, storage)
    plan = validate_v2_packet(rollback, environment="preview", storage=storage)
    assert plan["rollback"] is True and plan["opens_week"] == OPENS
    assert sorted(plan["before"]) == list(range(OPENS + 1))
    assert sorted(plan["after"]) == list(range(OPENS))
    assert plan["pending_run"] == plan["before"][OPENS]
    assert rollback["replacement_current_week"]["week"] == OPENS - 1


requires_db = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="requires disposable PostgreSQL via TEST_DATABASE_URL",
)


@pytest.fixture
def advance_database(monkeypatch):
    conn_url = os.environ["TEST_DATABASE_URL"]
    packet, storage = _advance_packet()
    _prepare_database(conn_url, storage)
    # Week 5 is new: no selection, and the site is still on Week 4.
    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM site_week_selections WHERE season = 2026 AND week = 5")
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


def _selections(conn_url):
    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT week, run_id FROM site_week_selections WHERE season = 2026 "
            "ORDER BY week"
        )
        selections = cur.fetchall()
        cur.execute("SELECT season, week, active_run_id FROM current_week WHERE id = 1")
        return selections, cur.fetchone()


@requires_db
def test_advance_selects_week_n_moves_current_week_and_retries_idempotently(
    advance_database,
):
    conn_url, packet, storage = advance_database
    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        assert (
            batch_v2.preflight_v2_packet(
                cur, packet, environment="preview", storage=storage
            )["state"]
            == "preflight"
        )
    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        result = batch_v2.apply_v2_packet(
            cur, packet, environment="preview", storage=storage
        )
        assert result["state"] == "selected"
    selections, current = _selections(conn_url)
    assert selections == [(week, f"new-{week}") for week in range(6)] + [(6, "old-6")]
    assert current == (2026, 5, "new-5")
    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        assert (
            batch_v2.apply_v2_packet(
                cur, packet, environment="preview", storage=storage
            )["state"]
            == "already_applied"
        )


@requires_db
def test_advance_refuses_when_week_n_is_already_selected(advance_database):
    conn_url, packet, storage = advance_database
    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO site_week_selections (season, week, run_id, reason) "
            "VALUES (2026, 5, 'old-5', 'already opened')"
        )
    before = _selections(conn_url)
    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        with pytest.raises(V5BatchSelectionError, match="differ from exact packet"):
            batch_v2.apply_v2_packet(
                cur, packet, environment="preview", storage=storage
            )
    assert _selections(conn_url) == before


@requires_db
def test_advance_refuses_when_the_site_is_not_on_the_previous_week(advance_database):
    conn_url, packet, storage = advance_database
    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        cur.execute("UPDATE current_week SET week = 3, active_run_id = 'old-3'")
    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        with pytest.raises(V5BatchSelectionError, match="current-week pointer"):
            batch_v2.apply_v2_packet(
                cur, packet, environment="preview", storage=storage
            )
    selections, _ = _selections(conn_url)
    assert selections == [(week, f"old-{week}") for week in range(5)] + [(6, "old-6")]


@requires_db
def test_advance_rollback_deletes_week_n_and_restores_the_previous_week(
    advance_database,
):
    conn_url, packet, storage = advance_database
    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        batch_v2.apply_v2_packet(cur, packet, environment="preview", storage=storage)
    rollback = _make_rollback_packet(packet, storage)
    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        result = batch_v2.apply_v2_packet(
            cur, rollback, environment="preview", storage=storage
        )
        assert result["state"] == "rolled_back"
    selections, current = _selections(conn_url)
    assert selections == [(week, f"old-{week}") for week in range(5)] + [(6, "old-6")]
    assert current == (2026, 4, "old-4")
    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT prior_run_id, run_id, reason FROM site_week_selection_history "
            "WHERE season = 2026 AND week = 5 ORDER BY selection_id DESC LIMIT 1"
        )
        prior, run, reason = cur.fetchone()
        assert prior == run == "new-5" and reason.startswith("DESELECTED: ")
        assert (
            batch_v2.apply_v2_packet(
                cur, rollback, environment="preview", storage=storage
            )["state"]
            == "already_applied"
        )


@requires_db
def test_deselect_needs_delete_privilege_and_fails_closed_for_the_pipeline_role(
    advance_database,
):
    conn_url, packet, storage = advance_database
    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        batch_v2.apply_v2_packet(cur, packet, environment="preview", storage=storage)
    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL ROLE cks_pipeline")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            deselect_week_run(cur, season=2026, week=5, reason="test")
    selections, _ = _selections(conn_url)
    assert (5, "new-5") in selections
    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        assert deselect_week_run(cur, season=2026, week=5, reason="owner") == "new-5"
        assert deselect_week_run(cur, season=2026, week=5, reason="owner") is None
        with pytest.raises(PublicSelectionError):
            deselect_week_run(cur, season=2026, week=5, reason=" ")


# ---------------------------------------------------------------------------
# The builders emit the advance shape and the applying validator accepts it.
# ---------------------------------------------------------------------------


def _built_advance(storage=None):
    from cks_picks_cfb.ops import v5_packet_builder as builder
    from tests import test_v5_packet_builder as fixtures
    from tests.test_v5_batch_selection_v2 import Storage

    storage = storage or Storage()
    packet = builder.build_selection_packet(
        fixtures._manifests(),
        environment="preview",
        cutover_week=fixtures.CUTOVER,
        decision_ref="decision-x",
        expected_current_runs={w: f"old-{w}" for w in range(fixtures.CUTOVER)},
        protected_runs={fixtures.CUTOVER + 1: "old-6"},
        certifications=fixtures._certs(storage, "new"),
        payload_refs=fixtures._refs(storage),
        advance=True,
    )
    return packet, storage, builder, fixtures


def test_builder_emits_an_advance_selection_the_validator_accepts():
    packet, storage, _builder, fixtures = _built_advance()
    assert packet["opens_week"] == fixtures.CUTOVER
    assert sorted(packet["expected_current_runs"]) == [
        str(w) for w in range(fixtures.CUTOVER)
    ]
    assert packet["expected_current_week"]["week"] == fixtures.CUTOVER - 1
    assert packet["replacement_current_week"]["week"] == fixtures.CUTOVER
    plan = validate_v2_packet(packet, environment="preview", storage=storage)
    assert plan["opens_week"] == fixtures.CUTOVER and not plan["rollback"]


def test_builder_requires_the_previous_weeks_only_in_advance_mode():
    from cks_picks_cfb.ops import v5_packet_builder as builder
    from tests import test_v5_packet_builder as fixtures
    from tests.test_v5_batch_selection_v2 import Storage

    storage = Storage()
    common = dict(
        environment="preview",
        cutover_week=fixtures.CUTOVER,
        decision_ref="decision-x",
        protected_runs={fixtures.CUTOVER + 1: "old-6"},
        certifications=fixtures._certs(storage, "new"),
        payload_refs=fixtures._refs(storage),
    )
    full = {w: f"old-{w}" for w in range(fixtures.CUTOVER + 1)}
    with pytest.raises(builder.PacketBuildError, match=r"N-1 \(advance\)"):
        builder.build_selection_packet(
            fixtures._manifests(), expected_current_runs=full, advance=True, **common
        )
    with pytest.raises(builder.PacketBuildError, match="through N"):
        builder.build_selection_packet(
            fixtures._manifests(),
            expected_current_runs={w: f"old-{w}" for w in range(fixtures.CUTOVER)},
            **common,
        )


def test_builder_emits_the_matching_advance_rollback():
    selection, storage, builder, fixtures = _built_advance()
    refs = fixtures._refs(storage)
    refs["team_stats_before"], refs["team_stats_after"] = (
        refs["team_stats_after"],
        refs["team_stats_before"],
    )
    refs["team_stats_verifier"] = fixtures._ref(
        storage,
        "r2://s/advance-rollback-verify",
        {
            "state": "verified",
            "before_sha256": refs["team_stats_before"]["sha256"],
            "after_sha256": refs["team_stats_after"]["sha256"],
            "decision_ref": "decision-x",
        },
    )
    prior = {
        week: manifest
        for week, manifest in fixtures._manifests(prefix="old").items()
        if week < fixtures.CUTOVER
    }
    rollback = builder.build_rollback_packet(
        selection,
        prior_manifests=prior,
        certifications=fixtures._certs(storage, "old"),
        payload_refs=refs,
    )
    assert rollback["opens_week"] == fixtures.CUTOVER
    assert rollback["replacement_current_week"]["week"] == fixtures.CUTOVER - 1
    assert sorted(rollback["replacement_runs"]) == [
        str(w) for w in range(fixtures.CUTOVER)
    ]
    plan = validate_v2_packet(rollback, environment="preview", storage=storage)
    assert plan["rollback"] and plan["pending_run"] == "new-5"
