#!/usr/bin/env python3
"""Validate that contracts/ files are in sync across Python and TypeScript."""

import json
import re
import sys
from pathlib import Path

from cks_picks_cfb.db.migrations import MigrationError, discover_migrations

CONTRACTS_DIR = Path(__file__).parent
ROOT = CONTRACTS_DIR.parent


def extract_python_map_keys(filepath: Path) -> set[str]:
    return set(extract_python_map(filepath))


def extract_ts_map_keys(filepath: Path) -> set[str]:
    return set(extract_ts_map(filepath))


def extract_python_map(filepath: Path) -> dict[str, str]:
    content = filepath.read_text()
    match = re.search(r"TEAM_LOGO_MAP\s*=\s*\{([^}]+)\}", content, re.DOTALL)
    if not match:
        return {}
    return dict(re.findall(r'"([^"]+)"\s*:\s*"([^"]+)"', match.group(1)))


def extract_ts_map(filepath: Path) -> dict[str, str]:
    content = filepath.read_text()
    match = re.search(r"TEAM_LOGO_MAP[^{]*\{([^}]+)\}", content, re.DOTALL)
    if not match:
        return {}
    quoted = dict(re.findall(r'"([^"]+)"\s*:\s*"([^"]+)"', match.group(1)))
    unquoted = dict(re.findall(r'(?<!["\w])(\w+)\s*:\s*"([^"]+)"', match.group(1)))
    return quoted | unquoted


def check_teams_sync() -> list[str]:
    errors = []
    canonical_py = extract_python_map(CONTRACTS_DIR / "teams.py")
    canonical_ts = extract_ts_map(CONTRACTS_DIR / "teams.ts")

    if canonical_py != canonical_ts:
        errors.append(
            f"contracts/teams.py != contracts/teams.ts\n"
            f"  Python only: {set(canonical_py) - set(canonical_ts)}\n"
            f"  TS only: {set(canonical_ts) - set(canonical_py)}\n"
            f"  Value mismatches: "
            f"{ {k for k in canonical_py.keys() & canonical_ts.keys() if canonical_py[k] != canonical_ts[k]} }"
        )

    web_teams = ROOT / "web" / "src" / "lib" / "teams.ts"
    if web_teams.exists():
        web_map = extract_ts_map(web_teams)
        if web_map and web_map != canonical_ts:
            errors.append(
                f"web/src/lib/teams.ts out of sync with contracts/teams.ts\n"
                f"  Web only: {set(web_map) - set(canonical_ts)}\n"
                f"  Missing: {set(canonical_ts) - set(web_map)}\n"
                f"  Value mismatches: "
                f"{ {k for k in web_map.keys() & canonical_ts.keys() if web_map[k] != canonical_ts[k]} }"
            )

    return errors


def _read_sql_parenthesized_block(source: str, opening_paren: int) -> str:
    """Return the content of a SQL parenthesized block without regex guessing."""
    depth = 0
    for index in range(opening_paren, len(source)):
        token = source[index]
        if token == "(":
            depth += 1
        elif token == ")":
            depth -= 1
            if depth == 0:
                return source[opening_paren + 1 : index]
    raise ValueError("Unclosed SQL parenthesized block")


def extract_sql_table_columns(filepath: Path) -> dict[str, set[str]]:
    """Extract canonical table columns, including additive ALTER TABLE columns."""
    source = filepath.read_text()
    tables: dict[str, set[str]] = {}
    create_pattern = re.compile(
        r"CREATE TABLE IF NOT EXISTS (?:(\w+)\.)?(\w+)\s*\(", re.IGNORECASE
    )
    for match in create_pattern.finditer(source):
        table = match.group(2)
        block = _read_sql_parenthesized_block(source, match.end() - 1)
        columns = {
            column
            for column in re.findall(r"^\s{4}([a-z][a-z0-9_]*)\s+", block, re.MULTILINE)
            if column not in {"primary", "unique", "check", "constraint", "foreign"}
        }
        tables.setdefault(table, set()).update(columns)
    for table, column in re.findall(
        r"ALTER TABLE\s+(?:\w+\.)?(\w+)\s+ADD COLUMN IF NOT EXISTS\s+(\w+)",
        source,
        re.IGNORECASE,
    ):
        tables.setdefault(table, set()).add(column)
    return tables


