#!/usr/bin/env python3
"""Compare successor-v2 R1 refs with immutable legacy comparison evidence."""

from __future__ import annotations

import argparse
import json
from typing import Any

from cks_picks_cfb.data.lake import DatasetRef, read_dataset, require_dataset
from cks_picks_cfb.data.season_lineage import load_season_lineage_policy
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ratings.cross_lineage import HARD_DATASETS, compare_season
from cks_picks_cfb.ratings.successor_history import DERIVED_REF_SET_VERSION

COMPARISON_SEASONS = (2019, 2021, 2022, 2023, 2024, 2025)


def _immutable_write(storage, uri: str, payload: bytes) -> None:
    if storage.exists(uri):
        if storage.read_bytes(uri) != payload:
            raise FileExistsError(f"Immutable successor-v2 artifact collision: {uri}")
        return
    storage.write_bytes(payload, uri)


def _refs(payload: dict[str, Any]) -> dict[tuple[int, str], DatasetRef]:
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError("ref-set entries must be a list")
    return {
        (int(entry["season"]), str(entry["dataset"])): DatasetRef(
            dataset=str(entry["dataset"]),
            version_id=str(entry["version_id"]),
            schema_version=str(entry["schema_version"]),
            content_sha=str(entry["content_sha"]),
            uri=str(entry["uri"]),
        )
        for entry in entries
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", choices=("preview", "production"), required=True)
    parser.add_argument("--derived-ref-set-uri", required=True)
    parser.add_argument("--comparison-ref-set-uri", required=True)
    parser.add_argument("--report-uri", required=True)
    args = parser.parse_args(argv)
    if args.environment != "preview":
        raise ValueError("Successor-v2 lineage audit is Preview-only")
    policy = load_season_lineage_policy("conf/ratings/successor_v2_season_lineage.yaml")
    if not args.report_uri.startswith(f"{policy.research_prefix}/"):
        raise ValueError("Cross-lineage report must use the isolated research prefix")
    storage = get_storage(environment="preview")
    successor = json.loads(storage.read_bytes(args.derived_ref_set_uri).decode())
    legacy = json.loads(storage.read_bytes(args.comparison_ref_set_uri).decode())
    if (
        successor.get("contract_version") != DERIVED_REF_SET_VERSION
        or successor.get("state") != "complete"
    ):
        raise ValueError("Cross-lineage audit requires the closed R1 derived-ref set")
    successor_refs = _refs(successor)
    legacy_refs = _refs(legacy)
    required = {(season, dataset) for season in COMPARISON_SEASONS for dataset in HARD_DATASETS}
    if not required.issubset(legacy_refs):
        raise ValueError("Legacy comparison ref set lacks required 2019/2021–2025 evidence")
    comparisons = []
    checks = {"season_membership_ok": True, "game_identity_ok": True, "team_identity_ok": True, "scores_ok": True}
    for season in COMPARISON_SEASONS:
        current = {dataset: successor_refs[(season, dataset)] for dataset in HARD_DATASETS}
        prior = {dataset: legacy_refs[(season, dataset)] for dataset in HARD_DATASETS}
        for dataset in HARD_DATASETS:
            require_dataset(current[dataset], dataset)
            require_dataset(prior[dataset], dataset)
        season_checks = compare_season(
            season=season,
            successor={
                dataset: read_dataset(storage, current[dataset])
                for dataset in HARD_DATASETS
            },
            legacy={
                dataset: read_dataset(storage, prior[dataset])
                for dataset in HARD_DATASETS
            },
        )
        for key, value in season_checks.items():
            checks[key] &= value
        revisions = {}
        for dataset in ("plays", "team_game_stats"):
            prior_ref = legacy_refs.get((season, dataset))
            current_ref = successor_refs.get((season, dataset))
            if prior_ref and current_ref:
                revisions[dataset] = {
                    "previous_content_sha": prior_ref.content_sha,
                    "successor_content_sha": current_ref.content_sha,
                    "schema_changed": prior_ref.schema_version != current_ref.schema_version,
                    "content_changed": prior_ref.content_sha != current_ref.content_sha,
                }
        comparisons.append(
            {"season": season, "revisions": revisions, "checks": season_checks}
        )
    report = {
        "contract_version": "successor-cross-lineage-audit-v2",
        "derived_ref_set_uri": args.derived_ref_set_uri,
        "comparison_ref_set_uri": args.comparison_ref_set_uri,
        "checks": checks,
        "seasons": comparisons,
    }
    report["all_checks_passed"] = all(checks.values())
    _immutable_write(storage, args.report_uri, json.dumps(report, indent=2, sort_keys=True).encode())
    print(json.dumps({"report_uri": args.report_uri, "all_checks_passed": report["all_checks_passed"]}, sort_keys=True))
    if not report["all_checks_passed"]:
        raise ValueError("Cross-lineage audit found incompatible game, team, score, or season evidence")


if __name__ == "__main__":
    main()
