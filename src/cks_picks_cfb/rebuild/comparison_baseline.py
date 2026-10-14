"""Canonical read-only Task 4 baseline capture and population enforcement."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from cks_picks_cfb.rebuild.errors import GateError

SCHEMA = "task4_w6_comparison_baseline_v1"
SEASON = 2026
RATING_RUNS = (
    "v5-intended-update-2026-ratings-v1",
    "v5-intended-update-2026-corrected-w6live-r1",
)
LOCK = Path("conf/rebuild/source_lock_2026_w6_v1.json")
#: Lock extension (post-week) -> expected number of newly final games.
MEASUREMENT_GAMES = {5: 56, 6: 58}
NEW_COMPONENTS = 276
#: table -> week column; provenance comes from ``provenance()``.
WEEK_COLUMN = {
    "team_game_measurements": "week",
    "team_possession_stats": "as_of_week",
    "team_possession_adjusted": "as_of_week",
    "team_rating_components": "as_of_week",
}
PUBLICATION_COLUMNS = (
    "publication_id",
    "season",
    "lineage",
    "rating_manifest_uri",
    "rating_manifest_sha256",
    "measurement_manifest_uri",
    "measurement_manifest_sha256",
    "observations_records_sha",
    "as_of_weeks",
    "rating_scale",
    "row_counts",
    "payload_sha256",
    "code_sha",
    "environment",
    "published_at",
)


class BaselineError(GateError):
    """The capture, the declaration or a comparison does not hold."""


def provenance(table: str, row: Mapping[str, str | None]) -> str | None:
    if table == "team_rating_components":
        return str(row["v5_snapshot_id"]).split(":", 1)[0]
    if table == "team_game_measurements":
        return row["measurement_manifest_sha256"]
    return row["rating_manifest_sha256"]


def fingerprint(
    table: str,
    rows: Iterable[Mapping[str, str | None]],
    columns: Iterable[str],
    keys: Iterable[str],
) -> list[dict[str, Any]]:
    """Row count and sha256 of canonically ordered rows, per (season, week, provenance)."""
    columns, keys = list(columns), list(keys)
    groups: dict[tuple, list[tuple]] = {}
    for row in rows:
        group = (row["season"], row[WEEK_COLUMN[table]], provenance(table, row))
        ordered = tuple(row[k] for k in keys)
        groups.setdefault(group, []).append((ordered, [row[c] for c in columns]))
    out = []
    for (season, week, source), members in sorted(
        groups.items(), key=lambda item: tuple(str(v) for v in item[0])
    ):
        members.sort(key=lambda m: m[0])
        if any(a[0] == b[0] for a, b in zip(members, members[1:], strict=False)):
            raise BaselineError(f"{table}: duplicate primary key in a group")
        digest = hashlib.sha256()
        for _, values in members:
            digest.update(json.dumps(values, separators=(",", ":")).encode() + b"\n")
        out.append(
            {
                "season": season,
                "week": week,
                "provenance": source,
                "rows": len(members),
                "sha256": digest.hexdigest(),
            }
        )
    return out


def diff_captures(baseline: Mapping[str, Any], current: Mapping[str, Any]) -> list[str]:
    """Every difference between two captures' tables and publications (empty = equal)."""
    # Reports are independent inputs too: never let dict indexing hide duplicate groups.
    for label, value in (("baseline", baseline), ("current", current)):
        try:
            if not isinstance(value["tables"], Mapping) or not isinstance(
                value["publications"], Mapping
            ):
                raise BaselineError(f"{label}: malformed capture structure")
            for table, groups in value["tables"].items():
                if not isinstance(groups, list):
                    raise BaselineError(f"{label}: malformed fingerprint groups")
                seen = set()
                for group in groups:
                    key = (group["season"], group["week"], group["provenance"])
                    if key in seen:
                        raise BaselineError(
                            f"{label} {table}: duplicate fingerprint group"
                        )
                    seen.add(key)
                    digest = group["sha256"]
                    if (
                        int(group["rows"]) <= 0
                        or len(digest) != 64
                        or any(c not in "0123456789abcdef" for c in digest)
                    ):
                        raise BaselineError(f"{label} {table}: invalid fingerprint")
        except (KeyError, TypeError, ValueError) as error:
            raise BaselineError(f"{label}: malformed capture: {error}") from error
    problems: list[str] = []
    for table in sorted(set(baseline["tables"]) | set(current["tables"])):
        before = {
            (g["season"], g["week"], g["provenance"]): g
            for g in baseline["tables"].get(table, [])
        }
        after = {
            (g["season"], g["week"], g["provenance"]): g
            for g in current["tables"].get(table, [])
        }
        for key in sorted(set(before) | set(after), key=lambda k: tuple(map(str, k))):
            if key not in after:
                problems.append(f"{table} {key}: group removed")
            elif key not in before:
                problems.append(f"{table} {key}: group added")
            elif (before[key]["sha256"], before[key]["rows"]) != (
                after[key]["sha256"],
                after[key]["rows"],
            ):
                problems.append(
                    f"{table} {key}: content changed "
                    f"(rows {before[key]['rows']} -> {after[key]['rows']})"
                )
    if baseline["publications"] != current["publications"]:
        problems.append("publication metadata of the rating runs changed")
    return problems


