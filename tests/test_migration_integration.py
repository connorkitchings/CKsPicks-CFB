import os
from pathlib import Path

import psycopg
import pytest

from cks_picks_cfb.data.game_venues import UPSERT_GAME_VENUE_SQL
from cks_picks_cfb.data.team_stats import UPSERT_TEAM_STAT_SQL, to_upsert_records
from cks_picks_cfb.db.migrations import apply_migrations


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="requires disposable PostgreSQL via TEST_DATABASE_URL",
)
def test_fresh_database_applies_snapshot_and_hardening_migration():
    conn_url = os.environ["TEST_DATABASE_URL"]
    with psycopg.connect(conn_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("DROP SCHEMA IF EXISTS ops CASCADE")
            cur.execute("DROP SCHEMA IF EXISTS catalog CASCADE")
            cur.execute("DROP SCHEMA IF EXISTS public CASCADE")
            cur.execute("CREATE SCHEMA public")
    applied = apply_migrations(conn_url, Path("contracts/migrations"))
    assert "0006" in applied
    assert "0008" in applied
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'ops' AND table_name = 'pipeline_runs'"
            )
            pipeline_columns = {row[0] for row in cur.fetchall()}
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'catalog' AND table_name = 'dataset_versions'"
            )
            dataset_columns = {row[0] for row in cur.fetchall()}
            cur.execute(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conname = 'predictions_regime_check'"
            )
            regime_constraint = cur.fetchone()[0]
    assert {"definition_sha", "lease_epoch", "lease_expires_at"} <= pipeline_columns
    assert {"identity_version", "schema_sha"} <= dataset_columns
    assert "game_4" in regime_constraint
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'market_quotes'"
            )
            quote_columns = {row[0] for row in cur.fetchall()}
    assert {
        "home_spread_price",
        "away_spread_price",
        "over_price",
        "under_price",
        "quote_updated_at",
        "source_event_id",
    } <= quote_columns


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="requires disposable PostgreSQL via TEST_DATABASE_URL",
)
def test_v5_rating_manifest_required_but_v4_rollback_remains_valid():
    conn_url = os.environ["TEST_DATABASE_URL"]
    with psycopg.connect(conn_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("DROP SCHEMA IF EXISTS ops CASCADE")
            cur.execute("DROP SCHEMA IF EXISTS catalog CASCADE")
            cur.execute("DROP SCHEMA IF EXISTS public CASCADE")
            cur.execute("CREATE SCHEMA public")
    applied = apply_migrations(conn_url, Path("contracts/migrations"))
    assert "0017" in applied
    insert = (
        "INSERT INTO prediction_runs "
        "(run_id, season, week, state, expected_games, predicted_games, "
        "lined_games, data_as_of, artifact_uri, artifact_sha256, model_id, "
        "rating_manifest_sha256) "
        "VALUES (%s, 2026, 5, 'preview', 0, 0, 0, NOW(), 'test', 'test', %s, %s)"
    )
    with psycopg.connect(conn_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(insert, ("v4-rollback", "v4-2026", None))
            with pytest.raises(psycopg.errors.CheckViolation):
                cur.execute(insert, ("v5-missing", "v5-live-2026", None))
            cur.execute(insert, ("v5-valid", "v5-live-2026", "a" * 64))
            cur.execute(
                "SELECT count(*) FROM prediction_runs WHERE run_id IN (%s, %s)",
                ("v4-rollback", "v5-valid"),
            )
            assert cur.fetchone()[0] == 2
            cur.execute(
                "ALTER TABLE prediction_runs "
                "DROP CONSTRAINT chk_prediction_runs_rating_manifest_required"
            )
            cur.execute("DELETE FROM schema_migrations WHERE version = '0017'")
            cur.execute(insert, ("v5-old-null", "v5-live-2026", None))
    with pytest.raises(psycopg.errors.RaiseException, match="Migration 0017 blocked"):
        apply_migrations(conn_url, Path("contracts/migrations"))
    with psycopg.connect(conn_url, autocommit=True) as conn:
        conn.execute("DELETE FROM prediction_runs WHERE run_id = 'v5-old-null'")
    assert apply_migrations(conn_url, Path("contracts/migrations")) == ["0017"]
    with psycopg.connect(conn_url, autocommit=True) as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(insert, ("v5-still-missing", "v5-live-2026", None))


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="requires disposable PostgreSQL via TEST_DATABASE_URL",
)
def test_hardening_migration_upgrades_pre_hardening_schema():
    """Exercise 0006 against a schema shaped exactly like the pre-0006 contract."""
    conn_url = os.environ["TEST_DATABASE_URL"]
    with psycopg.connect(conn_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("DROP SCHEMA IF EXISTS ops CASCADE")
            cur.execute("DROP SCHEMA IF EXISTS catalog CASCADE")
            cur.execute("DROP SCHEMA IF EXISTS public CASCADE")
            cur.execute("CREATE SCHEMA public")
    apply_migrations(conn_url, Path("contracts/migrations"))
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "ALTER TABLE catalog.dataset_versions "
                "DROP CONSTRAINT dataset_versions_identity_version_check, "
                "DROP COLUMN identity_version, DROP COLUMN schema_sha"
            )
            cur.execute("DROP INDEX IF EXISTS catalog.idx_dataset_versions_schema")
            cur.execute("ALTER TABLE catalog.schema_versions DROP COLUMN schema_sha")
            cur.execute(
                "ALTER TABLE ops.pipeline_runs "
                "DROP COLUMN definition_json, DROP COLUMN definition_sha, "
                "DROP COLUMN lease_owner, DROP COLUMN lease_epoch, "
                "DROP COLUMN lease_expires_at, DROP COLUMN heartbeat_at"
            )
            cur.execute(
                "ALTER TABLE ops.pipeline_steps "
                "DROP COLUMN definition_sha, DROP COLUMN lease_epoch"
            )
            cur.execute(
                Path(
                    "contracts/migrations/0006_pipeline_data_hardening.sql"
                ).read_text()
            )
        conn.commit()
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_constraint "
                "WHERE conname = 'dataset_versions_identity_version_check'"
            )
            assert cur.fetchone() is not None
            cur.execute(
                "SELECT 1 FROM pg_indexes WHERE schemaname = 'ops' "
                "AND indexname = 'idx_pipeline_runs_lease'"
            )
            assert cur.fetchone() is not None


