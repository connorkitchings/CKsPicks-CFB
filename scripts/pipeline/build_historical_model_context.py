#!/usr/bin/env python3
"""Build the immutable, diagnostic-only 2025 V4 context artifact."""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import yaml
from dotenv import load_dotenv

from cks_picks_cfb.data.lake import (
    BuildRequest,
    DatasetRef,
    build_dataset_version,
    read_dataset,
)
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.models.historical_model_context import (
    HISTORICAL_MODEL_CONTEXT_DATASET,
    HISTORICAL_MODEL_CONTEXT_SCHEMA_VERSION,
    aggregate_periods,
    build_audit,
    build_comparisons,
    config_from_mapping,
    validate_parent_refs,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "conf/weekly_bets/v4_2025_retrospective_context.yaml"
RELEVANT_PATHS = (
    "src/cks_picks_cfb/models/historical_model_context.py",
    "scripts/pipeline/build_historical_model_context.py",
    "conf/weekly_bets/v4_2025_retrospective_context.yaml",
)


def _immutable(storage, uri: str, payload: bytes) -> None:
    if storage.exists(uri):
        if storage.read_bytes(uri) != payload:
            raise FileExistsError(f"Immutable artifact exists: {uri}")
        return
    storage.write_bytes(payload, uri)


def _code_sha() -> str:
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if subprocess.run(
        ["git", "diff", "--quiet", sha, "--", *RELEVANT_PATHS], cwd=ROOT, check=False
    ).returncode:
        raise ValueError("Historical context artifact paths differ from committed HEAD")
    return sha


def _ref(raw: dict[str, str]) -> DatasetRef:
    return DatasetRef(**raw)


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", choices=("preview",), required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--output-ref-uri", required=True)
    parser.add_argument("--aggregates-uri", required=True)
    parser.add_argument("--audit-uri", required=True)
    parser.add_argument("--manifest-uri", required=True)
    args = parser.parse_args()
    config = config_from_mapping(yaml.safe_load(Path(args.config).read_text()))
    prefix = f"artifacts/research/historical-model-context/{config.design_id}/runs/{args.run_id}/"
    if not all(
        uri.startswith(prefix)
        for uri in (
            args.output_ref_uri,
            args.aggregates_uri,
            args.audit_uri,
            args.manifest_uri,
        )
    ):
        raise ValueError(
            "Historical context outputs must use the run-stamped research prefix"
        )
    code_sha = _code_sha()
    as_of = datetime.fromisoformat(args.as_of.replace("Z", "+00:00")).astimezone(
        timezone.utc
    )
    storage = get_storage(environment="preview")
    prediction_ref, feature_ref, market_ref = (
        _ref(config.prediction_ref),
        _ref(config.feature_ref),
        _ref(config.market_ref),
    )
    validate_parent_refs(
        prediction_ref=asdict(prediction_ref),
        feature_ref=asdict(feature_ref),
        market_ref=asdict(market_ref),
        config=config,
    )
    comparisons = build_comparisons(
        read_dataset(storage, prediction_ref),
        read_dataset(storage, feature_ref),
        read_dataset(storage, market_ref),
        config=config,
    )
    aggregates = aggregate_periods(comparisons)
    audit = build_audit(comparisons, aggregates, config=config)
    if not audit["all_checks_passed"]:
        _immutable(
            storage,
            args.audit_uri,
            json.dumps(audit, indent=2, sort_keys=True).encode(),
        )
        raise ValueError("Historical model context audit failed")
    context_ref, _ = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset=HISTORICAL_MODEL_CONTEXT_DATASET,
            parent_refs=(prediction_ref, feature_ref, market_ref),
            code_sha=code_sha,
            config_sha=config.design_id,
            as_of=as_of,
            schema_version=HISTORICAL_MODEL_CONTEXT_SCHEMA_VERSION,
            tier="gold",
        ),
        records=comparisons.to_dict("records"),
        partitions={"comparison_season": config.comparison_season},
        validation={"all_audit_checks_passed": True},
    )
    # Pandas represents the season row's null week as NaN; serialize through
    # its JSON writer so Neon receives a real SQL NULL, never a float NaN.
    aggregate_payload = json.dumps(
        json.loads(aggregates.to_json(orient="records")), indent=2, sort_keys=True
    ).encode()
    audit["context_ref"] = asdict(context_ref)
    audit_payload = json.dumps(audit, indent=2, sort_keys=True).encode()
    _immutable(
        storage,
        args.output_ref_uri,
        json.dumps(asdict(context_ref), sort_keys=True).encode(),
    )
    _immutable(storage, args.aggregates_uri, aggregate_payload)
    _immutable(storage, args.audit_uri, audit_payload)
    _immutable(
        storage,
        args.manifest_uri,
        json.dumps(
            {
                "schema_version": "historical_model_context_manifest_v1",
                "run_id": args.run_id,
                "code_sha": code_sha,
                "design_id": config.design_id,
                "context_ref": asdict(context_ref),
                "aggregates_uri": args.aggregates_uri,
                "audit_uri": args.audit_uri,
            },
            indent=2,
            sort_keys=True,
        ).encode(),
    )
    print(
        json.dumps(
            {"status": "built", "context_ref": asdict(context_ref), "audit": audit},
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
