#!/usr/bin/env python3
"""Contract 09 live forecast preflight, Preview apply, and independent verify."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from dotenv import load_dotenv

from cks_picks_cfb.data.data_first_live_forecast_v1 import (
    BRIDGE_MANIFEST_URI,
    LIVE_FORECAST_COLUMNS,
    LIVE_FORECAST_DATASET,
    LIVE_FORECAST_OUTPUT_ROOT,
    live_forecast_manifest,
    live_identity,
    validate_config,
    validate_prediction_frame,
)
from cks_picks_cfb.data.lake import (
    BuildRequest,
    DatasetRef,
    PartitionedDatasetPart,
    PartitionedDatasetRef,
    PartitionedDatasetWriter,
    canonical_frame_digest,
    partition_key,
    read_dataset,
)
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.forecast.live import apply_frozen_bridge
from cks_picks_cfb.forecast.live_sources import (
    load_live_forecast_sources,
)
from cks_picks_cfb.forecast.live_verification import (
    reconstruct_predictions,
    verify_manifest_envelope,
    verify_predictions,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "conf/research/data_first_football_v1/live_forecast_v1.yaml"
MANIFEST_NAME = "live-forecast-manifest.json"


class LiveForecastRunError(ValueError):
    """Raised when Contract 09 preflight or immutable apply cannot proceed."""


def _git_sha() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def _clean_worktree() -> bool:
    return not subprocess.check_output(
        ["git", "status", "--porcelain=v1"], cwd=ROOT, text=True
    ).strip()


def _utc(value: str) -> datetime:
    parsed = pd.Timestamp(value)
    if parsed.tzinfo is None:
        raise LiveForecastRunError("--as-of must be timezone-aware")
    return parsed.to_pydatetime().astimezone(timezone.utc)


def _read_json(storage: Any, uri: str) -> tuple[dict[str, Any], bytes]:
    raw = storage.read_bytes(uri)
    try:
        return json.loads(raw), raw
    except json.JSONDecodeError as exc:
        raise LiveForecastRunError(f"unreadable JSON object: {uri}") from exc


def _immutable_json(storage: Any, uri: str, value: dict[str, Any]) -> None:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str
    ).encode()
    if storage.exists(uri):
        if storage.read_bytes(uri) != encoded:
            raise LiveForecastRunError(f"immutable object collision at {uri}")
        return
    storage.write_bytes(encoded, uri)


def _identity(
    args: argparse.Namespace, config: dict[str, Any], storage: Any
) -> dict[str, Any]:
    schedule_raw = storage.read_bytes(args.schedule_ref_uri)
    return live_identity(
        run_id=args.run_id,
        as_of=args.as_of,
        code_sha=args.expected_code_sha,
        config_sha256=hashlib.sha256(Path(args.config).read_bytes()).hexdigest(),
        parents={
            "measurement_uri": args.measurement_manifest_uri,
            "measurement_raw_sha256": hashlib.sha256(
                storage.read_bytes(args.measurement_manifest_uri)
            ).hexdigest(),
            "rating_replay_uri": args.rating_manifest_uri,
            "rating_replay_raw_sha256": hashlib.sha256(
                storage.read_bytes(args.rating_manifest_uri)
            ).hexdigest(),
            "bridge_uri": str(config["bridge_manifest_uri"]),
            "bridge_raw_sha256": hashlib.sha256(
                storage.read_bytes(str(config["bridge_manifest_uri"]))
            ).hexdigest(),
            "schedule_ref_uri": args.schedule_ref_uri,
            "schedule_raw_sha256": hashlib.sha256(schedule_raw).hexdigest(),
        },
    )


def _compute(args: argparse.Namespace, config: dict[str, Any], storage: Any):
    sources = load_live_forecast_sources(
        storage=storage,
        measurement_uri=args.measurement_manifest_uri,
        rating_uri=args.rating_manifest_uri,
        schedule_uri=args.schedule_ref_uri,
        bridge_uri=str(config["bridge_manifest_uri"]),
        as_of=args.as_of,
    )
    result = apply_frozen_bridge(
        sources["historical_features"],
        sources["live_features"],
        recipes=sources["recipes"],
        calibration_variances=sources["variances"],
        run_id=args.run_id,
        model_ref=BRIDGE_MANIFEST_URI,
        state_refs=sources["state_refs"],
        source_ref=(
            f"measurement:{args.measurement_manifest_uri}"
            f"|schedule:{args.schedule_ref_uri}"
        ),
    )
    validate_prediction_frame(result.predictions, run_id=args.run_id)
    membership = sources["live_features"].loc[:, ["season", "week", "game_id"]]
    return (
        sources,
        result,
        canonical_frame_digest(membership, columns=membership.columns),
    )


def _partition_evidence(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {
            "partition": {"season": int(season), "week": int(week)},
            "row_count": int(len(group)),
            "records_sha256": canonical_frame_digest(
                group, columns=LIVE_FORECAST_COLUMNS
            ),
        }
        for (season, week), group in frame.groupby(
            ["season", "week"], sort=True, dropna=False
        )
    ]


def preflight(
    args: argparse.Namespace, config: dict[str, Any], storage: Any
) -> dict[str, Any]:
    identity = _identity(args, config, storage)
    sources, computation, population_sha = _compute(args, config, storage)
    frame = computation.predictions
    digest = canonical_frame_digest(frame, columns=LIVE_FORECAST_COLUMNS)
    return {
        "state": "dry_run",
        "identity": identity,
        "prediction_count": int(len(frame)),
        "prediction_records_sha256": digest,
        "population_sha256": population_sha,
        "bridge_recipes": dict(computation.recipes),
        "partitions": _partition_evidence(frame),
        "production_activation_authorized": False,
    }


def _parent_ref(value: dict[str, Any]) -> DatasetRef:
    required = ("dataset", "version_id", "schema_version", "content_sha", "uri")
    if any(not value.get(key) for key in required):
        raise LiveForecastRunError("writer parent reference is incomplete")
    return DatasetRef(**{key: value[key] for key in required})


def _load_stored_predictions(storage: Any, manifest: dict[str, Any]) -> pd.DataFrame:
    ref = manifest.get("output_ref") or {}
    if ref.get("artifact_kind") != "partitioned_dataset_v1":
        raise LiveForecastRunError("live forecast output is not a partitioned dataset")
    raw_manifest = json.loads(storage.read_bytes(str(ref["uri"])))
    dataset_ref = PartitionedDatasetRef(
        artifact_kind="partitioned_dataset_v1",
        dataset=str(ref["dataset"]),
        version_id=str(ref["version_id"]),
        schema_version=str(ref["schema_version"]),
        content_sha=str(ref["content_sha"]),
        records_sha=str(raw_manifest.get("records_sha", "")),
        uri=str(ref["uri"]),
        row_count=int(ref["row_count"]),
        partition_keys=tuple(raw_manifest.get("partition_keys") or ("season", "week")),
    )
    return read_dataset(storage, dataset_ref)


def verify(
    args: argparse.Namespace, config: dict[str, Any], storage: Any
) -> dict[str, Any]:
    manifest, raw = _read_json(storage, args.verify_manifest_uri)
    verified_envelope = verify_manifest_envelope(
        manifest, raw_sha256=hashlib.sha256(raw).hexdigest()
    )
    identity = manifest["identity"]
    expected_manifest_uri = f"{LIVE_FORECAST_OUTPUT_ROOT}/{args.run_id}/{MANIFEST_NAME}"
    if args.verify_manifest_uri != expected_manifest_uri:
        raise LiveForecastRunError(
            "live forecast manifest URI does not match the requested run ID"
        )
    expected_identity = _identity(args, config, storage)
    if identity != expected_identity:
        raise LiveForecastRunError(
            "live forecast identity differs from the requested code, config, or parents"
        )
    parents = manifest["parents"]
    for uri_name, checksum_name, arg_value in (
        ("measurement_uri", "measurement_raw_sha256", args.measurement_manifest_uri),
        ("rating_replay_uri", "rating_replay_raw_sha256", args.rating_manifest_uri),
        ("schedule_ref_uri", "schedule_raw_sha256", args.schedule_ref_uri),
    ):
        raw_parent = storage.read_bytes(arg_value)
        if (
            parents.get(uri_name) != arg_value
            or parents.get(checksum_name) != hashlib.sha256(raw_parent).hexdigest()
        ):
            raise LiveForecastRunError(f"live verifier parent mismatch: {uri_name}")
    sources = load_live_forecast_sources(
        storage=storage,
        measurement_uri=args.measurement_manifest_uri,
        rating_uri=args.rating_manifest_uri,
        schedule_uri=args.schedule_ref_uri,
        bridge_uri=str(config["bridge_manifest_uri"]),
        as_of=str(identity["as_of"]),
    )
    if parents != sources["parents"]:
        raise LiveForecastRunError(
            "live forecast manifest parent checksums differ from source bytes"
        )
    if str(manifest.get("source_cutoff")) != str(identity["as_of"]):
        raise LiveForecastRunError(
            "live forecast source cutoff differs from its identity"
        )
    population = sources["live_features"].loc[:, ["season", "week", "game_id"]]
    if canonical_frame_digest(population, columns=population.columns) != manifest.get(
        "population_sha256"
    ):
        raise LiveForecastRunError("live forecast schedule population digest differs")
    stored = _load_stored_predictions(storage, manifest)
    reconstructed = reconstruct_predictions(
        sources["historical_features"],
        sources["live_features"],
        recipes=manifest["bridge_recipes"],
        variances=sources["variances"],
        run_id=str(identity["run_id"]),
        model_ref=BRIDGE_MANIFEST_URI,
        state_refs=sources["state_refs"],
        source_ref=(
            f"measurement:{args.measurement_manifest_uri}"
            f"|schedule:{args.schedule_ref_uri}"
        ),
    )
    prediction_result = verify_predictions(
        manifest=manifest, stored=stored, reconstructed=reconstructed
    )
    return {
        "verified": True,
        "manifest_uri": args.verify_manifest_uri,
        "identity": verified_envelope,
        **prediction_result,
    }


def apply(
    args: argparse.Namespace,
    config: dict[str, Any],
    storage: Any,
    evidence_path: Path,
) -> dict[str, Any]:
    identity = _identity(args, config, storage)
    evidence = json.loads(evidence_path.read_bytes())
    if (
        evidence.get("state") != "dry_run"
        or evidence.get("identity") != identity
        or evidence.get("production_activation_authorized") is not False
    ):
        raise LiveForecastRunError("preflight evidence identity does not match apply")
    prefix = f"{LIVE_FORECAST_OUTPUT_ROOT}/{args.run_id}"
    manifest_uri = f"{prefix}/{MANIFEST_NAME}"
    if storage.exists(manifest_uri):
        old, _ = _read_json(storage, manifest_uri)
        if old.get("identity") != identity:
            raise LiveForecastRunError(
                "live forecast run ID is already bound to another identity"
            )
        verified = verify(args, config, storage)
        return {"state": "already_applied", "manifest_uri": manifest_uri, **verified}
    if storage.list_files(prefix):
        raise LiveForecastRunError("live forecast prefix has partial immutable output")
    sources, computation, population_sha = _compute(args, config, storage)
    frame = computation.predictions
    actual_sha = canonical_frame_digest(frame, columns=LIVE_FORECAST_COLUMNS)
    if (
        actual_sha != evidence.get("prediction_records_sha256")
        or population_sha != evidence.get("population_sha256")
        or len(frame) != int(evidence.get("prediction_count", -1))
        or computation.recipes != evidence.get("bridge_recipes")
        or _partition_evidence(frame) != evidence.get("partitions")
    ):
        raise LiveForecastRunError(
            "apply recomputation differs from reviewed preflight"
        )
    dataset, schema = LIVE_FORECAST_DATASET
    parts = evidence["partitions"]
    expected = {
        partition_key(item["partition"]): {
            "row_count": item["row_count"],
            "records_sha": item["records_sha256"],
        }
        for item in parts
    }
    parent_refs = (
        _parent_ref(sources["measurement"]["output_refs"]["population"]),
        _parent_ref(sources["rating"]["output_refs"]["team_states"]),
    )
    writer = PartitionedDatasetWriter(
        storage,
        build=BuildRequest(
            dataset=dataset,
            parent_refs=parent_refs,
            code_sha=args.expected_code_sha,
            config_sha=identity["config_sha256"],
            as_of=_utc(args.as_of),
            schema_version=schema,
            tier="gold",
        ),
        partition_keys=("season", "week"),
        expected_parts=expected,
        max_workers=4,
    )
    for (season, week), group in frame.groupby(["season", "week"], sort=True):
        group = group.loc[:, list(LIVE_FORECAST_COLUMNS)]
        writer.add(
            PartitionedDatasetPart({"season": int(season), "week": int(week)}, group)
        )
    ref = writer.finish()
    output_ref = {
        "artifact_kind": ref.artifact_kind,
        "dataset": ref.dataset,
        "version_id": ref.version_id,
        "schema_version": ref.schema_version,
        "content_sha": ref.content_sha,
        "records_sha": ref.records_sha,
        "uri": ref.uri,
        "row_count": ref.row_count,
        "partition_keys": list(ref.partition_keys),
    }
    manifest = live_forecast_manifest(
        identity=identity,
        parents=sources["parents"],
        output_ref=output_ref,
        prediction_count=len(frame),
        prediction_records_sha256=actual_sha,
        population_sha256=population_sha,
        bridge_recipes=computation.recipes,
        source_cutoff=args.as_of,
    )
    _immutable_json(storage, manifest_uri, manifest)
    return {"state": "applied", "manifest_uri": manifest_uri, "row_count": len(frame)}


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--environment", choices=("preview",), required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--measurement-manifest-uri", required=True)
    parser.add_argument("--rating-manifest-uri", required=True)
    parser.add_argument("--schedule-ref-uri", required=True)
    parser.add_argument("--verify-manifest-uri")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--preflight-evidence", type=Path)
    args = parser.parse_args(argv)
    if _git_sha() != args.expected_code_sha:
        raise LiveForecastRunError("expected code SHA does not match HEAD")
    if args.apply != bool(args.preflight_evidence):
        raise LiveForecastRunError(
            "--apply requires --preflight-evidence and vice versa"
        )
    config = yaml.safe_load(Path(args.config).read_text())
    validate_config(config)
    storage = get_storage(environment="preview")
    if args.verify_manifest_uri:
        print(json.dumps(verify(args, config, storage), sort_keys=True, indent=2))
    elif args.apply:
        if not _clean_worktree():
            raise LiveForecastRunError("apply requires a clean committed worktree")
        print(
            json.dumps(
                apply(args, config, storage, args.preflight_evidence),
                sort_keys=True,
                indent=2,
            )
        )
    else:
        print(
            json.dumps(
                preflight(args, config, storage), sort_keys=True, indent=2, default=str
            )
        )


if __name__ == "__main__":
    main()