# Kept in this file (not a separate one): every test here resets the shared test
# database, and CI runs files in parallel with --dist loadfile, so DB-resetting
# tests must live in one file to run serially.
@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="requires disposable PostgreSQL via TEST_DATABASE_URL",
)
def test_game_venues_migration_creates_table_and_upsert_round_trips():
    conn_url = os.environ["TEST_DATABASE_URL"]
    with psycopg.connect(conn_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            for schema in ("ops", "catalog", "public"):
                cur.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
            cur.execute("CREATE SCHEMA public")
    applied = apply_migrations(conn_url, Path("contracts/migrations"))
    assert "0019" in applied
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'game_venues'"
            )
            columns = {row[0] for row in cur.fetchall()}
            assert {"game_id", "city", "state", "neutral_site", "venue_name"} <= columns
            cur.execute(
                "INSERT INTO games (game_id, season, week, start_date, home_team, "
                "away_team) VALUES (1, 2026, 5, NOW(), 'Home', 'Away')"
            )
            record = {
                "game_id": 1,
                "venue_id": 10,
                "venue_name": "Rose Bowl",
                "city": "Pasadena",
                "state": "CA",
                "country_code": "US",
                "timezone": "America/Los_Angeles",
                "neutral_site": False,
            }
            cur.execute(UPSERT_GAME_VENUE_SQL, record)
            cur.execute(UPSERT_GAME_VENUE_SQL, {**record, "city": "Los Angeles"})
            cur.execute("SELECT city, state FROM game_venues WHERE game_id = 1")
            assert cur.fetchall() == [("Los Angeles", "CA")]
    # Re-applying migrations is a no-op.
    assert apply_migrations(conn_url, Path("contracts/migrations")) == []


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="requires disposable PostgreSQL via TEST_DATABASE_URL",
)
def test_team_season_stats_migration_creates_table_and_upsert_round_trips():
    import pandas as pd

    conn_url = os.environ["TEST_DATABASE_URL"]
    with psycopg.connect(conn_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            for schema in ("ops", "catalog", "public"):
                cur.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
            cur.execute("CREATE SCHEMA public")
    applied = apply_migrations(conn_url, Path("contracts/migrations"))
    assert "0020" in applied
    frame = pd.DataFrame(
        [
            {
                "season": 2026,
                "as_of_week": 5,
                "team": "A",
                "role": "offense",
                "metric": "epa_pass",
                "value": 0.25,
                "n": 40,
                "games": 4,
                "rank": 3,
                "cohort_size": 130,
            },
            {
                "season": 2026,
                "as_of_week": 5,
                "team": "A",
                "role": "defense",
                "metric": "epa_pass",
                "value": None,
                "n": 0,
                "games": 0,
                "rank": pd.NA,
                "cohort_size": pd.NA,
            },
        ]
    )
    versions = {"byplay": "443019a9a7b6a2454a4af4ac"}
    records = to_upsert_records(frame, versions)
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            for record in records:
                cur.execute(UPSERT_TEAM_STAT_SQL, record)
            cur.execute(UPSERT_TEAM_STAT_SQL, {**records[0], "value": 0.5, "rank": 1})
            cur.execute("SELECT role, value, rank FROM team_season_stats ORDER BY role")
            assert cur.fetchall() == [("defense", None, None), ("offense", 0.5, 1)]
            cur.execute("SELECT DISTINCT source_versions FROM team_season_stats")
            assert cur.fetchall() == [(versions,)]
            with pytest.raises(psycopg.errors.CheckViolation):
                cur.execute(UPSERT_TEAM_STAT_SQL, {**records[0], "role": "special"})
    assert apply_migrations(conn_url, Path("contracts/migrations")) == []


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="requires disposable PostgreSQL via TEST_DATABASE_URL",
)
def test_matchup_data_v2_migration_tables_constraints_and_grants():
    conn_url = os.environ["TEST_DATABASE_URL"]
    with psycopg.connect(conn_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            for schema in ("ops", "catalog", "public"):
                cur.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
            cur.execute("CREATE SCHEMA public")
    applied = apply_migrations(conn_url, Path("contracts/migrations"))
    assert "0021" in applied
    sha = "a" * 64
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO v5_rating_snapshots (snapshot_id, source_run_id, "
                "source_manifest_sha256, team, season, week, game_id, snapshot_class, "
                "cutoff_utc, offense_rating, offense_variance, defense_rating, "
                "defense_variance, overall_rating, overall_variance) VALUES "
                "('run:current:post-week-4:A', 'run', %s, 'A', 2026, 4, NULL, 'current', "
                "NOW(), 1, 1, 1, 1, 1, 1)",
                (sha,),
            )
            component = (
                "INSERT INTO team_rating_components (component_id, v5_snapshot_id, "
                "lineage, candidate_id, source_manifest_sha256, snapshot_class, season, "
                "as_of_week, cutoff_utc, rating_team, team, unit_role, rating_mean, "
                "rating_variance, evidence) VALUES (%s, %s, 'intended_update', 'c', %s, "
                "'current', 2026, 5, NOW(), 'A', 'A', %s, 1.5, 0.2, '[]'::jsonb)"
            )
            cur.execute(
                component,
                (
                    "run:current:post-week-4:A:offense",
                    "run:current:post-week-4:A",
                    sha,
                    "offense",
                ),
            )
            # The FK forces ratings to be projected first.
            with pytest.raises(psycopg.errors.ForeignKeyViolation):
                cur.execute(
                    component, ("x:offense", "missing-snapshot", sha, "offense")
                )
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            bad = [
                (
                    "INSERT INTO team_possession_stats (season, as_of_week, team, role, "
                    "metric, rating_manifest_sha256, measurement_manifest_sha256) VALUES "
                    "(2026, 5, 'A', 'offense', 'not_a_metric', %s, %s)"
                ),
                (
                    "INSERT INTO team_possession_adjusted (season, as_of_week, team, role, "
                    "measurement_id, adjustment_method, rating_manifest_sha256, "
                    "measurement_manifest_sha256) VALUES (2026, 5, 'A', 'offense', "
                    "'success_rate', 'm', %s, %s)"
                ),
                (
                    "INSERT INTO team_possession_stats (season, as_of_week, team, role, "
                    "metric, rating_manifest_sha256, measurement_manifest_sha256) VALUES "
                    "(2026, 5, 'A', 'offense', 'ppp', 'short', %s)"
                ),
            ]
            for statement in bad:
                params = (sha, sha) if statement.count("%s") == 2 else (sha,)
                with pytest.raises(psycopg.errors.CheckViolation):
                    cur.execute(statement, params)
                conn.rollback()
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT table_name, grantee, string_agg(privilege_type, ',' "
                "ORDER BY privilege_type) FROM information_schema.role_table_grants "
                "WHERE table_name = ANY(%s) AND grantee IN ('cks_web', 'cks_pipeline') "
                "GROUP BY 1, 2 ORDER BY 1, 2",
                (
                    [
                        "matchup_data_publications",
                        "team_game_measurements",
                        "team_possession_stats",
                        "team_possession_adjusted",
                        "team_rating_components",
                    ],
                ),
            )
            grants = cur.fetchall()
    assert len(grants) == 10
    assert {g[2] for g in grants if g[1] == "cks_web"} == {"SELECT"}
    assert {g[2] for g in grants if g[1] == "cks_pipeline"} == {"INSERT,SELECT,UPDATE"}
    assert apply_migrations(conn_url, Path("contracts/migrations")) == []


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="requires disposable PostgreSQL via TEST_DATABASE_URL",
)
def test_stage7a_migrations_guard_prospective_and_revocation_records():
    conn_url = os.environ["TEST_DATABASE_URL"]
    with psycopg.connect(conn_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            for schema in ("ops", "catalog", "public"):
                cur.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
            cur.execute("CREATE SCHEMA public")
    applied = apply_migrations(conn_url, Path("contracts/migrations"))
    assert {"0023", "0024"} <= set(applied)

    # Reconstruct the logical 0022 boundary and confirm the two additions
    # apply incrementally without replaying any earlier migration.
    with psycopg.connect(conn_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE public.prospective_week_records CASCADE")
            cur.execute("DROP TABLE ops.v5_release_revocations CASCADE")
            cur.execute("DROP FUNCTION public.validate_prospective_week_record()")
            cur.execute("DROP FUNCTION public.reject_prospective_week_record_delete()")
            cur.execute("DROP FUNCTION ops.validate_v5_release_revocation()")
            cur.execute("DROP FUNCTION ops.reject_v5_release_revocation_mutation()")
            cur.execute(
                "DELETE FROM schema_migrations WHERE version IN ('0023', '0024')"
            )
    assert apply_migrations(conn_url, Path("contracts/migrations")) == ["0023", "0024"]

    with psycopg.connect(conn_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT has_table_privilege('cks_pipeline', 'public.prospective_week_records', 'SELECT'), "
                "has_table_privilege('cks_pipeline', 'public.prospective_week_records', 'INSERT'), "
                "has_table_privilege('cks_pipeline', 'public.prospective_week_records', 'DELETE'), "
                "has_table_privilege('cks_web', 'public.prospective_week_records', 'SELECT'), "
                "has_table_privilege('cks_web', 'ops.v5_release_revocations', 'SELECT'), "
                "has_table_privilege('cks_pipeline', 'ops.v5_release_revocations', 'SELECT'), "
                "has_table_privilege('cks_pipeline', 'ops.v5_release_revocations', 'INSERT'), "
                "has_table_privilege('cks_release_authorizer', 'ops.v5_release_revocations', 'INSERT')"
            )
            assert cur.fetchone() == (True, True, False, True, False, True, False, True)

            future_kickoff = "2026-10-10 18:00:00+00"
            historical_kickoff = "2026-09-10 18:00:00+00"
            sha = "a" * 64
            for week, run_id, kickoff, frozen_at in (
                (5, "v5-prospective-5a", future_kickoff, "2026-10-06 12:00:00+00"),
                (5, "v5-prospective-5b", future_kickoff, "2026-10-06 13:00:00+00"),
                (6, "v5-prospective-6a", historical_kickoff, "2026-09-09 12:00:00+00"),
                (6, "v5-prospective-6b", historical_kickoff, "2026-09-09 13:00:00+00"),
            ):
                cur.execute(
                    "INSERT INTO games (game_id, season, week, start_date, home_team, away_team) "
                    "VALUES (%s, 2026, %s, %s, 'Home', 'Away')",
                    (100000 + week * 10 + ord(run_id[-1]), week, kickoff),
                )
                cur.execute(
                    "INSERT INTO prediction_runs (run_id, season, week, state, expected_games, "
                    "predicted_games, lined_games, data_as_of, model_id, rating_manifest_sha256, "
                    "artifact_uri, artifact_sha256, frozen_at, evidence_class) "
                    "VALUES (%s, 2026, %s, 'frozen', 1, 1, 1, %s, 'v5-fixture', %s, 'r2://fixture', %s, %s, 'live')",
                    (run_id, week, frozen_at, sha, sha, frozen_at),
                )
                cur.execute(
                    "INSERT INTO predictions (run_id, game_id, regime) VALUES (%s, %s, 'preseason')",
                    (run_id, 100000 + week * 10 + ord(run_id[-1])),
                )
                cur.execute(
                    "INSERT INTO ops.activation_history (environment, season, week, run_id, action) "
                    "VALUES ('preview', 2026, %s, %s, 'freeze')",
                    (week, run_id),
                )

            insert_record = (
                "INSERT INTO public.prospective_week_records "
                "(season, week, run_id, freeze_receipt_uri, freeze_receipt_sha256, "
                "frozen_at, first_kickoff_utc, decision_ref) "
                "VALUES (2026, %s, %s, 'r2://receipt', %s, %s, %s, 'fixture-decision')"
            )
            cur.execute(
                insert_record,
                (5, "v5-prospective-5a", sha, "2026-10-06 12:00:00+00", future_kickoff),
            )
            cur.execute(
                "UPDATE public.prospective_week_records SET run_id = %s, frozen_at = %s "
                "WHERE season = 2026 AND week = 5",
                ("v5-prospective-5b", "2026-10-06 13:00:00+00"),
            )
            with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
                cur.execute(
                    "DELETE FROM public.prospective_week_records WHERE season = 2026 AND week = 5"
                )

            cur.execute(
                insert_record,
                (
                    6,
                    "v5-prospective-6a",
                    sha,
                    "2026-09-09 12:00:00+00",
                    historical_kickoff,
                ),
            )
            with pytest.raises(
                psycopg.errors.RaiseException, match="before its earliest kickoff"
            ):
                cur.execute(
                    "UPDATE public.prospective_week_records SET run_id = %s, frozen_at = %s "
                    "WHERE season = 2026 AND week = 6",
                    ("v5-prospective-6b", "2026-09-09 13:00:00+00"),
                )
            with pytest.raises(
                psycopg.errors.RaiseException, match="restricted to 2026 Week 5"
            ):
                cur.execute(
                    insert_record,
                    (
                        4,
                        "v5-prospective-6b",
                        sha,
                        "2026-09-09 13:00:00+00",
                        historical_kickoff,
                    ),
                )

            cur.execute(
                "INSERT INTO v5_model_bundle_approvals (approval_id, model_id, inference_bundle_sha256, "
                "first_live_season, first_live_week, decision_ref) VALUES ('approval-fixture', 'v5-fixture', %s, 2026, 5, 'approved')",
                (sha,),
            )
            cur.execute("SET ROLE cks_release_authorizer")
            cur.execute(
                "INSERT INTO ops.v5_release_revocations (record_type, record_id, decision_ref) "
                "VALUES ('bundle_approval', 'approval-fixture', 'revoke-fixture')"
            )
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute(
                    "UPDATE ops.v5_release_revocations SET decision_ref = 'changed'"
                )
            cur.execute("RESET ROLE")
            with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
                cur.execute(
                    "UPDATE ops.v5_release_revocations SET decision_ref = 'changed'"
                )
