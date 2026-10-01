import os
from pathlib import Path

import psycopg
import pytest

from cks_picks_cfb.data.game_venues import UPSERT_GAME_VENUE_SQL
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
