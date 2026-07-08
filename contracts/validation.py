#!/usr/bin/env python3
"""Validate that contracts/ files are in sync across Python and TypeScript."""

import re
import sys
from pathlib import Path

CONTRACTS_DIR = Path(__file__).parent
ROOT = CONTRACTS_DIR.parent


def extract_python_map_keys(filepath: Path) -> set[str]:
    content = filepath.read_text()
    match = re.search(r"TEAM_LOGO_MAP\s*=\s*\{([^}]+)\}", content, re.DOTALL)
    if not match:
        return set()
    keys = re.findall(r'"([^"]+)"\s*:', match.group(1))
    return set(keys)


def extract_ts_map_keys(filepath: Path) -> set[str]:
    content = filepath.read_text()
    match = re.search(r"TEAM_LOGO_MAP[^{]*\{([^}]+)\}", content, re.DOTALL)
    if not match:
        return set()
    keys = re.findall(r'"([^"]+)"\s*:', match.group(1))
    unquoted = re.findall(r'(?<!["\w])(\w+)\s*:', match.group(1))
    return set(keys) | set(unquoted)


def check_teams_sync() -> list[str]:
    errors = []
    canonical_py = extract_python_map_keys(CONTRACTS_DIR / "teams.py")
    canonical_ts = extract_ts_map_keys(CONTRACTS_DIR / "teams.ts")

    if canonical_py != canonical_ts:
        errors.append(
            f"contracts/teams.py keys != contracts/teams.ts keys\n"
            f"  Python only: {canonical_py - canonical_ts}\n"
            f"  TS only: {canonical_ts - canonical_py}"
        )

    for script in [
        "scripts/pipeline/publish_to_db.py",
        "scripts/pipeline/publish_picks.py",
        "scripts/pipeline/publish_review.py",
    ]:
        path = ROOT / script
        if path.exists():
            script_keys = extract_python_map_keys(path)
            if script_keys and script_keys != canonical_py:
                errors.append(
                    f"{script} TEAM_LOGO_MAP out of sync with contracts/teams.py\n"
                    f"  Script only: {script_keys - canonical_py}\n"
                    f"  Missing: {canonical_py - script_keys}"
                )

    web_teams = ROOT / "web" / "src" / "lib" / "teams.ts"
    if web_teams.exists():
        web_keys = extract_ts_map_keys(web_teams)
        if web_keys and web_keys != canonical_ts:
            errors.append(
                f"web/src/lib/teams.ts out of sync with contracts/teams.ts\n"
                f"  Web only: {web_keys - canonical_ts}\n"
                f"  Missing: {canonical_ts - web_keys}"
            )

    return errors


def check_schema_sync() -> list[str]:
    errors = []
    sql_canonical = (CONTRACTS_DIR / "schema.sql").read_text()
    ts_canonical = (CONTRACTS_DIR / "schema.ts").read_text()

    sql_tables = set(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", sql_canonical))
    ts_tables = set(re.findall(r'pgTable\(\s*"(\w+)"', ts_canonical))

    if sql_tables != ts_tables:
        errors.append(
            f"Schema table mismatch:\n"
            f"  SQL only: {sql_tables - ts_tables}\n"
            f"  TS only: {ts_tables - sql_tables}"
        )

    web_migration = ROOT / "web" / "db" / "migrations" / "0001_init.sql"
    if web_migration.exists():
        web_sql = web_migration.read_text()
        if web_sql.strip() != sql_canonical.strip():
            errors.append(
                "web/db/migrations/0001_init.sql differs from contracts/schema.sql"
            )

    web_schema = ROOT / "web" / "src" / "lib" / "schema.ts"
    if web_schema.exists():
        web_ts = web_schema.read_text()
        if web_ts.strip() != ts_canonical.strip():
            errors.append("web/src/lib/schema.ts differs from contracts/schema.ts")

    return errors


def main():
    all_errors = []
    all_errors.extend(check_teams_sync())
    all_errors.extend(check_schema_sync())

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
