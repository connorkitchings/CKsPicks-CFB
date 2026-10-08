"""Shared constants and helpers for Stage 6B reconstruction stages."""

from __future__ import annotations

import hashlib
import io
import json
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from cks_picks_cfb.data.lake import (
    BuildRequest,
    DatasetRef,
    PartitionedDatasetPart,
    PartitionedDatasetRef,
    PartitionedDatasetWriter,
    iter_partitioned_dataset,
    parquet_bytes,
)
from cks_picks_cfb.data.storage.local import LocalStorage
from cks_picks_cfb.rebuild.errors import GateError
from cks_picks_cfb.rebuild.orchestrator import StageContext

WEEKS = (0, 1, 2, 3, 4, 5)
# Signed checksum of the Task 4 receipt of the first published 6A run. A plan replaying a
# different 6A run names its receipt in the ``expected_6a_receipt_sha`` policy instead.
LEGACY_6A_RECEIPT_SHA = (
    "efcedf3e67dd85055782474b5022bf73d7f53d80c630264ca7c491699309d15e"
)
EXPECTED_COUNTS = {0: 8, 1: 43, 2: 49, 3: 57, 4: 58, 5: 56}
TOTAL_2026_GAMES = 271

# Original forecast as_of timestamps from the source lock (0-4) and Week 5 serving manifest
WEEK_AS_OF = {
    0: "2026-08-23T18:00:00Z",
    1: "2026-09-03T05:00:00Z",
    2: "2026-09-08T19:00:00Z",
    3: "2026-09-13T21:00:00Z",
    4: "2026-09-20T19:00:00Z",
    5: "2026-09-29T20:29:00Z",
}

SELECTION_POLICY = "model_side_best_quote_v2"
EVIDENCE_CLASS = "retrospective_reconstruction"
RUN_ID_TEMPLATE = "2026w{week}-v5recon-6b-r1"
SERVED_RUN_ID_TEMPLATE = "2026w{week}-v5repair-20260929-p1"
SERVED_WEEK5_RUN_ID = "2026w5-v5repair-20260929-p2"


def original_run_id(week: int) -> str:
    return (
        SERVED_WEEK5_RUN_ID if week == 5 else SERVED_RUN_ID_TEMPLATE.format(week=week)
    )


def recon_run_id(week: int) -> str:
    return RUN_ID_TEMPLATE.format(week=week)


