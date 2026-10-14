#!/usr/bin/env python3
"""Capture (or re-verify) the published Preview baseline Task 4 r2 compares against.

Read-only. One REPEATABLE READ, read-only transaction on the Preview pipeline login
(``PREVIEW_DATABASE_URL``) records:
- for each matchup table, a content fingerprint (sha256 of canonically ordered rows,
  every column as Postgres text) and row count per (season, week, provenance), where
  provenance is the component's rating run (``v5_snapshot_id`` prefix), the stats and
  adjusted rows' ``rating_manifest_sha256`` and the game log's
  ``measurement_manifest_sha256``;
- the ``matchup_data_publications`` rows (manifest URIs and hashes) of the two published
  rating runs.

The baseline also declares, explicitly and with fixed counts, the only keys a rebuild may
add: the Week 5 (56) and Week 6 (58) game ids from the source lock's chained extensions
for ``team_game_measurements``, and the 276 new ``team_rating_components`` ids derived from the
hash-checked published 6A states. A declared key that is already published is refused, so published rows can
never be relabelled as additions. ``check_additions()`` applies the declaration: a
published row missing from the build, an extra row outside the declared set, or a
declared key the build did not produce all fail.

    zsh scripts/ops/with_preview_env.sh uv run python \\
      scripts/pipeline/capture_task4_w6_comparison_baseline.py \\
      --derive-component-additions --plan conf/rebuild/6a_task4_w6_v2.yaml \\
      --out conf/rebuild/task4_w6_component_additions_v1.json
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
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from cks_picks_cfb.rebuild import comparison_baseline as shared  # noqa: E402
from cks_picks_cfb.rebuild.errors import RebuildError  # noqa: E402

# Preserve existing importers of the original CLI helpers.
BaselineError = shared.BaselineError
LOCK, SCHEMA, SEASON = shared.LOCK, shared.SCHEMA, shared.SEASON
check_additions = shared.check_additions
component_declaration = shared.component_declaration
declared_overlap = shared.declared_overlap
diff_captures = shared.diff_captures
fingerprint = shared.fingerprint
measurement_declaration = shared.measurement_declaration
read_snapshot = shared.read_snapshot
validate_baseline = shared.validate_baseline


def derive_from_plan(path: Path, url: str) -> list[str]:
    """Hash-check comparison inputs, reconstruct in memory, never stage artifacts."""
    import psycopg
    import yaml

    from cks_picks_cfb.rebuild import common
    from cks_picks_cfb.rebuild import published_comparison as pc
    from cks_picks_cfb.rebuild.comparison_baseline import capture, derive_component_ids
    from cks_picks_cfb.rebuild.inputs import (
        no_implicit_latest,
        reject_legacy_parents,
        resolve_input,
    )
    from cks_picks_cfb.rebuild.orchestrator import StageContext
    from cks_picks_cfb.rebuild.plan import RebuildPlan
    from cks_picks_cfb.rebuild.targets import assert_preview_database

    plan = RebuildPlan.from_dict(yaml.safe_load(path.read_text()))
    plan.validate()
    reject_legacy_parents(plan)
    stage = next(s for s in plan.stages if s.name == "published_comparison")
    context = StageContext(
        plan,
        stage,
        {},
        {},
        lambda *_: (_ for _ in ()).throw(
            BaselineError("derivation cannot read staged artifacts")
        ),
    )
    storage = common.preview_storage(context)
    pins = {pin.name: pin for pin in plan.inputs}
    checked = {}
    for name in stage.inputs:
        if name == "comparison_baseline":
            continue  # Only this unfinished pin is exempt from derivation.
        pin = pins[name]
        resolve_input(pin, repo_root=REPO_ROOT, read_remote=storage.read_bytes)
        raw = (
            (REPO_ROOT / pin.uri).read_bytes()
            if pin.kind == "git_file"
            else storage.read_bytes(pin.uri)
        )
        if hashlib.sha256(raw).hexdigest() != pin.sha256:
            raise BaselineError(f"input {name} changed during derivation")
        checked[name] = raw
    context.read_input = checked.__getitem__
    with no_implicit_latest(), psycopg.connect(url) as conn:
        conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
        conn.read_only = True
        with conn.cursor() as cur:
            assert_preview_database(cur)
            _, published = capture(cur)
            rebuilt, _, _, lock, _ = pc.reconstruct_frames(context, cur)
            additions = pc.table_additions(dict(plan.policies), pc.lock_scope(lock))
            ids = derive_component_ids(
                published["team_rating_components"],
                rebuilt["team_rating_components"].to_dict("records"),
                additions["team_rating_components"]["first_as_of_week"],
            )
        conn.rollback()
    return ids


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--verify", type=Path, help="baseline to re-capture and compare")
    mode.add_argument("--derive-component-additions", action="store_true")
    parser.add_argument(
        "--out", type=Path, help="exclusive output for capture or derived IDs"
    )
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--component-additions", type=Path)
    args = parser.parse_args(argv)
    url = os.getenv("PREVIEW_DATABASE_URL")
    if not url:
        print("Set PREVIEW_DATABASE_URL (Preview pipeline login).", file=sys.stderr)
        return 2
    try:
        if args.verify and (args.out or args.plan or args.component_additions):
            raise BaselineError("verify cannot capture or derive")
        if args.derive_component_additions:
            if not args.plan or not args.out or args.component_additions:
                raise BaselineError("derive requires --plan and --out only")
            if args.out.exists():
                raise BaselineError(f"{args.out} already exists; create once")
            ids = derive_from_plan(args.plan, url)
            with args.out.open("x") as handle:
                handle.write(json.dumps(ids, indent=2) + "\n")
            print(f"Derived {len(ids)} component IDs to {args.out}.")
            return 0
        if args.plan:
            raise BaselineError("--plan requires --derive-component-additions")
        if args.verify:
            baseline = validate_baseline(args.verify.read_bytes(), LOCK.read_bytes())
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
        if args.out is None:
            raise BaselineError("--out is required to capture")
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
        raw = (json.dumps(baseline, indent=2, sort_keys=True) + "\n").encode()
        validate_baseline(raw, lock_raw)
        args.out.write_bytes(raw)
        print(f"Baseline written to {args.out}.")
        return 0
    except (RebuildError, OSError, ValueError) as exc:
        print(f"Refusing: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
