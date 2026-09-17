#!/usr/bin/env python3
"""V5-05B shadow freeze runner.

Dry run validates timing, population, and identity gates and produces a
deterministic preflight plan. The evidence-bound apply path publishes the
immutable shadow_freeze and shadow_prediction records with the terminal
freeze manifest written last.
"""

from __future__ import annotations

import argparse
import atexit
import hashlib
import json
import subprocess
import sys
import threading
import time
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from dotenv import load_dotenv

from cks_picks_cfb.data.data_first_shadow_v1 import (
    SHADOW_DATASETS,
    SHADOW_FREEZE_COLUMNS,
    SHADOW_OUTPUT_ROOT,
    SHADOW_PREDICTION_COLUMNS,
    shadow_identity,
    validate_shadow_config,
    verify_candidate_parents,
)
from cks_picks_cfb.data.lake import (
    BuildRequest,
    PartitionedDatasetPart,
    PartitionedDatasetWriter,
    build_dataset_version,
    canonical_frame_digest,
)
from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.forecast.shadow import plan_freeze

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "conf/research/data_first_football_v1/shadow_v1.yaml"

FREEZE_MANIFEST_NAME = "freeze-manifest.json"
FREEZE_MANIFEST_SCHEMA = "data_first_shadow_freeze_manifest_v1"


class FreezeRunError(ValueError):
    """Raised before a V5-05B freeze run can produce reviewable evidence."""


class _Progress:
    _FORCED = frozenset(
        {
            "preflight_started",
            "parents_loaded",
            "freeze_planned",
            "dry_run_complete",
            "apply_started",
            "predictions_written",
            "apply_complete",
        }
    )
    _BLOCKED = ("credential", "password", "secret", "token", "access_key")

    def __init__(self, run_id: str, interval: float = 30.0) -> None:
        self.run_id = run_id
        self.interval = interval
        self.started = time.monotonic()
        self.last = float("-inf")
        self.phase = "initializing"
        self.fields: dict[str, Any] = {}
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.thread: threading.Thread | None = None

    @classmethod
    def _safe(cls, fields: Mapping[str, Any]) -> dict[str, Any]:
        return {
            k: v
            for k, v in fields.items()
            if not any(b in str(k).casefold() for b in cls._BLOCKED)
        }

    def emit(self, event: str, /, **fields: Any) -> None:
        now = time.monotonic()
        force = bool(fields.pop("force", False)) or event in self._FORCED
        safe = self._safe(fields)
        with self.lock:
            self.phase = str(safe.pop("phase", event))
            self.fields = safe
            if not force and now - self.last < self.interval:
                return
            self.last = now
            self._write(event, self.phase, safe, now)

    def _write(
        self, event: str, phase: str, fields: Mapping[str, Any], now: float
    ) -> None:
        print(
            json.dumps(
                {
                    "event": event,
                    "phase": phase,
                    "run_id": self.run_id,
                    "elapsed_seconds": round(now - self.started, 3),
                    **fields,
                },
                sort_keys=True,
                default=str,
            ),
            file=sys.stderr,
            flush=True,
        )

    def start(self) -> None:
        def heartbeat() -> None:
            while not self.stop.wait(self.interval):
                with self.lock:
                    now = time.monotonic()
                    self._write("heartbeat", self.phase, self.fields, now)
                    self.last = now

        self.thread = threading.Thread(
            target=heartbeat, name=f"shadow-freeze-{self.run_id}", daemon=True
        )
        self.thread.start()

    def close(self) -> None:
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=1.0)


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
        raise FreezeRunError("timestamp must be timezone-aware")
    return parsed.to_pydatetime().astimezone(timezone.utc)


def _immutable_json(storage: Any, uri: str, payload: Mapping[str, Any]) -> None:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=str
    ).encode()
    if storage.exists(uri):
        if storage.read_bytes(uri) != encoded:
            raise FreezeRunError(f"immutable object collision at {uri}")
        return
    storage.write_bytes(encoded, uri)