def declared_overlap(
    published: Iterable[Mapping[str, str | None]], declaration: Mapping[str, Any]
) -> list[str]:
    """Declared addition keys that are already published (must be empty)."""
    declared = {str(v) for v in declaration["values"]}
    return sorted(
        {str(row[declaration["column"]]) for row in published} & declared, key=str
    )


def check_additions(
    table: str,
    published: Iterable[Mapping[str, Any]],
    built: Iterable[Mapping[str, Any]],
    keys: Iterable[str],
    declaration: Mapping[str, Any] | None,
) -> list[str]:
    """Population check of a build against the published rows and the declaration.

    Missing published rows always fail; they are never excused as additions. Extra rows
    must carry a declared value, every declared value must be added, and no published row
    may carry a declared value.
    """
    keys = list(keys)

    def index(rows):
        indexed = {}
        for row in rows:
            key = tuple(str(row[k]) for k in keys)
            if key in indexed:
                raise BaselineError(f"{table}: duplicate primary key {key}")
            indexed[key] = row
        return indexed

    old, new = index(published), index(built)
    problems = []
    if missing := set(old) - set(new):
        problems.append(
            f"{table}: {len(missing)} published rows missing from the build"
        )
    extra = [new[k] for k in set(new) - set(old)]
    if declaration is None:
        if extra:
            problems.append(f"{table}: {len(extra)} rows added with no declaration")
        return problems
    column, declared = declaration["column"], {str(v) for v in declaration["values"]}
    if len(declared) != declaration["count"]:
        problems.append(
            f"{table}: declaration lists {len(declared)} values, count says "
            f"{declaration['count']}"
        )
    if overlap := declared_overlap(old.values(), declaration):
        problems.append(f"{table}: declared values already published: {overlap[:5]}")
    added = {str(row[column]) for row in extra}
    if outside := added - declared:
        problems.append(
            f"{table}: rows added outside the declaration: {sorted(outside)[:5]}"
        )
    if absent := declared - added:
        problems.append(f"{table}: declared additions not built: {sorted(absent)[:5]}")
    return problems


def measurement_declaration(lock: Mapping[str, Any], lock_sha: str) -> dict[str, Any]:
    """Week 5 and Week 6 game ids from the lock's chained extensions, counts enforced."""
    found: dict[int, list[int]] = {}
    extension = lock.get("extends")
    while extension:
        week = int(extension["added_post_week"])
        if week in found:
            raise BaselineError(f"lock extends post-week {week} twice")
        found[week] = [int(g) for g in extension["newly_final_game_ids"]]
        extension = extension.get("previous_extension")
    counts = {week: len(found.get(week, [])) for week in MEASUREMENT_GAMES}
    if counts != MEASUREMENT_GAMES:
        raise BaselineError(
            f"lock extension games {counts}; expected {MEASUREMENT_GAMES}"
        )
    games = sorted(g for week in MEASUREMENT_GAMES for g in found[week])
    if len(set(games)) != len(games):
        raise BaselineError("a game is newly final in two extensions")
    return {
        "column": "game_id",
        "count": len(games),
        "counts_by_post_week": {str(w): n for w, n in MEASUREMENT_GAMES.items()},
        "source": {"uri": str(LOCK), "sha256": lock_sha},
        "values": games,
    }


