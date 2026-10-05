"""Helpers shared by 6A stages: storage identity, staged Silver frames, parent refs."""

from __future__ import annotations

import io
import json
from collections.abc import Mapping
from typing import Any

import pandas as pd

from cks_picks_cfb.rebuild.errors import GateError
from cks_picks_cfb.rebuild.orchestrator import StageContext
from cks_picks_cfb.rebuild.plan import HISTORICAL_SEASONS
from cks_picks_cfb.rebuild.retry import RetryingStorage
from cks_picks_cfb.rebuild.silver import SUMMARY as SILVER_SUMMARY
from cks_picks_cfb.rebuild.silver import check_capture_manifest

SILVER_STAGE = "silver"


def preview_storage(context: StageContext):
    """The legacy storage backend, only after its identity equals the plan's."""
    from dotenv import load_dotenv

    load_dotenv()
    from cks_picks_cfb.data.storage import get_storage
    from cks_picks_cfb.data.storage.base import StorageSettings

    settings = StorageSettings.from_env(environment="preview")
    if f"r2:{settings.account_id}:{settings.bucket}" != context.plan.storage_identity:
        raise GateError("storage identity differs from the plan")
    return RetryingStorage(get_storage(environment="preview"))


def dataset_ref(entry: Mapping[str, Any]):
    from cks_picks_cfb.data.lake import DatasetRef

    return DatasetRef(
        dataset=entry["dataset"],
        version_id=entry["version_id"],
        schema_version=entry["schema_version"],
        content_sha=entry["content_sha"],
        uri=entry["uri"],
    )


def silver_summary(context: StageContext) -> dict[str, Any]:
    return json.loads(
        context.read_artifact(
            SILVER_STAGE, SILVER_SUMMARY.format(run_id=context.plan.run_id)
        )
    )


def staged_silver(context: StageContext, dataset: str) -> pd.DataFrame:
    """Concatenate one derived Silver dataset across seasons from the staged build."""
    summary = silver_summary(context)
    seasons = sorted(item["season"] for item in summary["seasons"])
    if seasons != sorted(HISTORICAL_SEASONS):
        raise GateError(f"staged silver seasons are {seasons}")
    frames = []
    for item in sorted(summary["seasons"], key=lambda i: i["season"]):
        data_key = item["datasets"][dataset]["keys"][0]
        frames.append(
            pd.read_parquet(io.BytesIO(context.read_artifact(SILVER_STAGE, data_key)))
        )
    return pd.concat(frames, ignore_index=True)


def pinned_parent(pin_file: Mapping[str, Any], season: int, dataset: str):
    entry = pin_file["seasons"][str(season)]
    for item in entry["parents"]:
        if item["dataset"] == dataset:
            return dataset_ref(item)
    raise GateError(f"{season}: no pinned {dataset}")


def declared_missing_ids(
    storage, source_set: Mapping[str, Any], season: int
) -> set[int]:
    """Provider-declared play omissions for one season from its pinned capture manifest."""
    from cks_picks_cfb.data.history_play_capture import (
        manifest_declared_missing_game_ids,
    )

    entries = [
        e
        for e in source_set["entries"]
        if int(e["season"]) == season and e["entity"] == "plays"
    ]
    if len(entries) != 1:
        raise GateError(f"source set must hold exactly one {season} plays entry")
    uri = entries[0]["manifest_uri"]
    check_capture_manifest(storage.read_bytes(uri), entries[0]["manifest_sha256"])
    return manifest_declared_missing_game_ids(storage, uri, season=season)