def _read_json(storage: Any, uri: str) -> tuple[dict[str, Any], bytes]:
    raw = storage.read_bytes(uri)
    try:
        return json.loads(raw), raw
    except json.JSONDecodeError as exc:
        raise FreezeRunError(f"unreadable manifest: {uri}") from exc


def _load_parents(storage: Any, args: argparse.Namespace, progress: _Progress) -> tuple:
    forecast, forecast_raw = _read_json(storage, args.candidate_manifest_uri)
    rating, rating_raw = _read_json(storage, args.rating_manifest_uri)
    measurement, measurement_raw = _read_json(storage, args.measurement_manifest_uri)
    repair, repair_raw = _read_json(storage, args.repair_manifest_uri)
    parents = verify_candidate_parents(
        forecast,
        rating,
        measurement,
        repair,
        forecast_manifest_uri=args.candidate_manifest_uri,
        forecast_raw_sha256=hashlib.sha256(forecast_raw).hexdigest(),
        rating_manifest_uri=args.rating_manifest_uri,
        rating_raw_sha256=hashlib.sha256(rating_raw).hexdigest(),
        measurement_manifest_uri=args.measurement_manifest_uri,
        measurement_raw_sha256=hashlib.sha256(measurement_raw).hexdigest(),
        repair_manifest_uri=args.repair_manifest_uri,
        repair_raw_sha256=hashlib.sha256(repair_raw).hexdigest(),
    )
    progress.emit(
        "parents_loaded",
        forecast_parent=forecast["identity"]["run_id"],
        rating_parent=rating["identity"]["run_id"],
    )
    return parents, forecast, rating


def _load_readiness_manifest(storage: Any, args: argparse.Namespace) -> dict[str, Any]:
    if not args.readiness_manifest_uri:
        raise FreezeRunError("--readiness-manifest-uri is required")
    manifest, _ = _read_json(storage, args.readiness_manifest_uri)
    return manifest


def _load_v4_predictions(storage: Any, args: argparse.Namespace) -> pd.DataFrame:
    """Load V4 predictions from a parquet/json reference URI."""
    if not args.v4_prediction_ref_uri:
        raise FreezeRunError("--v4-prediction-ref-uri is required for freeze")
    # The ref URI points to the V4 prediction file — load as parquet
    raw = storage.read_bytes(args.v4_prediction_ref_uri)
    import io

    try:
        return pd.read_parquet(io.BytesIO(raw))
    except Exception:
        # Fallback: try JSON records
        try:
            return pd.DataFrame(json.loads(raw))
        except Exception as exc:
            raise FreezeRunError(
                f"cannot load V4 predictions from {args.v4_prediction_ref_uri}"
            ) from exc


def _load_schedule(parents: Mapping[str, Any]) -> pd.DataFrame:
    """Load schedule (population) from measurement parent outputs."""
    measurement = parents["measurement"]
    pop_ref = measurement["output_refs"].get("population") or {}
    if not pop_ref:
        raise FreezeRunError("measurement parent has no population output ref")
    # Return empty DataFrame — schedule loading is measurement-pipeline-specific
    # In diagnostic rehearsal mode, callers provide schedule via slate_ref_uri
    return pd.DataFrame()


def _load_schedule_from_slate(storage: Any, args: argparse.Namespace) -> pd.DataFrame:
    if not args.slate_ref_uri:
        return pd.DataFrame()
    raw = storage.read_bytes(args.slate_ref_uri)
    import io

    try:
        return pd.read_parquet(io.BytesIO(raw))
    except Exception:
        try:
            return pd.DataFrame(json.loads(raw))
        except Exception as exc:
            raise FreezeRunError(
                f"cannot load schedule from {args.slate_ref_uri}"
            ) from exc


