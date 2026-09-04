import os
from pathlib import Path

import psycopg
import pytest

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
