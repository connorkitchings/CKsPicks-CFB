"""Safety gates for the fixed local artifact archive command."""

# Ruff cannot lowercase the S3 API keyword arguments used by this fake client.
# ruff: noqa: N803

from __future__ import annotations

import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from botocore.exceptions import ClientError

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/ops/archive_local_artifacts.py"
SPEC = importlib.util.spec_from_file_location("archive_local_artifacts", SCRIPT)
assert SPEC and SPEC.loader
archive = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(archive)


def not_found() -> ClientError:
    return ClientError({"Error": {"Code": "404"}}, "HeadObject")


class FakeClient:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.uploads: dict[str, list[bytes]] = {}
        self.rules: list[dict] = []
        self.fail_part = False
        self.read_corrupt = False
        self.writes = 0

    def head_object(self, *, Bucket: str, Key: str) -> dict:
        if Key not in self.objects:
            raise not_found()
        return {"ContentLength": len(self.objects[Key])}

    def get_object(self, *, Bucket: str, Key: str) -> dict:
        data = self.objects[Key]
        if self.read_corrupt:
            data = b"X" + data[1:]
        return {
            "Body": SimpleNamespace(
                iter_chunks=lambda chunk_size: (
                    data[i : i + chunk_size] for i in range(0, len(data), chunk_size)
                ),
                close=lambda: None,
            ),
            "ContentLength": len(data),
        }

    def put_object(
        self, *, Bucket: str, Key: str, Body, IfNoneMatch: str, **kwargs
    ) -> dict:
        assert IfNoneMatch == "*"
        if Key in self.objects:
            raise ClientError({"Error": {"Code": "PreconditionFailed"}}, "PutObject")
        self.objects[Key] = Body.read() if hasattr(Body, "read") else Body
        self.writes += 1
        return {}

    def create_multipart_upload(self, *, Bucket: str, Key: str) -> dict:
        self.uploads[Key] = []
        return {"UploadId": Key}

    def upload_part(
        self, *, Bucket: str, Key: str, UploadId: str, PartNumber: int, Body: bytes
    ) -> dict:
        if self.fail_part:
            raise ValueError("incomplete upload")
        self.uploads[Key].append(Body)
        return {"ETag": str(PartNumber)}

    def complete_multipart_upload(
        self,
        *,
        Bucket: str,
        Key: str,
        UploadId: str,
        MultipartUpload: dict,
        IfNoneMatch: str,
    ) -> dict:
        assert IfNoneMatch == "*"
        if Key in self.objects:
            raise ClientError(
                {"Error": {"Code": "PreconditionFailed"}}, "CompleteMultipartUpload"
            )
        self.objects[Key] = b"".join(self.uploads.pop(Key))
        self.writes += 1
        return {}

    def abort_multipart_upload(self, *, Bucket: str, Key: str, UploadId: str) -> None:
        self.uploads.pop(Key, None)

    def get_bucket_lifecycle_configuration(self, *, Bucket: str) -> dict:
        return {"Rules": self.rules}


@pytest.fixture
def setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    paths = (
        "artifacts/preview/training/v4/selection-candidates-20260818.csv",
        "artifacts/preview/training/v4/locked-candidates-20260818.csv",
    )
    monkeypatch.setattr(archive, "ALLOWLIST", paths)
    monkeypatch.setattr(archive, "DELETE", frozenset((paths[0],)))
    monkeypatch.setattr(archive, "PART_SIZE", 8)
    for name in paths:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"abcdefghijklmnopq" if name == paths[0] else b"keep")
    return tmp_path, paths, FakeClient()


def rows_and_manifest(root: Path, client: FakeClient):
    rows = archive.inventory(root)
    manifest = archive.make_manifest(rows, "preview")
    return rows, manifest


def upload_all(
    root: Path, client: FakeClient, rows: list[dict], manifest: dict, tmp_path: Path
) -> Path:
    for row, item in zip(rows, manifest["files"], strict=True):
        archive.upload_item(
            client, "preview", root, {**item, "identity": row["identity"]}
        )
    local_manifest = tmp_path / "manifest.json"
    archive.publish_manifest(client, "preview", manifest, local_manifest)
    return local_manifest


def test_success_reuse_verify_and_prune(setup, tmp_path: Path):
    root, paths, client = setup
    rows, manifest = rows_and_manifest(root, client)
    local_manifest = upload_all(root, client, rows, manifest, tmp_path)
    writes = client.writes
    assert archive.load_manifest(local_manifest, "preview") == manifest
    for row, item in zip(rows, manifest["files"], strict=True):
        assert (
            archive.upload_item(
                client, "preview", root, {**item, "identity": row["identity"]}
            )
            == "reused"
        )
    assert client.writes == writes
    archive.verify_all(client, "preview", manifest)
    journal = tmp_path / "journal.jsonl"
    assert archive.prune(root, client, "preview", manifest, journal) == [paths[0]]
    first_event = json.loads(journal.read_text().splitlines()[0])
    assert first_event["lifecycle_proof"]["rules"] == []
    assert not (root / paths[0]).exists()
    assert (root / paths[1]).read_bytes() == b"keep"
    assert archive.prune(root, client, "preview", manifest, journal) == []