def parquet_data(frame: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    frame.to_parquet(buffer, index=False)
    return buffer.getvalue()


def read_parquet_data(data: bytes) -> pd.DataFrame:
    return pd.read_parquet(io.BytesIO(data))


def json_data(obj: Any) -> bytes:
    return json.dumps(
        obj, indent=2, sort_keys=True, separators=(",", ": "), default=str
    ).encode()


def frame_digest(frame: pd.DataFrame) -> str:
    hashed = pd.util.hash_pandas_object(frame.reset_index(drop=True), index=False)
    return hashlib.sha256(hashed.to_numpy().tobytes()).hexdigest()


def as_stored(frame: pd.DataFrame) -> pd.DataFrame:
    """The frame exactly as a reader sees it after a parquet round-trip."""
    return pd.read_parquet(io.BytesIO(parquet_bytes(frame.to_dict("records"))))


def write_partitioned_gold(
    context: StageContext,
    *,
    dataset: str,
    schema_version: str,
    frames_by_week: Mapping[int, pd.DataFrame],
    as_of: str | None = None,
    config_sha: str = "reconstruction_6b_v1",
    parent_refs: Sequence[Any] = (),
) -> tuple[dict[str, Any], list[tuple[str, bytes]]]:
    """Write week-partitioned Gold dataset parts and return summary and file tuples."""
    effective_as_of = as_of or context.plan.cutoff_2026
    summary: dict[str, Any] = {}
    artifacts: list[tuple[str, bytes]] = []

    with tempfile.TemporaryDirectory(prefix=f"6b-gold-{dataset}-") as tmp:
        local = LocalStorage(tmp)
        # Catalog edges name real immutable dataset versions, never stage/run IDs.
        typed_parents = catalog_parents(context)
        writer = PartitionedDatasetWriter(
            local,
            build=BuildRequest(
                dataset=dataset,
                parent_refs=typed_parents,
                code_sha=context.code_sha,
                config_sha=hashlib.sha256(
                    json_data(
                        {
                            "plan": context.plan.plan_sha(),
                            "stage": context.stage.name,
                            "parents": dict(context.parents),
                            "inputs": dict(context.inputs),
                        }
                    )
                ).hexdigest(),
                as_of=datetime.fromisoformat(effective_as_of.replace("Z", "+00:00")),
                schema_version=schema_version,
                tier="gold",
            ),
            partition_keys=("week",),
        )
        total_rows = 0
        for week in sorted(frames_by_week):
            frame = as_stored(frames_by_week[week])
            total_rows += len(frame)
            writer.add(
                PartitionedDatasetPart(
                    partition={"week": week},
                    frame=frame,
                )
            )
        ref = writer.finish()
        # Creation time is physical metadata, not a model input. Preserve the
        # first staged creation time when independently rebuilding a version.
        files = sorted((p for p in Path(tmp).rglob("*") if p.is_file()), key=str)
        for path in files:
            key = str(path.relative_to(tmp))
            if path.name in ("manifest.json", "partitioned-manifest.json"):
                value = json.loads(path.read_bytes())
                try:
                    prior = json.loads(context.read_artifact(context.stage.name, key))
                except (KeyError, FileNotFoundError, OSError):
                    prior = None
                if prior is not None:
                    value["created_at"] = prior["created_at"]
                path.write_bytes(
                    json.dumps(
                        value, sort_keys=True, separators=(",", ":"), default=str
                    ).encode()
                )
            artifacts.append((key, path.read_bytes()))
        root_bytes = next(data for key, data in artifacts if key == ref.uri)
        summary = {
            **asdict(ref),
            "content_sha": hashlib.sha256(root_bytes).hexdigest(),
            "rows": total_rows,
            "parts": [dict(p) for p in writer.parts],
        }
    return summary, artifacts


class StagedLakeStorage:
    """Serve staged bytes to lake reader functions for verification."""

    def __init__(self, context: StageContext, stage: str):
        self._context = context
        self._stage = stage

    def read_bytes(self, uri: str) -> bytes:
        return self._context.read_artifact(self._stage, uri)

    def exists(self, uri: str) -> bool:
        try:
            self.read_bytes(uri)
            return True
        except (FileNotFoundError, KeyError, OSError):
            return False


def load_partitioned_gold(
    context: StageContext,
    stage: str,
    summary_info: Mapping[str, Any],
) -> pd.DataFrame:
    ref_dict = dict(summary_info)
    ref = PartitionedDatasetRef(
        dataset=ref_dict["dataset"],
        version_id=ref_dict["version_id"],
        schema_version=ref_dict["schema_version"],
        content_sha=ref_dict["content_sha"],
        uri=ref_dict["uri"],
        partition_keys=("week",),
        artifact_kind=ref_dict["artifact_kind"],
        records_sha=ref_dict["records_sha"],
        row_count=ref_dict["row_count"],
    )
    manifest = json.loads(StagedLakeStorage(context, stage).read_bytes(ref.uri))
    if manifest["partition_keys"] != ["week"] or {
        int(p["partition"]["week"]) for p in manifest["parts"]
    } != set(WEEKS):
        raise GateError("Gold week partition coverage changed")
    frames = list(iter_partitioned_dataset(StagedLakeStorage(context, stage), ref))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def checked_read(storage, ref: Mapping[str, Any]) -> bytes:
    """Read an exact source reference and verify its raw content hash."""
    uri = ref["uri"]
    if uri.startswith(("artifacts/production/", "production/")):
        raise GateError("production input reads are outside the 6B review")
    data = storage.read_bytes(uri)
    expected = ref.get("content_sha", ref.get("sha256", ref.get("raw_sha256")))
    if not expected or hashlib.sha256(data).hexdigest() != expected:
        raise GateError(f"source hash mismatch: {uri}")
    return data


def source_refs(context: StageContext) -> dict[str, Any]:
    value = json.loads(context.read_input("reconstruction_source_refs"))
    if value["schema_version"] != "reconstruction_source_refs_v1" or set(
        value["weeks"]
    ) != {str(w) for w in WEEKS}:
        raise GateError("reconstruction source metadata coverage changed")
    return value


def weekly_as_of(context: StageContext) -> dict[int, str]:
    summary = json.loads(
        context.read_artifact(
            "foundation", f"{context.plan.run_prefix()}foundation/summary.json"
        )
    )
    values = summary["weekly_as_of"]
    if set(values) != {str(w) for w in WEEKS}:
        raise GateError("forecast cutoff coverage changed")
    return {int(w): value for w, value in values.items()}


def catalog_parents(context: StageContext) -> tuple[DatasetRef, ...]:
    refs = {}
    for stage in context.stage.parents:
        summary = json.loads(
            context.read_artifact(
                stage, f"{context.plan.run_prefix()}{stage}/summary.json"
            )
        )
        if "lake_gold" in summary:
            ref = summary["lake_gold"]
            refs[ref["version_id"]] = DatasetRef(
                **{
                    k: ref[k]
                    for k in (
                        "dataset",
                        "version_id",
                        "schema_version",
                        "content_sha",
                        "uri",
                    )
                }
            )
    if not refs and "root_manifest_6a" in context.stage.inputs:
        from cks_picks_cfb.rebuild.published import PublishedRun

        run = PublishedRun(context, root_input="root_manifest_6a")
        for key in sorted(run.objects):
            if key.startswith("lake/") and key.endswith(
                ("/manifest.json", "/partitioned-manifest.json")
            ):
                manifest = json.loads(run.read(key))
                if key.endswith("/partitioned-manifest.json"):
                    ref = DatasetRef(
                        manifest["dataset"],
                        manifest["version_id"],
                        manifest["schema_version"],
                        hashlib.sha256(run.read(key)).hexdigest(),
                        key,
                    )
                elif manifest["tier"] == "silver":
                    ref = DatasetRef(
                        **{
                            k: manifest[k]
                            for k in (
                                "dataset",
                                "version_id",
                                "schema_version",
                                "content_sha",
                                "uri",
                            )
                        }
                    )
                else:
                    continue
                refs[ref.version_id] = ref
    if not refs:
        raise GateError("reconstruction Gold dataset has no catalog parents")
    return tuple(refs[k] for k in sorted(refs))


def verify_rederived(context: StageContext, build, verify) -> list[str]:
    """Recompute from pinned source/parent bytes, not trusted summary booleans."""
    try:
        problems = list(verify(context))
        expected = build(context)
        for key, data in expected.artifacts:
            if context.read_artifact(context.stage.name, key) != data:
                problems.append(f"re-derived artifact differs: {key}")
        return problems
    except Exception as exc:
        return [f"{context.stage.name} persisted re-derivation failed: {exc}"]


def expected_6a_receipt_sha(context: StageContext) -> str:
    """The signed Task 4 receipt checksum this plan expects (plan policy, else the legacy)."""
    value = context.plan.policies.get("expected_6a_receipt_sha", LEGACY_6A_RECEIPT_SHA)
    if not isinstance(value, str) or len(value) != 64:
        raise GateError("policy expected_6a_receipt_sha must be a 64-hex checksum")
    return value
