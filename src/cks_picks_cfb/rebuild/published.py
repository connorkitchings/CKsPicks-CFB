"""Hash-checked access to the published 6A run, for the Task 4 analysis stages.

The published root manifest is pinned as a plan input; every other key is read from Preview
R2 and must equal the hash the root manifest recorded. Nothing is read from local staging.
"""

from __future__ import annotations

import hashlib
import io
import json
from typing import Any

import pandas as pd

from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload
from cks_picks_cfb.rebuild import common
from cks_picks_cfb.rebuild.errors import GateError
from cks_picks_cfb.rebuild.orchestrator import StageContext


class PublishedRun:
    def __init__(self, context: StageContext, *, root_input: str = "root_manifest"):
        self.context = context
        self.storage = common.preview_storage(context)
        self.root = json.loads(context.read_input(root_input))
        verify_signed_payload(self.root, label="published root manifest")
        if self.root.get("kind") != "rebuild_root_v1":
            raise GateError("pinned input is not a published 6A root manifest")
        self.prefix = f"rebuild/6a/{self.root['run_id']}/"
        self.objects: dict[str, str] = dict(self.root["objects"])

    def read(self, key: str) -> bytes:
        expected = self.objects.get(key)
        if expected is None:
            raise GateError(f"{key} is not in the published root manifest")
        data = self.storage.read_bytes(key)
        if hashlib.sha256(data).hexdigest() != expected:
            raise GateError(f"published object changed: {key}")
        return data

    def run_key(self, relative: str) -> str:
        return self.prefix + relative

    def json(self, relative: str) -> Any:
        return json.loads(self.read(self.run_key(relative)))

    def frame(self, relative: str) -> pd.DataFrame:
        return pd.read_parquet(io.BytesIO(self.read(self.run_key(relative))))

    def dataset_frames(
        self, dataset: str, *, season_scope: str
    ) -> dict[int, pd.DataFrame]:
        """Published Silver datasets by season; ``historical`` excludes 2026, ``2026`` keeps it."""
        frames: dict[int, pd.DataFrame] = {}
        for key in sorted(self.objects):
            if not key.startswith(
                f"lake/silver/dataset={dataset}/"
            ) or not key.endswith("/manifest.json"):
                continue
            manifest = json.loads(self.read(key))
            seasons = [int(s) for s in manifest["partitions"].get("seasons", [])]
            if len(seasons) != 1:
                continue
            season = seasons[0]
            if (season == 2026) != (season_scope == "2026"):
                continue
            data = self.read(manifest["uri"])
            if hashlib.sha256(data).hexdigest() != manifest["content_sha"]:
                raise GateError(
                    f"{dataset} {season}: data hash differs from its manifest"
                )
            frames[season] = pd.read_parquet(io.BytesIO(data))
        return frames
