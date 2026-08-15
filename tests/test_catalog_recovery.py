import json
from dataclasses import asdict

import pytest

from cks_picks_cfb.data.catalog import (
    catalog_connection_url,
    register_existing_dataset_ref,
)
from cks_picks_cfb.data.lake import DatasetManifest, DatasetRef


class MemoryStorage:
    def __init__(self, objects: dict[str, bytes]):
        self.objects = objects

    def read_bytes(self, path: str) -> bytes:
        return self.objects[path]

    def list_files(self, prefix: str) -> list[str]:
        return [path for path in self.objects if path.startswith(prefix)]


def _existing_dataset() -> tuple[MemoryStorage, str, DatasetRef, DatasetManifest]:
    ref_uri = "artifacts/preview/refs/history/games-2026.json"
    ref = DatasetRef(
        dataset="games",
        version_id="version-1",
        schema_version="games_v2",
        content_sha="abc123",
        uri="lake/silver/dataset=games/version=version-1/data.parquet",
    )
    manifest = DatasetManifest(
        dataset=ref.dataset,
        version_id=ref.version_id,
        tier="silver",
        schema_version=ref.schema_version,
        content_sha=ref.content_sha,
        uri=ref.uri,
        row_count=8,
        partitions={"seasons": [2026]},
        created_at="2026-08-15T00:00:00+00:00",
        as_of="2026-08-15T00:00:00+00:00",
        source_capture_ids=("capture-1",),
        validation={"valid": True},
    )
    manifest_uri = ref.uri.rsplit("/", 1)[0] + "/manifest.json"
    storage = MemoryStorage(
        {
            ref_uri: json.dumps(asdict(ref)).encode(),
            manifest_uri: json.dumps(asdict(manifest)).encode(),
        }
    )
    return storage, ref_uri, ref, manifest


def test_register_existing_dataset_ref_verifies_and_registers(monkeypatch):
    storage, ref_uri, expected_ref, expected_manifest = _existing_dataset()
    registered = []
    monkeypatch.setattr(
        "cks_picks_cfb.data.catalog.register_dataset_version",
        lambda conn_url, ref, manifest: registered.append((conn_url, ref, manifest)),
    )

    ref = register_existing_dataset_ref("postgresql://preview", storage, ref_uri)

    assert ref == expected_ref
    assert registered == [("postgresql://preview", expected_ref, expected_manifest)]


def test_register_existing_dataset_ref_rejects_identity_mismatch(monkeypatch):
    storage, ref_uri, _, _ = _existing_dataset()
    manifest_uri = "lake/silver/dataset=games/version=version-1/manifest.json"
    manifest = json.loads(storage.objects[manifest_uri])
    manifest["content_sha"] = "different"
    storage.objects[manifest_uri] = json.dumps(manifest).encode()
    monkeypatch.setattr(
        "cks_picks_cfb.data.catalog.register_dataset_version",
        lambda *_: pytest.fail("mismatched metadata must not be registered"),
    )

    with pytest.raises(ValueError, match="content_sha"):
        register_existing_dataset_ref("postgresql://preview", storage, ref_uri)


def test_register_existing_dataset_ref_registers_manifest_parents_first(monkeypatch):
    storage, ref_uri, child_ref, child_manifest = _existing_dataset()
    parent_ref = DatasetRef(
        dataset="teams",
        version_id="parent-1",
        schema_version="teams_v1",
        content_sha="parent-sha",
        uri="lake/silver/dataset=teams/version=parent-1/data.parquet",
    )
    parent_manifest = DatasetManifest(
        dataset=parent_ref.dataset,
        version_id=parent_ref.version_id,
        tier="silver",
        schema_version=parent_ref.schema_version,
        content_sha=parent_ref.content_sha,
        uri=parent_ref.uri,
        row_count=138,
        partitions={"seasons": [2026]},
        created_at="2026-08-15T00:00:00+00:00",
        as_of="2026-08-15T00:00:00+00:00",
        validation={"valid": True},
    )
    child_manifest = DatasetManifest(
        **{
            **asdict(child_manifest),
            "parent_versions": (parent_ref.version_id,),
            "source_capture_ids": (),
        }
    )
    child_manifest_uri = child_ref.uri.rsplit("/", 1)[0] + "/manifest.json"
    parent_manifest_uri = parent_ref.uri.rsplit("/", 1)[0] + "/manifest.json"
    storage.objects[child_manifest_uri] = json.dumps(asdict(child_manifest)).encode()
    storage.objects[parent_manifest_uri] = json.dumps(asdict(parent_manifest)).encode()
    registered = []
    monkeypatch.setattr(
        "cks_picks_cfb.data.catalog.register_dataset_version",
        lambda _conn_url, ref, _manifest: registered.append(ref.version_id),
    )

    register_existing_dataset_ref("postgresql://preview", storage, ref_uri)

    assert registered == [parent_ref.version_id, child_ref.version_id]


def test_catalog_connection_url_requires_preview_specific_credential(monkeypatch):
    monkeypatch.delenv("PREVIEW_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://production")

    with pytest.raises(RuntimeError, match="PREVIEW_DATABASE_URL"):
        catalog_connection_url("preview")
