"""Shared constants and helpers for Stage 6B reconstruction stages."""

from __future__ import annotations

import hashlib
import io
import json
import tempfile
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from cks_picks_cfb.data.lake import (
    BuildRequest,
    PartitionedDatasetPart,
    PartitionedDatasetRef,
    PartitionedDatasetWriter,
    iter_partitioned_dataset,
    parquet_bytes,
)
from cks_picks_cfb.data.storage.local import LocalStorage
from cks_picks_cfb.rebuild.orchestrator import StageContext

WEEKS = (0, 1, 2, 3, 4, 5)
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
    return SERVED_WEEK5_RUN_ID if week == 5 else SERVED_RUN_ID_TEMPLATE.format(week=week)


def recon_run_id(week: int) -> str:
    return RUN_ID_TEMPLATE.format(week=week)


def parquet_data(frame: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    frame.to_parquet(buffer, index=False)
    return buffer.getvalue()


def read_parquet_data(data: bytes) -> pd.DataFrame:
    return pd.read_parquet(io.BytesIO(data))


def json_data(obj: Any) -> bytes:
    return json.dumps(obj, indent=2, sort_keys=True, separators=(",", ": "), default=str).encode()


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
        writer = PartitionedDatasetWriter(
            local,
            build=BuildRequest(
                dataset=dataset,
                parent_refs=tuple(parent_refs),
                code_sha=context.code_sha,
                config_sha=config_sha,
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
        summary = {
            "dataset": dataset,
            "schema_version": schema_version,
            "version_id": ref.version_id,
            "content_sha": ref.content_sha,
            "uri": ref.uri,
            "rows": total_rows,
            "parts": [dict(p) for p in writer.parts],
        }
        files = sorted(
            (p for p in Path(tmp).rglob("*") if p.is_file()),
            key=lambda p: (p.name == "partitioned-manifest.json", str(p)),
        )
        for path in files:
            artifacts.append((str(path.relative_to(tmp)), path.read_bytes()))
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
    )
    frames = list(iter_partitioned_dataset(StagedLakeStorage(context, stage), ref))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
