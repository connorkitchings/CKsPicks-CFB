"""Versioned operational artifact paths and storage helpers."""

from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from cks_picks_cfb.data.storage import StorageBackend, get_storage


def local_prediction_path(year: int, week: int) -> Path:
    return _working_root() / "predictions" / str(year) / f"CFB_week{week}_bets.csv"


def local_scored_path(year: int, week: int) -> Path:
    return _working_root() / "scored" / str(year) / f"CFB_week{week}_bets_scored.csv"


def _working_root() -> Path:
    """Return an explicit ephemeral working root, never repository ``./data``."""
    configured = os.getenv("CFB_WORK_ROOT")
    if configured:
        return Path(configured)
    return Path(tempfile.gettempdir()) / "cks-picks-cfb"


def prediction_artifact_path(year: int, week: int) -> str:
    """Legacy mutable path retained only for backward-compatible reads."""
    return f"artifacts/{_artifact_environment()}/predictions/year={year}/CFB_week{week}_bets.csv"


def _artifact_environment() -> str:
    environment = os.getenv("CFB_ARTIFACT_ENV", "production").lower()
    if environment not in {"production", "preview"}:
        raise ValueError("CFB_ARTIFACT_ENV must be 'production' or 'preview'")
    return environment


def prediction_run_prefix(year: int, week: int, run_id: str) -> str:
    return f"artifacts/{_artifact_environment()}/predictions/year={year}/week={week}/run_id={run_id}"


def prediction_run_artifact_path(year: int, week: int, run_id: str) -> str:
    return f"{prediction_run_prefix(year, week, run_id)}/predictions.csv"


def prediction_run_manifest_path(year: int, week: int, run_id: str) -> str:
    return f"{prediction_run_prefix(year, week, run_id)}/manifest.json"


def prediction_run_features_path(year: int, week: int, run_id: str) -> str:
    return f"{prediction_run_prefix(year, week, run_id)}/point_in_time_features.csv"


def active_prediction_manifest_path(year: int, week: int) -> str:
    """Deprecated compatibility path; Neon owns active-run selection."""
    return f"artifacts/{_artifact_environment()}/legacy-pointers/year={year}/week={week}/active.json"


def frozen_prediction_manifest_path(year: int, week: int) -> str:
    """Deprecated compatibility path; Neon owns frozen-run selection."""
    return f"artifacts/{_artifact_environment()}/legacy-pointers/year={year}/week={week}/frozen.json"


def scored_artifact_path(year: int, week: int) -> str:
    return f"artifacts/{_artifact_environment()}/scored/year={year}/CFB_week{week}_bets_scored.csv"


def scored_run_artifact_path(year: int, week: int, run_id: str) -> str:
    return (
        f"artifacts/{_artifact_environment()}/scored/"
        f"year={year}/week={week}/run_id={run_id}/scored.csv"
    )


def preview_prediction_manifest_path(year: int, week: int) -> str:
    """Deprecated compatibility path; callers must supply an explicit run ID."""
    return f"artifacts/{_artifact_environment()}/legacy-pointers/year={year}/week={week}/preview.json"


def scored_run_manifest_path(year: int, week: int, run_id: str) -> str:
    return (
        f"artifacts/{_artifact_environment()}/scored/year={year}/week={week}/"
        f"run_id={run_id}/manifest.json"
    )


def scored_artifact_prefix(year: int) -> str:
    return f"artifacts/{_artifact_environment()}/scored/year={year}/"


def read_csv_artifact(path: str, storage: StorageBackend | None = None) -> pd.DataFrame:
    store = storage or get_storage()
    return store.read_csv(path)


def write_csv_artifact(
    df: pd.DataFrame,
    path: str,
    storage: StorageBackend | None = None,
) -> None:
    store = storage or get_storage()
    store.write_csv(df, path, index=False)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dataframe_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def write_json_artifact(
    payload: Mapping[str, Any],
    path: str,
    storage: StorageBackend | None = None,
) -> None:
    store = storage or get_storage()
    data = json.dumps(dict(payload), indent=2, sort_keys=True).encode("utf-8")
    store.write_bytes(data, path)


def read_json_artifact(
    path: str, storage: StorageBackend | None = None
) -> dict[str, Any]:
    store = storage or get_storage()
    return json.loads(store.read_bytes(path).decode("utf-8"))


def read_verified_csv_artifact(
    manifest: Mapping[str, Any], storage: StorageBackend | None = None
) -> pd.DataFrame:
    """Read a manifest-addressed CSV only when its checksum matches."""
    store = storage or get_storage()
    uri = str(manifest["artifact_uri"])
    expected = str(manifest["artifact_sha256"])
    payload = store.read_bytes(uri)
    actual = sha256_bytes(payload)
    if actual != expected:
        raise ValueError(
            f"Artifact checksum mismatch for {uri}: {actual} != {expected}"
        )
    return pd.read_csv(io.BytesIO(payload))


def write_prediction_run(
    df: pd.DataFrame,
    *,
    year: int,
    week: int,
    run_id: str,
    manifest: Mapping[str, Any],
    storage: StorageBackend | None = None,
) -> dict[str, Any]:
    """Write an immutable CSV+manifest without advancing any mutable pointer."""
    store = storage or get_storage()
    artifact_path = prediction_run_artifact_path(year, week, run_id)
    manifest_path = prediction_run_manifest_path(year, week, run_id)
    csv_bytes = dataframe_csv_bytes(df)
    artifact_exists = store.exists(artifact_path)
    manifest_exists = store.exists(manifest_path)
    if artifact_exists != manifest_exists:
        raise FileExistsError(
            f"Partial prediction run requires reconciliation: {run_id}"
        )
    if artifact_exists:
        existing = read_json_artifact(manifest_path, store)
        if (
            store.read_bytes(artifact_path) != csv_bytes
            or existing.get("artifact_sha256") != sha256_bytes(csv_bytes)
            or existing.get("run_id") != run_id
        ):
            raise FileExistsError(f"Immutable prediction run collision: {run_id}")
        return existing

    payload = {
        **dict(manifest),
        "schema_version": "prediction_run_v1",
        "run_id": run_id,
        "season": year,
        "week": week,
        "artifact_uri": artifact_path,
        "artifact_sha256": sha256_bytes(csv_bytes),
        "row_count": int(len(df)),
    }
    store.write_bytes(csv_bytes, artifact_path)
    write_json_artifact(payload, manifest_path, store)
    return payload
