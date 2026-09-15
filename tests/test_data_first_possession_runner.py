"""Runner idempotency and progress contracts for V5 possession certification."""

from __future__ import annotations

import json
from dataclasses import dataclass

import pandas as pd
import pytest

from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.data.data_first_possession_v1 import POSSESSION_DATASETS
from scripts.research.run_data_first_possession_measurements import (
    PossessionRunError,
    _concat_source_frames,
    _existing_apply_manifest,
)


@dataclass
class _MemoryStorage:
    objects: dict[str, bytes]

    def exists(self, uri: str) -> bool:
        return uri in self.objects

    def read_bytes(self, uri: str) -> bytes:
        return self.objects[uri]


def _payloads(identity_sha: str = "identity") -> tuple[str, dict[str, bytes]]:
    manifest_uri = "runs/example/measurement-manifest.json"
    certification = signed_payload(
        {
            "all_checks_passed": True,
            "production_activation_authorized": False,
        }
    )
    outputs = {
        name: {
            "artifact_kind": "partitioned_dataset_v1",
            "dataset": dataset,
            "version_id": f"{name}-v1",
            "schema_version": schema,
            "content_sha": "a" * 64,
            "records_sha": "b" * 64,
            "uri": f"lake/{name}/partitioned-manifest.json",
            "row_count": 1,
            "partition_keys": ["season"],
        }
        for name, (dataset, schema) in POSSESSION_DATASETS.items()
    }
    manifest = signed_payload(
        {
            "identity": {"identity_sha256": identity_sha},
            "output_refs": outputs,
            "certification_sha256": certification["manifest_sha256"],
            "production_activation_authorized": False,
        }
    )
    objects = {
        manifest_uri: json.dumps(
            manifest, sort_keys=True, separators=(",", ":")
        ).encode(),
        "runs/example/certification.json": json.dumps(
            certification, sort_keys=True, separators=(",", ":")
        ).encode(),
    }
    return manifest_uri, objects


def test_existing_apply_returns_before_expensive_preflight() -> None:
    manifest_uri, objects = _payloads()
    result = _existing_apply_manifest(
        _MemoryStorage(objects),
        manifest_uri=manifest_uri,
        identity={"identity_sha256": "identity"},
    )
    assert result is not None
    assert result["identity"]["identity_sha256"] == "identity"


def test_existing_apply_rejects_identity_collision() -> None:
    manifest_uri, objects = _payloads("other")
    with pytest.raises(PossessionRunError, match="different identity"):
        _existing_apply_manifest(
            _MemoryStorage(objects),
            manifest_uri=manifest_uri,
            identity={"identity_sha256": "identity"},
        )


def test_existing_apply_rejects_incomplete_output_reference() -> None:
    manifest_uri, objects = _payloads()
    manifest = json.loads(objects[manifest_uri])
    manifest["output_refs"]["adjusted_history"].pop("records_sha")
    manifest = signed_payload(manifest)
    objects[manifest_uri] = json.dumps(
        manifest, sort_keys=True, separators=(",", ":")
    ).encode()
    with pytest.raises(PossessionRunError, match="output reference is invalid"):
        _existing_apply_manifest(
            _MemoryStorage(objects),
            manifest_uri=manifest_uri,
            identity={"identity_sha256": "identity"},
        )


def test_source_concat_handles_cross_season_all_null_dtype_without_warning() -> None:
    frame = _concat_source_frames(
        [
            pd.DataFrame({"season": [2021], "optional": [None]}),
            pd.DataFrame({"season": [2022], "optional": [1.5]}),
        ]
    )
    assert frame["optional"].tolist() == [None, 1.5]
