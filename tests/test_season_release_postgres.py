"""Real-Postgres tests for atomic season releases (migrations 0025-0027 + release.py).

Harness: ``tests/pg_harness.py`` runs ``initdb --auth=trust --no-sync`` into a
pytest temporary directory and starts a server that listens only on a Unix
socket in a private directory (``listen_addresses=''``); no TCP port is bound.
The server is stopped and every directory removed at session teardown, also
after failures. The module skips when PostgreSQL binaries are not installed.

Prerequisite schema: ``contracts/schema.sql`` is the reconstructed snapshot the
migration runner (``cks_picks_cfb.db.migrations.apply_migrations``) loads into an
empty database before replaying every file in ``contracts/migrations``. Its tail,
starting at ``-- Additive season releases.``, is byte-identical to
``0025_season_releases.sql`` (asserted below). The pre-0025 state is therefore
the snapshot prefix before that marker followed by migrations 0002..0024, which
is exactly the runner's fresh-database path minus 0025. All DDL runs as a
non-superuser owner login (``cks_owner``), like a hosted database owner.

Databases: three templates are built once per session (pre-0025, 0025 applied,
and an "operable" copy). Every test gets its own ``CREATE DATABASE ... TEMPLATE``
copy, so tests are independent and the release functions' own transaction
handling is exercised unchanged.

Every template is built from the shipped SQL alone; the "operable" template
only adds the owner-installed release policies.

Candidates (``tests.season_candidates``) pass the REAL verification module: staging
re-derives every projection check from the payload bytes. Only the tests of the
database foreign keys and of rejection wrapping inject verification stand-ins.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

import psycopg
import pytest
from psycopg import errors, sql

from cks_picks_cfb.season import release
from cks_picks_cfb.season import verification as verifier
from cks_picks_cfb.season.manifest import canonical
from cks_picks_cfb.season.projection_common import (
    PROJECTION_SETS,
    recognized_projection_set,
)
from scripts.pipeline.run_season import _sealed_candidate
from tests.pg_harness import PgCluster, find_pg_bin
from tests.season_candidates import (
    POLICY,
    candidate,
    manifest_uri,
    payload_for,
    rename_venue,
    run_id,
    seal,
)
from tests.season_fixtures import build_season

PG_BIN = find_pg_bin()
if PG_BIN is None:
    pytest.skip(
        "PostgreSQL server binaries (initdb, pg_ctl, postgres) not found",
        allow_module_level=True,
    )

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "contracts" / "migrations"
WEB_DIR = ROOT / "web"
#: The web resolver checks run the TypeScript modules through node.
WEB_AVAILABLE = (WEB_DIR / "node_modules").is_dir()
ACTIVE_SQL = (
    "SELECT release_id, active_week FROM season_releases"
    " WHERE environment = %s AND season = %s AND status = 'active'"
)
MIGRATION_0025 = MIGRATIONS / "0025_season_releases.sql"
MIGRATION_0026 = MIGRATIONS / "0026_team_chart_tables.sql"
MIGRATION_0027 = MIGRATIONS / "0027_team_game_yardage.sql"
MIGRATION_0028 = MIGRATIONS / "0028_team_resume.sql"
SNAPSHOT_MARKER = "-- Additive season releases."

OWNER = "cks_owner"
WEB_LOGIN = "cks_web_reader"
PIPELINE = {"preview": "cks_preview_pipeline", "production": "cks_prod_pipeline"}
SEASON = 2026
ACTIVE_WEEK = 2  # tests.season_candidates identities: through Week 1, active Week 2
CONTROL_TABLES = {
    "season_release_policies",
    "season_releases",
    "season_release_history",
}

ACTIVATE_FN = "activate_season_release(text, text, text)"


# --------------------------------------------------------------------------
# SQL sources
# --------------------------------------------------------------------------


def pre0025_snapshot_sql() -> str:
    schema = (ROOT / "contracts" / "schema.sql").read_text()
    return schema[: schema.index(SNAPSHOT_MARKER)]


def apply_pre0025(conn) -> None:
    conn.execute(pre0025_snapshot_sql())
    for path in sorted(MIGRATIONS.glob("*.sql")):
        if path.name < "0025":
            conn.execute(path.read_text())


# --------------------------------------------------------------------------
# Cluster, templates, per-test databases
# --------------------------------------------------------------------------


def _create_db(cluster: PgCluster, name: str, template: str | None = None) -> None:
    statement = sql.SQL("CREATE DATABASE {} OWNER {}").format(
        sql.Identifier(name), sql.Identifier(OWNER)
    )
    if template:
        statement += sql.SQL(" TEMPLATE {}").format(sql.Identifier(template))
    with cluster.connect(autocommit=True) as conn:
        conn.execute(statement)


def _bootstrap(cluster: PgCluster) -> None:
    with cluster.connect(autocommit=True) as conn:
        conn.execute(f"CREATE ROLE {OWNER} LOGIN CREATEDB")
        for group in ("cks_web", "cks_pipeline", "cks_migrator"):
            conn.execute(f"CREATE ROLE {group} NOLOGIN")
        conn.execute("CREATE ROLE cks_release_authorizer NOLOGIN")
        for login in PIPELINE.values():
            conn.execute(f"CREATE ROLE {login} LOGIN IN ROLE cks_pipeline")
        conn.execute(f"CREATE ROLE {WEB_LOGIN} LOGIN IN ROLE cks_web")

    _create_db(cluster, "tpl_pre0025")
    with cluster.connect("tpl_pre0025", OWNER, autocommit=True) as conn:
        apply_pre0025(conn)
        conn.execute(
            "INSERT INTO games (game_id, season, week, start_date, home_team, away_team)"
            " VALUES (900001, 2025, 1, '2025-08-30T16:00:00Z', 'Legacy A', 'Legacy B')"
        )
    _create_db(cluster, "tpl_0025", "tpl_pre0025")
    with cluster.connect("tpl_0025", OWNER, autocommit=True) as conn:
        conn.execute(MIGRATION_0025.read_text())
    _create_db(cluster, "tpl_0025_operable", "tpl_0025")
    _create_db(cluster, "tpl_0026", "tpl_0025")
    with cluster.connect("tpl_0026", OWNER, autocommit=True) as conn:
        conn.execute(MIGRATION_0026.read_text())
    _create_db(cluster, "tpl_0026_operable", "tpl_0026")
    _create_db(cluster, "tpl_migrated", "tpl_0026")
    with cluster.connect("tpl_migrated", OWNER, autocommit=True) as conn:
        conn.execute(MIGRATION_0027.read_text())
    _create_db(cluster, "tpl_resume", "tpl_migrated")
    with cluster.connect("tpl_resume", OWNER, autocommit=True) as conn:
        conn.execute(MIGRATION_0028.read_text())
    _create_db(cluster, "tpl_operable", "tpl_resume")
    for template in ("tpl_0025_operable", "tpl_0026_operable", "tpl_operable"):
        with cluster.connect(template, OWNER, autocommit=True) as conn:
            for environment in PIPELINE:
                install_policy(conn, environment)


def install_policy(conn, environment: str, **overrides) -> None:
    policy = {**POLICY, "enabled": True, **overrides}
    conn.execute(
        "INSERT INTO season_release_policies (environment, season,"
        " model_manifest_sha256, workflow_version, grading_policy_sha256, enabled,"
        " decision_ref) VALUES (%s, %s, %s, %s, %s, %s, 'owner decision 1')"
        " ON CONFLICT (environment, season) DO UPDATE SET"
        " model_manifest_sha256 = EXCLUDED.model_manifest_sha256,"
        " workflow_version = EXCLUDED.workflow_version,"
        " grading_policy_sha256 = EXCLUDED.grading_policy_sha256,"
        " enabled = EXCLUDED.enabled",
        (
            environment,
            SEASON,
            policy["model_manifest_sha256"],
            policy["workflow_version"],
            policy["grading_policy_sha256"],
            policy["enabled"],
        ),
    )


@pytest.fixture(scope="session")
def cluster(tmp_path_factory):
    instance = PgCluster(PG_BIN, tmp_path_factory.mktemp("season_release_pg"))
    try:
        instance.start()
        _bootstrap(instance)
        yield instance
    finally:
        instance.stop()


@pytest.fixture
def make_db(cluster):
    created: list[str] = []

    def make(template: str) -> str:
        name = f"t_{uuid.uuid4().hex[:16]}"
        _create_db(cluster, name, template)
        created.append(name)
        return name

    yield make
    with cluster.connect(autocommit=True) as conn:
        for name in created:
            conn.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                    sql.Identifier(name)
                )
            )


@pytest.fixture
def pre0025_db(make_db):
    return make_db("tpl_pre0025")


@pytest.fixture
def migrated_db(make_db):
    return make_db("tpl_migrated")


@pytest.fixture
def db(make_db):
    return make_db("tpl_operable")


@pytest.fixture
def db_0025(make_db):
    """Operable database that has migration 0025 but not the 0026 chart tables."""
    return make_db("tpl_0025_operable")


@pytest.fixture
def db_0026(make_db):
    """Operable database with the charts_v1 tables (0026) but not 0027 yardage."""
    return make_db("tpl_0026_operable")


@pytest.fixture
def fake_verification(monkeypatch):
    """Verification stand-ins, only for payloads the real checks would refuse."""

    def derived(projections, manifest):
        report = json.loads(manifest["__report__"])
        return {
            name: report["checks"][name] for name in verifier.REQUIRED_PROJECTION_CHECKS
        }

    monkeypatch.setattr(verifier, "derive_checks", lambda p, m: _passing(p))
    monkeypatch.setattr(verifier, "validate_report", lambda report, **kwargs: None)


def _passing(projections) -> dict:
    return {
        name: {"passed": True, "observed": {}, "source": "projection"}
        for name in sorted(verifier.REQUIRED_PROJECTION_CHECKS)
    }


# --------------------------------------------------------------------------
# Candidate payloads and release helpers
# --------------------------------------------------------------------------


def views(label: str = "r1") -> dict:
    """The serving projections (payload minus the run registry) of ``label``."""
    payload = payload_for(label)
    payload.pop("prediction_runs")
    return payload


def release_id_of(label: str, environment: str = "preview") -> str:
    return f"{environment}-{run_id(label)}"


def stage(cluster, dbname, label, environment="preview", payload=None, **kwargs):
    """Stage and commit exactly as ``run_season.py`` does (rollback on error)."""
    sealed = payload or candidate(label, **kwargs)
    with cluster.connect(dbname, PIPELINE[environment]) as conn:
        staged = release.stage_release(
            conn,
            run_manifest_uri=manifest_uri(sealed),
            environment=environment,
            **sealed,
        )
        conn.commit()
    return staged


def activate(cluster, dbname, release_id, previous, environment="preview", **kwargs):
    with cluster.connect(dbname, PIPELINE[environment]) as conn:
        receipt = release.activate_release(
            conn,
            environment=environment,
            season=SEASON,
            release_id=release_id,
            expected_previous_release_id=previous,
            **kwargs,
        )
        conn.commit()
    return receipt


def rollback(cluster, dbname, release_id, previous, *, user=OWNER, **overrides):
    arguments = {"owner_authorized": True, "decision_ref": "owner rollback 7"}
    arguments.update(overrides)
    with cluster.connect(dbname, user) as conn:
        receipt = release.rollback_release(
            conn,
            environment="preview",
            season=SEASON,
            release_id=release_id,
            expected_previous_release_id=previous,
            **arguments,
        )
        conn.commit()
    return receipt


def release_state(cluster, dbname) -> dict[str, list[str]]:
    """Every row of every season-release table plus the run registry."""
    with cluster.connect(dbname, OWNER, autocommit=True) as conn:
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
                " AND tablename LIKE 'season\\_release%' ORDER BY 1"
            )
        ]
        return {
            table: [
                row[0]
                for row in conn.execute(
                    sql.SQL(
                        "SELECT to_jsonb(t)::text AS j FROM {} t ORDER BY j"
                    ).format(sql.Identifier(table))
                )
            ]
            for table in [*tables, "prediction_runs"]
        }


def legacy_state(cluster, dbname) -> dict[str, tuple]:
    """(columns, row count) for every non-season-release table in every schema."""
    with cluster.connect(dbname, OWNER, autocommit=True) as conn:
        tables = conn.execute(
            "SELECT table_schema, table_name FROM information_schema.tables"
            " WHERE table_schema IN ('public', 'catalog', 'ops')"
            " AND table_type = 'BASE TABLE' AND table_name NOT LIKE 'season\\_release%'"
            " ORDER BY 1, 2"
        ).fetchall()
        state = {}
        for schema, table in tables:
            columns = conn.execute(
                "SELECT column_name, data_type FROM information_schema.columns"
                " WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position",
                (schema, table),
            ).fetchall()
            count = conn.execute(
                sql.SQL("SELECT count(*) FROM {}.{}").format(
                    sql.Identifier(schema), sql.Identifier(table)
                )
            ).fetchone()[0]
            state[f"{schema}.{table}"] = (tuple(columns), count)
        return state


def statuses(cluster, dbname) -> dict[str, str]:
    with cluster.connect(dbname, OWNER, autocommit=True) as conn:
        return dict(conn.execute("SELECT release_id, status FROM season_releases"))


def history(cluster, dbname) -> list[tuple]:
    with cluster.connect(dbname, OWNER, autocommit=True) as conn:
        return conn.execute(
            "SELECT prior_release_id, release_id, action, decision_ref"
            " FROM season_release_history ORDER BY activation_id"
        ).fetchall()


@contextmanager
def as_role(cluster, dbname, role):
    """Superuser session with ``SET ROLE`` for pure privilege checks."""
    with cluster.connect(dbname, autocommit=True) as conn:
        conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role)))
        yield conn


def owner_insert_release(
    conn, release_id, environment="preview", season=SEASON, status="staged"
):
    conn.execute(
        "INSERT INTO season_releases (release_id, environment, season,"
        " model_manifest_sha256, revision_manifest_sha256, workflow_version,"
        " grading_policy_sha256, code_sha, config_sha, run_manifest_uri,"
        " run_manifest_sha256, verification_uri, verification_sha256, active_week,"
        " status, projection_checks) VALUES (%s, %s, %s, %s, %s, 'w', %s, 'code',"
        " 'cfg', 'run.json', %s, 'verify.json', %s, 0, %s, '{}')",
        (release_id, environment, season, *["a" * 64] * 5, status),
    )


# --------------------------------------------------------------------------
# A. Migration and schema
# --------------------------------------------------------------------------


def test_snapshot_tail_is_migrations_0025_to_0028_verbatim_matches():
    schema = (ROOT / "contracts" / "schema.sql").read_text()

    tail = schema[schema.index(SNAPSHOT_MARKER) :]

    assert tail == "".join(
        path.read_text()
        for path in (MIGRATION_0025, MIGRATION_0026, MIGRATION_0027, MIGRATION_0028)
    )


def test_shipped_0025_applies_to_pre0025_database_succeeds(cluster, pre0025_db):
    with cluster.connect(pre0025_db, OWNER, autocommit=True) as conn:
        conn.execute(MIGRATION_0025.read_text())


def test_migration_runner_bootstraps_empty_database_succeeds(cluster, make_db):
    from cks_picks_cfb.db.migrations import apply_migrations

    with cluster.connect(autocommit=True) as conn:
        conn.execute(f"CREATE DATABASE empty_bootstrap OWNER {OWNER}")
    try:
        applied = apply_migrations(
            cluster.conninfo("empty_bootstrap", OWNER), MIGRATIONS
        )
        assert "0025" in applied
    finally:
        with cluster.connect(autocommit=True) as conn:
            conn.execute("DROP DATABASE IF EXISTS empty_bootstrap WITH (FORCE)")


def test_0025_applies_with_all_tables_and_leaves_legacy_untouched(cluster, pre0025_db):
    before = legacy_state(cluster, pre0025_db)

    with cluster.connect(pre0025_db, OWNER, autocommit=True) as conn:
        conn.execute(MIGRATION_0025.read_text())
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
                " AND tablename LIKE 'season\\_release%'"
            )
        }
        index = conn.execute(
            "SELECT indexdef FROM pg_indexes WHERE indexname = 'season_releases_one_active'"
        ).fetchone()

    expected = CONTROL_TABLES | {
        f"season_release_{b}" for b in PROJECTION_SETS["core_v1"]
    }
    assert tables == expected
    assert index and "UNIQUE" in index[0] and "WHERE (status = 'active'" in index[0]
    assert legacy_state(cluster, pre0025_db) == before
    assert before["public.games"][1] == 1


def test_0025_reapplied_is_idempotent_and_schema_unchanged(cluster, migrated_db):
    catalog_sql = (
        "SELECT 'col', table_name || '.' || column_name || ':' || data_type"
        " FROM information_schema.columns WHERE table_name LIKE 'season\\_release%'"
        " UNION ALL SELECT 'idx', indexdef FROM pg_indexes WHERE tablename LIKE 'season\\_release%'"
        " UNION ALL SELECT 'con', conrelid::regclass || ':' || pg_get_constraintdef(oid)"
        "  FROM pg_constraint WHERE conrelid::regclass::text LIKE 'season\\_release%'"
        " UNION ALL SELECT 'trg', tgrelid::regclass || ':' || tgname FROM pg_trigger"
        "  WHERE NOT tgisinternal AND tgrelid::regclass::text LIKE 'season\\_release%'"
        " UNION ALL SELECT 'acl', relname || ':' || coalesce(relacl::text, '')"
        "  FROM pg_class WHERE relname LIKE 'season\\_release%'"
        " UNION ALL SELECT 'colacl', attrelid::regclass || '.' || attname || ':' || attacl::text"
        "  FROM pg_attribute WHERE attacl IS NOT NULL"
        "  AND attrelid::regclass::text LIKE 'season\\_release%'"
        " UNION ALL SELECT 'fn', proname || ':' || prosecdef || ':' || coalesce(proacl::text, '')"
        "  || ':' || coalesce(array_to_string(proconfig, ','), '') || ':' || md5(prosrc)"
        "  FROM pg_proc WHERE proname LIKE '%season\\_release%' OR proname LIKE '%season\\_projection%'"
        " ORDER BY 1, 2"
    )
    with cluster.connect(migrated_db, OWNER, autocommit=True) as conn:
        before = conn.execute(catalog_sql).fetchall()

        conn.execute(MIGRATION_0025.read_text())
        after = conn.execute(catalog_sql).fetchall()

    assert after == before


def test_second_active_release_for_same_scope_rejected(cluster, migrated_db):
    with cluster.connect(migrated_db, OWNER, autocommit=True) as conn:
        owner_insert_release(conn, "one")
        owner_insert_release(conn, "two")
        owner_insert_release(conn, "other-season", season=SEASON + 1)
        owner_insert_release(conn, "prod", environment="production")
        conn.execute(
            "UPDATE season_releases SET status = 'active' WHERE release_id = 'one'"
        )

        with pytest.raises(errors.UniqueViolation):
            conn.execute(
                "UPDATE season_releases SET status = 'active' WHERE release_id = 'two'"
            )
        conn.execute(
            "UPDATE season_releases SET status = 'active'"
            " WHERE release_id IN ('prod', 'other-season')"
        )
        active = conn.execute(
            "SELECT environment, season, count(*) FROM season_releases"
            " WHERE status = 'active' GROUP BY 1, 2 ORDER BY 1, 2"
        ).fetchall()

    assert active == [
        ("preview", 2026, 1),
        ("preview", 2027, 1),
        ("production", 2026, 1),
    ]


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE season_releases SET status = 'published' WHERE release_id = 'one'",
        "UPDATE season_releases SET environment = 'staging' WHERE release_id = 'one'",
        "UPDATE season_releases SET active_week = -1 WHERE release_id = 'one'",
        "UPDATE season_releases SET projection_checks = '[]' WHERE release_id = 'one'",
    ],
    ids=["status", "environment", "active-week", "projection-checks"],
)
def test_release_check_constraints_reject_invalid_values(
    cluster, migrated_db, statement
):
    with cluster.connect(migrated_db, OWNER, autocommit=True) as conn:
        owner_insert_release(conn, "one")
        conn.execute(
            "ALTER TABLE season_releases DISABLE TRIGGER season_release_transition"
        )

        with pytest.raises(errors.CheckViolation):
            conn.execute(statement)


def test_release_insert_with_non_staged_status_rejected(cluster, migrated_db):
    with cluster.connect(migrated_db, OWNER, autocommit=True) as conn:
        with pytest.raises(errors.RaiseException, match="staged first"):
            owner_insert_release(conn, "born-active", status="active")


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO season_releases (release_id) VALUES ('x')",
        "UPDATE season_releases SET status = 'active'",
        "DELETE FROM season_releases",
        "INSERT INTO season_release_games (release_id) VALUES ('x')",
        "SELECT * FROM season_release_policies",
        "INSERT INTO season_release_history (release_id) VALUES ('x')",
    ],
)
def test_web_role_cannot_write_or_read_policies(cluster, migrated_db, statement):
    with as_role(cluster, migrated_db, "cks_web") as conn:
        with pytest.raises(errors.InsufficientPrivilege):
            conn.execute(statement)


def test_web_role_reads_releases_and_every_projection(cluster, db):
    with as_role(cluster, db, "cks_web") as conn:
        for base in ("releases", *(f"release_{b}" for b in release.PROJECTION_KEYS)):
            conn.execute(
                sql.SQL("SELECT * FROM {}").format(sql.Identifier(f"season_{base}"))
            )


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO season_release_policies (environment, season) VALUES ('preview', 1)",
        "UPDATE season_release_policies SET enabled = true",
        "DELETE FROM season_releases",
        "TRUNCATE season_releases CASCADE",
        "DELETE FROM season_release_history",
        "TRUNCATE season_release_history",
        "DELETE FROM season_release_games",
        "TRUNCATE season_release_games",
    ],
)
def test_pipeline_role_cannot_delete_truncate_or_write_policy(cluster, db, statement):
    with as_role(cluster, db, "cks_pipeline") as conn:
        with pytest.raises(errors.InsufficientPrivilege):
            conn.execute(statement)


def test_pipeline_has_no_update_or_history_insert_privilege(cluster, migrated_db):
    with cluster.connect(migrated_db, OWNER, autocommit=True) as conn:
        privileges = conn.execute(
            "SELECT has_table_privilege('cks_pipeline', 'season_releases', 'UPDATE'),"
            " has_any_column_privilege('cks_pipeline', 'season_releases', 'UPDATE'),"
            " has_any_column_privilege('cks_pipeline', 'season_release_policies', 'UPDATE'),"
            " has_table_privilege('cks_pipeline', 'season_release_history', 'INSERT'),"
            " has_table_privilege('cks_pipeline', 'season_release_history', 'UPDATE'),"
            " has_table_privilege('cks_pipeline', 'season_release_games', 'UPDATE'),"
            " has_table_privilege('cks_web', 'season_release_history', 'SELECT')"
        ).fetchone()

    assert privileges == (False,) * 7


def test_activation_function_executable_only_by_pipeline(cluster, migrated_db):
    with cluster.connect(migrated_db, OWNER, autocommit=True) as conn:
        definer, config = conn.execute(
            "SELECT prosecdef, proconfig FROM pg_proc WHERE oid = %s::regprocedure",
            (ACTIVATE_FN,),
        ).fetchone()
        executable = {
            role: conn.execute(
                "SELECT has_function_privilege(%s, %s, 'EXECUTE')", (role, ACTIVATE_FN)
            ).fetchone()[0]
            for role in ("cks_pipeline", "cks_web", "cks_release_authorizer")
        }

    assert definer is True and config == ["search_path=pg_catalog, public"]
    assert executable == {
        "cks_pipeline": True,
        "cks_web": False,
        "cks_release_authorizer": False,  # holds no grant: PUBLIC has no EXECUTE
    }
    with as_role(cluster, migrated_db, "cks_web") as conn:
        with pytest.raises(errors.InsufficientPrivilege):
            conn.execute(f"SELECT activate_season_release('x', NULL, '{'0' * 64}')")


def test_pipeline_update_of_release_manifest_columns_refused(cluster, db):
    release_id = stage(cluster, db, "r1")
    before = release_state(cluster, db)

    with cluster.connect(db, PIPELINE["preview"], autocommit=True) as conn:
        for column, value in (("code_sha", "tampered"), ("active_week", 9)):
            with pytest.raises(errors.InsufficientPrivilege):
                conn.execute(
                    sql.SQL(
                        "UPDATE season_releases SET {} = %s WHERE release_id = %s"
                    ).format(sql.Identifier(column)),
                    (value, release_id),
                )

    assert release_state(cluster, db) == before


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE season_releases SET status = 'rolled_back' WHERE release_id = %(second)s",
        "UPDATE season_releases SET status = 'active' WHERE release_id = %(staged)s",
        "INSERT INTO season_release_history (environment, season, release_id, action,"
        " decision_ref, readback_sha256) VALUES ('preview', 2026, %(staged)s,"
        " 'activate', 'forged', repeat('0', 64))",
    ],
    ids=["roll-back", "activate", "history"],
)
def test_pipeline_cannot_change_releases_via_direct_sql(cluster, db, statement):
    first = stage(cluster, db, "r1")
    activate(cluster, db, first, None)
    second = stage(cluster, db, "r2")
    activate(cluster, db, second, first)
    staged = stage(cluster, db, "r3")
    before = release_state(cluster, db)

    with cluster.connect(db, PIPELINE["preview"]) as conn:
        with pytest.raises(errors.InsufficientPrivilege):
            conn.execute(statement, {"second": second, "staged": staged})

    assert release_state(cluster, db) == before


def _call_activation_function(conn, release_id, previous):
    return conn.execute(
        "SELECT activate_season_release(%s, %s, %s)", (release_id, previous, "0" * 64)
    ).fetchone()[0]


@pytest.mark.parametrize(
    "login,environment",
    [(PIPELINE["production"], "preview"), (PIPELINE["preview"], "production")],
    ids=["production-login-preview-release", "preview-login-production-release"],
)
def test_activation_function_refuses_other_environment_login(
    cluster, db, login, environment
):
    release_id = stage(cluster, db, "r1", environment=environment)
    before = release_state(cluster, db)

    with cluster.connect(db, login) as conn:
        with pytest.raises(errors.RaiseException, match="wrong release environment"):
            _call_activation_function(conn, release_id, None)

    assert release_state(cluster, db) == before


def test_activation_function_refuses_set_role_session(cluster, db):
    release_id = stage(cluster, db, "r1")

    with as_role(cluster, db, "cks_preview_pipeline") as conn:
        with pytest.raises(errors.RaiseException, match="wrong release environment"):
            _call_activation_function(conn, release_id, None)

    assert statuses(cluster, db) == {release_id: "staged"}


@pytest.mark.parametrize("fault", ["policy", "stale-previous", "not-staged"])
def test_direct_activation_function_call_enforces_checks(cluster, db, fault):
    first = stage(cluster, db, "r1")
    activate(cluster, db, first, None)
    second = stage(cluster, db, "r2")
    target, previous, message = second, first, "owner policy"
    if fault == "policy":
        with cluster.connect(db, OWNER, autocommit=True) as conn:
            install_policy(conn, "preview", enabled=False)
    elif fault == "stale-previous":
        previous, message = None, "changed since review"
    else:
        target, message = first, "invalid activation status"
    before = release_state(cluster, db)

    with cluster.connect(db, PIPELINE["preview"]) as conn:
        with pytest.raises(errors.RaiseException, match=message):
            _call_activation_function(conn, target, previous)

    assert release_state(cluster, db) == before


def test_direct_activation_function_call_supersedes_and_records_history(cluster, db):
    first = stage(cluster, db, "r1")
    activate(cluster, db, first, None)
    second = stage(cluster, db, "r2")

    with cluster.connect(db, PIPELINE["preview"]) as conn:
        prior = _call_activation_function(conn, second, first)
        conn.commit()

    assert prior == first
    assert statuses(cluster, db) == {first: "superseded", second: "active"}
    assert history(cluster, db)[-1] == (first, second, "activate", "owner decision 1")


def test_projection_rows_and_history_immutable_even_for_owner(cluster, db):
    release_id = stage(cluster, db, "r1")
    activate(cluster, db, release_id, None)
    before = release_state(cluster, db)

    with cluster.connect(db, OWNER, autocommit=True) as conn:
        with pytest.raises(errors.RaiseException, match="immutable"):
            conn.execute("UPDATE season_release_games SET home_team = 'X'")
        with pytest.raises(errors.RaiseException, match="immutable"):
            conn.execute("DELETE FROM season_release_predictions")
        with pytest.raises(errors.RaiseException, match="requires a staged release"):
            conn.execute(
                "INSERT INTO season_release_site_week_selections"
                " (release_id, season, week, run_id, reason) VALUES (%s, %s, 9, %s, 'x')",
                (release_id, SEASON, f"{run_id('r1')}:w0"),
            )
        with pytest.raises(errors.RaiseException, match="append-only"):
            conn.execute("UPDATE season_release_history SET decision_ref = 'x'")
        with pytest.raises(errors.RaiseException, match="append-only"):
            conn.execute("DELETE FROM season_release_history")
        with pytest.raises(errors.RaiseException, match="retained"):
            conn.execute("DELETE FROM season_releases")

    assert release_state(cluster, db) == before


# --------------------------------------------------------------------------
# B. Release functions
# --------------------------------------------------------------------------


def test_shipped_grants_allow_pipeline_activation(cluster, db):
    with cluster.connect(db, OWNER, autocommit=True) as conn:
        install_policy(conn, "preview")
    release_id = stage(cluster, db, "r1")

    receipt = activate(cluster, db, release_id, None)

    assert receipt["release_id"] == release_id


def test_stage_is_invisible_to_active_pointer_and_legacy_tables(cluster, db):
    legacy_before = legacy_state(cluster, db)

    release_id = stage(cluster, db, "r1")

    assert release_id == release_id_of("r1")
    assert statuses(cluster, db) == {release_id: "staged"}
    assert history(cluster, db) == []
    legacy_after = legacy_state(cluster, db)
    changed = {k for k in legacy_after if legacy_after[k] != legacy_before[k]}
    assert changed == {"public.prediction_runs"}  # registry row reused by the release
    with cluster.connect(db, WEB_LOGIN, autocommit=True) as conn:
        rows = conn.execute(ACTIVE_SQL, ("preview", SEASON)).fetchall()
    assert rows == []


def test_identical_restage_returns_same_release_without_new_rows(cluster, db):
    release_id = stage(cluster, db, "r1")
    before = release_state(cluster, db)

    again = stage(cluster, db, "r1")

    assert again == release_id
    assert release_state(cluster, db) == before


def test_activation_supersedes_previous_and_appends_history(cluster, db):
    first = stage(cluster, db, "r1")
    initial = activate(cluster, db, first, None)
    second = stage(cluster, db, "r2")

    receipt = activate(cluster, db, second, first)

    assert initial["prior_release_id"] is None
    assert receipt["prior_release_id"] == first and receipt["action"] == "activate"
    assert statuses(cluster, db) == {first: "superseded", second: "active"}
    assert history(cluster, db) == [
        (None, first, "activate", "owner decision 1"),
        (first, second, "activate", "owner decision 1"),
    ]
    with cluster.connect(db, OWNER, autocommit=True) as conn:
        activated = conn.execute(
            "SELECT count(*) FROM season_releases WHERE activated_at IS NOT NULL"
        ).fetchone()[0]
    assert activated == 2


@pytest.mark.parametrize(
    "expected_previous",
    [None, "preview-unknown"],
    ids=["initial-while-active", "wrong-previous"],
)
def test_activation_with_stale_expected_previous_refused_without_writes(
    cluster, db, expected_previous
):
    first = stage(cluster, db, "r1")
    activate(cluster, db, first, None)
    second = stage(cluster, db, "r2")
    before = release_state(cluster, db)

    with pytest.raises(release.SeasonReleaseError, match="changed since review"):
        activate(cluster, db, second, expected_previous)

    assert release_state(cluster, db) == before


def test_activation_from_other_environment_refused_without_writes(cluster, db):
    release_id = stage(cluster, db, "r1")
    before = release_state(cluster, db)

    with pytest.raises(release.SeasonReleaseError, match="another environment"):
        activate(cluster, db, release_id, None, environment="production")

    assert release_state(cluster, db) == before


def test_stage_with_wrong_environment_login_refused_without_writes(cluster, db):
    before = release_state(cluster, db)

    with cluster.connect(db, PIPELINE["preview"]) as conn:
        with pytest.raises(ValueError, match="restricted pipeline role"):
            release.stage_release(
                conn,
                run_manifest_uri=manifest_uri(candidate("r1")),
                environment="production",
                **candidate("r1"),
            )

    assert release_state(cluster, db) == before


@pytest.mark.parametrize(
    "policy_override",
    [
        {"model_manifest_sha256": "7" * 64},
        {"workflow_version": "season_workflow_v2"},
        {"grading_policy_sha256": "8" * 64},
        {"enabled": False},
    ],
    ids=["model", "workflow", "grading", "disabled"],
)
def test_activation_outside_owner_policy_refused_without_writes(
    cluster, db, policy_override
):
    release_id = stage(cluster, db, "r1")
    with cluster.connect(db, OWNER, autocommit=True) as conn:
        install_policy(conn, "preview", **policy_override)
    before = release_state(cluster, db)

    with pytest.raises(release.SeasonReleaseError, match="policy"):
        activate(cluster, db, release_id, None)

    assert release_state(cluster, db) == before


def test_activation_without_installed_policy_refused(cluster, db):
    release_id = stage(cluster, db, "r1")
    with cluster.connect(db, OWNER, autocommit=True) as conn:
        conn.execute(
            "DELETE FROM season_release_policies WHERE environment = 'preview'"
        )
    before = release_state(cluster, db)

    with pytest.raises(release.SeasonReleaseError, match="policy"):
        activate(cluster, db, release_id, None)

    assert release_state(cluster, db) == before


def _fail_check(report: dict) -> None:
    report["checks"]["paired_predictions"]["passed"] = False


def _tampered(fault: str) -> dict[str, bytes]:
    payload = candidate("r1")
    if fault == "verification-failed":
        return candidate("r1", edit_report=_fail_check)
    if fault == "verification-bytes":
        payload["verification_raw"] += b" "
    elif fault == "verification-missing":
        payload["verification_raw"] = b""
    elif fault == "projection-bytes":
        payload["projection_raw"] = candidate("r1", edit_payload=rename_venue)[
            "projection_raw"
        ]
    elif fault == "projection-checksum":
        manifest = json.loads(payload["manifest_raw"])
        manifest["output_refs"]["serving_projections"]["sha256"] = "0" * 64
        payload["manifest_raw"] = canonical(manifest)
    return payload


@pytest.mark.parametrize(
    "fault",
    [
        "verification-failed",
        "verification-bytes",
        "verification-missing",
        "projection-bytes",
        "projection-checksum",
    ],
)
def test_stage_of_unverified_candidate_refused_without_writes(cluster, db, fault):
    before = release_state(cluster, db)

    with pytest.raises(release.SeasonReleaseError):
        stage(cluster, db, "r1", payload=_tampered(fault))

    assert release_state(cluster, db) == before


def test_stage_with_unknown_payload_column_leaves_no_partial_rows(cluster, db):
    payload = candidate(
        "r1", edit_payload=lambda p: p["system_stats"][0].update(unexpected_column=1)
    )
    before = release_state(cluster, db)

    with pytest.raises(
        release.SeasonReleaseError, match="columns differ: system_stats"
    ):
        stage(cluster, db, "r1", payload=payload)

    assert release_state(cluster, db) == before


def test_rollback_reactivates_prior_release_and_keeps_all_rows(cluster, db):
    first = stage(cluster, db, "r1")
    activate(cluster, db, first, None)
    second = stage(cluster, db, "r2")
    activate(cluster, db, second, first)
    before = release_state(cluster, db)

    receipt = rollback(cluster, db, first, second)

    after = release_state(cluster, db)
    assert receipt["action"] == "rollback" and receipt["prior_release_id"] == second
    assert statuses(cluster, db) == {first: "active", second: "rolled_back"}
    assert history(cluster, db)[-1] == (second, first, "rollback", "owner rollback 7")
    for table, rows in before.items():
        if table not in {"season_releases", "season_release_history"}:
            assert after[table] == rows, table


@pytest.mark.parametrize(
    "overrides,user",
    [
        ({"owner_authorized": False}, OWNER),
        ({"decision_ref": "   "}, OWNER),
        ({}, PIPELINE["preview"]),
        ({}, WEB_LOGIN),
    ],
    ids=["not-authorized", "blank-decision", "pipeline-login", "web-login"],
)
def test_rollback_without_owner_inputs_refused_without_writes(
    cluster, db, overrides, user
):
    first = stage(cluster, db, "r1")
    activate(cluster, db, first, None)
    second = stage(cluster, db, "r2")
    activate(cluster, db, second, first)
    before = release_state(cluster, db)

    with pytest.raises(release.SeasonReleaseError, match="owner"):
        rollback(cluster, db, first, second, user=user, **overrides)

    assert release_state(cluster, db) == before


def test_rollback_from_set_role_session_refused(cluster, db):
    first = stage(cluster, db, "r1")
    activate(cluster, db, first, None)
    second = stage(cluster, db, "r2")
    activate(cluster, db, second, first)

    with cluster.connect(db) as conn:
        conn.execute(f"SET ROLE {OWNER}")
        with pytest.raises(release.SeasonReleaseError, match="owner/migrator login"):
            release.rollback_release(
                conn,
                environment="preview",
                season=SEASON,
                release_id=first,
                expected_previous_release_id=second,
                owner_authorized=True,
                decision_ref="owner rollback 7",
            )


def test_rollback_to_never_activated_release_refused_without_writes(cluster, db):
    first = stage(cluster, db, "r1")
    activate(cluster, db, first, None)
    staged = stage(cluster, db, "r2")
    before = release_state(cluster, db)

    with pytest.raises(release.SeasonReleaseError, match="invalid activation status"):
        rollback(cluster, db, staged, first)

    assert release_state(cluster, db) == before


def test_rollback_when_no_release_is_active_refused_without_writes(cluster, db):
    first = stage(cluster, db, "r1")
    activate(cluster, db, first, None)
    second = stage(cluster, db, "r2")
    activate(cluster, db, second, first)
    with cluster.connect(db, OWNER, autocommit=True) as conn:
        conn.execute(
            "UPDATE season_releases SET status = 'superseded' WHERE release_id = %s",
            (second,),
        )
    before = release_state(cluster, db)

    with pytest.raises(release.SeasonReleaseError, match="requires an active release"):
        rollback(cluster, db, first, None)

    assert release_state(cluster, db) == before


def test_rollback_with_stale_expected_active_refused_without_writes(cluster, db):
    first = stage(cluster, db, "r1")
    activate(cluster, db, first, None)
    second = stage(cluster, db, "r2")
    activate(cluster, db, second, first)
    rollback(cluster, db, first, second)
    before = release_state(cluster, db)

    with pytest.raises(release.SeasonReleaseError, match="changed since review"):
        rollback(cluster, db, second, second)

    assert release_state(cluster, db) == before


def preview_connection(
    cluster, dbname, *, server_read_only=True, client_read_only=True
):
    """Preview login opened like ``run_season.py`` (options + psycopg flag)."""
    options = "-c default_transaction_read_only=on" if server_read_only else ""
    conn = psycopg.connect(
        cluster.conninfo(dbname, PIPELINE["preview"]), options=options
    )
    conn.read_only = client_read_only
    return conn


def test_production_activation_with_read_only_preview_rehearsal_succeeds(cluster, db):
    rehearsal = stage(cluster, db, "r1")
    activate(cluster, db, rehearsal, None)
    candidate_id = stage(cluster, db, "r1", environment="production")

    with preview_connection(cluster, db) as preview:
        receipt = activate(
            cluster,
            db,
            candidate_id,
            None,
            environment="production",
            preview_conn=preview,
        )

    assert receipt["release_id"] == release_id_of("r1", "production")
    assert statuses(cluster, db)[candidate_id] == "active"


@pytest.mark.parametrize(
    "server_read_only,client_read_only,pending",
    [
        (False, False, None),
        (False, True, None),
        (True, False, "SET TRANSACTION READ WRITE"),
    ],
    ids=["read-write", "client-flag-only", "pending-read-write-transaction"],
)
def test_production_activation_with_writable_preview_connection_refused(
    cluster, db, server_read_only, client_read_only, pending
):
    rehearsal = stage(cluster, db, "r1")
    activate(cluster, db, rehearsal, None)
    candidate_id = stage(cluster, db, "r1", environment="production")
    before = release_state(cluster, db)

    with preview_connection(
        cluster,
        db,
        server_read_only=server_read_only,
        client_read_only=client_read_only,
    ) as preview:
        if pending:
            preview.execute(pending)
        with pytest.raises(release.SeasonReleaseError, match="read-only Preview"):
            activate(
                cluster,
                db,
                candidate_id,
                None,
                environment="production",
                preview_conn=preview,
            )

    assert release_state(cluster, db) == before


def test_production_activation_with_run_season_preview_connection_succeeds(cluster, db):
    rehearsal = stage(cluster, db, "r1")
    activate(cluster, db, rehearsal, None)
    candidate_id = stage(cluster, db, "r1", environment="production")

    with psycopg.connect(
        cluster.conninfo(db, PIPELINE["preview"]),
        options="-c default_transaction_read_only=on",
    ) as preview:
        receipt = activate(
            cluster,
            db,
            candidate_id,
            None,
            environment="production",
            preview_conn=preview,
        )

    assert receipt["release_id"] == candidate_id


def test_production_activation_without_matching_preview_refused(cluster, db):
    rehearsal = stage(cluster, db, "r1", edit_payload=rename_venue)
    activate(cluster, db, rehearsal, None)
    candidate_id = stage(cluster, db, "r1", environment="production")
    before = release_state(cluster, db)

    with preview_connection(cluster, db) as preview:
        with pytest.raises(release.SeasonReleaseError, match="Preview activation"):
            activate(
                cluster,
                db,
                candidate_id,
                None,
                environment="production",
                preview_conn=preview,
            )

    assert release_state(cluster, db) == before


# --------------------------------------------------------------------------
# B2. Environment-free payloads, enforced links, verified reports
# --------------------------------------------------------------------------


def _release_row(cluster, dbname, release_id) -> dict:
    with cluster.connect(dbname, OWNER, autocommit=True) as conn:
        checks, run_sha, verify_sha = conn.execute(
            "SELECT projection_checks, run_manifest_sha256, verification_sha256"
            " FROM season_releases WHERE release_id = %s",
            (release_id,),
        ).fetchone()
        environments = [
            row[0]
            for row in conn.execute(
                "SELECT environment FROM season_release_matchup_data_publications"
                " WHERE release_id = %s",
                (release_id,),
            )
        ]
    return {
        "projection_checks": checks,
        "run_manifest_sha256": run_sha,
        "verification_sha256": verify_sha,
        "environments": environments,
    }


def test_same_payload_bytes_stage_identically_in_preview_and_production(cluster, db):
    payload = candidate("r1")
    pinned = json.loads(payload["manifest_raw"])["output_refs"]["serving_projections"]

    preview_id = stage(cluster, db, "r1", payload=payload)
    preview_receipt = activate(cluster, db, preview_id, None)
    production_id = stage(cluster, db, "r1", "production", payload=payload)
    with preview_connection(cluster, db) as preview:
        production_receipt = activate(
            cluster, db, production_id, None, "production", preview_conn=preview
        )

    preview_row = _release_row(cluster, db, preview_id)
    production_row = _release_row(cluster, db, production_id)
    assert hashlib.sha256(payload["projection_raw"]).hexdigest() == pinned["sha256"]
    assert preview_row["projection_checks"] == production_row["projection_checks"]
    assert preview_row["projection_checks"] == {
        base: release.projection_check(rows) for base, rows in views("r1").items()
    }
    assert preview_receipt["readback_sha256"] == production_receipt["readback_sha256"]
    assert preview_row["run_manifest_sha256"] == production_row["run_manifest_sha256"]
    assert preview_row["environments"] == ["preview"]
    assert production_row["environments"] == ["production"]
    assert statuses(cluster, db)[production_id] == "active"


@pytest.mark.parametrize(
    "table,column,value",
    [
        ("matchup_data_publications", "environment", "preview"),
        ("games", "environment", "preview"),
        ("system_stats", "release_id", "preview-r1"),
    ],
)
def test_payload_row_with_server_column_refused_without_writes(
    cluster, db, table, column, value
):
    payload = candidate(
        "r1", edit_payload=lambda p: p[table][0].update({column: value})
    )
    before = release_state(cluster, db)

    with pytest.raises(release.SeasonReleaseError, match="server-filled column"):
        stage(cluster, db, "r1", payload=payload)

    assert release_state(cluster, db) == before


def test_activation_refuses_projection_row_of_another_environment(cluster, db):
    release_id = stage(cluster, db, "r1")
    with cluster.connect(db, OWNER, autocommit=True) as conn:
        row = views("r1")["matchup_data_publications"][0]
        conn.execute(
            "INSERT INTO season_release_matchup_data_publications (release_id,"
            " environment, publication_id, season, lineage, rating_manifest_sha256,"
            " rating_manifest_uri, measurement_manifest_sha256,"
            " measurement_manifest_uri, observations_records_sha, as_of_weeks,"
            " payload_sha256) VALUES (%s, 'production', 'foreign', %s, %s, %s, %s,"
            " %s, %s, %s, %s, %s)",
            (
                release_id,
                SEASON,
                row["lineage"],
                row["rating_manifest_sha256"],
                row["rating_manifest_uri"],
                row["measurement_manifest_sha256"],
                row["measurement_manifest_uri"],
                row["observations_records_sha"],
                row["as_of_weeks"],
                row["payload_sha256"],
            ),
        )
    before = release_state(cluster, db)

    with pytest.raises(
        release.SeasonReleaseError, match="projection rows of another environment"
    ):
        activate(cluster, db, release_id, None)

    assert release_state(cluster, db) == before


def _broken_link(fault: str) -> dict:
    payload = payload_for("r1")
    if fault == "result-unknown-game":
        payload["game_results"].append({**payload["game_results"][0], "game_id": 999})
    elif fault == "selection-quote-of-other-game":
        # q4 quotes game 2; the selection is for game 1.
        payload["prediction_market_selections"][0]["quote_id"] = "q4"
    elif fault == "grade-without-prediction":
        # Game 5 is scheduled (Week 3) but never predicted.
        payload["prediction_grades"].append(
            {**payload["prediction_grades"][0], "game_id": 5}
        )
    elif fault == "component-missing-rating-snapshot":
        payload["team_rating_components"][0]["v5_snapshot_id"] = "snap-missing"
    elif fault == "snapshot-quote-missing-quote":
        payload["market_snapshot_quotes"].append(
            {"snapshot_id": "s1", "quote_id": "quote-missing", "target": "total"}
        )
    elif fault == "prediction-missing-market-snapshot":
        payload["predictions"][0]["market_snapshot_id"] = "msnap-missing"
    return payload


LINK_FAULTS = {
    "result-unknown-game": "season_release_game_results_game_fk",
    "selection-quote-of-other-game": "season_release_selections_quote_game_fk",
    "grade-without-prediction": "season_release_prediction_grades_prediction_fk",
    "component-missing-rating-snapshot": (
        "season_release_team_rating_components_snapshot_fk"
    ),
    "snapshot-quote-missing-quote": "season_release_market_snapshot_quotes_quote_fk",
    "prediction-missing-market-snapshot": "season_release_predictions_snapshot_fk",
}


@pytest.mark.parametrize("fault,constraint", LINK_FAULTS.items())
def test_database_links_refuse_broken_payload_at_stage_without_writes(
    cluster, db, monkeypatch, fake_verification, fault, constraint
):
    # The real checks refuse these payloads first; disable them and the payload
    # scope check so the 0025 foreign keys alone decide.
    monkeypatch.setattr(release, "validate_candidate", lambda *args, **kwargs: None)
    monkeypatch.setattr(release, "_check_projection_scope", lambda *args: None)
    payload = _broken_link(fault)
    before = release_state(cluster, db)

    with pytest.raises(release.SeasonReleaseError, match=constraint):
        stage(
            cluster,
            db,
            "r1",
            payload=seal("r1", payload, reported_payload=payload_for("r1")),
        )

    assert release_state(cluster, db) == before


def test_release_links_are_deferred_composite_foreign_keys(cluster, migrated_db):
    with cluster.connect(migrated_db, OWNER, autocommit=True) as conn:
        links = conn.execute(
            "SELECT conrelid::regclass::text, conname, condeferrable, condeferred,"
            " confmatchtype FROM pg_constraint WHERE contype = 'f'"
            " AND confrelid::regclass::text LIKE 'season\\_release\\_%'"
            " AND conkey @> ARRAY[(SELECT attnum FROM pg_attribute"
            "  WHERE attrelid = conrelid AND attname = 'release_id')]"
        ).fetchall()
        unique = conn.execute(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint"
            " WHERE conname = 'season_release_market_quotes_game_key'"
        ).fetchone()

    assert len(links) == 16
    assert all(link[2:] == (True, True, "s") for link in links), links
    assert unique == ("UNIQUE (release_id, quote_id, game_id)",)


def test_full_schedule_with_unpredicted_games_stages(cluster, db):
    def later_games(payload):
        game = next(g for g in payload["games"] if g["week"] == 3)
        payload["games"] += [
            {**game, "game_id": 6, "week": 4},
            {**game, "game_id": 7, "week": 5},
        ]

    staged = stage(cluster, db, "r1", edit_payload=later_games)
    receipt = activate(cluster, db, staged, None)

    state = release_state(cluster, db)
    assert receipt["release_id"] == staged
    assert len(state["season_release_games"]) == 7
    assert len(state["season_release_predictions"]) == 4


def test_prediction_for_game_outside_schedule_refused_without_writes(cluster, db):
    def outside(payload):
        payload["predictions"].append({**payload["predictions"][0], "game_id": 999})

    before = release_state(cluster, db)

    with pytest.raises(release.SeasonReleaseError, match="outside the release"):
        stage(cluster, db, "r1", edit_payload=outside)

    assert release_state(cluster, db) == before


def _extra_check(report):
    report["checks"]["self_declared"] = {
        "passed": True,
        "observed": {},
        "source": "projection",
    }


def _bare_boolean(report):
    report["checks"]["market_links"] = True


def _forged_observation(report):
    report["checks"]["market_links"]["observed"] = {"games": 99}


@pytest.mark.parametrize(
    "forgery",
    ["rederived-failure", "extra-check", "missing-check", "bare-boolean", "observed"],
)
def test_forged_verification_report_refused_without_writes(cluster, db, forgery):
    edit = {
        "extra-check": _extra_check,
        "missing-check": lambda report: report["checks"].pop("market_links"),
        "bare-boolean": _bare_boolean,
        "observed": _forged_observation,
    }.get(forgery)
    if forgery == "rederived-failure":
        # An honest report of the original payload, sealed with changed bytes.
        changed = payload_for("r1")
        changed["prediction_market_selections"][0]["price"] = -105.0
        payload = seal("r1", changed, reported_payload=payload_for("r1"))
    else:
        payload = candidate("r1", edit_report=edit)
    before = release_state(cluster, db)

    with pytest.raises(release.SeasonReleaseError, match="check"):
        stage(cluster, db, "r1", payload=payload)

    assert release_state(cluster, db) == before


def test_verification_module_rejection_refuses_stage(cluster, db, monkeypatch):
    def reject(report, *, projections, manifest=None):
        raise ValueError("row_counts do not match projections")

    monkeypatch.setattr(verifier, "validate_report", reject)
    before = release_state(cluster, db)

    with pytest.raises(release.SeasonReleaseError, match="row_counts"):
        stage(cluster, db, "r1")

    assert release_state(cluster, db) == before


# --------------------------------------------------------------------------
# C. Concurrency
# --------------------------------------------------------------------------


def _race(workers):
    """Run callables on threads released together by a barrier."""
    barrier = threading.Barrier(len(workers))
    outcomes: list = [None] * len(workers)

    def run(index, work):
        try:
            outcomes[index] = ("ok", work(barrier))
        except Exception as error:  # noqa: BLE001 - outcome is asserted by caller
            outcomes[index] = ("error", error)

    threads = [
        threading.Thread(target=run, args=(i, work)) for i, work in enumerate(workers)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert not any(thread.is_alive() for thread in threads), "race deadlocked"
    return outcomes


def _activation_worker(cluster, dbname, release_id):
    def work(barrier):
        with cluster.connect(dbname, PIPELINE["preview"]) as conn:
            conn.execute("SELECT 1")
            conn.rollback()
            barrier.wait()
            receipt = release.activate_release(
                conn,
                environment="preview",
                season=SEASON,
                release_id=release_id,
                expected_previous_release_id=None,
            )
            conn.commit()
            return receipt

    return work


@pytest.mark.parametrize("attempt", range(5))
def test_concurrent_initial_activations_exactly_one_wins(cluster, db, attempt):
    first = stage(cluster, db, "r1")
    second = stage(cluster, db, "r2")

    outcomes = _race(
        [
            _activation_worker(cluster, db, first),
            _activation_worker(cluster, db, second),
        ]
    )

    winners = [value["release_id"] for kind, value in outcomes if kind == "ok"]
    losers = [value for kind, value in outcomes if kind == "error"]
    assert len(winners) == 1 and len(losers) == 1, outcomes
    assert isinstance(losers[0], release.SeasonReleaseError)
    assert "changed since review" in str(losers[0])
    loser = second if winners[0] == first else first
    assert statuses(cluster, db) == {winners[0]: "active", loser: "staged"}
    assert history(cluster, db) == [(None, winners[0], "activate", "owner decision 1")]


def test_activation_blocked_by_open_activation_then_refused(cluster, db):
    first = stage(cluster, db, "r1")
    second = stage(cluster, db, "r2")
    holder = cluster.connect(db, PIPELINE["preview"])
    try:
        release.activate_release(
            holder,
            environment="preview",
            season=SEASON,
            release_id=first,
            expected_previous_release_id=None,
        )
        result: dict = {}

        def contender():
            try:
                activate(cluster, db, second, None)
            except Exception as error:  # noqa: BLE001 - asserted below
                result["error"] = error

        thread = threading.Thread(target=contender)
        thread.start()
        with cluster.connect(db, OWNER, autocommit=True) as observer:
            deadline = time.monotonic() + 30
            waiting = 0
            while waiting == 0 and time.monotonic() < deadline:
                waiting = observer.execute(
                    "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory'"
                    " AND NOT granted"
                ).fetchone()[0]
        assert waiting == 1, "contender never blocked on the release lock"
        holder.commit()
        thread.join(timeout=30)
    finally:
        holder.close()

    assert isinstance(result.get("error"), release.SeasonReleaseError)
    assert statuses(cluster, db) == {first: "active", second: "staged"}
    assert len(history(cluster, db)) == 1


def test_concurrent_identical_stages_create_one_release(cluster, db):
    def worker(barrier):
        with cluster.connect(db, PIPELINE["preview"]) as conn:
            conn.execute("SELECT 1")
            conn.rollback()
            barrier.wait()
            sealed = candidate("r1")
            staged = release.stage_release(
                conn,
                run_manifest_uri=manifest_uri(sealed),
                environment="preview",
                **sealed,
            )
            conn.commit()
            return staged

    outcomes = _race([worker, worker, worker])

    assert [kind for kind, _ in outcomes] == ["ok"] * 3, outcomes
    assert {value for _, value in outcomes} == {release_id_of("r1")}
    state = release_state(cluster, db)
    assert len(state["season_releases"]) == 1
    assert len(state["season_release_games"]) == 5
    assert len(state["season_release_predictions"]) == 4
    assert len(state["prediction_runs"]) == 3


# --------------------------------------------------------------------------
# D. Web read contract
# --------------------------------------------------------------------------


def _web_script(script: str, spec: dict) -> dict:
    """Run a web module snippet (``--experimental-strip-types``) and parse its JSON."""
    if not WEB_AVAILABLE:
        if os.environ.get("CI"):
            pytest.fail("web dependencies are required in CI; run npm ci --prefix web")
        pytest.skip("web dependencies are not installed; run npm ci --prefix web")
    result = subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script],
        cwd=WEB_DIR,
        env={**os.environ, "WEB_SPEC": json.dumps(spec)},
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


_WEB_PROJECTIONS = """
import {
  CHART_SET_KEYS, CHART_SET_PROJECTIONS, RECORDED_PROJECTION_SETS, RELEASE_PROJECTIONS,
  TEAM_RESUME_PROJECTION,
} from "./src/lib/season-release-query.ts";
console.log(JSON.stringify({
  core: RELEASE_PROJECTIONS, charts: CHART_SET_PROJECTIONS, keys: CHART_SET_KEYS,
  optional: [TEAM_RESUME_PROJECTION], recorded: RECORDED_PROJECTION_SETS,
}));
"""


def web_projections() -> dict:
    """The web's core relations and, per chart set, its relations and recorded keys."""
    return _web_script(_WEB_PROJECTIONS, {})


