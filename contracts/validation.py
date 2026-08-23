#!/usr/bin/env python3
"""Validate that contracts/ files are in sync across Python and TypeScript."""

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

    for script in [
        "scripts/pipeline/publish_to_db.py",
        "scripts/pipeline/publish_review.py",
    ]:
        path = ROOT / script
        if path.exists():
            script_map = extract_python_map(path)
            if script_map and script_map != canonical_py:
                errors.append(
                    f"{script} TEAM_LOGO_MAP out of sync with contracts/teams.py\n"
                    f"  Script only: {set(script_map) - set(canonical_py)}\n"
                    f"  Missing: {set(canonical_py) - set(script_map)}\n"
                    f"  Value mismatches: "
                    f"{ {k for k in script_map.keys() & canonical_py.keys() if script_map[k] != canonical_py[k]} }"
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
        if not schema and table != "schema_migrations"
    }
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


def check_python_contracts() -> list[str]:
    errors = []
    try:
        from cks_picks_cfb.data.schema_contracts import schema_for
        schema = schema_for("games", "v1")
        if not schema.required:
            errors.append("schema_for('games', 'v1') returned empty required columns")
    except Exception as exc:
        errors.append(f"Failed to import or validate schema_for: {exc}")

    try:
        from cks_picks_cfb.model_bundle import validate_model_feature_allowlist
        validate_model_feature_allowlist(("off_epa_play_mean",))
    except Exception as exc:
        errors.append(f"Failed to import or validate validate_model_feature_allowlist: {exc}")

    return errors


def main():
    all_errors = []
    all_errors.extend(check_teams_sync())
    all_errors.extend(check_schema_sync())
    all_errors.extend(check_migration_history())
    all_errors.extend(check_python_contracts())

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
