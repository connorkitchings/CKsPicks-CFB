import hashlib
import json
import os
import threading
import time
from pathlib import Path

import psycopg
import pytest

from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.db.migrations import apply_migrations
from cks_picks_cfb.ops import v5_batch_selection_v2 as batch_v2
from cks_picks_cfb.ops.v5_batch_selection_v2 import (
    V5BatchSelectionError,
    validate_v2_packet,
)
from cks_picks_cfb.ops.v5_revocations import (
    V5RevocationError,
    append_release_revocation,
    assert_release_records_active,
    lock_release_records,
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
        "model_id": "v5-intended-update-test",
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
            {
                **record,
                "record_sha256": hashlib.sha256(canonical_json(record)).hexdigest(),
            }
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
    packet = signed_payload(
        {key: value for key, value in packet.items() if key != "manifest_sha256"}
    )
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
    packet = signed_payload(
        {key: value for key, value in packet.items() if key != "manifest_sha256"}
    )
    with pytest.raises(V5BatchSelectionError, match="identical complete keys"):
        validate_v2_packet(packet, environment="preview", storage=storage)


def _packet_with_changed_provenance(*, bind: bool, tamper: bool = False, versions=None):
    """A packet whose after-payload carries new ``source_versions`` (corrected lineage)."""
    packet, storage = _packet()
    before_rows = json.loads(storage.objects["r2://stats/before"])["rows"]
    corrected = versions if versions is not None else {"silver": "silver-corrected-v2"}
    after_rows = [
        {**row, "source_versions": corrected}
        for row in json.loads(storage.objects["r2://stats/after"])["rows"]
    ]
    after_ref = _ref(
        storage,
        "r2://stats/after-corrected",
        {
            "schema_version": "v5_team_stats_release_payload_v1",
            "environment": "preview",
            "season": 2026,
            "scope": [{"season": 2026, "as_of_week": 5}],
            "rows": after_rows,
        },
    )
    body = {
        "schema_version": "v5_team_stats_release_verification_v1",
        "state": "verified",
        "before_sha256": packet["team_stats_before"]["sha256"],
        "after_sha256": after_ref["sha256"],
        "decision_ref": "decision-7a",
    }
    if bind:
        body["provenance_change"] = {
            "keys_changed": len(after_rows),
            "before_provenance_sha256": batch_v2.stats_provenance_digest(before_rows),
            "after_provenance_sha256": (
                "0" * 64 if tamper else batch_v2.stats_provenance_digest(after_rows)
            ),
        }
    packet["team_stats_after"] = after_ref
    packet["team_stats_verifier"] = _ref(storage, "r2://stats/verify-corrected", body)
    packet = signed_payload(
        {key: value for key, value in packet.items() if key != "manifest_sha256"}
    )
    return packet, storage


def test_v2_packet_accepts_changed_provenance_only_when_the_verifier_binds_it():
    packet, storage = _packet_with_changed_provenance(bind=True)
    result = validate_v2_packet(packet, environment="preview", storage=storage)
    after = result["payloads"]["team_stats_after"]["rows"][0]
    assert after["source_versions"] == {"silver": "silver-corrected-v2"}


def test_v2_packet_rejects_changed_provenance_without_a_verifier_binding():
    packet, storage = _packet_with_changed_provenance(bind=False)
    with pytest.raises(V5BatchSelectionError, match="without a matching verifier"):
        validate_v2_packet(packet, environment="preview", storage=storage)


def test_v2_packet_rejects_a_tampered_provenance_digest():
    packet, storage = _packet_with_changed_provenance(bind=True, tamper=True)
    with pytest.raises(V5BatchSelectionError, match="without a matching verifier"):
        validate_v2_packet(packet, environment="preview", storage=storage)


def test_v2_packet_rejects_changed_provenance_that_is_not_a_nonempty_mapping():
    packet, storage = _packet_with_changed_provenance(bind=True, versions={})
    with pytest.raises(V5BatchSelectionError, match="nonempty mapping"):
        validate_v2_packet(packet, environment="preview", storage=storage)


def test_provenance_digest_is_order_independent_and_sensitive_to_every_key():
    base = {
        "season": 2026,
        "as_of_week": 5,
        "team": "A",
        "role": "offense",
        "metric": "m",
        "source_versions": {"silver": "v1"},
    }
    other = {**base, "team": "B"}
    one = batch_v2.stats_provenance_digest([base, other])
    assert one == batch_v2.stats_provenance_digest([other, base])
    changed = {**other, "source_versions": {"silver": "v2"}}
    assert one != batch_v2.stats_provenance_digest([base, changed])


def test_v2_packet_rejects_prospective_record_drift():
    packet, storage = _packet()
    packet["prospective_records_after"] = _ref(
        storage,
        "r2://prospective/drift",
        {
            "schema_version": "v5_prospective_records_release_payload_v1",
            "environment": "preview",
            "season": 2026,
            "rows": [
                {
                    "season": 2026,
                    "week": 5,
                    "run_id": "live-5",
                    "freeze_receipt_uri": "r2://receipt",
                    "freeze_receipt_sha256": "a" * 64,
                    "frozen_at": "2026-10-01T00:00:00+00:00",
                    "first_kickoff_utc": "2026-10-10T00:00:00+00:00",
                    "decision_ref": "decision",
                }
            ],
        },
    )
    packet = signed_payload(
        {key: value for key, value in packet.items() if key != "manifest_sha256"}
    )
    with pytest.raises(
        V5BatchSelectionError, match="preserve prospective records exactly"
    ):
        validate_v2_packet(packet, environment="preview", storage=storage)


def test_v2_packet_current_pointer_must_bind_to_the_exact_expected_run():
    packet, storage = _packet()
    packet["expected_current_week"] = {"season": 2026, "week": 5, "run_id": "old-4"}
    packet = signed_payload(
        {key: value for key, value in packet.items() if key != "manifest_sha256"}
    )
    with pytest.raises(
        V5BatchSelectionError, match="current-week before/after bindings"
    ):
        validate_v2_packet(packet, environment="preview", storage=storage)


def _seed_run(cur, run_id, week, game_id):
    replay = week < 5
    cur.execute(
        "INSERT INTO games (game_id, season, week, start_date, home_team, away_team) "
        "VALUES (%s, 2026, %s, %s, 'Home', 'Away') ON CONFLICT (game_id) DO NOTHING",
        (
            game_id,
            week,
            "2026-10-20 18:00:00+00" if week == 5 else "2026-09-01 18:00:00+00",
        ),
    )
    cur.execute(
        "INSERT INTO prediction_runs (run_id, season, week, state, expected_games, "
        "predicted_games, lined_games, data_as_of, model_id, model_bundle_sha256, "
        "rating_manifest_sha256, artifact_uri, artifact_sha256, evidence_class) "
        "VALUES (%s, 2026, %s, %s, 1, 1, 1, NOW(), 'v5-intended-update-test', %s, %s, %s, %s, %s)",
        (
            run_id,
            week,
            "scored" if replay else "published",
            "a" * 64,
            "b" * 64,
            f"r2://fixture/{run_id}",
            "f" * 64,
            "replay" if replay else "pending",
        ),
    )
    cur.execute(
        "INSERT INTO predictions (run_id, game_id, regime) "
        "VALUES (%s, %s, 'preseason')",
        (run_id, game_id),
    )


def _prepare_database(conn_url, storage):
    with psycopg.connect(conn_url, autocommit=True) as conn, conn.cursor() as cur:
        for schema in ("ops", "catalog", "public"):
            cur.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        cur.execute("CREATE SCHEMA public")
    apply_migrations(conn_url, Path("contracts/migrations"))

    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO v5_model_bundle_approvals "
            "(approval_id, model_id, inference_bundle_sha256, first_live_season, "
            "first_live_week, decision_ref) VALUES ('bundle-7a', "
            "'v5-intended-update-test', %s, 2026, 5, 'decision-7a')",
            ("a" * 64,),
        )
        for week in range(6):
            game_id = 20260000 + week
            for prefix in ("old", "new"):
                run_id = f"{prefix}-{week}"
                _seed_run(cur, run_id, week, game_id)
            cur.execute(
                "INSERT INTO site_week_selections (season, week, run_id, reason) "
                "VALUES (2026, %s, %s, 'fixture before')",
                (week, f"old-{week}"),
            )
        _seed_run(cur, "old-6", 6, 20260006)
        cur.execute(
            "INSERT INTO site_week_selections (season, week, run_id, reason) "
            "VALUES (2026, 6, 'old-6', 'protected fixture')"
        )
        cur.execute(
            "UPDATE current_week SET season = 2026, week = 5, active_run_id = 'old-5' "
            "WHERE id = 1"
        )
        stat_ref = json.loads(storage.objects["r2://stats/before"])
        stat = stat_ref["rows"][0]
        cur.execute(
            "INSERT INTO team_season_stats "
            "(season, as_of_week, team, role, metric, value, n, games, rank, "
            "cohort_size, source_versions) VALUES (%(season)s, %(as_of_week)s, "
            "%(team)s, %(role)s, %(metric)s, %(value)s, %(n)s, %(games)s, "
            "%(rank)s, %(cohort_size)s, %(source_versions)s::jsonb)",
            {
                **stat,
                "source_versions": json.dumps(stat["source_versions"], sort_keys=True),
            },
        )


