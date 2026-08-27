#!/usr/bin/env python3
"""Write immutable successor-v2 expanded-history ref-set and coverage reports.

The command is Preview-only. It accepts exact immutable dataset refs and a
separately computed coverage-evidence payload, so reconstruction and
certification cannot silently substitute a newly discovered "latest" object.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cks_picks_cfb.data.lake import DatasetRef
from cks_picks_cfb.data.season_lineage import load_season_lineage_policy
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ratings.successor_history import (
    SeasonCoverageEvidence,
    coverage_report,
    expanded_history_ref_set,
)


def _immutable_write(storage, uri: str, payload: bytes) -> None:
    if storage.exists(uri):
        if storage.read_bytes(uri) != payload:
            raise FileExistsError(f"Immutable successor-v2 artifact collision: {uri}")
        return
    storage.write_bytes(payload, uri)


def _parse_ref(value: str) -> tuple[tuple[int, str], str]:
    try:
        season_text, dataset, uri = value.split(":", 2)
        return (int(season_text), dataset), uri
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "--dataset-ref must be SEASON:DATASET:REF_URI"
        ) from exc


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--environment", choices=("preview", "production"), required=True
    )
    parser.add_argument(
        "--season-lineage-policy",
        default="conf/ratings/successor_v2_season_lineage.yaml",
    )
    parser.add_argument("--dataset-ref", action="append", required=True)
    parser.add_argument(
        "--coverage-evidence-json",
        required=True,
        help="Local JSON array of SeasonCoverageEvidence-compatible objects.",
    )
    parser.add_argument("--ref-set-uri", required=True)
    parser.add_argument("--coverage-report-uri", required=True)
    args = parser.parse_args(argv)
    if args.environment != "preview":
        raise ValueError("Successor-v2 history certification is Preview-only")
    policy = load_season_lineage_policy(args.season_lineage_policy)
    if not (
        args.ref_set_uri.startswith(f"{policy.research_prefix}/")
        and args.coverage_report_uri.startswith(f"{policy.research_prefix}/")
    ):
        raise ValueError("Successor-v2 outputs must use the isolated research prefix")
    storage = get_storage(environment="preview")
    refs: dict[tuple[int, str], DatasetRef] = {}
    for value in args.dataset_ref:
        key, uri = _parse_ref(value)
        if key in refs:
            raise ValueError(f"Duplicate dataset ref for {key}")
        refs[key] = DatasetRef(**json.loads(storage.read_bytes(uri).decode()))
    evidence_raw = json.loads(Path(args.coverage_evidence_json).read_text())
    if not isinstance(evidence_raw, list):
        raise ValueError("Coverage evidence must be a JSON array")
    report = coverage_report(
        policy, [SeasonCoverageEvidence(**item) for item in evidence_raw]
    )
    ref_set = expanded_history_ref_set(policy, refs)
    _immutable_write(
        storage,
        args.ref_set_uri,
        json.dumps(ref_set, indent=2, sort_keys=True).encode(),
    )
    _immutable_write(
        storage,
        args.coverage_report_uri,
        json.dumps(report, indent=2, sort_keys=True).encode(),
    )
    print(
        json.dumps(
            {
                "ref_set_uri": args.ref_set_uri,
                "ref_set_sha256": ref_set["ref_set_sha256"],
                "coverage_report_uri": args.coverage_report_uri,
                "tournaments_permitted": report["tournaments_permitted"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
