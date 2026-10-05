#!/usr/bin/env python3
"""One-off, read-only: pin the normalized Silver the Step 5 byplay was built from.

Reads each season's legacy ``byplay`` manifest (reached through the approved repair-v2
parent) and records, per season, the exact parent versions of that build plus the legacy
derived datasets kept only for like-for-like comparison. The output is a tracked file that
the 6A ``silver`` stage pins by hash; the stage never reads the legacy chain at run time
for its inputs.

    PYTHONPATH=src:. uv run python scripts/pipeline/pin_6a_silver_parents.py --out <file>
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv

from cks_picks_cfb.data.storage import get_storage
from scripts.research.run_data_first_possession_measurements import _repair, _sources

REPAIR_URI = (
    "artifacts/research/data-first-football-v1/repair/v2/runs/"
    "repair-v2-20260909T1417Z/repair-manifest.json"
)
PARENT_DATASETS = (
    "plays",
    "fbs_involved_games",
    "teams",
    "team_game_stats",
    "data_corrections",
)
SCHEMAS = {
    "plays": "plays_v1",
    "fbs_involved_games": "fbs_involved_games_v1",
    "teams": "teams_v1",
    "team_game_stats": "team_game_stats_v1",
    "data_corrections": "data_corrections_v1",
}


def _entry(storage, dataset: str, version_id: str) -> dict:
    manifest_key = f"lake/silver/dataset={dataset}/version={version_id}/manifest.json"
    if not storage.exists(manifest_key):
        raise SystemExit(f"parent manifest not found: {manifest_key}")
    manifest = json.loads(storage.read_bytes(manifest_key))
    return {
        "dataset": dataset,
        "version_id": version_id,
        "schema_version": manifest["schema_version"],
        "content_sha": manifest["content_sha"],
        "uri": manifest["uri"],
        "row_count": manifest["row_count"],
    }


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    storage = get_storage(environment="preview")
    repair, _ = _repair(storage, REPAIR_URI, scope="historical")
    refs = _sources(storage, repair, scope="historical")
    core = json.loads(storage.read_bytes(repair["parents"]["core_eligibility"]["uri"]))
    core_inputs = {
        (int(item["season"]), str(item["dataset"])): item for item in core["inputs"]
    }
    seasons = {}
    for season in sorted(refs):
        byplay = refs[season]["byplay"]
        manifest = json.loads(
            storage.read_bytes(byplay.uri.rsplit("/", 1)[0] + "/manifest.json")
        )
        found: dict[str, dict] = {}
        for version_id in manifest["parent_versions"]:
            for dataset in PARENT_DATASETS:
                key = (
                    f"lake/silver/dataset={dataset}/version={version_id}/manifest.json"
                )
                if storage.exists(key):
                    found[dataset] = _entry(storage, dataset, version_id)
        missing = sorted(set(PARENT_DATASETS) - set(found))
        if missing or len(manifest["parent_versions"]) != len(PARENT_DATASETS):
            raise SystemExit(f"{season}: unexpected parent set, missing {missing}")
        outcomes = refs[season]["game_outcomes"]
        seasons[str(season)] = {
            "parents": [found[name] for name in PARENT_DATASETS],
            "game_outcomes": asdict(outcomes),
            "legacy_comparison": {
                **{
                    name: asdict(refs[season][name])
                    for name in (
                        "byplay",
                        "drives",
                        "reconciled_team_game",
                        "game_outcomes",
                    )
                },
                "source_reconciliation": {
                    key: core_inputs[(season, "source_reconciliation")][key]
                    for key in (
                        "dataset",
                        "version_id",
                        "schema_version",
                        "content_sha",
                        "uri",
                    )
                },
            },
            "legacy_byplay_as_of": manifest["as_of"],
            "legacy_byplay_code_sha": manifest["code_sha"],
        }
    payload = {
        "schema_version": "rebuild_6a_silver_parents_v1",
        "source": "legacy byplay manifest parents via repair-v2 core eligibility",
        "repair_manifest_uri": REPAIR_URI,
        "seasons": seasons,
    }
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"wrote {args.out}: {len(seasons)} seasons")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
