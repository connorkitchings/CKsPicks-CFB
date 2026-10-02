"""Silver promotion between catalogs by registration (no object copies)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg
import pytest

from cks_picks_cfb.data.catalog import register_dataset_version, register_source_capture
from cks_picks_cfb.data.lake import BuildRequest, SourceCapture, build_dataset_version
from cks_picks_cfb.data.promotion import (
    PromotionError,
    assert_same_bucket,
    promote,
    resolve_version,
)
from cks_picks_cfb.data.storage.base import StorageSettings
from cks_picks_cfb.data.storage.local import LocalStorage
from cks_picks_cfb.db.migrations import apply_migrations

SOURCE = os.getenv("TEST_DATABASE_URL")
TARGET = os.getenv("TEST_DATABASE_URL_TARGET")
needs_db = pytest.mark.skipif(
    not (SOURCE and TARGET),
    reason="requires two disposable PostgreSQL databases (TEST_DATABASE_URL[_TARGET])",
)
NOW = datetime(2026, 9, 27, 15, tzinfo=timezone.utc)


def _reset(url: str) -> None:
    with psycopg.connect(url, autocommit=True) as conn, conn.cursor() as cur:
        for schema in ("ops", "catalog", "public"):
            cur.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        cur.execute("CREATE SCHEMA public")
    apply_migrations(url, Path("contracts/migrations"))


def _settings(bucket="b", account="a", endpoint="e"):
    return StorageSettings(
        backend="r2", bucket=bucket, account_id=account, endpoint=endpoint
    )


def test_different_bucket_is_refused():
    assert_same_bucket(_settings(), _settings())
    with pytest.raises(PromotionError, match="bucket"):
        assert_same_bucket(_settings(), _settings(bucket="other"))
    with pytest.raises(PromotionError, match="bucket"):
        assert_same_bucket(_settings(bucket=None), _settings(bucket=None))


def _seed_source(tmp_path):
    storage = LocalStorage(str(tmp_path))
    capture = SourceCapture(
        capture_id="cap-1",
        provider="cfbd",
        entity="plays",
        captured_at=NOW,
        effective_at=None,
        request={"year": 2026},
        content_sha="c" * 64,
        object_sha="d" * 64,
        uri="lake/bronze/x.parquet",
        row_count=1,
    )
    register_source_capture(SOURCE, capture)
    parent, parent_manifest = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset="teams",
            parent_refs=(),
            code_sha="x",
            config_sha="y",
            as_of=NOW,
            identity_version="v1",
        ),
        records=[{"team": "A"}],
        partitions={"seasons": [2026]},
    )
    child, child_manifest = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset="byplay",
            parent_refs=(parent,),
            code_sha="x",
            config_sha="y",
            as_of=NOW,
            source_capture_ids=("cap-1",),
            identity_version="v1",
        ),
        records=[{"game_id": 1}],
        partitions={"seasons": [2026]},
    )
    register_dataset_version(SOURCE, parent, parent_manifest)
    register_dataset_version(SOURCE, child, child_manifest)
    return storage, parent, child


@needs_db
def test_promotion_registers_lineage_and_is_idempotent(tmp_path):
    _reset(SOURCE)
    _reset(TARGET)
    storage, parent, child = _seed_source(tmp_path)
    assert resolve_version(SOURCE, "byplay", 2026) == child.version_id
    assert resolve_version(SOURCE, "byplay", 2026, child.version_id[:8]) == (
        child.version_id
    )

    dry = promote(
        source_url=SOURCE,
        target_url=TARGET,
        storage=storage,
        root_versions=[child.version_id],
        dry_run=True,
    )
    assert [v["dataset"] for v in dry.versions] == ["teams", "byplay"]
    assert len(dry.new_versions) == 2 and dry.captures_to_register == ["cap-1"]
    with psycopg.connect(TARGET) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM catalog.dataset_versions")
        assert cur.fetchone() == (0,)

    real = promote(
        source_url=SOURCE,
        target_url=TARGET,
        storage=storage,
        root_versions=[child.version_id],
        dry_run=False,
    )
    assert len(real.new_versions) == 2
    with psycopg.connect(TARGET) as conn, conn.cursor() as cur:
        cur.execute("SELECT dataset FROM catalog.dataset_versions ORDER BY dataset")
        assert cur.fetchall() == [("byplay",), ("teams",)]
        cur.execute("SELECT parent_version_id FROM catalog.dataset_dependencies")
        assert cur.fetchall() == [(parent.version_id,)]
        cur.execute("SELECT capture_id FROM catalog.dataset_capture_dependencies")
        assert cur.fetchall() == [("cap-1",)]

    again = promote(
        source_url=SOURCE,
        target_url=TARGET,
        storage=storage,
        root_versions=[child.version_id],
        dry_run=False,
    )
    assert again.new_versions == [] and again.captures_present == ["cap-1"]


@needs_db
def test_corrupt_object_is_not_promoted(tmp_path):
    _reset(SOURCE)
    _reset(TARGET)
    storage, _, child = _seed_source(tmp_path)
    (tmp_path / child.uri).write_bytes(b"tampered")
    with pytest.raises(PromotionError, match="hash mismatch"):
        promote(
            source_url=SOURCE,
            target_url=TARGET,
            storage=storage,
            root_versions=[child.version_id],
            dry_run=False,
        )
    with psycopg.connect(TARGET) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM catalog.dataset_versions WHERE dataset='byplay'"
        )
        assert cur.fetchone() == (0,)
