"""Catalog-only recovery of a published 6A root: verify, register once, read back, retry."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.rebuild.errors import GateError, RebuildError
from cks_picks_cfb.rebuild.plan import RebuildPlan
from scripts.pipeline import recover_6a_catalog as rc

PLAN = RebuildPlan.from_dict(
    yaml.safe_load(Path("conf/rebuild/6a_w6_v1.yaml").read_text())
)
ROOT_URI = f"{PLAN.run_prefix()}root-manifest.json"
BUILD_SHA = "a" * 40


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _published() -> dict[str, bytes]:
    """Two Silver versions and one Gold partitioned root (with its skipped child)."""
    files: dict[str, bytes] = {}

    def put(key, value):
        files[key] = value if isinstance(value, bytes) else json.dumps(value).encode()

    for dataset, version, season in (
        ("byplay", "s2025", 2025),
        ("drives", "s2015", 2015),
    ):
        base = f"lake/silver/dataset={dataset}/version={version}"
        data = f"data-{version}".encode()
        put(f"{base}/data.parquet", data)
        put(
            f"{base}/manifest.json",
            {
                "dataset": dataset,
                "version_id": version,
                "tier": "silver",
                "schema_version": f"{dataset}_v1",
                "content_sha": _sha(data),
                "uri": f"{base}/data.parquet",
                "row_count": 5,
                "partitions": {"seasons": [season]},
                "as_of": "2026-10-12T00:00:00+00:00",
                "parent_versions": ["external-parent"],
                "source_capture_ids": ["capture-1"],
                "validation": {"nonempty": True},
            },
        )
    put(
        "lake/gold/dataset=ledger/version=root1/partitioned-manifest.json",
        {
            "dataset": "ledger",
            "version_id": "root1",
            "tier": "gold",
            "schema_version": "ledger_v1",
            "artifact_kind": "partitioned_dataset_v1",
            "partition_keys": ["season"],
            "row_count": 2,
            "as_of": "2026-10-12T00:00:00+00:00",
            "parents": [{"version_id": "s2015"}],
            "source_captures": [],
            "parts": [],
        },
    )
    root = signed_payload(
        {
            "kind": "rebuild_root_v1",
            "run_id": PLAN.run_id,
            "code_sha": BUILD_SHA,
            "publisher_code_sha": None,
            "objects": {key: _sha(raw) for key, raw in files.items()},
        }
    )
    files[ROOT_URI] = json.dumps(root).encode()
    return files


class FakeDB:
    def __init__(self):
        self.role = "cks_preview_pipeline"
        self.schemas, self.versions = {}, {}
        self.edges: dict[str, set] = {
            "deps": set(),
            "captures": set(),
            "quality": set(),
        }
        self.external = {"external-parent"}
        self.fail_on = None
        self.commits = 0

    def state(self):
        return copy.deepcopy((self.schemas, self.versions, self.edges))


class FakeCursor:
    TABLES = {
        "dataset_dependencies": "deps",
        "dataset_capture_dependencies": "captures",
        "quality_results": "quality",
    }

    def __init__(self, db):
        self.db, self.rowcount, self._rows = db, 0, []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=()):
        db = self.db
        if db.fail_on and db.fail_on in sql:
            raise RuntimeError("db failure")
        self.rowcount, self._rows = 0, []
        if sql.startswith("SELECT session_user"):
            self._rows = [(db.role, db.role, "neondb")]
        elif sql.startswith("SELECT schema_json"):
            row = db.schemas.get(tuple(params))
            self._rows = [row] if row else []
        elif sql.startswith("INSERT INTO catalog.schema_versions"):
            db.schemas[tuple(params[:2])] = (json.loads(params[2]), params[3])
        elif sql.startswith("SELECT dataset, tier"):
            row = db.versions.get(params[0])
            self._rows = [row] if row else []
        elif sql.startswith("INSERT INTO catalog.dataset_versions"):
            version_id, *rest = params
            rest[7] = json.loads(rest[7])
            db.versions[version_id] = tuple(rest)
        elif sql.startswith("INSERT INTO catalog."):
            name = self.TABLES[sql.split()[2].split(".")[1]]
            if tuple(params[:2]) not in db.edges[name]:
                db.edges[name].add(tuple(params[:2]))
                self.rowcount = 1
        elif sql.startswith("SELECT version_id, dataset"):
            self._rows = [(v, *db.versions[v]) for v in params[0] if v in db.versions]
        elif sql.startswith("SELECT version_id FROM"):
            known = set(db.versions) | db.external
            self._rows = [(v,) for v in params[0] if v in known]
        elif sql.startswith("SELECT count(*)"):
            name = self.TABLES[sql.split("catalog.")[1].split()[0]]
            self._rows = [(sum(1 for e in db.edges[name] if e[0] in params[0]),)]
        else:
            raise AssertionError(sql)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


class FakeConn:
    def __init__(self, db):
        self.db, self.read_only = db, False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self):
        return FakeCursor(self.db)

    def transaction(self):
        conn = self

        class Tx:
            def __enter__(self):
                self.saved = conn.db.state()

            def __exit__(self, kind, *rest):
                if kind:
                    conn.db.schemas, conn.db.versions, conn.db.edges = self.saved
                else:
                    conn.db.commits += 1
                return False

        return Tx()


class Schema:
    sha256 = "s" * 64

    def json(self):
        return {"x": 1}


def _recover(db, files=None, apply=False, **overrides):
    files = _published() if files is None else files
    kwargs = {
        "read": files.__getitem__,
        "storage_identity": PLAN.storage_identity,
        "plan": PLAN,
        "root_uri": ROOT_URI,
        "root_sha256": _sha(files[ROOT_URI]),
        "code_sha": BUILD_SHA,
        "expected_versions": 3,
        "connect": lambda _url: FakeConn(db),
        "conn_url": "url",
        "schema_lookup": lambda *_: Schema(),
        "apply": apply,
        **overrides,
    }
    return rc.recover(**kwargs)


def test_the_dry_run_verifies_everything_and_writes_nothing():
    db = FakeDB()
    report = _recover(db)
    assert report["mode"] == "dry-run" and report["catalog_write_scope_ok"]
    assert report["catalog_before"]["to_register"] == 3
    assert report["root"]["publisher_code_sha"] is None
    assert not db.versions and db.commits == 0


def test_apply_registers_once_reads_back_and_an_identical_retry_writes_nothing():
    db, files = FakeDB(), _published()
    before = dict(files)
    report = _recover(db, files, apply=True)
    assert report["written"]["versions"] == 3
    assert report["readback"]["complete"]
    assert report["readback"]["counts"] == {
        "dependencies": 3,
        "captures": 2,
        "quality": 2,
    }
    assert not any(report["retry_written"].values())
    assert report["root_bytes_unchanged"] and files == before
    rerun = _recover(db, files, apply=True)
    assert not any(rerun["written"].values())
    assert rerun["catalog_before"]["already_registered"] == 3


def _tamper(files):
    key = "lake/silver/dataset=byplay/version=s2025/manifest.json"
    files[key] = files[key].replace(b'"row_count": 5', b'"row_count": 6')
    return files


@pytest.mark.parametrize(
    ("overrides", "word"),
    [
        ({"root_sha256": "0" * 64}, "not the root pinned"),
        ({"storage_identity": "r2:other:cks-picks-cfb-preview"}, "storage"),
        (
            {"root_uri": "rebuild/6a/other-run/root-manifest.json"},
            "not the root of plan",
        ),
        ({"code_sha": "b" * 40}, "build commit"),
        ({"expected_versions": 49}, "not 49"),
    ],
)
def test_a_wrong_hash_bucket_root_commit_or_version_count_is_refused(overrides, word):
    db = FakeDB()
    with pytest.raises(GateError, match=word):
        _recover(db, apply=True, **overrides)
    assert not db.versions


def test_an_object_that_differs_from_the_root_is_refused():
    db = FakeDB()
    files = _tamper(_published())
    with pytest.raises(GateError, match="published object changed"):
        _recover(db, files, apply=True)
    assert not db.versions


def test_the_wrong_database_role_is_refused_before_any_write():
    db = FakeDB()
    db.role = "neondb_owner"
    with pytest.raises(RebuildError, match="cks_preview_pipeline"):
        _recover(db, apply=True)
    assert not db.versions


def test_a_conflicting_existing_version_is_refused():
    db = FakeDB()
    _recover(db, apply=True)
    row = list(db.versions["s2025"])
    row[3] = "e" * 64  # content_sha
    db.versions["s2025"] = tuple(row)
    snapshot = db.state()
    with pytest.raises(GateError, match="conflict"):
        _recover(db, apply=True)
    assert db.state() == snapshot


@pytest.mark.parametrize(
    ("column", "value"),
    [(7, {"seasons": [1999]}), (9, "c" * 40), (11, "draft"), (13, "f" * 64)],
)
def test_the_dry_run_refuses_any_column_the_apply_would_refuse(column, value):
    db = FakeDB()
    _recover(db, apply=True)
    row = list(db.versions["s2025"])
    row[column] = value  # partitions, code_sha, state, schema_sha
    db.versions["s2025"] = tuple(row)
    with pytest.raises(GateError, match="conflict"):
        _recover(db)
    with pytest.raises(GateError, match="conflict"):
        _recover(db, apply=True)


def test_missing_parents_are_refused():
    db = FakeDB()
    db.external = set()
    with pytest.raises(GateError, match="parents missing"):
        _recover(db, apply=True)
    assert not db.versions


def test_a_failure_inside_the_transaction_rolls_everything_back():
    db = FakeDB()
    db.fail_on = "INSERT INTO catalog.quality_results"
    with pytest.raises(RuntimeError):
        _recover(db, apply=True)
    assert not db.versions and not db.schemas and not any(db.edges.values())
