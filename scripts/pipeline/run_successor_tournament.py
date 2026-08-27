#!/usr/bin/env python3
"""Publish an immutable R2/R3/R4 successor-v2 selection report from exact refs."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict

from cks_picks_cfb.data.lake import DatasetRef, read_dataset
from cks_picks_cfb.data.season_lineage import load_season_lineage_policy
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ratings.successor_tournaments import (
    candidate_v2_gate,
    load_tournament_configs,
    select_from_fold_metrics,
)


def _read_ref(storage, uri: str) -> DatasetRef:
    return DatasetRef(**json.loads(storage.read_bytes(uri).decode()))


def _immutable_write(storage, uri: str, payload: bytes) -> None:
    if storage.exists(uri):
        if storage.read_bytes(uri) != payload:
            raise FileExistsError(f"Immutable tournament report collision: {uri}")
        return
    storage.write_bytes(payload, uri)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--environment", choices=("preview", "production"), required=True
    )
    parser.add_argument(
        "--stage",
        choices=("between_season", "within_season", "structured_predictor"),
        required=True,
    )
    parser.add_argument("--metrics-ref-uri", required=True)
    parser.add_argument("--output-uri", required=True)
    parser.add_argument("--admitted-context-family", action="append", default=[])
    parser.add_argument("--paired-predictions-ref-uri")
    parser.add_argument("--locked-2025-passed", action="store_true")
    parser.add_argument("--existing-quality-gates-passed", action="store_true")
    args = parser.parse_args(argv)
    if args.environment != "preview":
        raise ValueError("Successor-v2 tournaments are Preview-only")
    policy = load_season_lineage_policy("conf/ratings/successor_v2_season_lineage.yaml")
    configs = load_tournament_configs("conf/ratings/successor_v2_tournaments.yaml")
    if not args.output_uri.startswith(f"{policy.research_prefix}/"):
        raise ValueError("Tournament report must use the successor-v2 research prefix")
    storage = get_storage(environment="preview")
    metrics_ref = _read_ref(storage, args.metrics_ref_uri)
    result = select_from_fold_metrics(
        read_dataset(storage, metrics_ref),
        policy=policy,
        config=configs[args.stage],
        admitted_context_families=args.admitted_context_family,
    )
    report: dict[str, object] = {
        "report_version": "rating_successor_v2_tournament_report_v1",
        "stage": args.stage,
        "metrics_ref": asdict(metrics_ref),
        "selection": result,
    }
    if args.stage == "structured_predictor":
        if not args.paired_predictions_ref_uri:
            raise ValueError("R4 requires --paired-predictions-ref-uri")
        paired_ref = _read_ref(storage, args.paired_predictions_ref_uri)
        gates = candidate_v2_gate(
            read_dataset(storage, paired_ref),
            locked_2025_passed=args.locked_2025_passed,
            existing_quality_gates_passed=args.existing_quality_gates_passed,
        )
        report["paired_predictions_ref"] = asdict(paired_ref)
        report["candidate_v2_gates"] = gates
        report["all_checks_passed"] = bool(result["all_checks_passed"]) and bool(
            gates["all_checks_passed"]
        )
    else:
        report["all_checks_passed"] = bool(result["all_checks_passed"])
    payload = json.dumps(report, indent=2, sort_keys=True, default=str).encode()
    _immutable_write(storage, args.output_uri, payload)
    print(
        json.dumps(
            {
                "output_uri": args.output_uri,
                "report_sha256": hashlib.sha256(payload).hexdigest(),
                "winner": result["winner"],
                "all_checks_passed": report["all_checks_passed"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
