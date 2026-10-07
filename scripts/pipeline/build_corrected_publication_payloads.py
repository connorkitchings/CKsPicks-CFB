#!/usr/bin/env python3
"""Build the corrected team-statistics release payloads from the published 6A run.

Read-only everywhere: the published 6A rebuild is read from Preview R2 through hash-checked
access, the "before" rows come from the database named by ``--before-environment`` in a
read-only transaction, and the payloads are written only to ``--out-dir`` (never to R2 or a
database). The "after" rows are the website ``team_season_stats`` rebuilt from the corrected
2026 Silver with the repository's own builder, carrying the corrected lineage in
``source_versions`` (never the previous rows' provenance; see Contract 04 Amendment 6).

Run the database side through the restricted wrapper, for example:

    zsh scripts/ops/with_production_pipeline_env.sh uv run python \\
        scripts/pipeline/build_corrected_publication_payloads.py --out-dir <dir>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

import psycopg
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload  # noqa: E402
from cks_picks_cfb.data.storage import get_storage  # noqa: E402
from cks_picks_cfb.rebuild import release_payloads as rp  # noqa: E402
from cks_picks_cfb.rebuild.published import PublishedRun  # noqa: E402
from cks_picks_cfb.rebuild.published_comparison import season_stats_frame  # noqa: E402

PUBLISHED_RUN_ID = "6a-rebuild-20261004-r1"
ROOT_KEY = f"rebuild/6a/{PUBLISHED_RUN_ID}/root-manifest.json"
ROOT_RAW_SHA256 = "741d262f116a51db0d33ffc84efb22aa5ff4093e7da38535073343aee1fa85d0"
PIN_FILE = REPO_ROOT / "conf" / "rebuild" / "silver_2026_parents_v1.json"
SEASON = 2026
URL_ENV = {"preview": "PREVIEW_DATABASE_URL", "production": "DATABASE_URL"}


def open_published_run(storage: Any) -> PublishedRun:
    """The published 6A run, pinned by the raw SHA-256 of its root manifest."""
    raw = storage.read_bytes(ROOT_KEY)
    if hashlib.sha256(raw).hexdigest() != ROOT_RAW_SHA256:
        raise SystemExit("published 6A root manifest changed")
    root = json.loads(raw)
    verify_signed_payload(root, label="published root manifest")
    run = object.__new__(PublishedRun)
    run.context = None
    run.storage = storage
    run.root = root
    run.prefix = f"{root.get('namespace', 'rebuild/6a/')}{root['run_id']}/"
    run.objects = dict(root["objects"])
    return run


def silver_version(run: PublishedRun, dataset: str) -> str:
    """The version id of the rebuild's 2026 Silver dataset (exactly one)."""
    found = []
    for key in sorted(run.objects):
        if not key.startswith(f"lake/silver/dataset={dataset}/") or not key.endswith(
            "/manifest.json"
        ):
            continue
        manifest = json.loads(run.read(key))
        if [int(s) for s in manifest["partitions"].get("seasons", [])] == [SEASON]:
            found.append(key.split("version=")[1].split("/")[0])
    if len(found) != 1:
        raise SystemExit(f"expected one 2026 {dataset} version, found {found}")
    return found[0]


def corrected_source_versions(
    run: PublishedRun, pins: dict[str, Any]
) -> dict[str, str]:
    parents = {p["dataset"]: p for p in pins["parents"]}
    return {
        "lineage": f"corrected:{PUBLISHED_RUN_ID}",
        "rebuild_root_sha256": ROOT_RAW_SHA256,
        "byplay": silver_version(run, "byplay"),
        "drives": silver_version(run, "drives"),
        "games": parents["games"]["version_id"],
        "game_outcomes": pins["game_outcomes"]["version_id"],
        "teams": parents["teams"]["version_id"],
    }


def write_payload(out_dir: Path, name: str, payload: dict[str, Any]) -> dict[str, Any]:
    raw, digest = rp.payload_bytes(payload)
    (out_dir / f"{name}.json").write_bytes(raw)
    return {
        "file": f"{name}.json",
        "raw_sha256": digest,
        "manifest_sha256": payload["manifest_sha256"],
        "rows": payload["row_count"],
    }


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--before-environment", choices=sorted(URL_ENV), default="production"
    )
    args = parser.parse_args()
    if REPO_ROOT / "data" in [args.out_dir.resolve(), *args.out_dir.resolve().parents]:
        raise SystemExit("output cannot be the repository ./data directory")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    storage = get_storage(environment="preview")
    run = open_published_run(storage)
    pins = json.loads(PIN_FILE.read_text())
    versions = corrected_source_versions(run, pins)
    frame, fbs_source = season_stats_frame(run, storage, pins, set())
    after_rows = rp.stat_rows(frame, versions)
    scope = rp.scope_of(after_rows)

    url = os.getenv(URL_ENV[args.before_environment])
    if not url:
        raise SystemExit(f"{URL_ENV[args.before_environment]} is not set")
    with psycopg.connect(url) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            cur.execute("SELECT current_user, current_setting('transaction_read_only')")
            identity = list(cur.fetchone())
            before_rows = rp.database_stat_rows(cur, scope)

    parents = {
        "published_run_id": PUBLISHED_RUN_ID,
        "published_root_raw_sha256": ROOT_RAW_SHA256,
        "silver_2026_parents_file": PIN_FILE.name,
        "silver_2026_parents_sha256": hashlib.sha256(PIN_FILE.read_bytes()).hexdigest(),
        "fbs_team_source": fbs_source,
    }
    before = rp.team_stats_payload(
        before_rows,
        environment=args.before_environment,
        season=SEASON,
        parents={"captured_from": "database", "database_identity": identity},
        label="before (database rows)",
    )
    after = rp.team_stats_payload(
        after_rows,
        environment=args.before_environment,
        season=SEASON,
        parents=parents,
        label="after (corrected lineage)",
    )
    summary = {
        "environment": args.before_environment,
        "scope": scope,
        "source_versions_after": versions,
        "before": write_payload(args.out_dir, "team-stats-before", before),
        "after": write_payload(args.out_dir, "team-stats-after", after),
        "comparison": rp.compare_stats(before_rows, after_rows),
    }
    (args.out_dir / "team-stats-build-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, default=str)
    )
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    return 0 if summary["comparison"]["same_key_set"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