def web_release_projections() -> list[str]:
    """The core relations every active release must expose."""
    return web_projections()["core"]


# The real resolver, run with an ``execute`` that replays rows Python read from
# Postgres; an unanswered query stops the run so Python can execute it next.
_WEB_CONTEXT = """
import { PgDialect } from "drizzle-orm/pg-core";
import { loadReleaseContext } from "./src/lib/season-release-context.ts";
const spec = JSON.parse(process.env.WEB_SPEC);
const dialect = new PgDialect();
const queries = [];
const pending = new Error("pending");
let context;
try {
  context = await loadReleaseContext(async (query) => {
    queries.push(dialect.sqlToQuery(query));
    if (queries.length > spec.results.length) throw pending;
    return { rows: spec.results[queries.length - 1] };
  }, spec.season, spec.environment);
} catch (error) {
  if (error !== pending) throw error;
  context = "pending";
}
console.log(JSON.stringify({ queries, context }));
"""


def _pg_query(query: dict) -> tuple[str, dict]:
    statement = re.sub(r"\$(\d+)", r"%(p\1)s", query["sql"])
    params = {f"p{i}": value for i, value in enumerate(query["params"], start=1)}
    return statement, params


def _json_rows(cursor) -> list[dict]:
    names = [column.name for column in cursor.description]
    return [
        {
            name: value.isoformat() if hasattr(value, "isoformat") else value
            for name, value in zip(names, row, strict=True)
        }
        for row in cursor.fetchall()
    ]


