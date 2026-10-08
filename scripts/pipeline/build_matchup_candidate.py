#!/usr/bin/env python3
"""Candidate and previous matchup tables for a corrected rebuild, written locally.

Read-only everywhere: the published 6A run comes from Preview R2 through hash-checked
access, database rows are read in read-only transactions, and every output goes to
``--out-dir`` (parquet plus JSON). Three modes:

``capture``    read the four matchup tables, the season's game names and the published
               rating-run id from ``--database-environment`` (the "previous" rows);
``candidate``  rebuild the four tables from the published run's 2026 states with the
               repository's own builders and run the publisher's static gates;
``diff``       compare the candidate with the previous Production rows using the Task 4
               rules (set-aside added scope, recorded kickoff revisions, expected buckets),
               after proving Production equals Preview so Task 4's Preview comparison and
               control carry over.

    zsh scripts/ops/with_production_pipeline_env.sh uv run python \\
        scripts/pipeline/build_matchup_candidate.py capture --database-environment production ...
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from cks_picks_cfb.data import matchup_data as md  # noqa: E402
from cks_picks_cfb.data import matchup_publish as mp  # noqa: E402
from cks_picks_cfb.data.storage import get_storage  # noqa: E402
from cks_picks_cfb.rebuild import published_diff  # noqa: E402
from cks_picks_cfb.rebuild.published_comparison import (  # noqa: E402
    STATE_FILES,
    game_scope,
    kickoff_revision,
    lock_scope,
    week_scope,
)
from scripts.pipeline.build_corrected_publication_payloads import (  # noqa: E402
    SEASON,
    URL_ENV,
    open_published_run,
)

TABLES = tuple(md.TABLES)
METRIC_COLUMN = {
    "team_game_measurements": "measurement_id",
    "team_possession_stats": "metric",
    "team_possession_adjusted": "measurement_id",
    "team_rating_components": None,
}
PROVENANCE = {
    "rating_manifest_sha256",
    "measurement_manifest_sha256",
    "source_manifest_sha256",
    "source_versions",
}


def _plain(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return [_plain(v) for v in value.tolist()]
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def jsonb_as_text(frame: pd.DataFrame, jsonb: tuple[str, ...]) -> pd.DataFrame:
    """JSON columns as canonical text, as the database returns them (parquet keeps text)."""
    out = frame.copy()
    for column in jsonb:
        if column in out.columns:
            out[column] = [
                None
                if v is None
                else json.dumps(_plain(v), sort_keys=True, default=str)
                for v in out[column]
            ]
    return out


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_database(environment: str, out: Path) -> dict[str, Any]:
    import psycopg

    from cks_picks_cfb.rebuild.published_comparison import fetch_table

    url = os.getenv(URL_ENV[environment])
    if not url:
        raise SystemExit(f"{URL_ENV[environment]} is not set")
    target = out / f"previous-{environment}"
    target.mkdir(parents=True, exist_ok=True)
    files = {}
    with psycopg.connect(url) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            cur.execute("SELECT current_user, current_setting('transaction_read_only')")
            identity = list(cur.fetchone())
            names = sorted(mp.season_game_names(cur, SEASON))
            cur.execute(
                "SELECT DISTINCT split_part(v5_snapshot_id, ':', 1) "
                "FROM team_rating_components WHERE season = %s",
                (SEASON,),
            )
            run_ids = sorted(row[0] for row in cur.fetchall())
            for table, (columns, _keys, jsonb) in md.TABLES.items():
                frame = fetch_table(
                    cur, table, columns, jsonb, "season = %s", (SEASON,)
                )
                path = target / f"{table}.parquet"
                frame.to_parquet(path)
                files[table] = {"rows": len(frame), "sha256": sha256_file(path)}
    meta = {
        "environment": environment,
        "database_identity": identity,
        "rating_run_ids": run_ids,
        "game_names": names,
        "tables": files,
    }
    (target / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True))
    return meta


def build_candidate(args: argparse.Namespace) -> dict[str, Any]:
    from contracts.teams import TEAM_LOGO_MAP

    previous = json.loads(
        (args.out_dir / f"previous-{args.reference}" / "meta.json").read_text()
    )
    if len(previous["rating_run_ids"]) != 1:
        raise SystemExit(f"published components name runs {previous['rating_run_ids']}")
    storage = get_storage(environment="preview")
    run = open_published_run(storage, args.run_id, args.root_sha256)
    lock = json.loads(args.lock.read_text())
    states = {name: run.frame(f"states_2026/{name}.parquet") for name in STATE_FILES}
    cutoffs = {int(w): pd.Timestamp(c) for w, c in lock["post_week_cutoffs"].items()}
    root_sha = run.root["manifest_sha256"]
    artifacts = mp.Artifacts(
        lineage="intended_update",
        run_id=previous["rating_run_ids"][0],
        candidate_id=str(states["pregame_roles"]["candidate_id"].iloc[0]),
        rating_manifest={},
        rating_sha256=root_sha,
        rating_uri="",
        measurement_manifest={},
        measurement_sha256=root_sha,
        measurement_uri="",
        observations=states["observations"],
        observations_records_sha="corrected",
        observations_version_id="corrected",
        priors=states["priors"],
        pregame_roles=states["pregame_roles"],
        current_roles=states["current_roles"],
        post_week_cutoffs=cutoffs,
    )
    names = set(previous["game_names"])
    built = mp.build_payload(
        artifacts, season=SEASON, game_names=names, alias_map=TEAM_LOGO_MAP
    )
    gates = mp.run_static_gates(built, names)
    target = args.out_dir / "candidate"
    target.mkdir(parents=True, exist_ok=True)
    files = {}
    for table, frame in built.payload.frames.items():
        path = target / f"{table}.parquet"
        jsonb_as_text(frame, md.TABLES[table][2]).to_parquet(path)
        files[table] = {"rows": len(frame), "sha256": sha256_file(path)}
    meta = {
        "published_run_id": args.run_id,
        "published_root_raw_sha256": args.root_sha256,
        "as_of_weeks": built.weeks,
        "tables": files,
        "static_gates": [dataclasses.asdict(g) for g in gates],
        "static_gates_passed": all(g.ok for g in gates),
        "not_run": [
            "database gates (need a successor-format rating manifest and its v5 "
            "snapshots; the corrected lineage has none yet)"
        ],
    }
    (target / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True))
    return meta


def compare_tables(
    out: Path, lock: dict[str, Any], control_matches: bool
) -> dict[str, Any]:
    scope = lock_scope(lock)
    added = {
        "team_game_measurements": game_scope(scope),
        "team_possession_stats": week_scope(scope),
        "team_possession_adjusted": week_scope(scope),
        "team_rating_components": week_scope(scope),
    }
    tables = {}
    equivalence = {}
    for table, (columns, keys, jsonb) in md.TABLES.items():
        values = [c for c in columns if c not in keys and c not in PROVENANCE]
        production = pd.read_parquet(out / "previous-production" / f"{table}.parquet")
        preview = pd.read_parquet(out / "previous-preview" / f"{table}.parquet")
        same = published_diff.diff_frames(
            production,
            preview,
            keys=keys,
            columns=[c for c in columns if c not in keys],
            metric_of=lambda row: None,
            jsonb=[c for c in jsonb if c in columns],
            expected=set(),
        )
        equivalence[table] = {
            "rows_production": same["rows_built"],
            "rows_preview": same["rows_published"],
            "identical": same["rows_with_a_difference"] == 0
            and not same["population"]["only_built"]
            and not same["population"]["only_published"],
        }
        candidate = pd.read_parquet(out / "candidate" / f"{table}.parquet")
        components = table == "team_rating_components"
        column = METRIC_COLUMN[table]
        expected = None
        if components:
            expected = (
                published_diff.EXPECTED_TO_DIFFER
                | {"kickoff_revision"}
                | ({"history_correction"} if control_matches else set())
            )
        tables[table] = published_diff.diff_frames(
            candidate,
            production,
            keys=keys,
            columns=values,
            metric_of=(
                (lambda row: "history_correction")
                if components
                else (lambda row, c=column: row[c])
            ),
            jsonb=[c for c in jsonb if c in values],
            expected=expected,
            added_scope=added[table],
            bucket_override=kickoff_revision(scope) if components else None,
        )
    return {
        "previous_equals_preview": equivalence,
        "tables": tables,
        "summary": published_diff.summarize(tables),
    }


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["capture", "candidate", "diff"])
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--database-environment", choices=sorted(URL_ENV))
    parser.add_argument("--run-id")
    parser.add_argument("--root-sha256")
    parser.add_argument("--lock", type=Path)
    parser.add_argument(
        "--reference",
        choices=sorted(URL_ENV),
        default="production",
        help="which captured environment supplies game names and the rating-run id",
    )
    parser.add_argument(
        "--task4-report", type=Path, help="the Task 4 published_comparison report.json"
    )
    args = parser.parse_args()
    if REPO_ROOT / "data" in [args.out_dir.resolve(), *args.out_dir.resolve().parents]:
        raise SystemExit("output cannot be the repository ./data directory")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    if args.mode == "capture":
        if not args.database_environment:
            raise SystemExit("capture needs --database-environment")
        result = read_database(args.database_environment, args.out_dir)
    elif args.mode == "candidate":
        if not (args.run_id and args.root_sha256 and args.lock):
            raise SystemExit("candidate needs --run-id, --root-sha256 and --lock")
        result = build_candidate(args)
    else:
        if not (args.lock and args.task4_report):
            raise SystemExit("diff needs --lock and --task4-report")
        report = json.loads(args.task4_report.read_text())
        control = bool(report["control_baseline_history"]["matches_published"])
        result = compare_tables(
            args.out_dir, json.loads(args.lock.read_text()), control
        )
        result["task4_control_matches_published"] = control
        (args.out_dir / "matchup-diff.json").write_text(
            json.dumps(result, indent=2, sort_keys=True, default=str)
        )
    print(json.dumps(result, indent=2, sort_keys=True, default=str)[:6000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
