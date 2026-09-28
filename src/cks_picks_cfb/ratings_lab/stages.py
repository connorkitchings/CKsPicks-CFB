"""Deterministic frame and report stages built on create-once research objects."""

from __future__ import annotations

import io
import json
from typing import Any

import pandas as pd

from .artifacts import ResearchArtifact, ResearchStorage, canonical_json, sha256
from .corpus import frame_bytes


def stage_identity(
    stage: str,
    parents: dict[str, str],
    config: dict[str, Any],
    code_sha: str,
    lock_sha: str,
) -> str:
    return sha256(
        canonical_json(
            {
                "stage": stage,
                "parents": parents,
                "config": config,
                "code_sha": code_sha,
                "lock_sha": lock_sha,
            }
        )
    )[:24]


def write_frame_stage(
    storage: ResearchStorage,
    *,
    stage: str,
    frame: pd.DataFrame,
    parents: dict[str, str],
    config: dict[str, Any],
    code_sha: str,
    lock_sha: str,
) -> ResearchArtifact:
    if "season" not in frame or frame.empty:
        raise ValueError("stage frame must have season-partitioned rows")
    identity = stage_identity(stage, parents, config, code_sha, lock_sha)
    children: list[ResearchArtifact] = []
    for season, part in frame.groupby("season", sort=True):
        columns = [
            key
            for key in ("season", "week", "game_id", "team", "role", "target")
            if key in part
        ]
        data = frame_bytes(
            part.sort_values(columns, kind="mergesort") if columns else part
        )
        digest = sha256(data)
        children.append(
            storage.write(
                key=f"ratings-lab/v1/runs/{identity}/{stage}/season={int(season)}/{digest}.parquet",
                data=data,
            )
        )
    return storage.publish_stage(
        stage=stage,
        identity=identity,
        children=children,
        metadata={
            "parents": parents,
            "config": config,
            "code_sha": code_sha,
            "lock_sha": lock_sha,
            "row_count": len(frame),
            "seasons": sorted(int(s) for s in frame.season.unique()),
        },
    )


def read_frame_stage(
    storage: ResearchStorage, manifest: ResearchArtifact, stage: str
) -> pd.DataFrame:
    payload = json.loads(storage.read_output(manifest))
    if (
        payload.get("stage") != stage
        or payload.get("schema_version") != "ratings_lab_stage_v1"
    ):
        raise ValueError("wrong research frame stage")
    parts = [
        pd.read_parquet(io.BytesIO(storage.read_output(ResearchArtifact(**item))))
        for item in payload["children"]
    ]
    if not parts:
        raise ValueError("empty research frame stage")
    frame = pd.concat(parts, ignore_index=True)
    if len(frame) != payload["metadata"]["row_count"]:
        raise ValueError("research stage row count mismatch")
    return frame


def write_report(
    storage: ResearchStorage,
    *,
    report: dict[str, Any],
    parents: dict[str, str],
    config: dict[str, Any],
    code_sha: str,
    lock_sha: str,
) -> ResearchArtifact:
    identity = stage_identity("comparison", parents, config, code_sha, lock_sha)
    data = canonical_json(report)
    child = storage.write(
        key=f"ratings-lab/v1/runs/{identity}/comparison/{sha256(data)}.json", data=data
    )
    return storage.publish_stage(
        stage="comparison",
        identity=identity,
        children=[child],
        metadata={
            "parents": parents,
            "config": config,
            "code_sha": code_sha,
            "lock_sha": lock_sha,
        },
    )
