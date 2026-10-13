#!/usr/bin/env python3
"""Capture (or re-verify) the published Preview baseline Task 4 r2 compares against.

Read-only. One REPEATABLE READ, read-only transaction on the Preview pipeline login
(``DATABASE_URL``) records:
- for each matchup table, a content fingerprint (sha256 of canonically ordered rows,
  every column as Postgres text) and row count per (season, week, provenance), where
  provenance is the component's rating run (``v5_snapshot_id`` prefix), the stats and
  adjusted rows' ``rating_manifest_sha256`` and the game log's
  ``measurement_manifest_sha256``;
- the ``matchup_data_publications`` rows (manifest URIs and hashes) of the two published
  rating runs.

The baseline also declares, explicitly and with fixed counts, the only keys a rebuild may
add: the Week 5 (56) and Week 6 (58) game ids from the source lock's chained extensions
for ``team_game_measurements``, and the 276 new ``team_rating_components`` ids from the
build output. A declared key that is already published is refused, so published rows can
never be relabelled as additions. ``check_additions()`` applies the declaration: a
published row missing from the build, an extra row outside the declared set, or a
declared key the build did not produce all fail.

    zsh scripts/ops/with_preview_env.sh uv run python \\
      scripts/pipeline/capture_task4_w6_comparison_baseline.py \\
      --component-additions <new component ids .json> --out <baseline.json>
    zsh scripts/ops/with_preview_env.sh uv run python \\
      scripts/pipeline/capture_task4_w6_comparison_baseline.py \\
      --verify conf/rebuild/task4_w6_comparison_baseline_v1.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

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


class BaselineError(ValueError):
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
            elif before[key]["sha256"] != after[key]["sha256"]:
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
        return {tuple(str(row[k]) for k in keys): row for row in rows}

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--verify", type=Path, help="baseline to re-capture and compare")
    mode.add_argument("--out", type=Path, help="where to write a new baseline")
    parser.add_argument("--component-additions", type=Path)
    args = parser.parse_args(argv)
    url = os.getenv("DATABASE_URL")
    if not url:
        print("Set DATABASE_URL (Preview pipeline login).", file=sys.stderr)
        return 2
    try:
        if args.verify:
            baseline = json.loads(args.verify.read_text())
            if baseline.get("schema_version") != SCHEMA or not baseline.get("tables"):
                raise BaselineError(f"{args.verify} is not a captured {SCHEMA}")
            current, _ = read_snapshot(url)
            problems = diff_captures(baseline, current)
            for problem in problems:
                print(f"DIFF: {problem}", file=sys.stderr)
            if problems:
                return 1
            print(f"Published baseline unchanged ({current['snapshot_at']}).")
            return 0
        if args.out.exists() and json.loads(args.out.read_text()).get("tables"):
            raise BaselineError(f"{args.out} already holds a capture; create once")
        if args.component_additions is None:
            raise BaselineError("--component-additions is required to capture")
        lock_raw = LOCK.read_bytes()
        declarations = {
            "team_game_measurements": measurement_declaration(
                json.loads(lock_raw), hashlib.sha256(lock_raw).hexdigest()
            ),
            "team_rating_components": component_declaration(args.component_additions),
        }
        current, rows = read_snapshot(url)
        for table, declaration in declarations.items():
            if overlap := declared_overlap(rows[table], declaration):
                raise BaselineError(
                    f"{table}: declared additions published: {overlap[:5]}"
                )
        baseline = {
            "schema_version": SCHEMA,
            "environment": "preview",
            "season": SEASON,
            "transaction": "read only, repeatable read, cks_preview_pipeline",
            **current,
            "expected_additions": declarations,
        }
        args.out.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n")
        print(f"Baseline written to {args.out}.")
        return 0
    except BaselineError as exc:
        print(f"Refusing: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