def web_release_context(conn, environment="preview") -> tuple[dict | None, list]:
    """``loadReleaseContext`` of the web app against this database.

    Returns the resolved context (``None`` when there is no active release) and
    the SQL statements it issued.
    """
    results: list[list[dict]] = []
    while True:
        spec = {"results": results, "season": SEASON, "environment": environment}
        run = _web_script(_WEB_CONTEXT, spec)
        if run["context"] != "pending":
            return run["context"], run["queries"]
        results.append(_json_rows(conn.execute(*_pg_query(run["queries"][-1]))))


def chart_set(conn, environment="preview") -> str | None:
    """The web resolver's chart capability for the active release."""
    context, _ = web_release_context(conn, environment)
    return context and context["chartSet"]


def _created(path: Path) -> set[str]:
    return set(
        re.findall(r"CREATE TABLE IF NOT EXISTS (season_release_\w+)", path.read_text())
    )


def test_release_projection_list_matches_migration_and_release_module():
    web = web_projections()
    core = web["core"]

    assert len(core) == len(set(core))
    assert set(core) == _created(MIGRATION_0025) - CONTROL_TABLES
    assert set(core) == {f"season_release_{b}" for b in PROJECTION_SETS["core_v1"]}
    assert set(web["charts"]["charts_v1"]) == _created(MIGRATION_0026)
    assert set(web["charts"]["charts_v2"]) == _created(MIGRATION_0026) | _created(
        MIGRATION_0027
    )
    # The résumé table is the one optional relation: read on its own, absent from the
    # core and chart lists so releases staged without it still load.
    assert web["optional"] == ["season_release_team_resume"]
    assert not set(web["optional"]) & (set(core) | set(web["charts"]["charts_v2"]))
    assert set(core) | set(web["charts"]["charts_v2"]) | set(web["optional"]) == {
        f"season_release_{b}" for b in release.PROJECTION_KEYS
    }
    # The web recognizes a set exactly by the keys staging records for it.
    for name in ("charts_v1", "charts_v2"):
        assert web["keys"][name] == sorted(PROJECTION_SETS[name])
    for name, recorded in web["recorded"].items():
        assert recorded["keys"] == sorted(PROJECTION_SETS[name]), name
    assert web["recorded"]["resume_v1"]["chartSet"] == "charts_v2"


