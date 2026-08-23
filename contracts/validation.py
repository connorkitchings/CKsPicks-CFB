#!/usr/bin/env python3
"""Validate that contracts/ files are in sync across Python and TypeScript."""

import ast
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


def _literal_dict_keys(tree: ast.AST, *, function_name: str | None) -> set[str]:
    nodes = tree.body if isinstance(tree, ast.Module) else []
    if function_name:
        nodes = [
            node
            for node in nodes
            if isinstance(node, ast.FunctionDef) and node.name == function_name
        ]
    for node in ast.walk(ast.Module(body=nodes, type_ignores=[])):
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "run_record"
                for target in node.targets
            )
            and isinstance(node.value, ast.Dict)
        ):
            return {
                key.value
                for key in node.value.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            }
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
            return {
                key.value
                for key in node.value.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            }
    return set()


def extract_publication_record_keys(filepath: Path) -> dict[str, set[str]]:
    """Extract the concrete mapping keys supplied to publication SQL statements."""
    tree = ast.parse(filepath.read_text(), filename=str(filepath))
    return {
        "record": _literal_dict_keys(tree, function_name="_row_to_record"),
        "run_record": _literal_dict_keys(tree, function_name="publish_week"),
        "activation": {"season", "week", "run_id"},
    }


def extract_insert_contracts(
    filepath: Path,
) -> dict[str, tuple[str, set[str], set[str]]]:
    """Return SQL constant -> (table, inserted columns, named placeholders)."""
    tree = ast.parse(filepath.read_text(), filename=str(filepath))
    contracts: dict[str, tuple[str, set[str], set[str]]] = {}
    insert_pattern = re.compile(
        r"INSERT INTO\s+(?:\w+\.)?(\w+)\s*\((.*?)\)\s*VALUES\s*\((.*?)\)",
        re.IGNORECASE | re.DOTALL,
    )
    for node in tree.body:
        if not (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            continue
        match = insert_pattern.search(node.value.value)
        if not match:
            continue
        columns = set(re.findall(r"\b([a-z][a-z0-9_]*)\b", match.group(2)))
        placeholders = set(re.findall(r"%\((\w+)\)s", match.group(3)))
        contracts[node.targets[0].id] = (match.group(1), columns, placeholders)
    return contracts


def check_publication_contracts(
    *,
    schema_path: Path | None = None,
    publisher_path: Path | None = None,
) -> list[str]:
    """Validate Python publication writes against the canonical SQL DDL.

    This deliberately validates the concrete INSERT/UPSERT surface instead of
    claiming that lake-schema imports prove database contract alignment.
    """
    schema_path = schema_path or CONTRACTS_DIR / "schema.sql"
    publisher_path = publisher_path or ROOT / "scripts/pipeline/publish_to_db.py"
    tables = extract_sql_table_columns(schema_path)
    records = extract_publication_record_keys(publisher_path)
    inserts = extract_insert_contracts(publisher_path)
    providers = {
        "UPSERT_SQL": records["record"],
        "INSERT_RUN_SQL": records["run_record"],
        "INSERT_PREDICTION_SQL": records["record"] | {"run_id"},
        "INSERT_MARKET_SNAPSHOT_SQL": records["record"],
        "UPDATE_CURRENT_WEEK_SQL": records["activation"],
    }
    errors: list[str] = []
    for name, supplied in providers.items():
        if name not in inserts:
            errors.append(
                f"Publication SQL constant {name} is missing or is not an INSERT"
            )
            continue
        table, columns, placeholders = inserts[name]
        canonical_columns = tables.get(table)
        if canonical_columns is None:
            errors.append(f"{name} writes unknown canonical table {table}")
            continue
        unknown_columns = columns - canonical_columns
        if unknown_columns:
            errors.append(
                f"{name} writes columns absent from schema.sql {table}: {sorted(unknown_columns)}"
            )
        missing_placeholders = placeholders - supplied
        if missing_placeholders:
            errors.append(
                f"{name} placeholders are not supplied by its record builder: {sorted(missing_placeholders)}"
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


def main():
    all_errors = []
    all_errors.extend(check_teams_sync())
    all_errors.extend(check_schema_sync())
    all_errors.extend(check_migration_history())
    all_errors.extend(check_publication_contracts())

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
