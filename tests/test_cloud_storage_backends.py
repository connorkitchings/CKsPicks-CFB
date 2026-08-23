"""Offline behavior tests for the S3-compatible storage backends."""

from __future__ import annotations

import io
import sys
from datetime import datetime, timezone
from types import SimpleNamespace

import pandas as pd
import pytest

from cks_picks_cfb.data.storage import Partition, R2Storage, ReadOnlyStorage, S3Storage
from cks_picks_cfb.data.storage.base import StorageError


class FakeS3Client:
    """Small in-memory S3 implementation with the operations used by storage."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.put_calls: list[dict] = []
        self.deleted: list[str] = []

    def get_object(self, *, Bucket: str, Key: str):  # noqa: N803
        if Key not in self.objects:
            raise FileNotFoundError(Key)
        return {"Body": io.BytesIO(self.objects[Key])}

    def put_object(self, *, Bucket: str, Key: str, Body: bytes | str):  # noqa: N803
        self.objects[Key] = Body.encode() if isinstance(Body, str) else Body
        self.put_calls.append({"Bucket": Bucket, "Key": Key})

    def head_object(self, *, Bucket: str, Key: str):  # noqa: N803
        if Key not in self.objects:
            raise FileNotFoundError(Key)
        return {
            "ContentLength": len(self.objects[Key]),
            "ETag": '"fixture"',
            "LastModified": datetime(2026, 8, 23, tzinfo=timezone.utc),
            "VersionId": "v1",
            "ContentType": "application/octet-stream",
        }

    def delete_object(self, *, Bucket: str, Key: str):  # noqa: N803
        self.objects.pop(Key, None)
        self.deleted.append(Key)

    def list_objects_v2(self, *, Bucket: str, Prefix: str, **_: str):  # noqa: N803
        contents = [
            {
                "Key": key,
                "Size": len(value),
                "ETag": '"fixture"',
                "LastModified": datetime(2026, 8, 23, tzinfo=timezone.utc),
            }
            for key, value in sorted(self.objects.items())
            if key.startswith(Prefix)
        ]
        return {"Contents": contents, "IsTruncated": False}


def _r2(tmp_path) -> tuple[R2Storage, FakeS3Client]:
    client = FakeS3Client()
    storage = R2Storage.__new__(R2Storage)
    storage.bucket = "fixture"
    storage.s3_client = client
    storage.cache_dir = tmp_path / "cache"
    storage.cache_dir.mkdir()
    storage.max_workers = 2
    storage._cache_hits = 0
    storage._cache_misses = 0
    storage._memory_cache = {}
    storage._memory_cache_ttl = 300
    storage._memory_cache_timestamps = {}
    return storage, client


def _s3() -> tuple[S3Storage, FakeS3Client]:
    client = FakeS3Client()
    storage = S3Storage.__new__(S3Storage)
    storage.bucket = "fixture"
    storage.s3_client = client
    return storage, client


def test_cloud_constructors_configure_boto_without_network(monkeypatch, tmp_path):
    clients = []

    def client(*args, **kwargs):
        clients.append((args, kwargs))
        return FakeS3Client()

    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(client=client))
    r2 = R2Storage("bucket", "account", "key", "secret", cache_dir=str(tmp_path))
    s3 = S3Storage("bucket", region="us-west-2", access_key="key", secret_key="secret")

    assert r2.describe() == "r2:bucket"
    assert s3.describe() == "s3:bucket"
    assert clients[0][1]["endpoint_url"] == "https://account.r2.cloudflarestorage.com"
    assert clients[1][1]["region_name"] == "us-west-2"


def test_r2_bytes_csv_parquet_cache_and_metadata(tmp_path):
    storage, client = _r2(tmp_path)
    frame = pd.DataFrame({"team": ["A", "B"], "value": [1, 2]})

    storage.write_bytes(b"first", "objects/value.bin")
    assert storage.exists("objects/value.bin")
    assert storage.read_bytes("objects/value.bin") == b"first"
    assert (
        storage.get_full_path("objects/value.bin") == "s3://fixture/objects/value.bin"
    )
    assert storage.object_metadata("objects/value.bin")["version_id"] == "v1"

    storage.write_csv(frame, "objects/data.csv", index=False)
    pd.testing.assert_frame_equal(storage.read_csv("objects/data.csv"), frame)
    storage.write_parquet(frame, "objects/data.parquet")
    pd.testing.assert_frame_equal(storage.read_parquet("objects/data.parquet"), frame)

    assert storage._download_file("objects/value.bin") == b"first"
    client.objects["objects/value.bin"] = b"changed-remotely"
    assert storage._download_file("objects/value.bin") == b"first"
    storage.write_bytes(b"fresh", "objects/value.bin")
    assert storage._download_file("objects/value.bin") == b"fresh"
    assert storage._cache_hits >= 1
    assert storage._cache_misses >= 2


def test_r2_reads_parallel_indexes_and_writes_partition_manifests(tmp_path):
    storage, client = _r2(tmp_path)
    prefix = "raw/games/year=2026"
    for number in (1, 2):
        buffer = io.BytesIO()
        pd.DataFrame({"game_id": [number], "team": [f"T{number}"]}).to_parquet(buffer)
        client.objects[f"{prefix}/part-{number}.parquet"] = buffer.getvalue()

    rows = storage.read_index("raw/games", {"year": 2026}, parallel=True)
    assert {row["game_id"] for row in rows} == {1, 2}
    assert storage.read_index("raw/games", {"year": 2026}) == rows

    count = storage.write(
        "silver/games",
        [{"game_id": 10, "season": 2026}],
        Partition({"year": "2026"}),
    )
    assert count == 1
    assert any(key.endswith("part-0.parquet") for key in client.objects)
    assert any(key.endswith("manifest.json") for key in client.objects)
    assert storage.write("silver/empty", [], Partition({"year": "2026"})) == 0


def test_r2_quarantines_unreadable_index_and_parallel_download_errors(
    tmp_path, monkeypatch
):
    storage, client = _r2(tmp_path)
    client.objects["raw/games/year=2026/bad.parquet"] = b"not parquet"
    quarantined = []
    monkeypatch.setattr(
        storage, "quarantine_object", lambda key, error: quarantined.append(key)
    )
    with pytest.raises(StorageError, match="Unreadable parquet"):
        storage.read_index("raw/games", {"year": 2026}, parallel=False)
    assert quarantined == ["raw/games/year=2026/bad.parquet"]

    monkeypatch.setattr(
        storage, "_download_file", lambda *_: (_ for _ in ()).throw(OSError("down"))
    )
    with pytest.raises(StorageError, match="Failed to download"):
        storage._download_files_parallel(["missing"])


def test_s3_index_csv_parquet_write_and_read_only_delegate(tmp_path):
    storage, client = _s3()
    storage.write_csv(
        pd.DataFrame({"id": [1]}), "raw/teams/year=2026/data.csv", index=False
    )
    assert storage.read_index("raw/teams", {"year": 2026}) == [{"id": 1}]
    assert (
        storage.write("silver/teams", [{"team": "A"}], Partition({"year": "2026"})) == 1
    )
    assert storage.root() == "s3://fixture"
    assert storage.list_object_metadata("silver/")

    read_only = ReadOnlyStorage(storage)
    assert read_only.read_bytes("raw/teams/year=2026/data.csv")
    with pytest.raises(StorageError, match="read-only"):
        read_only.write_bytes(b"no", "forbidden")
    with pytest.raises(StorageError, match="read_index is disabled"):
        read_only.read_index("raw/teams", {"year": 2026})