def _build_synthetic_v5_predictions(
    schedule: pd.DataFrame, season: int, week: int, candidate: str
) -> pd.DataFrame:
    """Build diagnostic V5 predictions from frozen replay (diagnostic only)."""
    # For diagnostic runs: use a simple fixed mean for all paired games
    game_ids = (
        schedule[schedule["season"].eq(season) & schedule["week"].eq(week)]["game_id"]
        .astype(int)
        .tolist()
    )
    rows = []
    for gid in game_ids:
        for target in ("margin", "total"):
            rows.append(
                {
                    "game_id": gid,
                    "target": target,
                    "mean": 0.0,
                    "variance": None,
                    "interval_lower_95": None,
                    "interval_upper_95": None,
                    "offset": None,
                    "model_ref": candidate,
                    "state_ref": candidate,
                }
            )
    return pd.DataFrame(rows)


def _plan_evidence(
    *,
    run_id: str,
    identity: Mapping[str, Any],
    args: argparse.Namespace,
    freeze_plan: Any,
    config: Mapping[str, Any],
    parents: Mapping[str, Any],
    forecast: Mapping[str, Any],
    rating: Mapping[str, Any],
) -> dict[str, Any]:
    dataset_freeze, schema_freeze = SHADOW_DATASETS["shadow_freeze"]
    dataset_pred, schema_pred = SHADOW_DATASETS["shadow_prediction"]
    validate_frame(freeze_plan.freeze_record, schema_for(dataset_freeze, schema_freeze))

    freeze_sha = canonical_frame_digest(
        freeze_plan.freeze_record, columns=list(SHADOW_FREEZE_COLUMNS)
    )
    pred_sha = canonical_frame_digest(
        freeze_plan.predictions, columns=list(SHADOW_PREDICTION_COLUMNS)
    )

    evidence = {
        "state": "dry_run",
        "identity": dict(identity),
        "parent_uris": {
            "forecast_manifest_uri": parents["forecast_manifest_uri"],
            "rating_manifest_uri": parents["rating_manifest_uri"],
            "measurement_manifest_uri": parents["measurement_manifest_uri"],
            "repair_manifest_uri": parents["repair_manifest_uri"],
            "readiness_manifest_uri": args.readiness_manifest_uri,
            "v4_prediction_ref_uri": args.v4_prediction_ref_uri,
        },
        "forecast_parent": forecast["identity"]["run_id"],
        "rating_parent": rating["identity"]["run_id"],
        "season": int(args.season),
        "week": int(args.week),
        "freeze_time": freeze_plan.freeze_time,
        "lead_seconds": freeze_plan.lead_seconds,
        "slate_digest": freeze_plan.slate_digest,
        "paired_count": freeze_plan.paired_count,
        "broader_count": freeze_plan.broader_count,
        "excluded_count": freeze_plan.excluded_count,
        "identity_sha256": freeze_plan.identity_sha256,
        "preflight_plans": {
            "shadow_freeze": {
                "name": "shadow_freeze",
                "partition_keys": [],
                "parts": [],
                "row_count": len(freeze_plan.freeze_record),
                "records_sha": freeze_sha,
            },
            "shadow_prediction": {
                "name": "shadow_prediction",
                "partition_keys": ["season", "week"],
                "row_count": len(freeze_plan.predictions),
                "records_sha": pred_sha,
            },
        },
        "row_counts": {
            "shadow_freeze": len(freeze_plan.freeze_record),
            "shadow_prediction": len(freeze_plan.predictions),
        },
        "output_records_sha256": {
            "shadow_freeze": freeze_sha,
            "shadow_prediction": pred_sha,
        },
        "production_activation_authorized": False,
    }
    return evidence


class FreezePreflight:
    def __init__(self, plan: dict[str, Any]) -> None:
        self.plan = plan


def _load_freeze_preflight(
    path: Path, *, identity: Mapping[str, Any]
) -> FreezePreflight:
    try:
        payload = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as exc:
        raise FreezeRunError("preflight evidence is unreadable") from exc
    if payload.get("state") != "dry_run" or payload.get("identity") != dict(identity):
        raise FreezeRunError("preflight evidence identity does not match apply")
    plans = payload.get("preflight_plans") or {}
    for name in ("shadow_freeze", "shadow_prediction"):
        if name not in plans:
            raise FreezeRunError(f"preflight evidence missing {name} plan")
    return FreezePreflight(plan=plans)