def test_web_existence_probe_false_before_0025(cluster, pre0025_db):
    with cluster.connect(pre0025_db, WEB_LOGIN, autocommit=True) as conn:
        context, queries = web_release_context(conn)

    assert context is None and len(queries) == 1


def test_web_active_query_returns_no_row_without_activation(cluster, db):
    stage(cluster, db, "r1")

    with cluster.connect(db, WEB_LOGIN, autocommit=True) as conn:
        context, queries = web_release_context(conn)

    assert context is None and len(queries) == 2


def test_web_active_query_returns_one_row_and_no_missing_projections(cluster, db):
    first = stage(cluster, db, "r1")
    activate(cluster, db, first, None)
    second = stage(cluster, db, "r2")
    activate(cluster, db, second, first)

    with cluster.connect(db, WEB_LOGIN, autocommit=True) as conn:
        context, queries = web_release_context(conn)
        other, _ = web_release_context(conn, "production")

    assert len(queries) == 3  # existence, active release, missing projections
    assert (
        context["releaseId"],
        context["environment"],
        context["season"],
        context["activeWeek"],
        context["chartSet"],
    ) == (second, "preview", SEASON, ACTIVE_WEEK, "charts_v2")
    assert context["activatedAt"]
    assert other is None


def test_web_missing_projection_query_with_one_array_parameter_succeeds(cluster, db):
    """season-release.test.ts pins drizzle's rendering to one ``$1::text[]``."""
    first = stage(cluster, db, "r1")
    activate(cluster, db, first, None)
    names = web_release_projections()

    with cluster.connect(db, WEB_LOGIN, autocommit=True) as conn:
        _, queries = web_release_context(conn)
        statement, params = _pg_query(queries[2])
        missing = conn.execute(statement, params).fetchall()
        absent = conn.execute(statement, {"p1": [*names, "season_release_absent"]})

        assert params == {"p1": names}
        assert missing == []
        assert absent.fetchall() == [("season_release_absent",)]


