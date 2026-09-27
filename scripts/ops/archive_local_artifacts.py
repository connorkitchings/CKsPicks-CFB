"""Back up a fixed set of historical local artifacts to Preview R2.

Run from the repository root with ``.venv/bin/python scripts/ops/archive_local_artifacts.py``.
No mode reads the project's ``data/`` directory. Prune is deliberately gated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from botocore.exceptions import ClientError
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
PREFIX = "artifacts/research/local-artifact-archive-v1"
MANIFEST = ROOT / "docs/reports/2026-09-27-local-artifact-archive-manifest.json"
JOURNAL = ROOT / "docs/reports/2026-09-27-local-artifact-prune-journal.jsonl"
PART_SIZE = 16 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024
TRAINING = (
    "artifacts/preview/training/v4/selection-candidates-20260818.csv",
    "artifacts/preview/training/week0-regime-candidates.csv",
    "artifacts/preview/training/v4/locked-candidates-20260818.csv",
    "artifacts/preview/training/v4/selection-candidates-20260818.blend-weights.json",
    "artifacts/preview/training/week0-regime-candidates.weights.json",
)
TRACES = tuple(
    f"archive/legacy_v1_2025/artifacts/ratings/{year}/trace.nc"
    for year in (2019, 2021, 2022, 2023, 2024, 2025)
)
ALLOWLIST = TRAINING + TRACES
DELETE = frozenset((TRAINING[0], TRAINING[1], *TRACES))


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def identity(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def checked_path(root: Path, relative: str) -> Path:
    if relative not in ALLOWLIST:
        raise ValueError(f"not allowlisted: {relative}")
    path = root / relative
    parent = root
    if parent.is_symlink():
        raise ValueError(f"symlink in path: {relative}")
    for component in Path(relative).parts[:-1]:
        parent = parent / component
        if parent.is_symlink():
            raise ValueError(f"symlink in path: {relative}")
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError(f"not a regular file: {relative}")
    return path


def local_digest(root: Path, relative: str) -> dict[str, Any]:
    path = checked_path(root, relative)
    before = path.lstat()
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        if identity(os.fstat(stream.fileno())) != identity(before):
            raise ValueError(f"changed before hashing: {relative}")
        digest = hashlib.sha256()
        while chunk := stream.read(CHUNK_SIZE):
            digest.update(chunk)
        if identity(os.fstat(stream.fileno())) != identity(before):
            raise ValueError(f"changed during hashing: {relative}")
    if identity(path.lstat()) != identity(before):
        raise ValueError(f"changed after hashing: {relative}")
    return {
        "path": relative,
        "size": before.st_size,
        "allocated_bytes": before.st_blocks * 512,
        "sha256": digest.hexdigest(),
        "identity": list(identity(before)),
    }


def inventory(root: Path) -> list[dict[str, Any]]:
    return [local_digest(root, name) for name in ALLOWLIST]


def key_for(item: dict[str, Any]) -> str:
    return f"{PREFIX}/files/sha256={item['sha256']}/{Path(item['path']).name}"


def remote_digest(client: Any, bucket: str, key: str) -> tuple[int, str]:
    response = client.get_object(Bucket=bucket, Key=key)
    digest = hashlib.sha256()
    size = 0
    body = response["Body"]
    try:
        for chunk in body.iter_chunks(chunk_size=CHUNK_SIZE):
            if chunk:
                digest.update(chunk)
                size += len(chunk)
    finally:
        body.close()
    if size != response["ContentLength"]:
        raise ValueError(f"incomplete remote read: {key}")
    return size, digest.hexdigest()


def remote_exists(client: Any, bucket: str, key: str) -> bool:
    try:
        client.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] in {"404", "NoSuchKey", "NotFound"}:
            return False
        raise


def verify_item(client: Any, bucket: str, item: dict[str, Any]) -> None:
    size, sha256 = remote_digest(client, bucket, item["key"])
    if (size, sha256) != (item["size"], item["sha256"]):
        raise ValueError(f"remote hash or size mismatch: {item['path']}")


def upload_item(client: Any, bucket: str, root: Path, item: dict[str, Any]) -> str:
    """Write once. Complete multipart conditionally; abort unfinished uploads."""
    key = item["key"]
    if remote_exists(client, bucket, key):
        verify_item(client, bucket, item)
        after = local_digest(root, item["path"])
        if any(after[k] != item[k] for k in ("size", "sha256", "identity")):
            raise ValueError(f"local file changed during reuse: {item['path']}")
        return "reused"
    path = checked_path(root, item["path"])
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    if item["size"] <= PART_SIZE:
        with os.fdopen(os.open(path, flags), "rb") as stream:
            if list(identity(os.fstat(stream.fileno()))) != item["identity"]:
                raise ValueError(f"local file changed before upload: {item['path']}")
            try:
                client.put_object(
                    Bucket=bucket,
                    Key=key,
                    Body=stream,
                    ContentLength=item["size"],
                    IfNoneMatch="*",
                )
            except ClientError as exc:
                if exc.response["Error"]["Code"] not in {"PreconditionFailed", "412"}:
                    raise
                verify_item(client, bucket, item)
                if local_digest(root, item["path"])["identity"] != item["identity"]:
                    raise ValueError(f"local file changed during reuse: {item['path']}")
                return "reused"
    else:
        response = client.create_multipart_upload(Bucket=bucket, Key=key)
        upload_id = response["UploadId"]
        completed = False
        try:
            parts = []
            with os.fdopen(os.open(path, flags), "rb") as stream:
                if list(identity(os.fstat(stream.fileno()))) != item["identity"]:
                    raise ValueError(
                        f"local file changed before multipart upload: {item['path']}"
                    )
                number = 1
                while chunk := stream.read(PART_SIZE):
                    part = client.upload_part(
                        Bucket=bucket,
                        Key=key,
                        UploadId=upload_id,
                        PartNumber=number,
                        Body=chunk,
                    )
                    parts.append({"PartNumber": number, "ETag": part["ETag"]})
                    number += 1
            try:
                client.complete_multipart_upload(
                    Bucket=bucket,
                    Key=key,
                    UploadId=upload_id,
                    MultipartUpload={"Parts": parts},
                    IfNoneMatch="*",
                )
                completed = True
            except ClientError as exc:
                if exc.response["Error"]["Code"] not in {"PreconditionFailed", "412"}:
                    raise
                verify_item(client, bucket, item)
                if local_digest(root, item["path"])["identity"] != item["identity"]:
                    raise ValueError(f"local file changed during reuse: {item['path']}")
                return "reused"
        finally:
            if not completed:
                client.abort_multipart_upload(
                    Bucket=bucket, Key=key, UploadId=upload_id
                )
    after = local_digest(root, item["path"])
    if any(after[k] != item[k] for k in ("size", "sha256", "identity")):
        raise ValueError(f"local file changed during upload: {item['path']}")
    verify_item(client, bucket, item)
    return "uploaded"


def make_manifest(rows: list[dict[str, Any]], bucket: str) -> dict[str, Any]:
    return {
        "schema": "local-artifact-archive-v1",
        "bucket": bucket,
        "prefix": PREFIX,
        "files": [
            {
                "path": row["path"],
                "size": row["size"],
                "sha256": row["sha256"],
                "key": key_for(row),
            }
            for row in rows
        ],
    }


def manifest_key(manifest: dict[str, Any]) -> str:
    return f"{PREFIX}/manifests/sha256={hashlib.sha256(canonical(manifest)).hexdigest()}.json"


def publish_manifest(
    client: Any, bucket: str, manifest: dict[str, Any], path: Path
) -> str:
    data = canonical(manifest)
    key = manifest_key(manifest)
    if remote_exists(client, bucket, key):
        size, digest = remote_digest(client, bucket, key)
        if (size, digest) != (len(data), hashlib.sha256(data).hexdigest()):
            raise ValueError("manifest key collision")
    else:
        client.put_object(Bucket=bucket, Key=key, Body=data, IfNoneMatch="*")
        size, digest = remote_digest(client, bucket, key)
        if (size, digest) != (len(data), hashlib.sha256(data).hexdigest()):
            raise ValueError("remote manifest mismatch")
    if path.exists() and path.read_bytes() != data:
        raise ValueError("tracked manifest differs; refusing overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return key


def load_manifest(path: Path, bucket: str) -> dict[str, Any]:
    manifest = json.loads(path.read_bytes())
    if (
        manifest.get("schema") != "local-artifact-archive-v1"
        or manifest.get("bucket") != bucket
    ):
        raise ValueError("manifest schema or bucket mismatch")
    if manifest.get("prefix") != PREFIX:
        raise ValueError("manifest prefix mismatch")
    files = manifest.get("files", [])
    if [row.get("path") for row in files] != list(ALLOWLIST):
        raise ValueError("manifest path allowlist mismatch")
    if any(row.get("key") != key_for(row) for row in files):
        raise ValueError("manifest backup key mismatch")
    return manifest


def verify_all(client: Any, bucket: str, manifest: dict[str, Any]) -> None:
    for item in manifest["files"]:
        verify_item(client, bucket, item)
        print(f"verified {item['path']}", flush=True)
    data = canonical(manifest)
    size, digest = remote_digest(client, bucket, manifest_key(manifest))
    if (size, digest) != (len(data), hashlib.sha256(data).hexdigest()):
        raise ValueError("remote manifest mismatch")


def expiry_applies(rules: list[dict[str, Any]], prefix: str) -> bool:
    for rule in rules:
        if rule.get("Status") not in {"Enabled", "Disabled"}:
            raise ValueError("unrecognized lifecycle status; retain local files")
        if rule.get("Status") != "Enabled":
            continue
        filter_value = rule.get("Filter", {})
        if not isinstance(filter_value, dict) or set(filter_value) - {"Prefix"}:
            raise ValueError("unrecognized lifecycle filter; retain local files")
        rule_prefix = rule.get("Prefix", filter_value.get("Prefix", ""))
        if not isinstance(rule_prefix, str):
            raise ValueError("invalid lifecycle prefix")
        intersects = prefix.startswith(rule_prefix) or rule_prefix.startswith(prefix)
        if intersects and any(
            field in rule for field in ("Expiration", "NoncurrentVersionExpiration")
        ):
            return True
    return False


def lifecycle_gate(
    client: Any, bucket: str, proof: Path | None = None
) -> dict[str, Any]:
    if proof is None:
        try:
            response = client.get_bucket_lifecycle_configuration(Bucket=bucket)
            rules = response.get("Rules", [])
            source = "Preview R2 GetBucketLifecycleConfiguration"
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "NoSuchLifecycleConfiguration":
                raise ValueError(
                    "lifecycle proof unavailable; retain every local file"
                ) from exc
            rules = []
            source = "Preview R2 NoSuchLifecycleConfiguration"
    else:
        record = json.loads(proof.read_text())
        if (
            record.get("bucket") != bucket
            or record.get("source") != "cloudflare_dashboard"
        ):
            raise ValueError("invalid dashboard lifecycle proof")
        if not record.get("evidence_sha256") or len(record["evidence_sha256"]) != 64:
            raise ValueError("dashboard evidence SHA-256 missing")
        evidence = Path(record.get("evidence_path", ""))
        if not evidence.is_file() or evidence.is_symlink():
            raise ValueError("dashboard evidence file missing or symlinked")
        if (
            hashlib.sha256(evidence.read_bytes()).hexdigest()
            != record["evidence_sha256"]
        ):
            raise ValueError("dashboard evidence hash mismatch")
        observed = datetime.fromisoformat(record["observed_at"])
        now = datetime.now(timezone.utc)
        if observed.tzinfo is None or not now - timedelta(days=1) <= observed <= now:
            raise ValueError("lifecycle proof is stale")
        rules = record["Rules"]
        source = str(proof)
    if not isinstance(rules, list) or expiry_applies(rules, PREFIX + "/"):
        raise ValueError("enabled lifecycle expiration may cover backup prefix")
    return {
        "bucket": bucket,
        "source": source,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "rules": json.loads(json.dumps(rules, default=str)),
        "evidence_sha256": record["evidence_sha256"] if proof else None,
    }


def journal_event(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as stream:
        stream.write(canonical(event))
        stream.flush()
        os.fsync(stream.fileno())


def prune(
    root: Path,
    client: Any,
    bucket: str,
    manifest: dict[str, Any],
    journal: Path,
    proof: Path | None = None,
) -> list[str]:
    lifecycle_record = lifecycle_gate(client, bucket, proof)
    verify_all(client, bucket, manifest)
    events = (
        [json.loads(line) for line in journal.read_text().splitlines()]
        if journal.exists()
        else []
    )
    latest = {event["path"]: event for event in events}
    deleted = []
    for item in manifest["files"]:
        relative = item["path"]
        if relative not in DELETE:
            continue
        path = root / relative
        try:
            path.lstat()
        except FileNotFoundError:
            prior = latest.get(relative, {})
            if prior.get("state") not in {"prepared", "deleted"} or any(
                prior.get(field) != item[field] for field in ("size", "sha256")
            ):
                raise ValueError(f"missing without prune proof: {relative}")
            continue
        fresh = local_digest(root, relative)
        if any(fresh[k] != item[k] for k in ("size", "sha256")):
            raise ValueError(f"local file changed before prune: {relative}")
        if latest.get(relative, {}).get("state") == "deleted":
            raise ValueError(f"file reappeared after prune: {relative}")
        # Hash was computed immediately above. Open without following symlinks and
        # ensure the named path still resolves to the same inode before unlink.
        checked_path(root, relative)
        if list(identity(path.lstat())) != fresh["identity"]:
            raise ValueError(f"file changed immediately before unlink: {relative}")
        journal_event(
            journal,
            {
                "path": relative,
                "state": "prepared",
                "size": fresh["size"],
                "sha256": fresh["sha256"],
                "identity": fresh["identity"],
                "lifecycle_proof": lifecycle_record,
            },
        )
        path.unlink()
        journal_event(
            journal,
            {
                "path": relative,
                "state": "deleted",
                "size": fresh["size"],
                "sha256": fresh["sha256"],
            },
        )
        deleted.append(relative)
        print(f"deleted {relative}", flush=True)
    return deleted


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("inventory", "upload", "verify", "prune"))
    parser.add_argument(
        "--lifecycle-proof",
        type=Path,
        help="reviewed Cloudflare dashboard lifecycle record JSON",
    )
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    if os.getenv("CFB_STORAGE_BACKEND") != "r2":
        raise ValueError("CFB_STORAGE_BACKEND must be r2")
    if args.mode == "inventory":
        print(json.dumps(inventory(ROOT), indent=2))
        return
    import boto3

    names = ("BUCKET", "ACCOUNT_ID", "ACCESS_KEY", "SECRET_KEY")
    config = {name: os.getenv(f"CFB_R2_PREVIEW_{name}") for name in names}
    if not all(config.values()):
        raise ValueError("Preview R2 configuration incomplete")
    bucket = config["BUCKET"]
    assert bucket is not None
    client = boto3.client(
        "s3",
        endpoint_url=f"https://{config['ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=config["ACCESS_KEY"],
        aws_secret_access_key=config["SECRET_KEY"],
        region_name="auto",
    )
    if args.mode == "upload":
        rows = inventory(ROOT)
        manifest = make_manifest(rows, bucket)
        for item in sorted(manifest["files"], key=lambda entry: entry["size"]):
            original = next(row for row in rows if row["path"] == item["path"])
            item_with_identity = {**item, "identity": original["identity"]}
            result = upload_item(client, bucket, ROOT, item_with_identity)
            print(f"{result} {item['path']}", flush=True)
        key = publish_manifest(client, bucket, manifest, MANIFEST)
        print(f"manifest {key}")
        return
    manifest = load_manifest(MANIFEST, bucket)
    if args.mode == "verify":
        verify_all(client, bucket, manifest)
    else:
        prune(ROOT, client, bucket, manifest, JOURNAL, args.lifecycle_proof)


if __name__ == "__main__":
    main()