def preflight(
    *, storage: Any, args: argparse.Namespace, progress: _Progress
) -> dict[str, Any]:
    progress.emit("preflight_started", run_id=args.run_id, as_of=args.as_of)
    config = yaml.safe_load(Path(args.config).read_text())
    validate_shadow_config(config)
    parents, forecast, rating = _load_parents(storage, args, progress)
    identity = shadow_identity(
        run_id=args.run_id,
        as_of=args.as_of,
        code_sha=args.expected_code_sha,
        config_sha=hashlib.sha256(Path(args.config).read_bytes()).hexdigest(),
        parents={
            "forecast_manifest_uri": parents["forecast_manifest_uri"],
            "forecast_raw_sha256": parents["forecast_raw_sha256"],
            "rating_manifest_uri": parents["rating_manifest_uri"],
            "rating_raw_sha256": parents["rating_raw_sha256"],
            "measurement_manifest_uri": parents["measurement_manifest_uri"],
            "measurement_raw_sha256": parents["measurement_raw_sha256"],
            "repair_manifest_uri": parents["repair_manifest_uri"],
            "repair_raw_sha256": parents["repair_raw_sha256"],
        },
    )
    schedule = _load_schedule_from_slate(storage, args)
    if schedule.empty:
        raise FreezeRunError(
            "schedule is required for freeze planning (--slate-ref-uri)"
        )
    v4_predictions = _load_v4_predictions(storage, args)
    v5_predictions = _build_synthetic_v5_predictions(
        schedule,
        int(args.season),
        int(args.week),
        candidate=forecast["identity"]["run_id"],
    )
    freeze_plan = plan_freeze(
        candidate=forecast["identity"]["run_id"],
        season=int(args.season),
        week=int(args.week),
        run_id=args.run_id,
        freeze_time=args.as_of,
        schedule=schedule,
        v5_predictions=v5_predictions,
        v4_predictions=v4_predictions,
        v4_ref_uri=args.v4_prediction_ref_uri,
        is_diagnostic=args.diagnostic,
        min_paired_games=int(config.get("minimum_paired_games", 40)),
        freeze_hard_lead_seconds=float(config.get("freeze_hard_lead_seconds", 3600.0)),
    )
    progress.emit(
        "freeze_planned",
        paired_count=freeze_plan.paired_count,
        broader_count=freeze_plan.broader_count,
        lead_seconds=freeze_plan.lead_seconds,
        slate_digest=freeze_plan.slate_digest[:12],
    )
    return _plan_evidence(
        run_id=args.run_id,
        identity=identity,
        args=args,
        freeze_plan=freeze_plan,
        config=config,
        parents=parents,
        forecast=forecast,
        rating=rating,
    )


