"""Bucket-isolated, immutable research artifacts and verified source reads."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from botocore.exceptions import ClientError

ROOT = "ratings-lab/v1/"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


class LabStore(Protocol):
    identity: str

    def read(self, key: str) -> bytes: ...

    def create_once(self, key: str, data: bytes) -> str: ...


class ReadOnlySource:
    """Expose only reads to V5 artifact adapters, regardless of store type."""

    def __init__(self, store: LabStore):
        self._store = store
        self.identity = store.identity

    def read(self, key: str) -> bytes:
        return self._store.read(key)

    def read_bytes(self, key: str) -> bytes:
        return self.read(key)


@dataclass(frozen=True)
class ResearchArtifact:
    storage_identity: str
    key: str
    sha256: str
    size: int

    def as_dict(self) -> dict[str, Any]:
        return vars(self).copy()


class LocalLabStore:
    """Fixture-only create-once store; never defaults to repository ./data/."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.identity = f"local:{self.root}"

    def _path(self, key: str) -> Path:
        relative = Path(key)
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError("invalid laboratory object key")
        return self.root / relative

    def read(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def create_once(self, key: str, data: bytes) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("xb") as handle:
                handle.write(data)
        except FileExistsError:
            if path.read_bytes() != data:
                raise ValueError(f"immutable object conflict: {key}") from None
        return sha256(data)


class R2LabStore:
    def __init__(
        self,
        *,
        bucket: str,
        account: str,
        access: str,
        secret: str,
        endpoint: str | None = None,
    ):
        import boto3

        self.bucket = bucket
        self.identity = f"r2:{account}:{bucket}"
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint or f"https://{account}.r2.cloudflarestorage.com",
            aws_access_key_id=access,
            aws_secret_access_key=secret,
            region_name="auto",
        )

    def read(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def create_once(self, key: str, data: bytes) -> str:
        try:
            self.client.put_object(
                Bucket=self.bucket, Key=key, Body=data, IfNoneMatch="*"
            )
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code not in {
                "PreconditionFailed",
                "412",
                "ConditionalRequestConflict",
                "409",
            }:
                raise
            if self.read(key) != data:
                raise ValueError(f"immutable object conflict: {key}") from exc
        return sha256(data)


@dataclass(frozen=True)
class ResearchStorage:
    source: ReadOnlySource
    output: LabStore

    def __post_init__(self) -> None:
        if self.source.identity == self.output.identity:
            raise ValueError("research source and output storage must differ")

    def read_source(self, *, key: str, expected_sha256: str) -> bytes:
        data = self.source.read(key)
        if sha256(data) != expected_sha256:
            raise ValueError(f"source checksum mismatch: {key}")
        return data

    def write(self, *, key: str, data: bytes) -> ResearchArtifact:
        if not key.startswith(ROOT):
            raise ValueError("research writes must remain in ratings-lab/v1/")
        digest = self.output.create_once(key, data)
        return ResearchArtifact(self.output.identity, key, digest, len(data))

    def read_output(self, ref: ResearchArtifact) -> bytes:
        if ref.storage_identity != self.output.identity or not ref.key.startswith(ROOT):
            raise ValueError("research artifact escaped configured output storage")
        data = self.output.read(ref.key)
        if sha256(data) != ref.sha256 or len(data) != ref.size:
            raise ValueError("research artifact checksum mismatch")
        return data

    def stage_at(self, key: str) -> tuple[ResearchArtifact, dict[str, Any]]:
        if not key.startswith(ROOT) or not key.endswith(".json"):
            raise ValueError("invalid laboratory stage key")
        data = self.output.read(key)
        ref = ResearchArtifact(self.output.identity, key, sha256(data), len(data))
        payload = json.loads(self.read_output(ref))
        if payload.get("schema_version") != "ratings_lab_stage_v1":
            raise ValueError("unknown research stage schema")
        for child in payload.get("children", []):
            self.read_output(ResearchArtifact(**child))
        return ref, payload

    def publish_stage(
        self,
        *,
        stage: str,
        identity: str,
        children: list[ResearchArtifact],
        metadata: dict[str, Any],
    ) -> ResearchArtifact:
        if not stage.replace("-", "").isalpha() or not identity or "/" in identity:
            raise ValueError("invalid research stage identity")
        for child in children:
            self.read_output(child)
        payload = canonical_json(
            {
                "schema_version": "ratings_lab_stage_v1",
                "stage": stage,
                "identity": identity,
                "children": [item.as_dict() for item in children],
                "metadata": metadata,
            }
        )
        return self.write(key=f"{ROOT}runs/{identity}/{stage}.json", data=payload)


def _required(prefix: str) -> dict[str, str]:
    names = ("BUCKET", "ACCOUNT_ID", "ACCESS_KEY", "SECRET_KEY")
    values = {name: os.getenv(f"{prefix}_{name}", "") for name in names}
    if missing := [f"{prefix}_{name}" for name, value in values.items() if not value]:
        raise ValueError(
            "missing research storage configuration: " + ", ".join(missing)
        )
    return values


def open_research_storage() -> ResearchStorage:
    """Use explicit research credentials only, with no Preview/production fallback."""
    source, output = _required("CFB_R2_LAB_SOURCE"), _required("CFB_R2_LAB")
    if (source["ACCOUNT_ID"], source["BUCKET"]) == (
        output["ACCOUNT_ID"],
        output["BUCKET"],
    ):
        raise ValueError("research output bucket equals source bucket")
    return ResearchStorage(
        source=ReadOnlySource(
            R2LabStore(
                bucket=source["BUCKET"],
                account=source["ACCOUNT_ID"],
                access=source["ACCESS_KEY"],
                secret=source["SECRET_KEY"],
                endpoint=os.getenv("CFB_R2_LAB_SOURCE_ENDPOINT"),
            )
        ),
        output=R2LabStore(
            bucket=output["BUCKET"],
            account=output["ACCOUNT_ID"],
            access=output["ACCESS_KEY"],
            secret=output["SECRET_KEY"],
            endpoint=os.getenv("CFB_R2_LAB_ENDPOINT"),
        ),
    )