# --------------------------------------------------------------------------
# E. End-to-end prepare, stage, activate, rollback
# --------------------------------------------------------------------------


def test_season_prepare_stage_activate_rollback_e2e(cluster, make_db, tmp_path):
    """End-to-end test of the full lifecycle against real PostgreSQL:
    1. Real preparation via runner.prepare / build_season writes sealed artifacts.
    2. Negative checks: corrupted outputs refused at sealing; corrupted payload refused at staging.
    3. Candidate staged and activated in Preview.
    4. Identical candidate staged in Production and activated with read-only Preview proof.
    5. Web reader queries (loadReleaseContext) against Production succeed and find all projections.
    6. Second candidate staged and activated, superseding the first.
    7. Owner rolls back Production to the first candidate; all projection rows preserved.
    """
    db_name = make_db("tpl_resume")

    # 1. Real preparation
    s1_dir = tmp_path / "s1"
    s1_dir.mkdir()
    s1 = build_season(s1_dir)
    manifest_path1 = s1_dir / s1["identity"]["run_id"] / "run-manifest.json"
    manifest_raw1 = manifest_path1.read_bytes()
    manifest1 = json.loads(manifest_raw1)
    pinned1 = manifest1["output_refs"]["serving_projections"]["sha256"]

    # 2a. Negative: corrupted output refused at sealing
    serving_path1 = Path(manifest1["output_refs"]["serving_projections"]["uri"])
    serving_bytes1 = serving_path1.read_bytes()
    try:
        serving_path1.write_bytes(serving_bytes1 + b" ")
        with pytest.raises(ValueError, match="checksum"):
            _sealed_candidate(manifest1, pinned1)
    finally:
        serving_path1.write_bytes(serving_bytes1)

    with pytest.raises(ValueError, match="pinned projection payload checksum"):
        _sealed_candidate(manifest1, "0" * 64)

    proj1, verif1 = _sealed_candidate(manifest1, pinned1)
    rev1 = Path(manifest1["output_refs"]["revision_manifest"]["uri"]).read_bytes()

    # Install owner policy for s1 in preview and production
    with cluster.connect(db_name, OWNER, autocommit=True) as conn:
        for env in ("preview", "production"):
            conn.execute(
                """
                INSERT INTO season_release_policies (
                    environment, season, model_manifest_sha256,
                    workflow_version, grading_policy_sha256, enabled, decision_ref
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    env,
                    SEASON,
                    manifest1["model_manifest_ref"]["sha256"],
                    manifest1["workflow_version"],
                    manifest1["grading_policy_sha256"],
                    True,
                    "e2e owner policy",
                ),
            )

    # 2b. Negative: corrupted payload row refused at staging without writes
    corrupted_payload = json.loads(proj1.decode())
    corrupted_payload["system_stats"][0]["unexpected_column"] = 999
    corrupted_raw = canonical(corrupted_payload)
    before_state = release_state(cluster, db_name)
    with cluster.connect(db_name, PIPELINE["preview"]) as conn:
        with pytest.raises(release.SeasonReleaseError):
            release.stage_release(
                conn,
                manifest_raw=manifest_raw1,
                run_manifest_uri=manifest1["run_manifest_logical_uri"],
                verification_raw=verif1,
                projection_raw=corrupted_raw,
                revision_raw=rev1,
                environment="preview",
            )
    assert release_state(cluster, db_name) == before_state

    # 3. Stage and activate s1 in Preview
    with cluster.connect(db_name, PIPELINE["preview"]) as conn:
        prev_id1 = release.stage_release(
            conn,
            manifest_raw=manifest_raw1,
            run_manifest_uri=manifest1["run_manifest_logical_uri"],
            verification_raw=verif1,
            projection_raw=proj1,
            revision_raw=rev1,
            environment="preview",
        )
        prev_receipt1 = release.activate_release(
            conn,
            environment="preview",
            season=SEASON,
            release_id=prev_id1,
            expected_previous_release_id=None,
        )
        conn.commit()
    assert prev_receipt1["release_id"] == prev_id1

    # 4. Stage identical bytes in Production and activate with Preview read-only connection
    with cluster.connect(db_name, PIPELINE["production"]) as conn:
        prod_id1 = release.stage_release(
            conn,
            manifest_raw=manifest_raw1,
            run_manifest_uri=manifest1["run_manifest_logical_uri"],
            verification_raw=verif1,
            projection_raw=proj1,
            revision_raw=rev1,
            environment="production",
        )
        conn.commit()

    with psycopg.connect(
        cluster.conninfo(db_name, PIPELINE["preview"]),
        options="-c default_transaction_read_only=on",
    ) as preview:
        preview.read_only = True
        with cluster.connect(db_name, PIPELINE["production"]) as conn:
            prod_receipt1 = release.activate_release(
                conn,
                environment="production",
                season=SEASON,
                release_id=prod_id1,
                expected_previous_release_id=None,
                preview_conn=preview,
            )
            conn.commit()
    assert prod_receipt1["release_id"] == prod_id1

    # 5. Web reads against Production. With the web modules installed, the real
    # resolver finds every projection and a charts_v2 release.
    with cluster.connect(db_name, WEB_LOGIN, autocommit=True) as conn:
        assert conn.execute(ACTIVE_SQL, ("production", SEASON)).fetchall() == [
            (prod_id1, ACTIVE_WEEK)
        ]
        if WEB_AVAILABLE:
            context, queries = web_release_context(conn, "production")
            assert len(queries) == 3  # existence, active, no missing projections
            assert context["releaseId"] == prod_id1
            assert context["activeWeek"] == ACTIVE_WEEK
            assert context["chartSet"] == "charts_v2"

    # 6. Prepare, stage, activate second candidate (s2)
    s2_dir = tmp_path / "s2"
    s2_dir.mkdir()

    def edit_venue(tables):
        tables["venues"].loc[0, "city"] = "Alt City"

    s2 = build_season(s2_dir, edit=edit_venue)
    manifest_path2 = s2_dir / s2["identity"]["run_id"] / "run-manifest.json"
    manifest_raw2 = manifest_path2.read_bytes()
    manifest2 = json.loads(manifest_raw2)
    pinned2 = manifest2["output_refs"]["serving_projections"]["sha256"]
    proj2, verif2 = _sealed_candidate(manifest2, pinned2)
    rev2 = Path(manifest2["output_refs"]["revision_manifest"]["uri"]).read_bytes()

    with cluster.connect(db_name, PIPELINE["preview"]) as conn:
        prev_id2 = release.stage_release(
            conn,
            manifest_raw=manifest_raw2,
            run_manifest_uri=manifest2["run_manifest_logical_uri"],
            verification_raw=verif2,
            projection_raw=proj2,
            revision_raw=rev2,
            environment="preview",
        )
        release.activate_release(
            conn,
            environment="preview",
            season=SEASON,
            release_id=prev_id2,
            expected_previous_release_id=prev_id1,
        )
        conn.commit()

    with cluster.connect(db_name, PIPELINE["production"]) as conn:
        prod_id2 = release.stage_release(
            conn,
            manifest_raw=manifest_raw2,
            run_manifest_uri=manifest2["run_manifest_logical_uri"],
            verification_raw=verif2,
            projection_raw=proj2,
            revision_raw=rev2,
            environment="production",
        )
        conn.commit()

    with psycopg.connect(
        cluster.conninfo(db_name, PIPELINE["preview"]),
        options="-c default_transaction_read_only=on",
    ) as preview:
        preview.read_only = True
        with cluster.connect(db_name, PIPELINE["production"]) as conn:
            release.activate_release(
                conn,
                environment="production",
                season=SEASON,
                release_id=prod_id2,
                expected_previous_release_id=prod_id1,
                preview_conn=preview,
            )
            conn.commit()

    assert statuses(cluster, db_name) == {
        prev_id1: "superseded",
        prev_id2: "active",
        prod_id1: "superseded",
        prod_id2: "active",
    }

    # 7. Owner rolls back Production to the first candidate
    state_before_rollback = release_state(cluster, db_name)
    with cluster.connect(db_name, OWNER) as conn:
        rollback_receipt = release.rollback_release(
            conn,
            environment="production",
            season=SEASON,
            release_id=prod_id1,
            expected_previous_release_id=prod_id2,
            owner_authorized=True,
            decision_ref="e2e owner rollback decision",
        )
        conn.commit()

    state_after_rollback = release_state(cluster, db_name)
    assert rollback_receipt["action"] == "rollback"
    assert rollback_receipt["release_id"] == prod_id1
    assert rollback_receipt["prior_release_id"] == prod_id2
    assert statuses(cluster, db_name) == {
        prev_id1: "superseded",
        prev_id2: "active",
        prod_id1: "active",
        prod_id2: "rolled_back",
    }
    assert history(cluster, db_name)[-1] == (
        prod_id2,
        prod_id1,
        "rollback",
        "e2e owner rollback decision",
    )

    # All projection rows are preserved without deletion
    for table, rows in state_before_rollback.items():
        if table not in {"season_releases", "season_release_history"}:
            assert state_after_rollback[table] == rows, (
                f"Table {table} rows changed during rollback"
            )

    # Web reads see prod_id1 as active again
    with cluster.connect(db_name, WEB_LOGIN, autocommit=True) as conn:
        active_after = conn.execute(ACTIVE_SQL, ("production", SEASON)).fetchall()
        if WEB_AVAILABLE:
            assert web_release_context(conn, "production")[0]["releaseId"] == prod_id1
    assert active_after == [(prod_id1, ACTIVE_WEEK)]


# --------------------------------------------------------------------------
# F. Chart tables (migration 0026) and projection-set compatibility
# --------------------------------------------------------------------------

CHART_TABLES = ("team_season_roster", "team_game_stats", "team_adjusted_epa")
_WEB_QUERY = """
import { drizzle } from "drizzle-orm/neon-http";
import * as schema from "./src/lib/schema.ts";
import { seasonReleaseDb } from "./src/lib/season-release-query.ts";
const spec = JSON.parse(process.env.WEB_SPEC);
const db = drizzle.mock({ schema });
const table = schema[spec.table];
const columns = Object.fromEntries(spec.columns.map((name) => [name, table[name]]));
const query = seasonReleaseDb(db, spec.releaseId, { chartSet: spec.chartSet })
  .select(columns).from(table).toSQL();
console.log(JSON.stringify(query));
"""


def web_query_rows(conn, release_id, table, columns, *, chart_set):
    """Run the SQL the web app generates for ``select(columns).from(table)``.

    The statement comes from season-release-query.ts through drizzle itself, so it
    is exactly the release-scoped CTE query a page would execute for ``chart_set``.
    """
    spec = {
        "releaseId": release_id,
        "chartSet": chart_set,
        "table": table,
        "columns": columns,
    }
    query = _web_script(_WEB_QUERY, spec)
    return conn.execute(*_pg_query(query)).fetchall()


def sealed_retained(label, projection_set, **kwargs):
    """A candidate in the shape releases of an older set had (core_v1 or charts_v1)."""
    tables = set(PROJECTION_SETS[projection_set])
    projection_names, prepare_names = verifier.REQUIRED_CHECK_SETS[projection_set]
    full = payload_for(label)
    if edit := kwargs.get("edit_payload"):
        edit(full)

    def trim(report):
        for key in ("projection_checks", "row_counts"):
            report[key] = {k: v for k, v in report[key].items() if k in tables}
        passing = _passing(None)
        report["checks"] = {
            name: passing.get(name, entry)
            for name, entry in report["checks"].items()
            if name in projection_names | prepare_names
        }

    older = {k: v for k, v in full.items() if k in tables | {"prediction_runs"}}
    return seal(label, older, reported_payload=full, edit_report=trim)


def patch_retained_staging(monkeypatch, projection_set):
    """Stage like the code of an older set did (only to create retained releases)."""
    order = PROJECTION_SETS[projection_set]
    projection_names, prepare_names = verifier.REQUIRED_CHECK_SETS[projection_set]
    monkeypatch.setattr(release, "PROJECTION_ORDER", order)
    monkeypatch.setattr(
        release,
        "PROJECTION_KEYS",
        {k: v for k, v in release.PROJECTION_KEYS.items() if k in order},
    )
    monkeypatch.setattr(release, "_require_staging_set", lambda tables: None)
    monkeypatch.setattr(release, "_check_chart_scope", lambda *args: None)
    monkeypatch.setattr(release, "_check_resume_scope", lambda *args: None)
    monkeypatch.setattr(release, "_bind_yardage_evidence", lambda *args: None)
    monkeypatch.setattr(verifier, "REQUIRED_PROJECTION_CHECKS", projection_names)
    monkeypatch.setattr(verifier, "REQUIRED_PREPARE_CHECKS", prepare_names)
    monkeypatch.setattr(verifier, "derive_checks", lambda p, m: _passing(p))
    monkeypatch.setattr(verifier, "validate_report", lambda report, **kwargs: None)


def stage_retained(cluster, dbname, label, monkeypatch, projection_set, **kwargs):
    sealed = sealed_retained(label, projection_set, **kwargs)
    with monkeypatch.context() as patch:
        patch_retained_staging(patch, projection_set)
        return stage(cluster, dbname, label, payload=sealed)


def stage_retained_core_v1(cluster, dbname, label, monkeypatch, **kwargs):
    return stage_retained(cluster, dbname, label, monkeypatch, "core_v1", **kwargs)


def recorded_set(cluster, dbname, release_id) -> str:
    with cluster.connect(dbname, OWNER, autocommit=True) as conn:
        checks = conn.execute(
            "SELECT projection_checks FROM season_releases WHERE release_id = %s",
            (release_id,),
        ).fetchone()[0]
    return recognized_projection_set(checks)


_CATALOG = (
    "SELECT table_name || '.' || column_name || ':' || data_type || ':' || is_nullable"
    " FROM information_schema.columns WHERE table_name = ANY(%s)"
    " UNION ALL SELECT tgrelid::regclass || ':' || tgname FROM pg_trigger"
    "  WHERE NOT tgisinternal AND tgrelid::regclass::text LIKE 'season\\_release\\_team\\_%%'"
    " UNION ALL SELECT relname || ':' || coalesce(relacl::text, '') FROM pg_class"
    "  WHERE relname = ANY(%s) ORDER BY 1"
)


@pytest.mark.parametrize(
    "template, migration, tables",
    [
        ("tpl_0025", MIGRATION_0026, CHART_TABLES),
        ("tpl_0026", MIGRATION_0027, ("team_game_yardage",)),
    ],
    ids=["0026", "0027"],
)
def test_chart_tables_are_additive_and_migration_is_idempotent(
    cluster, make_db, template, migration, tables
):
    name = make_db(template)
    before = legacy_state(cluster, name)
    names = [*tables, *(f"season_release_{t}" for t in tables)]
    with cluster.connect(name, OWNER, autocommit=True) as conn:
        conn.execute(migration.read_text())
        first = conn.execute(_CATALOG, (names, names)).fetchall()
        conn.execute(migration.read_text())
        second = conn.execute(_CATALOG, (names, names)).fetchall()
    after = legacy_state(cluster, name)

    assert first == second and first
    assert {k: after[k] for k in before} == before
    assert set(after) - set(before) == {f"public.{t}" for t in tables}


def test_yardage_grants_follow_the_chart_tables(cluster, migrated_db):
    with cluster.connect(migrated_db, OWNER, autocommit=True) as conn:
        rows = conn.execute(
            "SELECT relname, coalesce(relacl::text, '') FROM pg_class"
            " WHERE relname IN ('season_release_team_game_stats',"
            " 'season_release_team_game_yardage', 'team_game_stats',"
            " 'team_game_yardage')"
        ).fetchall()
    acl = dict(rows)
    assert (
        acl["season_release_team_game_yardage"] == acl["season_release_team_game_stats"]
    )
    assert "cks_web" not in acl["team_game_yardage"]
    assert "cks_pipeline" not in acl["team_game_yardage"]


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE season_release_team_season_roster SET conference = 'x'",
        "DELETE FROM season_release_team_game_stats",
        "TRUNCATE season_release_team_adjusted_epa",
        "UPDATE season_release_team_game_yardage SET off_yards_n = 0",
        "DELETE FROM season_release_team_game_yardage",
        "TRUNCATE season_release_team_game_yardage",
    ],
)
def test_pipeline_cannot_update_delete_or_truncate_chart_projections(
    cluster, migrated_db, statement
):
    with as_role(cluster, migrated_db, "cks_pipeline") as conn:
        with pytest.raises(errors.InsufficientPrivilege):
            conn.execute(statement)


def test_chart_projection_rows_are_immutable_even_for_the_owner(cluster, db):
    release_id = stage(cluster, db, "r1")
    with cluster.connect(db, OWNER, autocommit=True) as conn:
        for statement in (
            "UPDATE season_release_team_season_roster SET conference = 'x'",
            "DELETE FROM season_release_team_game_stats",
            "UPDATE season_release_team_game_yardage SET off_yards_n = 0",
            "DELETE FROM season_release_team_game_yardage",
        ):
            with pytest.raises(errors.RaiseException, match="immutable"):
                conn.execute(statement)
        with pytest.raises(errors.RaiseException, match="staged release"):
            conn.execute(
                "INSERT INTO season_release_team_season_roster (release_id, season, team)"
                " VALUES ('absent', 2026, 'T')"
            )
        counts = conn.execute(
            "SELECT (SELECT count(*) FROM season_release_team_season_roster"
            "  WHERE release_id = %(r)s),"
            " (SELECT count(*) FROM season_release_team_game_yardage"
            "  WHERE release_id = %(r)s)",
            {"r": release_id},
        ).fetchone()
    assert counts == (4, 6)


def test_chart_queries_return_release_values_never_live_rows(cluster, db):
    release_id = stage(cluster, db, "r1")
    activate(cluster, db, release_id, None)
    with cluster.connect(db, OWNER, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO team_season_roster (season, team, conference)"
            " SELECT season, team, 'LIVE' FROM season_release_team_season_roster"
            " WHERE release_id = %s",
            (release_id,),
        )
        conn.execute(
            "INSERT INTO team_season_roster (season, team, conference)"
            " VALUES (2026, 'Live Only', 'LIVE')"
        )
        conn.execute(
            "INSERT INTO team_game_yardage SELECT season, game_id, team, 99, 99, 99,"
            " 99.0, 99, 99, 99, 99.0 FROM season_release_team_game_yardage"
            " WHERE release_id = %s",
            (release_id,),
        )
        live = conn.execute(
            "SELECT DISTINCT conference FROM team_season_roster"
        ).fetchall()
    assert live == [("LIVE",)]
    with cluster.connect(db, WEB_LOGIN, autocommit=True) as conn:
        assert chart_set(conn) == "charts_v2"
        rows = web_query_rows(
            conn,
            release_id,
            "teamSeasonRoster",
            ["team", "conference"],
            chart_set="charts_v2",
        )
        yardage = web_query_rows(
            conn,
            release_id,
            "teamGameYardage",
            ["gameId", "team", "offYardsN"],
            chart_set="charts_v2",
        )
    assert {team for team, _ in rows} == {"A", "B", "C", "D"}  # not 'Live Only'
    assert {conference for _, conference in rows} == {"Fixture"}
    assert {(game, team): n for game, team, n in yardage}[(1, "A")] == 6  # not 99


def test_charts_release_over_core_release_and_owner_rollback_round_trip(
    cluster, db, monkeypatch
):
    old = stage_retained_core_v1(cluster, db, "old", monkeypatch)
    activate(cluster, db, old, None)
    new = stage(cluster, db, "new", payload=candidate("new", edit_payload=rename_venue))

    receipt = activate(cluster, db, new, old)
    assert receipt["prior_release_id"] == old
    with cluster.connect(db, WEB_LOGIN, autocommit=True) as conn:
        assert chart_set(conn) == "charts_v2"
        venues = web_query_rows(conn, new, "gameVenues", ["city"], chart_set=None)
        assert {c for (c,) in venues} == {"Elsewhere"}

    # Owner rollback to the retained core_v1 release: readback uses its recorded set.
    rollback(cluster, db, old, new)
    assert statuses(cluster, db) == {old: "active", new: "rolled_back"}
    with cluster.connect(db, WEB_LOGIN, autocommit=True) as conn:
        context, queries = web_release_context(conn)
        cities = web_query_rows(conn, old, "gameVenues", ["city"], chart_set=None)
    assert context["releaseId"] == old and context["chartSet"] is None
    assert len(queries) == 3  # no missing core projections
    assert {c for (c,) in cities} == {"City"}

    # The chart release is rolled_back, so ordinary activation refuses it ...
    with pytest.raises(release.SeasonReleaseError, match="invalid activation status"):
        activate(cluster, db, new, old)
    # ... and the authorized rollback path returns to it with a full readback.
    rollback(cluster, db, new, old)
    assert statuses(cluster, db) == {old: "rolled_back", new: "active"}
    with cluster.connect(db, WEB_LOGIN, autocommit=True) as conn:
        assert chart_set(conn) == "charts_v2"
    assert [row[2] for row in history(cluster, db)] == [
        "activate",
        "activate",
        "rollback",
        "rollback",
    ]


def test_charts_v1_rollback_over_charts_v2_and_back(cluster, db, monkeypatch):
    old = stage_retained(cluster, db, "old", monkeypatch, "charts_v1")
    assert recorded_set(cluster, db, old) == "charts_v1"
    activate(cluster, db, old, None)
    new = stage(cluster, db, "new", payload=candidate("new", edit_payload=rename_venue))
    assert recorded_set(cluster, db, new) == "resume_v1"
    activate(cluster, db, new, old)
    with cluster.connect(db, WEB_LOGIN, autocommit=True) as conn:
        assert chart_set(conn) == "charts_v2"

    # Rollback to charts_v1 reads back its 21 tables only; the web serves charts
    # without explosiveness and never references the yardage relation.
    rollback(cluster, db, old, new)
    assert statuses(cluster, db) == {old: "active", new: "rolled_back"}
    with cluster.connect(db, WEB_LOGIN, autocommit=True) as conn:
        assert chart_set(conn) == "charts_v1"
        stats = web_query_rows(
            conn, old, "teamGameStats", ["gameId", "team"], chart_set="charts_v1"
        )
    assert len(stats) == 6

    rollback(cluster, db, new, old)
    assert statuses(cluster, db) == {old: "rolled_back", new: "active"}
    with cluster.connect(db, WEB_LOGIN, autocommit=True) as conn:
        assert chart_set(conn) == "charts_v2"


def test_retained_charts_v1_release_serves_charts_without_migration_0027(
    cluster, db_0026, monkeypatch
):
    release_id = stage_retained(cluster, db_0026, "old", monkeypatch, "charts_v1")
    activate(cluster, db_0026, release_id, None)
    with cluster.connect(db_0026, WEB_LOGIN, autocommit=True) as conn:
        assert chart_set(conn) == "charts_v1"
        stats = web_query_rows(
            conn, release_id, "teamGameStats", ["gameId"], chart_set="charts_v1"
        )
    assert len(stats) == 6
    # A charts_v2 candidate cannot be staged before 0027 exists.
    with pytest.raises(release.SeasonReleaseError, match="projection schema missing"):
        stage(cluster, db_0026, "new")


def test_charts_v2_release_without_its_yardage_relation_serves_no_charts(cluster, db):
    release_id = stage(cluster, db, "r1")
    activate(cluster, db, release_id, None)
    with cluster.connect(db, OWNER, autocommit=True) as conn:
        conn.execute("DROP TABLE season_release_team_game_yardage")
    with cluster.connect(db, WEB_LOGIN, autocommit=True) as conn:
        context, _ = web_release_context(conn)
    assert context["releaseId"] == release_id and context["chartSet"] is None


@pytest.mark.parametrize("projection_set", ["core_v1", "charts_v1"])
def test_older_set_and_partial_candidates_are_refused_at_stage_without_writes(
    cluster, db, projection_set
):
    before = release_state(cluster, db)
    with pytest.raises(
        release.SeasonReleaseError, match=f"{projection_set} candidates"
    ):
        stage(cluster, db, "old", payload=sealed_retained("old", projection_set))
    full = payload_for("partial")
    partial = {k: v for k, v in full.items() if k != "team_game_stats"}
    with pytest.raises(release.SeasonReleaseError, match="complete fixed"):
        stage(
            cluster,
            db,
            "partial",
            payload=seal("partial", partial, reported_payload=full),
        )
    assert release_state(cluster, db) == before


def test_resolver_without_migration_0026_serves_core_pages_without_charts(
    cluster, db_0025, monkeypatch
):
    release_id = stage_retained_core_v1(cluster, db_0025, "old", monkeypatch)
    activate(cluster, db_0025, release_id, None)
    with cluster.connect(db_0025, WEB_LOGIN, autocommit=True) as conn:
        context, queries = web_release_context(conn)
        cities = web_query_rows(
            conn, release_id, "gameVenues", ["city"], chart_set=None
        )
    assert context["releaseId"] == release_id and context["chartSet"] is None
    assert len(queries) == 3  # no missing core projections
    assert {c for (c,) in cities} == {"City"}
