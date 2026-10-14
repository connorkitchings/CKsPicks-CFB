"""Real-Postgres tests for atomic season releases (migration 0025 + release.py).

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

Shipped defects and the test-only workarounds (each defect also has a strict
xfail test against the unmodified source, so the workaround becomes a no-op
signal once the source is fixed):

1. ``0025_season_releases.sql:583`` (same text at ``schema.sql:1758``): an
   unparenthesized ``CASE ... THEN`` inside a PL/pgSQL ``IF`` ends the ``IF``
   condition early, so ``CREATE FUNCTION validate_season_release_transition``
   is a syntax error and the migration cannot apply. ``migration_0025_sql()``
   adds the parentheses, only when the exact defective text is present.
2. ``release.py:238`` (``_policy``) reads ``season_release_policies ... FOR
   SHARE``; Postgres requires UPDATE privilege for row locks, but 0025 grants
   the pipeline only SELECT, so every pipeline activation fails. The "operable"
   template adds ``OPERABILITY_COMPAT_SQL`` (a single-column UPDATE grant)
   so the activation, rollback and concurrency behaviour can still be tested.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

import psycopg
import pytest
from psycopg import errors, sql

from cks_picks_cfb.season import release
from tests.pg_harness import PgCluster, find_pg_bin

PG_BIN = find_pg_bin()
if PG_BIN is None:
    pytest.skip(
        "PostgreSQL server binaries (initdb, pg_ctl, postgres) not found",
        allow_module_level=True,
    )

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "contracts" / "migrations"
MIGRATION_0025 = MIGRATIONS / "0025_season_releases.sql"
SNAPSHOT_MARKER = "-- Additive season releases."

OWNER = "cks_owner"
WEB_LOGIN = "cks_web_reader"
PIPELINE = {"preview": "cks_preview_pipeline", "production": "cks_prod_pipeline"}
SEASON = 2026
RUN_ID = "season-2026-week-0"
TS = "2026-08-29T16:00:00+00:00"
POLICY = {
    "model_manifest_sha256": "a" * 64,
    "workflow_version": "season_workflow_v1",
    "grading_policy_sha256": "c" * 64,
}
CONTROL_TABLES = {
    "season_release_policies",
    "season_releases",
    "season_release_history",
}

SYNTAX_DEFECT = (
    "IF current_user <> CASE WHEN NEW.environment = 'preview' THEN "
    "'cks_preview_pipeline' ELSE 'cks_prod_pipeline' END\n"
    "           OR session_user <> current_user THEN"
)
SYNTAX_FIX = (
    "IF (current_user <> CASE WHEN NEW.environment = 'preview' THEN "
    "'cks_preview_pipeline' ELSE 'cks_prod_pipeline' END\n"
    "           OR session_user <> current_user) THEN"
)
OPERABILITY_COMPAT_SQL = (
    "GRANT UPDATE (installed_at) ON season_release_policies TO cks_pipeline"
)


# --------------------------------------------------------------------------
# SQL sources
# --------------------------------------------------------------------------


def pre0025_snapshot_sql() -> str:
    schema = (ROOT / "contracts" / "schema.sql").read_text()
    return schema[: schema.index(SNAPSHOT_MARKER)]


def migration_0025_sql() -> str:
    """0025 with only the defect-1 parenthesization (see module docstring)."""
    return MIGRATION_0025.read_text().replace(SYNTAX_DEFECT, SYNTAX_FIX)


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
    _create_db(cluster, "tpl_migrated", "tpl_pre0025")
    with cluster.connect("tpl_migrated", OWNER, autocommit=True) as conn:
        conn.execute(migration_0025_sql())
    _create_db(cluster, "tpl_operable", "tpl_migrated")
    with cluster.connect("tpl_operable", OWNER, autocommit=True) as conn:
        conn.execute(OPERABILITY_COMPAT_SQL)
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


# --------------------------------------------------------------------------
# Candidate payloads and release helpers
# --------------------------------------------------------------------------


def _encoded(doc) -> bytes:
    return json.dumps(doc, sort_keys=True).encode()


def run_record() -> dict:
    return {
        "run_id": RUN_ID,
        "season": SEASON,
        "week": 0,
        "state": "published",
        "expected_games": 1,
        "predicted_games": 1,
        "lined_games": 1,
        "data_as_of": TS,
        "source_config": "conf/season/test.yaml",
        "system_name": "Season Test",
        "model_id": "season-test",
        "code_sha": "d" * 40,
        "config_sha": "e" * 64,
        "model_bundle_sha256": None,
        "rating_manifest_sha256": None,
        "artifact_uri": "runs/week0.json",
        "artifact_sha256": "f" * 64,
        "input_dataset_refs": [],
        "validation": {},
        "created_at": TS,
        "published_at": TS,
        "frozen_at": None,
        "scored_at": None,
        "evidence_class": "legacy",
    }


def projections(spread: float) -> dict:
    """Complete week-0 serving view; ``spread`` makes release contents differ."""
    lines = {
        "home_team_spread_line": -3.5,
        "total_line": 51.5,
        "predicted_spread": spread,
        "predicted_total": 50.0,
        "predicted_spread_std_dev": 13.0,
        "predicted_total_std_dev": 12.0,
        "spread_lean": "home",
        "total_lean": "under",
        "edge_spread": 1.5,
        "edge_total": 1.5,
        "high_confidence": False,
    }
    views = {base: [] for base in release.PROJECTION_KEYS}
    views.update(
        games=[
            {
                "game_id": 401,
                "season": SEASON,
                "week": 0,
                "start_date": TS,
                "home_team": "Home U",
                "away_team": "Away St",
                **lines,
                "source_config": "conf/season/test.yaml",
                "system_name": "Season Test",
                "model_id": "season-test",
                "inserted_at": TS,
                "updated_at": TS,
            }
        ],
        predictions=[
            {
                "run_id": RUN_ID,
                "game_id": 401,
                **lines,
                "high_confidence_eligible": False,
                "home_completed_games": 0,
                "away_completed_games": 0,
                "regime": "preseason",
                "spread_model_version": "v-test",
                "total_model_version": "v-test",
                "created_at": TS,
                "market_snapshot_id": None,
            }
        ],
        site_week_selections=[
            {
                "season": SEASON,
                "week": 0,
                "run_id": RUN_ID,
                "selected_at": TS,
                "reason": "season release",
            }
        ],
        v5_rating_snapshots=[
            {
                "snapshot_id": "snap-home-u",
                "source_run_id": RUN_ID,
                "source_manifest_sha256": "9" * 64,
                "team": "Home U",
                "season": SEASON,
                "week": 0,
                "game_id": None,
                "snapshot_class": "pregame",
                "cutoff_utc": TS,
                "offense_rating": 1.25,
                "offense_variance": 0.5,
                "defense_rating": -0.75,
                "defense_variance": 0.5,
                "overall_rating": 2.0,
                "overall_variance": 0.75,
                "fallback_reason": None,
                "created_at": TS,
            }
        ],
        system_stats=[
            {
                "season": SEASON,
                "as_of_week": 0,
                "spread_wins": 0,
                "spread_losses": 0,
                "spread_pushes": 0,
                "total_wins": 0,
                "total_losses": 0,
                "total_pushes": 0,
                "spread_profit_units": "0.0000",
                "total_profit_units": "0.0000",
                "updated_at": TS,
            }
        ],
    )
    return views


def candidate(
    label: str,
    *,
    spread: float = -2.0,
    model_sha: str = POLICY["model_manifest_sha256"],
    verification_state: str = "passed",
) -> dict[str, bytes]:
    """Sealed manifest/verification/projection bytes, chained by checksums."""
    projection_raw = _encoded(
        {**projections(spread), "prediction_runs": [run_record()]}
    )
    manifest = {
        "schema_version": "season_run_v1",
        "release_id": label,
        "season": SEASON,
        "active_week": 0,
        "model_manifest_sha256": model_sha,
        "revision_manifest_sha256": "b" * 64,
        "workflow_version": POLICY["workflow_version"],
        "grading_policy_sha256": POLICY["grading_policy_sha256"],
        "code_sha": "d" * 40,
        "config_sha": "e" * 64,
        "verification_uri": f"verify/{label}.json",
        "output_refs": {
            "serving_projections": {
                "uri": f"projections/{label}.json",
                "sha256": hashlib.sha256(projection_raw).hexdigest(),
            }
        },
    }
    verification_raw = _encoded(
        {
            "state": verification_state,
            "identity": {key: manifest[key] for key in release.IDENTITY_FIELDS},
            "checks": {"complete": True},
            "output_refs": manifest["output_refs"],
        }
    )
    manifest["verification_sha256"] = hashlib.sha256(verification_raw).hexdigest()
    return {
        "manifest_raw": _encoded(manifest),
        "verification_raw": verification_raw,
        "projection_raw": projection_raw,
    }


def stage(cluster, dbname, label, environment="preview", payload=None, **kwargs):
    """Stage and commit exactly as ``run_season.py`` does (rollback on error)."""
    with cluster.connect(dbname, PIPELINE[environment]) as conn:
        release_id = release.stage_release(
            conn,
            run_manifest_uri=f"runs/{label}.json",
            environment=environment,
            **(payload or candidate(label, **kwargs)),
        )
        conn.commit()
    return release_id


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


def test_snapshot_tail_is_migration_0025_verbatim_matches():
    schema = (ROOT / "contracts" / "schema.sql").read_text()

    tail = schema[schema.index(SNAPSHOT_MARKER) :]

    assert tail == MIGRATION_0025.read_text()


@pytest.mark.xfail(
    strict=True,
    raises=errors.SyntaxError,
    reason="0025_season_releases.sql:583 unparenthesized CASE inside PL/pgSQL IF",
)
def test_shipped_0025_applies_to_pre0025_database_succeeds(cluster, pre0025_db):
    with cluster.connect(pre0025_db, OWNER, autocommit=True) as conn:
        conn.execute(MIGRATION_0025.read_text())


@pytest.mark.xfail(
    strict=True,
    raises=errors.SyntaxError,
    reason="schema.sql:1758 carries the same 0025 syntax error into fresh bootstraps",
)
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
        conn.execute(migration_0025_sql())
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

    expected = CONTROL_TABLES | {f"season_release_{b}" for b in release.PROJECTION_KEYS}
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
        " ORDER BY 1, 2"
    )
    with cluster.connect(migrated_db, OWNER, autocommit=True) as conn:
        before = conn.execute(catalog_sql).fetchall()

        conn.execute(migration_0025_sql())
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


def test_web_role_reads_releases_and_every_projection(cluster, migrated_db):
    with as_role(cluster, migrated_db, "cks_web") as conn:
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
def test_pipeline_role_cannot_delete_truncate_or_write_policy(
    cluster, migrated_db, statement
):
    with as_role(cluster, migrated_db, "cks_pipeline") as conn:
        with pytest.raises(errors.InsufficientPrivilege):
            conn.execute(statement)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "schema.sql ALTER DEFAULT PRIVILEGES gives cks_pipeline table-wide UPDATE on"
        " every 0025 table; 0025 revokes only from PUBLIC (0025:504), so the"
        " column-limited GRANT UPDATE (status, activated_at) is not the effective grant"
    ),
)
def test_pipeline_update_privilege_limited_to_status_columns(cluster, migrated_db):
    with cluster.connect(migrated_db, OWNER, autocommit=True) as conn:
        privileges = conn.execute(
            "SELECT has_table_privilege('cks_pipeline', 'season_releases', 'UPDATE'),"
            " has_column_privilege('cks_pipeline', 'season_releases', 'code_sha', 'UPDATE'),"
            " has_table_privilege('cks_pipeline', 'season_release_history', 'UPDATE'),"
            " has_table_privilege('cks_pipeline', 'season_release_games', 'UPDATE')"
        ).fetchone()

    assert privileges == (False, False, False, False)


def test_pipeline_update_of_release_manifest_columns_refused(cluster, db):
    release_id = stage(cluster, db, "r1")
    before = release_state(cluster, db)

    with cluster.connect(db, PIPELINE["preview"], autocommit=True) as conn:
        for column, value in (("code_sha", "tampered"), ("active_week", 9)):
            with pytest.raises(psycopg.Error, match="immutable|permission denied"):
                conn.execute(
                    sql.SQL(
                        "UPDATE season_releases SET {} = %s WHERE release_id = %s"
                    ).format(sql.Identifier(column)),
                    (value, release_id),
                )

    assert release_state(cluster, db) == before


def test_pipeline_cannot_roll_back_via_direct_update(cluster, db):
    first = stage(cluster, db, "r1")
    activate(cluster, db, first, None)
    second = stage(cluster, db, "r2", spread=-4.0)
    activate(cluster, db, second, first)

    with cluster.connect(db, PIPELINE["preview"]) as conn:
        with pytest.raises(errors.RaiseException, match="may not roll back"):
            conn.execute(
                "UPDATE season_releases SET status = 'rolled_back' WHERE release_id = %s",
                (second,),
            )

    assert statuses(cluster, db) == {first: "superseded", second: "active"}


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
                " (release_id, season, week, run_id, reason) VALUES (%s, %s, 1, %s, 'x')",
                (release_id, SEASON, RUN_ID),
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


@pytest.mark.xfail(
    strict=True,
    raises=errors.InsufficientPrivilege,
    reason=(
        "release.py:238 _policy uses SELECT ... FOR SHARE on season_release_policies"
        " but 0025:502-503 grants cks_pipeline only SELECT; row locks need UPDATE"
    ),
)
def test_shipped_grants_allow_pipeline_activation(cluster, migrated_db):
    with cluster.connect(migrated_db, OWNER, autocommit=True) as conn:
        install_policy(conn, "preview")
    release_id = stage(cluster, migrated_db, "r1")

    receipt = activate(cluster, migrated_db, release_id, None)

    assert receipt["release_id"] == release_id


def test_stage_is_invisible_to_active_pointer_and_legacy_tables(cluster, db):
    legacy_before = legacy_state(cluster, db)

    release_id = stage(cluster, db, "r1")

    assert release_id == "preview-r1"
    assert statuses(cluster, db) == {release_id: "staged"}
    assert history(cluster, db) == []
    legacy_after = legacy_state(cluster, db)
    changed = {k for k in legacy_after if legacy_after[k] != legacy_before[k]}
    assert changed == {"public.prediction_runs"}  # registry row reused by the release
    with cluster.connect(db, WEB_LOGIN, autocommit=True) as conn:
        rows = conn.execute(web_sql()[1], ("preview", SEASON)).fetchall()
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
    second = stage(cluster, db, "r2", spread=-4.0)

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
    second = stage(cluster, db, "r2", spread=-4.0)
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
                run_manifest_uri="runs/r1.json",
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


def _tampered(fault: str) -> dict[str, bytes]:
    payload = candidate("r1")
    if fault == "verification-failed":
        return candidate("r1", verification_state="failed")
    if fault == "verification-bytes":
        payload["verification_raw"] += b" "
    elif fault == "verification-missing":
        payload["verification_raw"] = b""
    elif fault == "projection-bytes":
        payload["projection_raw"] = _encoded(projections(-9.0))
    elif fault == "projection-checksum":
        manifest = json.loads(payload["manifest_raw"])
        manifest["output_refs"]["serving_projections"]["sha256"] = "0" * 64
        payload["manifest_raw"] = _encoded(manifest)
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


def test_stage_failing_after_inserts_leaves_no_partial_rows(cluster, db):
    payload = candidate("r1")
    views = json.loads(payload["projection_raw"])
    views["system_stats"][0]["unexpected_column"] = 1
    raw = _encoded(views)
    manifest = json.loads(payload["manifest_raw"])
    manifest["output_refs"]["serving_projections"]["sha256"] = hashlib.sha256(
        raw
    ).hexdigest()
    verification = json.loads(payload["verification_raw"])
    verification["output_refs"] = manifest["output_refs"]
    payload["verification_raw"] = _encoded(verification)
    manifest["verification_sha256"] = hashlib.sha256(
        payload["verification_raw"]
    ).hexdigest()
    payload.update(manifest_raw=_encoded(manifest), projection_raw=raw)
    before = release_state(cluster, db)

    with pytest.raises(
        release.SeasonReleaseError, match="columns differ: system_stats"
    ):
        stage(cluster, db, "r1", payload=payload)

    assert release_state(cluster, db) == before


def test_rollback_reactivates_prior_release_and_keeps_all_rows(cluster, db):
    first = stage(cluster, db, "r1")
    activate(cluster, db, first, None)
    second = stage(cluster, db, "r2", spread=-4.0)
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
    second = stage(cluster, db, "r2", spread=-4.0)
    activate(cluster, db, second, first)
    before = release_state(cluster, db)

    with pytest.raises(release.SeasonReleaseError, match="owner"):
        rollback(cluster, db, first, second, user=user, **overrides)

    assert release_state(cluster, db) == before


def test_rollback_from_set_role_session_refused(cluster, db):
    first = stage(cluster, db, "r1")
    activate(cluster, db, first, None)
    second = stage(cluster, db, "r2", spread=-4.0)
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
    staged = stage(cluster, db, "r2", spread=-4.0)
    before = release_state(cluster, db)

    with pytest.raises(release.SeasonReleaseError, match="invalid activation status"):
        rollback(cluster, db, staged, first)

    assert release_state(cluster, db) == before


def test_rollback_when_no_release_is_active_refused_without_writes(cluster, db):
    first = stage(cluster, db, "r1")
    activate(cluster, db, first, None)
    second = stage(cluster, db, "r2", spread=-4.0)
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
    second = stage(cluster, db, "r2", spread=-4.0)
    activate(cluster, db, second, first)
    rollback(cluster, db, first, second)
    before = release_state(cluster, db)

    with pytest.raises(release.SeasonReleaseError, match="changed since review"):
        rollback(cluster, db, second, second)

    assert release_state(cluster, db) == before


def test_production_activation_with_read_only_preview_rehearsal_succeeds(cluster, db):
    rehearsal = stage(cluster, db, "r1")
    activate(cluster, db, rehearsal, None)
    candidate_id = stage(cluster, db, "r1", environment="production")

    with cluster.connect(db, PIPELINE["preview"]) as preview:
        preview.read_only = True
        receipt = activate(
            cluster,
            db,
            candidate_id,
            None,
            environment="production",
            preview_conn=preview,
        )

    assert receipt["release_id"] == "production-r1"
    assert statuses(cluster, db)[candidate_id] == "active"


@pytest.mark.xfail(
    strict=True,
    raises=release.SeasonReleaseError,
    reason=(
        "run_season.py:147 opens Preview with options='-c default_transaction_read_only=on'"
        " but release.py:461 checks psycopg conn.read_only, which stays None"
    ),
)
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
    rehearsal = stage(cluster, db, "r1", spread=-4.0)
    activate(cluster, db, rehearsal, None)
    candidate_id = stage(cluster, db, "r1", environment="production")
    before = release_state(cluster, db)

    with cluster.connect(db, PIPELINE["preview"]) as preview:
        preview.read_only = True
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
    second = stage(cluster, db, "r2", spread=-4.0)

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
    second = stage(cluster, db, "r2", spread=-4.0)
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
            release_id = release.stage_release(
                conn,
                run_manifest_uri="runs/r1.json",
                environment="preview",
                **candidate("r1"),
            )
            conn.commit()
            return release_id

    outcomes = _race([worker, worker, worker])

    assert [kind for kind, _ in outcomes] == ["ok"] * 3, outcomes
    assert {value for _, value in outcomes} == {"preview-r1"}
    state = release_state(cluster, db)
    assert len(state["season_releases"]) == 1
    assert len(state["season_release_games"]) == 1
    assert len(state["season_release_predictions"]) == 1
    assert len(state["prediction_runs"]) == 1


# --------------------------------------------------------------------------
# D. Web read contract
# --------------------------------------------------------------------------


def web_release_projections() -> list[str]:
    """RELEASE_PROJECTIONS from season-release-query.ts, resolved via schema.ts."""
    query_ts = (ROOT / "web/src/lib/season-release-query.ts").read_text()
    block = re.search(r"RELEASE_TABLES = \[(.*?)\] as const", query_ts, re.S)
    assert block, "RELEASE_TABLES literal not found in season-release-query.ts"
    keys = re.findall(r'"(\w+)"', block[1])
    schema_ts = (ROOT / "web/src/lib/schema.ts").read_text()
    names = dict(re.findall(r'export const (\w+) = pgTable\(\s*"(\w+)"', schema_ts))
    unknown = [key for key in keys if key not in names]
    assert not unknown, f"RELEASE_TABLES keys missing from schema.ts: {unknown}"
    return [f"season_release_{names[key]}" for key in keys]


def web_sql() -> list[str]:
    """The three sql`` templates in loadReleaseContext, ${...} as %s."""
    source = (ROOT / "web/src/lib/season-release-context.ts").read_text()
    body = source[source.index("export async function loadReleaseContext") :]
    templates = re.findall(r"sql`(.*?)`", body, re.S)
    assert len(templates) == 3, "loadReleaseContext query count changed"
    return [re.sub(r"\$\{[^}]+\}", "%s", template) for template in templates]


def test_release_projection_list_matches_migration_and_release_module():
    web = web_release_projections()
    created = set(
        re.findall(
            r"CREATE TABLE IF NOT EXISTS (season_release_\w+)",
            MIGRATION_0025.read_text(),
        )
    )

    assert len(web) == len(set(web))
    assert set(web) == created - CONTROL_TABLES, (
        "web RELEASE_PROJECTIONS and 0025 projection tables drifted: "
        f"web-only={sorted(set(web) - created)}, "
        f"migration-only={sorted(created - CONTROL_TABLES - set(web))}"
    )
    assert set(web) == {f"season_release_{b}" for b in release.PROJECTION_KEYS}


def test_web_existence_probe_false_before_0025(cluster, pre0025_db):
    with cluster.connect(pre0025_db, WEB_LOGIN, autocommit=True) as conn:
        exists = conn.execute(web_sql()[0]).fetchone()[0]

    assert exists is False


def test_web_active_query_returns_no_row_without_activation(cluster, db):
    stage(cluster, db, "r1")

    with cluster.connect(db, WEB_LOGIN, autocommit=True) as conn:
        exists = conn.execute(web_sql()[0]).fetchone()[0]
        rows = conn.execute(web_sql()[1], ("preview", SEASON)).fetchall()

    assert exists is True
    assert rows == []


def test_web_active_query_returns_one_row_and_no_missing_projections(cluster, db):
    first = stage(cluster, db, "r1")
    activate(cluster, db, first, None)
    second = stage(cluster, db, "r2", spread=-4.0)
    activate(cluster, db, second, first)
    exists_sql, active_sql, missing_sql = web_sql()

    with cluster.connect(db, WEB_LOGIN, autocommit=True) as conn:
        rows = conn.execute(active_sql, ("preview", SEASON)).fetchall()
        other = conn.execute(active_sql, ("production", SEASON)).fetchall()
        missing = conn.execute(missing_sql, (web_release_projections(),)).fetchall()

    assert len(rows) == 1
    release_id, environment, season, active_week, activated_at = rows[0]
    assert (release_id, environment, season, active_week) == (
        second,
        "preview",
        SEASON,
        0,
    )
    assert activated_at is not None
    assert other == []
    assert missing == []


@pytest.mark.xfail(
    strict=True,
    raises=psycopg.Error,
    reason=(
        "drizzle-orm 0.45.2 renders the JS array in season-release-context.ts:53 as"
        " ($1, ..., $n)::text[], a row constructor that cannot be cast to text[]"
    ),
)
def test_web_missing_projection_query_as_rendered_by_drizzle_succeeds(cluster, db):
    names = web_release_projections()
    rendered = web_sql()[2].replace("%s", "(" + ", ".join(["%s"] * len(names)) + ")")

    with cluster.connect(db, WEB_LOGIN, autocommit=True) as conn:
        missing = conn.execute(rendered, names).fetchall()

    assert missing == []