def _make_rollback_packet(packet, storage):
    rollback = json.loads(json.dumps(packet))
    before = rollback["expected_current_runs"]
    after = rollback["replacement_runs"]
    rollback["expected_current_runs"], rollback["replacement_runs"] = after, before
    rollback["expected_current_week"], rollback["replacement_current_week"] = (
        rollback["replacement_current_week"],
        rollback["expected_current_week"],
    )
    rollback["schema_version"] = "v5_intended_update_batch_rollback_v2"

    revised_auth = []
    for auth in rollback["run_authorizations"]:
        record = dict(auth)
        week = int(record["week"])
        record["prediction_run_id"] = before[str(week)]
        body = {
            key: record[key]
            for key in (
                "authorization_id",
                "environment",
                "season",
                "week",
                "prediction_run_id",
                "evidence_class",
                "model_id",
                "inference_bundle_sha256",
                "rating_manifest_sha256",
                "forecast_manifest_uri",
                "forecast_manifest_sha256",
                "serving_manifest_uri",
                "serving_manifest_sha256",
                "verifier_uri",
                "verifier_sha256",
                "prediction_artifact_uri",
                "prediction_artifact_sha256",
                "decision_ref",
            )
        }
        record["record_sha256"] = hashlib.sha256(canonical_json(body)).hexdigest()
        revised_auth.append(record)
    rollback["run_authorizations"] = revised_auth

    rollback["completed_week_certifications"] = []
    for week in range(5):
        rollback["completed_week_certifications"].append(
            _ref(
                storage,
                f"r2://certs/rollback/{week}",
                {
                    "schema_version": "v5_replay_certification_v1",
                    "state": "verified",
                    "season": 2026,
                    "week": week,
                    "run_id": before[str(week)],
                    "finals_complete": True,
                    "finals_stabilized_at": "2026-10-01T00:00:00+00:00",
                },
            )
            | {"week": week}
        )

    before_stats = json.loads(storage.objects["r2://stats/before"])
    after_stats = json.loads(storage.objects["r2://stats/after"])
    rollback["team_stats_before"] = _ref(
        storage, "r2://stats/rollback-before", after_stats
    )
    rollback["team_stats_after"] = _ref(
        storage, "r2://stats/rollback-after", before_stats
    )
    verifier = {
        "schema_version": "v5_team_stats_release_verification_v1",
        "state": "verified",
        "before_sha256": rollback["team_stats_before"]["sha256"],
        "after_sha256": rollback["team_stats_after"]["sha256"],
        "decision_ref": rollback["decision_ref"],
    }
    rollback["team_stats_verifier"] = _ref(
        storage, "r2://stats/rollback-verifier", verifier
    )
    return signed_payload(
        {key: value for key, value in rollback.items() if key != "manifest_sha256"}
    )


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="requires disposable PostgreSQL via TEST_DATABASE_URL",
)
def test_v2_database_preflight_apply_retry_failure_rollback_and_compensation(
    monkeypatch,
):
    conn_url = os.environ["TEST_DATABASE_URL"]
    packet, storage = _packet()
    _prepare_database(conn_url, storage)

    monkeypatch.setattr(batch_v2, "assert_v5_database_environment", lambda *_args: None)
    monkeypatch.setattr(
        batch_v2, "_verify_registered_authorizations", lambda *_args: None
    )
    monkeypatch.setattr(batch_v2, "_verify_week_evidence", lambda *_args: None)
    from cks_picks_cfb.ops import v5_release

    monkeypatch.setattr(
        v5_release, "assert_v5_database_environment", lambda *_args: None
    )

    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        assert (
            batch_v2.preflight_v2_packet(
                cur, packet, environment="preview", storage=storage
            )["state"]
            == "preflight"
        )

    original_select = batch_v2.select_week_run

    def fail_after_three_selections(cur, **kwargs):
        previous = original_select(cur, **kwargs)
        if kwargs["week"] == 2:
            raise RuntimeError("injected transaction failure")
        return previous

    conn = psycopg.connect(conn_url)
    with pytest.raises(RuntimeError, match="injected transaction failure"):
        with conn.cursor() as cur, monkeypatch.context() as scoped:
            scoped.setattr(batch_v2, "select_week_run", fail_after_three_selections)
            batch_v2.apply_v2_packet(
                cur, packet, environment="preview", storage=storage
            )
    conn.rollback()
    conn.close()
    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT week, run_id FROM site_week_selections WHERE season = 2026 ORDER BY week"
        )
        assert cur.fetchall() == [(week, f"old-{week}") for week in range(7)]
        cur.execute("SELECT value FROM team_season_stats WHERE season = 2026")
        assert cur.fetchone()[0] == 0.2

    class FailDuringStatsRefresh:
        def __init__(self, cursor):
            self.cursor = cursor

        def __getattr__(self, name):
            return getattr(self.cursor, name)

        def execute(self, query, params=None):
            if "WITH selected_runs AS" in query:
                raise RuntimeError(
                    "injected failure after selection and team-stat writes"
                )
            return self.cursor.execute(query, params)

    conn = psycopg.connect(conn_url)
    with pytest.raises(RuntimeError, match="after selection and team-stat writes"):
        with conn.cursor() as raw_cur:
            batch_v2.apply_v2_packet(
                FailDuringStatsRefresh(raw_cur),
                packet,
                environment="preview",
                storage=storage,
            )
    conn.rollback()
    conn.close()
    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT week, run_id FROM site_week_selections WHERE season = 2026 ORDER BY week"
        )
        assert cur.fetchall() == [(week, f"old-{week}") for week in range(7)]
        cur.execute("SELECT season, week, active_run_id FROM current_week WHERE id = 1")
        assert cur.fetchone() == (2026, 5, "old-5")
        cur.execute("SELECT value FROM team_season_stats WHERE season = 2026")
        assert cur.fetchone()[0] == 0.2

    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        assert (
            batch_v2.apply_v2_packet(
                cur, packet, environment="preview", storage=storage
            )["state"]
            == "selected"
        )
        cur.execute(
            "SELECT COUNT(*) FROM site_week_selection_history WHERE season = 2026"
        )
        history_count = cur.fetchone()[0]
    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        assert (
            batch_v2.apply_v2_packet(
                cur, packet, environment="preview", storage=storage
            )["state"]
            == "already_applied"
        )
        cur.execute(
            "SELECT COUNT(*) FROM site_week_selection_history WHERE season = 2026"
        )
        assert cur.fetchone()[0] == history_count

    rollback = _make_rollback_packet(packet, storage)
    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        assert (
            batch_v2.apply_v2_packet(
                cur, rollback, environment="preview", storage=storage
            )["state"]
            == "rolled_back"
        )
    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT week, run_id FROM site_week_selections WHERE season = 2026 ORDER BY week"
        )
        assert cur.fetchall() == [(week, f"old-{week}") for week in range(7)]
        cur.execute("SELECT value FROM team_season_stats WHERE season = 2026")
        assert cur.fetchone()[0] == 0.2


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="requires disposable PostgreSQL via TEST_DATABASE_URL",
)
def test_v2_revocation_waits_for_selection_shared_advisory_lock():
    conn_url = os.environ["TEST_DATABASE_URL"]
    packet, storage = _packet()
    _prepare_database(conn_url, storage)
    started = threading.Event()
    finished = threading.Event()
    errors = []

    def revoke():
        try:
            with psycopg.connect(
                conn_url, application_name="v5_stage7a_revoker_test"
            ) as conn:
                with conn.cursor() as cur:
                    started.set()
                    append_release_revocation(
                        cur,
                        record_type="bundle_approval",
                        record_id="bundle-7a",
                        decision_ref="concurrent-revocation",
                    )
        except Exception as exc:  # surfaced in the main test thread
            errors.append(exc)
        finally:
            finished.set()

    selection_conn = psycopg.connect(conn_url)
    with selection_conn.cursor() as cur:
        lock_release_records(cur, [("bundle_approval", "bundle-7a")])
    thread = threading.Thread(target=revoke, daemon=True)
    thread.start()
    assert started.wait(2)
    deadline = time.monotonic() + 3
    observed_wait = False
    while time.monotonic() < deadline:
        with psycopg.connect(conn_url) as observer, observer.cursor() as cur:
            cur.execute(
                "SELECT wait_event_type, wait_event FROM pg_stat_activity "
                "WHERE application_name = 'v5_stage7a_revoker_test'"
            )
            observed_wait = cur.fetchone() == ("Lock", "advisory")
        if observed_wait:
            break
        time.sleep(0.05)
    assert observed_wait, "revocation writer did not wait on the shared selection lock"
    selection_conn.commit()
    selection_conn.close()
    assert finished.wait(3)
    thread.join(timeout=1)
    assert not errors
    with psycopg.connect(conn_url) as conn, conn.cursor() as cur:
        with pytest.raises(V5RevocationError, match="has been revoked"):
            assert_release_records_active(cur, [("bundle_approval", "bundle-7a")])