def check_schema_sync() -> list[str]:
    errors = []
    sql_canonical = (CONTRACTS_DIR / "schema.sql").read_text()
    ts_canonical = (CONTRACTS_DIR / "schema.ts").read_text()

    sql_matches = re.findall(
        r"CREATE TABLE IF NOT EXISTS (?:(\w+)\.)?(\w+)", sql_canonical
    )
    sql_tables = {
        table
        for schema, table in sql_matches
        if schema in (None, "", "public") and table != "schema_migrations"
    }
    # Drizzle's unqualified pgTable declarations represent public tables. Ops
    # and catalog tables intentionally remain outside this web-facing schema.
    ts_tables = set(re.findall(r'pgTable\(\s*"(\w+)"', ts_canonical))

    if sql_tables != ts_tables:
        errors.append(
            f"Schema table mismatch:\n"
            f"  SQL only: {sql_tables - ts_tables}\n"
            f"  TS only: {ts_tables - sql_tables}"
        )

    web_schema = ROOT / "web" / "src" / "lib" / "schema.ts"
    if web_schema.exists():
        web_ts = web_schema.read_text()
        if web_ts.strip() != ts_canonical.strip():
            errors.append("web/src/lib/schema.ts differs from contracts/schema.ts")

    return errors


def check_projection_sets_sync() -> list[str]:
    """The projection-set registry must be valid and mirrored byte-for-byte for the web app."""
    registry_path = CONTRACTS_DIR / "projection_sets.json"
    errors = []
    try:
        registry = json.loads(registry_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return [f"contracts/projection_sets.json is unreadable: {exc}"]
    sets = registry.get("sets", {})
    if registry.get("staging_set") not in sets:
        errors.append("projection_sets.json staging_set is not one of its sets")
    for name, entry in sets.items():
        tables = entry.get("tables", [])
        if len(tables) != len(set(tables)):
            errors.append(f"projection set {name} lists a table twice")
        if entry.get("chart_set") is not None and entry["chart_set"] not in sets:
            errors.append(
                f"projection set {name} serves unknown chart_set {entry['chart_set']}"
            )
    mirror = ROOT / "web" / "src" / "lib" / "projection-sets.json"
    if not mirror.exists() or mirror.read_bytes() != registry_path.read_bytes():
        errors.append(
            "web/src/lib/projection-sets.json differs from contracts/projection_sets.json"
        )
    return errors


def check_migration_history() -> list[str]:
    errors = []
    migration_dir = CONTRACTS_DIR / "migrations"
    if not migration_dir.is_dir():
        return ["contracts/migrations directory is missing"]
    try:
        migrations = discover_migrations(migration_dir)
    except MigrationError as exc:
        return [str(exc)]
    if not migrations:
        errors.append("contracts/migrations contains no append-only migrations")
    if any(not migration.sql.strip() for migration in migrations):
        errors.append("Empty SQL migration found")
    return errors


def check_logo_assets() -> list[str]:
    """Generated name->id map, manifest and files on disk must describe one set."""
    logos = ROOT / "web" / "public" / "logos" / "v2"
    manifest_path = logos / "manifest.json"
    generated = ROOT / "web" / "src" / "lib" / "team-logos.generated.ts"
    if not manifest_path.exists():
        return []  # logos are optional until built (web/scripts/build-team-logos.mjs)
    import hashlib
    import json

    errors: list[str] = []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    teams = manifest.get("teams", {})
    ids_in_map = {
        name: int(team_id)
        for name, team_id in re.findall(
            r'"([^"]+)"\s*:\s*(\d+)', generated.read_text(encoding="utf-8")
        )
    }
    manifest_names = {int(i): t["school"] for i, t in teams.items()}
    if set(ids_in_map.values()) != set(manifest_names):
        errors.append(
            "logo ids differ between team-logos.generated.ts and manifest.json: "
            f"{sorted(set(ids_in_map.values()) ^ set(manifest_names))[:10]}"
        )
    for name, team_id in ids_in_map.items():
        if manifest_names.get(team_id) != name:
            errors.append(f"logo map {name!r} -> {team_id} disagrees with manifest")
    listed: set[str] = set()
    for team_id, team in teams.items():
        for rel, sha in team["files"].items():
            listed.add(rel)
            path = logos / rel
            if not path.exists():
                errors.append(f"logo file missing: {rel}")
            elif hashlib.sha256(path.read_bytes()).hexdigest() != sha:
                errors.append(f"logo file hash differs from manifest: {rel}")
    on_disk = {p.relative_to(logos).as_posix() for p in logos.rglob("*.webp")}
    if on_disk - listed:
        errors.append(f"logo files not in manifest: {sorted(on_disk - listed)[:10]}")
    return errors


def main():
    all_errors = []
    all_errors.extend(check_logo_assets())
    all_errors.extend(check_teams_sync())
    all_errors.extend(check_schema_sync())
    all_errors.extend(check_projection_sets_sync())
    all_errors.extend(check_migration_history())

    if all_errors:
        print("Contracts validation FAILED:")
        for err in all_errors:
            print(f"\n  - {err}")
        sys.exit(1)
    else:
        print("Contracts validation passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