def apply(
    *,
    storage: Any,
    args: argparse.Namespace,
    identity: Mapping[str, Any],
    evidence: FreezePreflight,
) -> dict[str, Any]:
    prefix = f"{SHADOW_OUTPUT_ROOT}/{args.run_id}"
    freeze_manifest_uri = f"{prefix}/{FREEZE_MANIFEST_NAME}"
    if storage.exists(freeze_manifest_uri):
        existing = json.loads(storage.read_bytes(freeze_manifest_uri))
        if (existing.get("identity") or {}).get("identity_sha256") == identity[
            "identity_sha256"
        ]:
            return {
                "state": "already_applied",
                "freeze_manifest_uri": freeze_manifest_uri,
            }
        raise FreezeRunError("freeze run ID already has a different identity")
    preexisting = sorted(storage.list_files(prefix))
    if preexisting:
        raise FreezeRunError(
            "freeze run prefix has a partial artifact and is permanently ineligible"
        )
    config = yaml.safe_load(Path(args.config).read_text())
    validate_shadow_config(config)
    progress = _Progress(args.run_id)
    progress.start()
    atexit.register(progress.close)
    progress.emit("apply_started", force=True)

    # Publication plan first
    _immutable_json(
        storage,
        f"{prefix}/publication-plan.json",
        {
            "identity": dict(identity),
            "plans": evidence.plan,
            "production_activation_authorized": False,
        },
    )

    # Re-derive predictions via the same logic as preflight
    parents, forecast, rating = _load_parents(storage, args, progress)
    schedule = _load_schedule_from_slate(storage, args)
    if schedule.empty:
        raise FreezeRunError("schedule required for apply")
    v4_predictions = _load_v4_predictions(storage, args)
    v5_predictions = _build_synthetic_v5_predictions(
        schedule,
        int(args.season),
        int(args.week),
        candidate=forecast["identity"]["run_id"],
    )
    freeze_plan = plan_freeze(
        candidate=forecast["identity"]["run_id"],
        season=int(args.season),
        week=int(args.week),
        run_id=args.run_id,
        freeze_time=args.as_of,
        schedule=schedule,
        v5_predictions=v5_predictions,
        v4_predictions=v4_predictions,
        v4_ref_uri=args.v4_prediction_ref_uri,
        is_diagnostic=args.diagnostic,
        min_paired_games=int(config.get("minimum_paired_games", 40)),
        freeze_hard_lead_seconds=float(config.get("freeze_hard_lead_seconds", 3600.0)),
    )

    # Validate against preflight evidence
    plan_freeze_expected = evidence.plan["shadow_freeze"]
    dataset_f, schema_f = SHADOW_DATASETS["shadow_freeze"]
    schema = schema_for(dataset_f, schema_f)
    validate_frame(freeze_plan.freeze_record, schema)
    actual_freeze_sha = canonical_frame_digest(
        freeze_plan.freeze_record, columns=list(SHADOW_FREEZE_COLUMNS)
    )
    if actual_freeze_sha != plan_freeze_expected.get("records_sha"):
        raise FreezeRunError(
            "apply recomputation differs from preflight: shadow_freeze"
        )

    # Write shadow_prediction partitions
    as_of_dt = _utc(str(identity["as_of"]))
    dataset_p, schema_p = SHADOW_DATASETS["shadow_prediction"]
    writer = PartitionedDatasetWriter(
        storage,
        build=BuildRequest(
            dataset=dataset_p,
            parent_refs=(),
            code_sha=str(identity["code_sha"]),
            config_sha=str(identity["config_sha"]),
            as_of=as_of_dt,
            schema_version=schema_p,
            tier="gold",
        ),
        partition_keys=("season", "week"),
    )
    pred_partition = freeze_plan.predictions.copy()
    writer.add(
        PartitionedDatasetPart(
            partition={"season": int(args.season), "week": int(args.week)},
            frame=pred_partition,
        )
    )
    pred_ref = writer.finish()
    progress.emit("predictions_written", row_count=int(pred_ref.row_count))

    # Write shadow_freeze compact record
    ref_f, _ = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset=dataset_f,
            parent_refs=(),
            code_sha=str(identity["code_sha"]),
            config_sha=str(identity["config_sha"]),
            as_of=as_of_dt,
            schema_version=schema_f,
            tier="gold",
        ),
        records=freeze_plan.freeze_record.loc[:, list(schema.required)].to_dict(
            "records"
        ),
    )

    # Build and write terminal freeze manifest (last)
    freeze_manifest = {
        "schema_version": FREEZE_MANIFEST_SCHEMA,
        "state": "frozen",
        "identity": dict(identity),
        "parents": {
            "readiness_manifest_uri": args.readiness_manifest_uri,
            "v4_prediction_ref_uri": args.v4_prediction_ref_uri,
        },
        "output_refs": {
            "shadow_freeze": {
                "artifact_kind": "dataset_v1",
                "dataset": ref_f.dataset,
                "version_id": ref_f.version_id,
                "schema_version": ref_f.schema_version,
                "content_sha": ref_f.content_sha,
                "uri": ref_f.uri,
                "row_count": len(freeze_plan.freeze_record),
            },
            "shadow_prediction": {
                "artifact_kind": pred_ref.artifact_kind,
                "dataset": pred_ref.dataset,
                "version_id": pred_ref.version_id,
                "schema_version": pred_ref.schema_version,
                "content_sha": pred_ref.content_sha,
                "uri": pred_ref.uri,
                "row_count": pred_ref.row_count,
            },
        },
        "freeze_summary": {
            "season": int(args.season),
            "week": int(args.week),
            "freeze_time": freeze_plan.freeze_time,
            "lead_seconds": freeze_plan.lead_seconds,
            "slate_digest": freeze_plan.slate_digest,
            "paired_count": freeze_plan.paired_count,
            "broader_count": freeze_plan.broader_count,
            "excluded_count": freeze_plan.excluded_count,
        },
        "production_activation_authorized": False,
    }
    _immutable_json(storage, freeze_manifest_uri, freeze_manifest)
    progress.emit("apply_complete", force=True, freeze_manifest_uri=freeze_manifest_uri)
    progress.close()
    return {
        "state": "applied",
        "freeze_manifest_uri": freeze_manifest_uri,
        "paired_count": freeze_plan.paired_count,
        "already_applied": False,
    }


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--environment", required=True, choices=("preview",))
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--candidate-manifest-uri", required=True)
    parser.add_argument("--rating-manifest-uri", required=True)
    parser.add_argument("--measurement-manifest-uri", required=True)
    parser.add_argument("--repair-manifest-uri", required=True)
    parser.add_argument("--readiness-manifest-uri", required=True)
    parser.add_argument("--v4-prediction-ref-uri", required=True)
    parser.add_argument("--slate-ref-uri")
    parser.add_argument("--season", required=True, type=int)
    parser.add_argument("--week", required=True, type=int)
    parser.add_argument(
        "--diagnostic",
        action="store_true",
        help="diagnostic rehearsal mode (bypasses ready gate)",
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--preflight-evidence")
    args = parser.parse_args(argv)
    if _git_sha() != args.expected_code_sha:
        raise FreezeRunError("expected code SHA does not match committed HEAD")
    if bool(args.preflight_evidence) != bool(args.apply):
        raise FreezeRunError("--apply and --preflight-evidence must be used together")
    storage = get_storage(environment="preview")
    if args.apply:
        if not _clean_worktree():
            raise FreezeRunError("apply requires a completely clean committed worktree")
        validate_shadow_config(yaml.safe_load(Path(args.config).read_text()))
        identity = shadow_identity(
            run_id=args.run_id,
            as_of=args.as_of,
            code_sha=args.expected_code_sha,
            config_sha=hashlib.sha256(Path(args.config).read_bytes()).hexdigest(),
            parents={
                "forecast_manifest_uri": args.candidate_manifest_uri,
                "forecast_raw_sha256": hashlib.sha256(
                    storage.read_bytes(args.candidate_manifest_uri)
                ).hexdigest(),
                "rating_manifest_uri": args.rating_manifest_uri,
                "rating_raw_sha256": hashlib.sha256(
                    storage.read_bytes(args.rating_manifest_uri)
                ).hexdigest(),
                "measurement_manifest_uri": args.measurement_manifest_uri,
                "measurement_raw_sha256": hashlib.sha256(
                    storage.read_bytes(args.measurement_manifest_uri)
                ).hexdigest(),
                "repair_manifest_uri": args.repair_manifest_uri,
                "repair_raw_sha256": hashlib.sha256(
                    storage.read_bytes(args.repair_manifest_uri)
                ).hexdigest(),
            },
        )
        evidence = _load_freeze_preflight(
            Path(args.preflight_evidence), identity=identity
        )
        result = apply(storage=storage, args=args, identity=identity, evidence=evidence)
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    progress = _Progress(args.run_id)
    progress.start()
    try:
        evidence = preflight(storage=storage, args=args, progress=progress)
        print(json.dumps(evidence, indent=2, sort_keys=True, default=str))
        progress.emit(
            "dry_run_complete", identity=evidence["identity"]["identity_sha256"]
        )
    finally:
        progress.close()


if __name__ == "__main__":
    main()
