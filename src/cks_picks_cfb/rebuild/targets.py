"""Fail-closed write targets: namespace allow-list, create-once, identity checks."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, Protocol

from cks_picks_cfb.rebuild.errors import ImmutableCollisionError, TargetError

#: Immutable namespaces 6A may write. ``rebuild/6a/<run_id>/`` is added per run.
STATIC_NAMESPACES = ("lake/silver/", "lake/gold/", "quality/receipts/")
RUN_NAMESPACE = "rebuild/6a/"

#: Prefixes that must never be written, even if a namespace were widened.
FORBIDDEN_PREFIXES = (
    "serving/",
    "predictions/",
    "selections/",
    "authorizations/",
    "market_snapshots/",
    "release/",
    "production/",
)

#: Catalog tables the 6A publish may write.
CATALOG_WRITE_SCHEMA = "catalog"
PREVIEW_PIPELINE_ROLE = "cks_preview_pipeline"


class ObjectStore(Protocol):
    """Minimal immutable object interface the harness depends on."""

    identity: str

    def exists(self, key: str) -> bool: ...
    def read(self, key: str) -> bytes: ...
    def put_if_absent(self, key: str, data: bytes) -> bool:
        """Store ``data`` only if the key is absent; return False if it exists."""
        ...


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class InMemoryStore:
    """Test and staging store with exact create-once semantics."""

    def __init__(self, identity: str = "memory:test"):
        self.identity = identity
        self.objects: dict[str, bytes] = {}

    def exists(self, key: str) -> bool:
        return key in self.objects

    def read(self, key: str) -> bytes:
        return self.objects[key]

    def put_if_absent(self, key: str, data: bytes) -> bool:
        if key in self.objects:
            return False
        self.objects[key] = data
        return True


class R2ObjectStore:
    """R2 create-once store using ``If-None-Match: *`` conditional puts."""

    def __init__(
        self,
        *,
        bucket: str,
        account_id: str,
        access_key: str,
        secret_key: str,
        endpoint: str | None = None,
    ):
        import boto3

        self.bucket = bucket
        self.identity = f"r2:{account_id}:{bucket}"
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint or f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="auto",
        )

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") in {"404", "NoSuchKey"}:
                return False
            raise

    def read(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def put_if_absent(self, key: str, data: bytes) -> bool:
        from botocore.exceptions import ClientError

        try:
            self.client.put_object(
                Bucket=self.bucket, Key=key, Body=data, IfNoneMatch="*"
            )
            return True
        except ClientError as error:
            code = str(error.response.get("Error", {}).get("Code"))
            status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if code in {"PreconditionFailed", "412", "ConditionalRequestConflict"} or (
                status in {409, 412}
            ):
                return False
            raise


@dataclass
class WriteLedger:
    """Evidence of what a guarded store wrote, for the idempotence proof."""

    created: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)

    @property
    def writes(self) -> int:
        return len(self.created)


class GuardedStore:
    """Wrap an ObjectStore with the 6A namespace allow-list and create-once checks."""

    def __init__(
        self,
        store: ObjectStore,
        *,
        run_id: str,
        expected_identity: str,
        extra_namespaces: Iterable[str] = (),
    ):
        if store.identity != expected_identity:
            raise TargetError(
                f"unexpected storage identity {store.identity!r}; "
                f"plan requires {expected_identity!r}"
            )
        if not run_id or "/" in run_id:
            raise TargetError("run_id must be a single path segment")
        self.store = store
        self.identity = store.identity
        self.namespaces = (
            *STATIC_NAMESPACES,
            f"{RUN_NAMESPACE}{run_id}/",
            *extra_namespaces,
        )
        self.ledger = WriteLedger()

    def check_key(self, key: str) -> None:
        if key.startswith("/") or ".." in key.split("/"):
            raise TargetError(f"invalid object key: {key}")
        if key.startswith(FORBIDDEN_PREFIXES):
            raise TargetError(f"forbidden serving/production prefix: {key}")
        if not key.startswith(self.namespaces):
            raise TargetError(f"key outside permitted 6A namespaces: {key}")

    def exists(self, key: str) -> bool:
        return self.store.exists(key)

    def read(self, key: str) -> bytes:
        return self.store.read(key)

    def create_once(self, key: str, data: bytes) -> str:
        """Create ``key``; identical existing bytes are a no-op, different bytes fail."""
        self.check_key(key)
        digest = sha256_bytes(data)
        if self.store.put_if_absent(key, data):
            self.ledger.created.append(key)
            return digest
        existing = self.store.read(key)
        if sha256_bytes(existing) != digest:
            raise ImmutableCollisionError(f"immutable object collision: {key}")
        self.ledger.unchanged.append(key)
        return digest


def assert_preview_database(cur: Any, *, expected_database: str | None = None) -> None:
    """Require the restricted Preview pipeline login (and optional database name)."""
    cur.execute("SELECT session_user, current_user, current_database()")
    row = cur.fetchone()
    if not row or len(row) < 3:
        raise TargetError("database identity is unreadable")
    session_role, effective_role, database = (str(value) for value in row[:3])
    if session_role != PREVIEW_PIPELINE_ROLE or effective_role != PREVIEW_PIPELINE_ROLE:
        raise TargetError(
            f"6A catalog writes require {PREVIEW_PIPELINE_ROLE}; got "
            f"session_user={session_role!r}, current_user={effective_role!r}"
        )
    if expected_database is not None and database != expected_database:
        raise TargetError(f"unexpected database {database!r}")


def assert_catalog_only(statements: Iterable[str]) -> None:
    """Reject any SQL that does not target the catalog schema (used by publish)."""
    for statement in statements:
        lowered = " ".join(statement.lower().split())
        if lowered.startswith(("insert into", "update", "delete from")):
            if f" {CATALOG_WRITE_SCHEMA}." not in f" {lowered}":
                raise TargetError("6A may write only catalog tables")


Verifier = Callable[..., Any]
