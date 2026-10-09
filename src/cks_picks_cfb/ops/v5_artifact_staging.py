"""Stage packaged prediction runs from one artifact namespace into another.

A packaged run is four immutable objects: the predictions CSV, the ``prediction_run_v1``
manifest, the scored CSV and the ``scored_run_v1`` manifest. Only ``artifact_uri`` is
environment specific, so staging copies the CSV bytes unchanged, rewrites that one field
in each manifest, and writes every object once with a byte readback. Nothing the research
chain signed (forecast, serving, verifier manifests) is touched; those live at shared,
environment-independent paths. The caller supplies the target storage, so a dry run needs
no credentials for it beyond read access.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.ratings_lab.artifacts import canonical_json

ENVIRONMENTS = ("preview", "production")
RECEIPT_SCHEMA = "v5_artifact_staging_receipt_v1"


class StagingError(ValueError):
    """A run cannot be staged byte-for-byte into the target namespace."""


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _prefix(environment: str) -> str:
    return f"artifacts/{environment}/"


def _rebase(uri: str, source: str, target: str) -> str:
    if not uri.startswith(_prefix(source)):
        raise StagingError(f"{uri} is not in the {source} namespace")
    return _prefix(target) + uri[len(_prefix(source)) :]


def _run_dir(environment: str, week: int, run_id: str) -> tuple[str, str]:
    predictions = (
        f"artifacts/{environment}/predictions/year=2026/week={week}/run_id={run_id}"
    )
    scored = f"artifacts/{environment}/scored/year=2026/week={week}/run_id={run_id}"
    return predictions, scored


def plan_run(
    source_storage: Any,
    *,
    source: str,
    target: str,
    week: int,
    run_id: str,
    predictions_only: bool = False,
) -> dict[str, Any]:
    """Read and verify one source run, returning the exact target objects.

    ``predictions_only`` stages a run that has no scored artifact yet (a pending display-only
    run). It is explicit, and it refuses a run that does have a scored artifact so a scored run
    is never staged half way.
    """
    if source not in ENVIRONMENTS or target not in ENVIRONMENTS or source == target:
        raise StagingError("source and target must be different known environments")
    pred_dir, scored_dir = _run_dir(source, week, run_id)
    manifest_raw = source_storage.read_bytes(f"{pred_dir}/manifest.json")
    manifest = json.loads(manifest_raw)
    if predictions_only:
        if source_storage.exists(f"{scored_dir}/manifest.json"):
            raise StagingError(
                f"run {run_id} has a scored artifact; stage it without predictions_only"
            )
        if manifest.get("schema_version") != "prediction_run_v1" or (
            manifest.get("run_id") != run_id or manifest.get("week") != week
        ):
            raise StagingError(f"source manifest does not describe run {run_id}")
        predictions_raw = source_storage.read_bytes(manifest["artifact_uri"])
        if _sha(predictions_raw) != manifest["artifact_sha256"]:
            raise StagingError(f"source artifact for {run_id} fails its own checksum")
        target_manifest = {
            **manifest,
            "artifact_uri": _rebase(manifest["artifact_uri"], source, target),
        }
        t_pred_dir, _ = _run_dir(target, week, run_id)
        if target_manifest["artifact_uri"] != f"{t_pred_dir}/predictions.csv":
            raise StagingError(f"run {run_id} is not at the standard artifact layout")
        return {
            "run_id": run_id,
            "week": week,
            "objects": [
                (target_manifest["artifact_uri"], predictions_raw),
                (f"{t_pred_dir}/manifest.json", canonical_json(target_manifest)),
            ],
            "target_manifest": target_manifest,
            "target_artifact_sha256": target_manifest["artifact_sha256"],
        }
    scored_manifest_raw = source_storage.read_bytes(f"{scored_dir}/manifest.json")
    scored_manifest = json.loads(scored_manifest_raw)
    if (
        manifest.get("schema_version") != "prediction_run_v1"
        or scored_manifest.get("schema_version") != "scored_run_v1"
        or manifest.get("run_id") != run_id
        or scored_manifest.get("run_id") != run_id
        or manifest.get("week") != week
        or scored_manifest.get("week") != week
    ):
        raise StagingError(f"source manifests do not describe run {run_id}")
    predictions_raw = source_storage.read_bytes(manifest["artifact_uri"])
    scored_raw = source_storage.read_bytes(scored_manifest["artifact_uri"])
    if (
        _sha(predictions_raw) != manifest["artifact_sha256"]
        or _sha(scored_raw) != scored_manifest["artifact_sha256"]
        or scored_manifest["prediction_artifact_sha256"] != manifest["artifact_sha256"]
    ):
        raise StagingError(f"source artifacts for {run_id} fail their own checksums")

    target_manifest = {
        **manifest,
        "artifact_uri": _rebase(manifest["artifact_uri"], source, target),
    }
    target_scored = {
        **scored_manifest,
        "artifact_uri": _rebase(scored_manifest["artifact_uri"], source, target),
    }
    t_pred_dir, t_scored_dir = _run_dir(target, week, run_id)
    if (
        target_manifest["artifact_uri"] != f"{t_pred_dir}/predictions.csv"
        or target_scored["artifact_uri"] != f"{t_scored_dir}/scored.csv"
    ):
        raise StagingError(f"run {run_id} is not at the standard artifact layout")
    objects = [
        (target_manifest["artifact_uri"], predictions_raw),
        (f"{t_pred_dir}/manifest.json", canonical_json(target_manifest)),
        (target_scored["artifact_uri"], scored_raw),
        (f"{t_scored_dir}/manifest.json", canonical_json(target_scored)),
    ]
    return {
        "run_id": run_id,
        "week": week,
        "objects": objects,
        "target_manifest": target_manifest,
        "target_artifact_sha256": target_manifest["artifact_sha256"],
    }


def _write_once(storage: Any, uri: str, raw: bytes) -> str:
    if storage.exists(uri):
        if storage.read_bytes(uri) != raw:
            raise StagingError(f"target object already differs: {uri}")
        return "present"
    storage.write_bytes(raw, uri)
    if storage.read_bytes(uri) != raw:
        raise StagingError(f"target object failed byte readback: {uri}")
    return "written"


def stage_runs(
    source_storage: Any,
    target_storage: Any,
    runs: Mapping[int, str],
    *,
    source: str,
    target: str,
    apply: bool,
    predictions_only: bool = False,
) -> dict[str, Any]:
    """Plan every run first, then (only with ``apply``) write them all once."""
    plans = [
        plan_run(
            source_storage,
            source=source,
            target=target,
            week=w,
            run_id=r,
            predictions_only=predictions_only,
        )
        for w, r in sorted(runs.items())
    ]
    items = []
    for plan in plans:
        results = {}
        for uri, raw in plan["objects"]:
            if apply:
                results[uri] = _write_once(target_storage, uri, raw)
            else:
                exists = target_storage.exists(uri)
                if exists and target_storage.read_bytes(uri) != raw:
                    raise StagingError(f"target object already differs: {uri}")
                results[uri] = "present" if exists else "would_write"
        items.append(
            {
                "week": plan["week"],
                "run_id": plan["run_id"],
                "artifact_sha256": plan["target_artifact_sha256"],
                "objects": [
                    {"uri": uri, "sha256": _sha(raw), "state": results[uri]}
                    for uri, raw in plan["objects"]
                ],
            }
        )
    return signed_payload(
        {
            "schema_version": RECEIPT_SCHEMA,
            "source": source,
            "target": target,
            "applied": apply,
            "runs": items,
        }
    )
