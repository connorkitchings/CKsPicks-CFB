#!/usr/bin/env python3
"""V5-05B shadow score runner.

Dry run validates 24h stabilization, completion timestamps, and population gates
and produces a deterministic preflight plan. The evidence-bound apply path
publishes the immutable shadow_evaluation and shadow_evidence_counter records
with the terminal score manifest written last.
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
    EVIDENCE_COUNTER_COLUMNS,
    SHADOW_DATASETS,
    SHADOW_EVALUATION_COLUMNS,
    SHADOW_OUTPUT_ROOT,
    shadow_identity,
    validate_shadow_config,
    verify_candidate_parents,
)
from cks_picks_cfb.data.lake import (
    BuildRequest,
    DatasetRef,
    PartitionedDatasetPart,
    PartitionedDatasetRef,
    PartitionedDatasetWriter,
    build_dataset_version,
    canonical_frame_digest,
    iter_partitioned_dataset,
    read_dataset,
)
from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.forecast.shadow import score_freeze, update_evidence_counter

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "conf/research/data_first_football_v1/shadow_v1.yaml"

SCORE_MANIFEST_NAME = "score-manifest.json"
SCORE_MANIFEST_SCHEMA = "data_first_shadow_score_manifest_v1"
FREEZE_MANIFEST_SCHEMA = "data_first_shadow_freeze_manifest_v1"


class ScoreRunError(ValueError):
    """Raised before a V5-05B score run can produce reviewable evidence."""


class _Progress:
    _FORCED = frozenset(
        {
            "preflight_started",
            "parents_loaded",
            "freeze_loaded",
            "scoring_complete",
            "dry_run_complete",
            "apply_started",
            "evaluations_written",
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
            target=heartbeat, name=f"shadow-score-{self.run_id}", daemon=True
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
        raise ScoreRunError("timestamp must be timezone-aware")
    return parsed.to_pydatetime().astimezone(timezone.utc)


def _immutable_json(storage: Any, uri: str, payload: Mapping[str, Any]) -> None:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=str
    ).encode()
    if storage.exists(uri):
        if storage.read_bytes(uri) != encoded:
            raise ScoreRunError(f"immutable object collision at {uri}")
        return
    storage.write_bytes(encoded, uri)


def _read_json(storage: Any, uri: str) -> tuple[dict[str, Any], bytes]:
    raw = storage.read_bytes(uri)
    try:
        return json.loads(raw), raw
    except json.JSONDecodeError as exc:
        raise ScoreRunError(f"unreadable manifest: {uri}") from exc


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


def _load_freeze_manifest(storage: Any, uri: str) -> dict[str, Any]:
    manifest, _ = _read_json(storage, uri)
    if manifest.get("schema_version") != FREEZE_MANIFEST_SCHEMA:
        raise ScoreRunError(
            f"freeze manifest schema mismatch: {manifest.get('schema_version')}"
        )
    if manifest.get("state") != "frozen":
        raise ScoreRunError(
            f"freeze manifest not frozen: state={manifest.get('state')}"
        )
    return manifest


def _load_freeze_datasets(
    storage: Any, freeze_manifest: Mapping[str, Any]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    output_refs = freeze_manifest.get("output_refs") or {}
    freeze_ref_dict = output_refs.get("shadow_freeze")
    pred_ref_dict = output_refs.get("shadow_prediction")
    if not freeze_ref_dict or not pred_ref_dict:
        raise ScoreRunError(
            "freeze manifest missing shadow_freeze or shadow_prediction output ref"
        )

    # Load shadow_freeze
    freeze_ref = DatasetRef(
        dataset=freeze_ref_dict["dataset"],
        version_id=freeze_ref_dict["version_id"],
        schema_version=freeze_ref_dict["schema_version"],
        content_sha=freeze_ref_dict["content_sha"],
        uri=freeze_ref_dict["uri"],
    )
    freeze_record = read_dataset(storage, freeze_ref)

    # Load shadow_prediction
    if pred_ref_dict["artifact_kind"] == "partitioned_dataset_v1":
        part_manifest = json.loads(storage.read_bytes(pred_ref_dict["uri"]))
        pred_ref = PartitionedDatasetRef(
            artifact_kind=pred_ref_dict["artifact_kind"],
            dataset=pred_ref_dict["dataset"],
            version_id=pred_ref_dict["version_id"],
            schema_version=pred_ref_dict["schema_version"],
            content_sha=pred_ref_dict["content_sha"],
            records_sha=part_manifest.get("records_sha", ""),
            uri=pred_ref_dict["uri"],
            row_count=int(pred_ref_dict["row_count"]),
            partition_keys=tuple(
                part_manifest.get("partition_keys")
                or pred_ref_dict.get("partition_keys")
                or ("season", "week")
            ),
        )
        pred_frames = list(iter_partitioned_dataset(storage, pred_ref))
        predictions = (
            pd.concat(pred_frames, ignore_index=True) if pred_frames else pd.DataFrame()
        )
    else:
        pred_compact = DatasetRef(
            dataset=pred_ref_dict["dataset"],
            version_id=pred_ref_dict["version_id"],
            schema_version=pred_ref_dict["schema_version"],
            content_sha=pred_ref_dict["content_sha"],
            uri=pred_ref_dict["uri"],
        )
        predictions = read_dataset(storage, pred_compact)

    return freeze_record, predictions


def _load_outcomes(storage: Any, uri: str) -> pd.DataFrame:
    raw = storage.read_bytes(uri)
    import io

    try:
        return pd.read_parquet(io.BytesIO(raw))
    except Exception:
        try:
            return pd.DataFrame(json.loads(raw))
        except Exception as exc:
            raise ScoreRunError(f"cannot load outcomes from {uri}") from exc


def _load_existing_counter(storage: Any, uri: str | None) -> pd.DataFrame:
    if not uri or not storage.exists(uri):
        return pd.DataFrame(columns=list(EVIDENCE_COUNTER_COLUMNS))
    raw = storage.read_bytes(uri)
    import io

    try:
        df = pd.read_parquet(io.BytesIO(raw))
        if set(EVIDENCE_COUNTER_COLUMNS) <= set(df.columns):
            return df[list(EVIDENCE_COUNTER_COLUMNS)].copy()
    except Exception:
        pass
    try:
        data = json.loads(raw)
        df = pd.DataFrame(data)
        if set(EVIDENCE_COUNTER_COLUMNS) <= set(df.columns):
            return df[list(EVIDENCE_COUNTER_COLUMNS)].copy()
    except Exception:
        pass
    return pd.DataFrame(columns=list(EVIDENCE_COUNTER_COLUMNS))


def _plan_evidence(
    *,
    run_id: str,
    identity: Mapping[str, Any],
    args: argparse.Namespace,
    score_result: Any,
    counter_df: pd.DataFrame,
    qualifying_count: int,
    config: Mapping[str, Any],
    parents: Mapping[str, Any],
    forecast: Mapping[str, Any],
    rating: Mapping[str, Any],
) -> dict[str, Any]:
    dataset_e, schema_e = SHADOW_DATASETS["shadow_evaluation"]
    dataset_c, schema_c = SHADOW_DATASETS["evidence_counter"]

    schema_eval = schema_for(dataset_e, schema_e)
    validate_frame(score_result.evaluation, schema_eval)

    schema_count = schema_for(dataset_c, schema_c)
    validate_frame(counter_df, schema_count)

    eval_sha = canonical_frame_digest(
        score_result.evaluation, columns=list(SHADOW_EVALUATION_COLUMNS)
    )
    counter_sha = canonical_frame_digest(
        counter_df, columns=list(EVIDENCE_COUNTER_COLUMNS)
    )

    evidence = {
        "state": "dry_run",
        "identity": dict(identity),
        "run_id": run_id,
        "as_of": str(identity["as_of"]),
        "season": int(score_result.evaluation["season"].iloc[0]),
        "week": int(score_result.evaluation["week"].iloc[0]),
        "outcome_version": score_result.outcome_version,
        "qualifying": score_result.qualifying,
        "qualifying_reason": score_result.reason,
        "total_qualifying_slates": qualifying_count,
        "paired_count": score_result.paired_count,
        "mae_margin": score_result.mae_margin,
        "mae_total": score_result.mae_total,
        "freeze_manifest_uri": args.freeze_manifest_uri,
        "outcome_ref_uri": args.outcome_ref_uri,
        "preflight_plans": {
            "shadow_evaluation": {
                "name": "shadow_evaluation",
                "partition_keys": ["season", "week", "outcome_version"],
                "row_count": len(score_result.evaluation),
                "records_sha": eval_sha,
            },
            "shadow_evidence_counter": {
                "name": "shadow_evidence_counter",
                "partition_keys": [],
                "parts": [],
                "row_count": len(counter_df),
                "records_sha": counter_sha,
            },
        },
        "row_counts": {
            "shadow_evaluation": len(score_result.evaluation),
            "shadow_evidence_counter": len(counter_df),
        },
        "output_records_sha256": {
            "shadow_evaluation": eval_sha,
            "shadow_evidence_counter": counter_sha,
        },
        "production_activation_authorized": False,
    }
    return evidence


class ScorePreflight:
    def __init__(self, plan: dict[str, Any]) -> None:
        self.plan = plan


def _load_score_preflight(path: Path, *, identity: Mapping[str, Any]) -> ScorePreflight:
    try:
        payload = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as exc:
        raise ScoreRunError("preflight evidence is unreadable") from exc
    if payload.get("state") != "dry_run" or payload.get("identity") != dict(identity):
        raise ScoreRunError("preflight evidence identity does not match apply")
    plans = payload.get("preflight_plans") or {}
    for name in ("shadow_evaluation", "shadow_evidence_counter"):
        if name not in plans:
            raise ScoreRunError(f"preflight evidence missing {name} plan")
    return ScorePreflight(plan=plans)


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

    freeze_manifest = _load_freeze_manifest(storage, args.freeze_manifest_uri)
    freeze_record, predictions = _load_freeze_datasets(storage, freeze_manifest)
    progress.emit("freeze_loaded", paired_rows=len(predictions))

    outcomes = _load_outcomes(storage, args.outcome_ref_uri)
    freeze_summary = freeze_manifest.get("freeze_summary") or {}
    season = int(freeze_summary.get("season") or freeze_record["season"].iloc[0])
    week = int(freeze_summary.get("week") or freeze_record["week"].iloc[0])
    candidate = str(freeze_record["candidate"].iloc[0])

    min_stabilization = float(config.get("score_stabilization_seconds", 86400.0))
    score_result = score_freeze(
        candidate=candidate,
        season=season,
        week=week,
        run_id=args.run_id,
        freeze_record=freeze_record,
        predictions=predictions,
        outcomes=outcomes,
        outcome_version=args.outcome_version,
        scored_at=args.as_of,
        freeze_ref=args.freeze_manifest_uri,
        evaluation_ref="",
        min_stabilization_seconds=min_stabilization,
    )

    existing_counter = _load_existing_counter(
        storage, getattr(args, "existing_counter_uri", None)
    )
    updated_counter, qualifying_count = update_evidence_counter(
        existing_counter,
        score_result.counter_record,
        candidate=candidate,
        season=season,
        week=week,
    )

    progress.emit(
        "scoring_complete",
        paired_count=score_result.paired_count,
        qualifying=score_result.qualifying,
        mae_margin=round(score_result.mae_margin, 3)
        if score_result.mae_margin is not None
        else None,
        mae_total=round(score_result.mae_total, 3)
        if score_result.mae_total is not None
        else None,
        qualifying_slates=qualifying_count,
    )

    return _plan_evidence(
        run_id=args.run_id,
        identity=identity,
        args=args,
        score_result=score_result,
        counter_df=updated_counter,
        qualifying_count=qualifying_count,
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
    evidence: ScorePreflight,
) -> dict[str, Any]:
    prefix = f"{SHADOW_OUTPUT_ROOT}/{args.run_id}"
    score_manifest_uri = f"{prefix}/{SCORE_MANIFEST_NAME}"
    if storage.exists(score_manifest_uri):
        existing = json.loads(storage.read_bytes(score_manifest_uri))
        if (existing.get("identity") or {}).get("identity_sha256") == identity[
            "identity_sha256"
        ]:
            return {
                "state": "already_applied",
                "score_manifest_uri": score_manifest_uri,
            }
        raise ScoreRunError("score run ID already has a different identity")
    preexisting = sorted(storage.list_files(prefix))
    if preexisting:
        raise ScoreRunError(
            "score run prefix has a partial artifact and is permanently ineligible"
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

    # Re-derive scoring
    freeze_manifest = _load_freeze_manifest(storage, args.freeze_manifest_uri)
    freeze_record, predictions = _load_freeze_datasets(storage, freeze_manifest)
    outcomes = _load_outcomes(storage, args.outcome_ref_uri)
    freeze_summary = freeze_manifest.get("freeze_summary") or {}
    season = int(freeze_summary.get("season") or freeze_record["season"].iloc[0])
    week = int(freeze_summary.get("week") or freeze_record["week"].iloc[0])
    candidate = str(freeze_record["candidate"].iloc[0])

    min_stabilization = float(config.get("score_stabilization_seconds", 86400.0))
    score_result = score_freeze(
        candidate=candidate,
        season=season,
        week=week,
        run_id=args.run_id,
        freeze_record=freeze_record,
        predictions=predictions,
        outcomes=outcomes,
        outcome_version=args.outcome_version,
        scored_at=args.as_of,
        freeze_ref=args.freeze_manifest_uri,
        evaluation_ref="",
        min_stabilization_seconds=min_stabilization,
    )

    existing_counter = _load_existing_counter(
        storage, getattr(args, "existing_counter_uri", None)
    )
    updated_counter, qualifying_count = update_evidence_counter(
        existing_counter,
        score_result.counter_record,
        candidate=candidate,
        season=season,
        week=week,
    )

    # Validate frames against preflight evidence
    dataset_e, schema_e = SHADOW_DATASETS["shadow_evaluation"]
    dataset_c, schema_c = SHADOW_DATASETS["evidence_counter"]

    schema_eval = schema_for(dataset_e, schema_e)
    validate_frame(score_result.evaluation, schema_eval)
    eval_sha = canonical_frame_digest(
        score_result.evaluation, columns=list(SHADOW_EVALUATION_COLUMNS)
    )
    if eval_sha != evidence.plan["shadow_evaluation"].get("records_sha"):
        raise ScoreRunError(
            "apply recomputation differs from preflight: shadow_evaluation"
        )

    schema_count = schema_for(dataset_c, schema_c)
    validate_frame(updated_counter, schema_count)
    counter_sha = canonical_frame_digest(
        updated_counter, columns=list(EVIDENCE_COUNTER_COLUMNS)
    )
    if counter_sha != evidence.plan["shadow_evidence_counter"].get("records_sha"):
        raise ScoreRunError(
            "apply recomputation differs from preflight: shadow_evidence_counter"
        )

    # Write shadow_evaluation partitions
    as_of_dt = _utc(str(identity["as_of"]))
    writer = PartitionedDatasetWriter(
        storage,
        build=BuildRequest(
            dataset=dataset_e,
            parent_refs=(),
            code_sha=str(identity["code_sha"]),
            config_sha=str(identity["config_sha"]),
            as_of=as_of_dt,
            schema_version=schema_e,
            tier="gold",
        ),
        partition_keys=("season", "week", "outcome_version"),
    )
    eval_partition = score_result.evaluation.copy()
    writer.add(
        PartitionedDatasetPart(
            partition={
                "season": season,
                "week": week,
                "outcome_version": args.outcome_version,
            },
            frame=eval_partition,
        )
    )
    eval_ref = writer.finish()
    progress.emit("evaluations_written", row_count=int(eval_ref.row_count))

    # Write shadow_evidence_counter compact record
    ref_c, _ = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset=dataset_c,
            parent_refs=(),
            code_sha=str(identity["code_sha"]),
            config_sha=str(identity["config_sha"]),
            as_of=as_of_dt,
            schema_version=schema_c,
            tier="gold",
        ),
        records=updated_counter.loc[:, list(schema_count.required)].to_dict("records"),
    )

    # Build and write terminal score manifest (last)
    score_manifest = {
        "schema_version": SCORE_MANIFEST_SCHEMA,
        "state": "frozen",
        "identity": dict(identity),
        "parents": {
            "freeze_manifest_uri": args.freeze_manifest_uri,
            "outcome_ref_uri": args.outcome_ref_uri,
        },
        "output_refs": {
            "shadow_evaluation": {
                "artifact_kind": eval_ref.artifact_kind,
                "dataset": eval_ref.dataset,
                "version_id": eval_ref.version_id,
                "schema_version": eval_ref.schema_version,
                "content_sha": eval_ref.content_sha,
                "uri": eval_ref.uri,
                "row_count": eval_ref.row_count,
            },
            "shadow_evidence_counter": {
                "artifact_kind": ref_c.artifact_kind,
                "dataset": ref_c.dataset,
                "version_id": ref_c.version_id,
                "schema_version": ref_c.schema_version,
                "content_sha": ref_c.content_sha,
                "uri": ref_c.uri,
                "row_count": len(updated_counter),
            },
        },
        "score_summary": {
            "season": season,
            "week": week,
            "outcome_version": score_result.outcome_version,
            "qualifying": score_result.qualifying,
            "reason": score_result.reason,
            "paired_count": score_result.paired_count,
            "mae_margin": score_result.mae_margin,
            "mae_total": score_result.mae_total,
            "qualifying_slates_total": qualifying_count,
        },
        "production_activation_authorized": False,
    }
    _immutable_json(storage, score_manifest_uri, score_manifest)
    progress.emit("apply_complete", force=True, score_manifest_uri=score_manifest_uri)
    progress.close()
    return {
        "state": "applied",
        "score_manifest_uri": score_manifest_uri,
        "paired_count": score_result.paired_count,
        "qualifying": score_result.qualifying,
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
    parser.add_argument("--freeze-manifest-uri", required=True)
    parser.add_argument("--outcome-ref-uri", required=True)
    parser.add_argument("--outcome-version", default="v1")
    parser.add_argument("--existing-counter-uri")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--preflight-evidence")
    args = parser.parse_args(argv)

    if _git_sha() != args.expected_code_sha:
        raise ScoreRunError("expected code SHA does not match committed HEAD")
    if bool(args.preflight_evidence) != bool(args.apply):
        raise ScoreRunError("--apply and --preflight-evidence must be used together")
    storage = get_storage(environment="preview")
    if args.apply:
        if not _clean_worktree():
            raise ScoreRunError("apply requires a completely clean committed worktree")
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
        evidence = _load_score_preflight(
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