def test_moving_cutover_requires_completed_week5_prospective_evidence():
    """A later N cannot silently drop authentic completed prospective history."""
    import copy

    from cks_picks_cfb.ops.v5_intended_update_release import AUTH_COLUMNS

    packet, storage = _packet()
    packet["cutover_week"] = 6
    packet["certified_completed_weeks"] = list(range(6))
    packet["expected_current_runs"]["6"] = "old-6"
    packet["replacement_runs"]["6"] = "new-6"
    packet["protected_runs"] = {"7": "protected-7"}
    packet["expected_current_week"] = dict(season=2026, week=6, run_id="old-6")
    packet["replacement_current_week"] = dict(season=2026, week=6, run_id="new-6")
    bundle = packet["bundle_approval"]
    bundle["first_live_week"] = 6
    bundle.pop("record_sha256")
    bundle["record_sha256"] = hashlib.sha256(canonical_json(bundle)).hexdigest()
    last = packet["run_authorizations"][-1]
    next_record = copy.deepcopy(last)
    last["evidence_class"] = "replay"
    next_record.update(week=6, prediction_run_id="new-6", authorization_id="auth-6")
    packet["run_authorizations"].append(next_record)
    for record in packet["run_authorizations"]:
        record["record_sha256"] = hashlib.sha256(
            canonical_json({key: record.get(key) for key in AUTH_COLUMNS})
        ).hexdigest()
    with pytest.raises(V5BatchSelectionError, match="completed prospective Week 5"):
        validate_v2_packet(
            signed_payload(packet), environment="preview", storage=storage
        )