def component_declaration(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    ids = json.loads(raw)
    if not isinstance(ids, list) or len(set(map(str, ids))) != len(ids):
        raise BaselineError("component additions must be a JSON list of unique ids")
    if len(ids) != NEW_COMPONENTS:
        raise BaselineError(
            f"{len(ids)} component additions; expected {NEW_COMPONENTS}"
        )
    return {
        "column": "component_id",
        "count": NEW_COMPONENTS,
        "source": {"uri": str(path), "sha256": hashlib.sha256(raw).hexdigest()},
        "values": sorted(map(str, ids)),
    }


def capture(cur) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    """Fingerprints, publications and the raw published rows, in the caller's snapshot."""
    from cks_picks_cfb.data import matchup_data as md

    tables, rows_by_table = {}, {}
    for table, (columns, keys, _jsonb) in md.TABLES.items():
        select = ", ".join(f"{c}::text" for c in columns)
        cur.execute(f"SELECT {select} FROM {table} WHERE season = %s", (SEASON,))  # noqa: S608
        rows = [dict(zip(columns, r, strict=True)) for r in cur.fetchall()]
        rows_by_table[table] = rows
        tables[table] = fingerprint(table, rows, columns, keys)
    select = ", ".join(f"{c}::text" for c in PUBLICATION_COLUMNS)
    cur.execute(
        f"SELECT {select} FROM matchup_data_publications WHERE season = %s "  # noqa: S608
        "ORDER BY publication_id",
        (SEASON,),
    )
    publications: dict[str, list[dict[str, Any]]] = {run: [] for run in RATING_RUNS}
    for values in cur.fetchall():
        row = dict(zip(PUBLICATION_COLUMNS, values, strict=True))
        run = row["rating_manifest_uri"].rstrip("/").split("/")[-2]
        if run in publications:
            publications[run].append(row)
    if empty := [run for run, rows in publications.items() if not rows]:
        raise BaselineError(f"no publication rows for rating runs {empty}")
    cur.execute("SELECT now()")
    snapshot_at = str(cur.fetchone()[0])
    return (
        {"snapshot_at": snapshot_at, "tables": tables, "publications": publications},
        rows_by_table,
    )


def read_snapshot(url: str):
    import psycopg

    from cks_picks_cfb.rebuild.targets import assert_preview_database

    with psycopg.connect(url) as conn:
        conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
        conn.read_only = True
        with conn.cursor() as cur:
            assert_preview_database(cur)
            result = capture(cur)
        conn.rollback()
    return result


def validate_baseline(raw: bytes, lock_raw: bytes | None = None) -> dict[str, Any]:
    """Reject incomplete captures and unbound or malformed additions."""
    try:
        baseline = json.loads(raw)
        if (
            baseline["schema_version"],
            baseline["environment"],
            baseline["season"],
        ) != (SCHEMA, "preview", SEASON):
            raise BaselineError("not a Preview Task 4 comparison baseline")
        if set(baseline["tables"]) != set(WEEK_COLUMN):
            raise BaselineError("baseline must fingerprint every matchup table")
        for groups in baseline["tables"].values():
            if not isinstance(groups, list) or not groups:
                raise BaselineError("baseline table fingerprints are empty")
            seen = set()
            for group in groups:
                key = (group["season"], group["week"], group["provenance"])
                if key in seen or int(group["rows"]) <= 0:
                    raise BaselineError(
                        "invalid or duplicate baseline fingerprint group"
                    )
                seen.add(key)
                digest = group["sha256"]
                if len(digest) != 64 or any(
                    c not in "0123456789abcdef" for c in digest
                ):
                    raise BaselineError("invalid baseline fingerprint hash")
        if set(baseline["publications"]) != set(RATING_RUNS) or not all(
            baseline["publications"].values()
        ):
            raise BaselineError("baseline lacks both rating publication populations")
        for rows in baseline["publications"].values():
            if not isinstance(rows, list) or any(
                set(row) != set(PUBLICATION_COLUMNS) for row in rows
            ):
                raise BaselineError("malformed rating publication metadata")
        w6 = sum(
            int(g["rows"])
            for g in baseline["tables"]["team_rating_components"]
            if int(g["week"]) == 6
        )
        if w6 != 508:
            raise BaselineError(
                "baseline must retain all 508 published Week 6 components"
            )
        declarations = baseline["expected_additions"]
        if set(declarations) != {"team_game_measurements", "team_rating_components"}:
            raise BaselineError("baseline addition tables differ")
        for table, column, count in (
            ("team_game_measurements", "game_id", 114),
            ("team_rating_components", "component_id", NEW_COMPONENTS),
        ):
            d = declarations[table]
            if (
                d["column"] != column
                or d["count"] != count
                or len(d["values"]) != count
            ):
                raise BaselineError(f"{table}: invalid addition declaration")
            if len(set(map(str, d["values"]))) != count:
                raise BaselineError(f"{table}: duplicate declared addition")
            if table == "team_rating_components":
                if component_declaration(Path(d["source"]["uri"])) != d:
                    raise BaselineError("component declaration source bytes changed")
        if lock_raw is not None and declarations[
            "team_game_measurements"
        ] != measurement_declaration(
            json.loads(lock_raw), hashlib.sha256(lock_raw).hexdigest()
        ):
            raise BaselineError("measurement declaration differs from the pinned lock")
        return baseline
    except (KeyError, TypeError, ValueError, OSError) as error:
        if isinstance(error, BaselineError):
            raise
        raise BaselineError(f"malformed comparison baseline: {error}") from error


def derive_component_ids(published, built, first_as_of_week: int | None) -> list[str]:
    """Enumerate exactly the approved new week, retaining every published key."""
    old = list(published)
    new = list(built)
    for label, rows in (("published", old), ("built", new)):
        ids = [str(row["component_id"]) for row in rows]
        if len(set(ids)) != len(ids):
            raise BaselineError(f"{label}: duplicate component primary key")
        if any(int(row["season"]) != SEASON for row in rows):
            raise BaselineError(f"{label}: unexpected component season")
    if sum(int(row["as_of_week"]) == 6 for row in old) != 508:
        raise BaselineError("expected all 508 published Week 6 components")
    old_ids = {str(row["component_id"]) for row in old}
    new_ids = {str(row["component_id"]) for row in new}
    if old_ids - new_ids:
        raise BaselineError("published components missing from reconstructed build")
    extra = [row for row in new if str(row["component_id"]) not in old_ids]
    if first_as_of_week != 7 or any(int(row["as_of_week"]) != 7 for row in extra):
        raise BaselineError("new components outside the declared as-of-week 7 scope")
    ids = sorted(str(row["component_id"]) for row in extra)
    if len(ids) != NEW_COMPONENTS:
        raise BaselineError(
            f"{len(ids)} component additions; expected {NEW_COMPONENTS}"
        )
    return ids


def enforce_populations(published, rebuilt, declarations) -> dict[str, Any]:
    from cks_picks_cfb.data import matchup_data as md

    results = {}
    for table, declaration in declarations.items():
        old, new = published[table], rebuilt[table]
        problems = check_additions(table, old, new, md.TABLES[table][1], declaration)
        if table == "team_rating_components":
            derive_component_ids(old, new, 7)
        if problems:
            raise BaselineError("; ".join(problems))
        keys = md.TABLES[table][1]
        old_keys = {tuple(str(row[k]) for k in keys) for row in old}
        new_keys = {tuple(str(row[k]) for k in keys) for row in new}
        results[table] = {
            "passed": True,
            "published_rows": len(old),
            "built_rows": len(new),
            "added_rows": len(new_keys - old_keys),
            "declaration": declaration,
        }
    return results