def test_existing_key_collision_and_remote_mismatch(setup):
    root, _, client = setup
    rows, manifest = rows_and_manifest(root, client)
    item = {**manifest["files"][0], "identity": rows[0]["identity"]}
    client.objects[item["key"]] = b"wrong"
    with pytest.raises(ValueError, match="remote hash or size mismatch"):
        archive.upload_item(client, "preview", root, item)
    client.objects[item["key"]] = (root / item["path"]).read_bytes()
    client.read_corrupt = True
    with pytest.raises(ValueError, match="remote hash or size mismatch"):
        archive.upload_item(client, "preview", root, item)


def test_incomplete_upload_aborts(setup):
    root, _, client = setup
    rows, manifest = rows_and_manifest(root, client)
    client.fail_part = True
    item = {**manifest["files"][0], "identity": rows[0]["identity"]}
    with pytest.raises(ValueError, match="incomplete upload"):
        archive.upload_item(client, "preview", root, item)
    assert item["key"] not in client.objects
    assert client.uploads == {}


def test_changed_file_and_symlink_rejected(setup, tmp_path: Path):
    root, paths, client = setup
    rows, manifest = rows_and_manifest(root, client)
    item = {**manifest["files"][0], "identity": rows[0]["identity"]}
    (root / paths[0]).write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed before multipart upload"):
        archive.upload_item(client, "preview", root, item)
    path = root / paths[1]
    path.unlink()
    path.symlink_to(tmp_path / "other")
    with pytest.raises(ValueError, match="not a regular file"):
        archive.local_digest(root, paths[1])


def test_missing_lifecycle_proof_and_expiring_rule(setup, tmp_path: Path):
    root, paths, client = setup
    rows, manifest = rows_and_manifest(root, client)
    upload_all(root, client, rows, manifest, tmp_path)
    client.get_bucket_lifecycle_configuration = lambda **kwargs: (_ for _ in ()).throw(
        ClientError(
            {"Error": {"Code": "AccessDenied"}}, "GetBucketLifecycleConfiguration"
        )
    )
    journal = tmp_path / "journal.jsonl"
    with pytest.raises(ValueError, match="lifecycle proof unavailable"):
        archive.prune(root, client, "preview", manifest, journal)
    assert (root / paths[0]).exists()
    assert not journal.exists()
    client.get_bucket_lifecycle_configuration = lambda **kwargs: {
        "Rules": [
            {
                "Status": "Enabled",
                "Filter": {"Prefix": archive.PREFIX},
                "Expiration": {"Days": 30},
            }
        ]
    }
    with pytest.raises(ValueError, match="expiration"):
        archive.prune(root, client, "preview", manifest, journal)
    assert (root / paths[0]).exists()


def test_interrupted_prune_requires_prepared_proof(setup, tmp_path: Path):
    root, paths, client = setup
    rows, manifest = rows_and_manifest(root, client)
    upload_all(root, client, rows, manifest, tmp_path)
    journal = tmp_path / "journal.jsonl"
    (root / paths[0]).unlink()
    with pytest.raises(ValueError, match="missing without prune proof"):
        archive.prune(root, client, "preview", manifest, journal)
    archive.journal_event(
        journal,
        {
            "path": paths[0],
            "state": "prepared",
            "size": rows[0]["size"],
            "sha256": rows[0]["sha256"],
        },
    )
    assert archive.prune(root, client, "preview", manifest, journal) == []


def test_unexpected_path_and_unknown_lifecycle_filter(setup):
    root, _, _ = setup
    with pytest.raises(ValueError, match="not allowlisted"):
        archive.checked_path(root, "other")
    with pytest.raises(ValueError, match="unrecognized lifecycle filter"):
        archive.expiry_applies(
            [
                {
                    "Status": "Enabled",
                    "Filter": {"Tag": {"k": "v"}},
                    "Expiration": {"Days": 1},
                }
            ],
            archive.PREFIX,
        )


def test_dashboard_proof_is_bound_to_evidence_file(tmp_path: Path):
    client = FakeClient()
    screenshot = tmp_path / "lifecycle.png"
    screenshot.write_bytes(b"reviewed dashboard capture")
    record = {
        "bucket": "preview",
        "source": "cloudflare_dashboard",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "evidence_path": str(screenshot),
        "evidence_sha256": hashlib.sha256(screenshot.read_bytes()).hexdigest(),
        "Rules": [],
    }
    proof = tmp_path / "proof.json"
    proof.write_text(json.dumps(record))
    assert archive.lifecycle_gate(client, "preview", proof)["rules"] == []
    screenshot.write_bytes(b"changed")
    with pytest.raises(ValueError, match="evidence hash mismatch"):
        archive.lifecycle_gate(client, "preview", proof)
