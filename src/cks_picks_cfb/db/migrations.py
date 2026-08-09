"""Checksummed, append-only Postgres migration runner."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import psycopg

MIGRATION_RE = re.compile(r"^(?P<version>\d{4})_[a-z0-9_]+\.sql$")


class MigrationError(RuntimeError):
    """Raised for invalid, changed, or failed migrations."""


@dataclass(frozen=True)
class Migration:
    version: str
    name: str
    checksum: str
    sql: str


def discover_migrations(directory: Path) -> list[Migration]:
    migrations: list[Migration] = []
    seen: set[str] = set()
    for path in sorted(directory.glob("*.sql")):
        match = MIGRATION_RE.match(path.name)
        if not match:
            raise MigrationError(f"Invalid migration filename: {path.name}")
        version = match.group("version")
        if version in seen:
            raise MigrationError(f"Duplicate migration version: {version}")
        seen.add(version)
        sql = path.read_text(encoding="utf-8")
        migrations.append(
            Migration(
                version=version,
                name=path.name,
                checksum=hashlib.sha256(sql.encode("utf-8")).hexdigest(),
                sql=sql,
            )
        )
    return migrations


CREATE_HISTORY_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    checksum TEXT NOT NULL CHECK (length(checksum) = 64),
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""


def apply_migrations(conn_url: str, directory: Path) -> list[str]:
    """Apply migrations or bootstrap an empty database from the current snapshot.

    ``contracts/schema.sql`` is a reconstructed snapshot for new databases;
    ``contracts/migrations`` remains the append-only upgrade history for existing
    databases.  Both paths record checksums in ``schema_migrations``.
    """
    applied: list[str] = []
    migrations = discover_migrations(directory)
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            cur.execute(CREATE_HISTORY_SQL)
            cur.execute("SELECT to_regclass('public.games')")
            is_empty = cur.fetchone()[0] is None
            if is_empty:
                snapshot = directory.parent / "schema.sql"
                if not snapshot.is_file():
                    raise MigrationError(f"Schema snapshot not found: {snapshot}")
                snapshot_sql = snapshot.read_text(encoding="utf-8")
                snapshot_checksum = hashlib.sha256(
                    snapshot_sql.encode("utf-8")
                ).hexdigest()
                cur.execute(snapshot_sql)
                cur.execute(
                    "INSERT INTO schema_migrations (version, name, checksum) "
                    "VALUES (%s, %s, %s) ON CONFLICT (version) DO NOTHING",
                    ("0000", "schema_snapshot", snapshot_checksum),
                )
            cur.execute("SELECT version, checksum FROM schema_migrations")
            existing = dict(cur.fetchall())
            for migration in migrations:
                if migration.version in existing:
                    if existing[migration.version] != migration.checksum:
                        raise MigrationError(
                            f"Applied migration {migration.name} checksum changed"
                        )
                    continue
                cur.execute(migration.sql)
                cur.execute(
                    "INSERT INTO schema_migrations (version, name, checksum) "
                    "VALUES (%s, %s, %s)",
                    (migration.version, migration.name, migration.checksum),
                )
                applied.append(migration.version)
        conn.commit()
    return applied
