"""Atomic catalog registration: collection order, rollback, immutability, idempotence."""

from __future__ import annotations

import copy
import hashlib
import json

import pytest

from cks_picks_cfb.rebuild import catalog_publish as cp
from cks_picks_cfb.rebuild.errors import GateError


class FakeDB:
    def __init__(self):
        self.schemas, self.versions, self.deps, self.quality = {}, {}, set(), set()
        self.fail_on = None
        self.commits = self.rollbacks = 0

    def snapshot(self):
        return copy.deepcopy((self.schemas, self.versions, self.deps, self.quality))

    def restore(self, state):
        self.schemas, self.versions, self.deps, self.quality = state


class FakeCursor:
    def __init__(self, db):
        self.db, self.rowcount, self._row = db, 0, None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=()):
        db = self.db
        if db.fail_on and db.fail_on in sql:
            raise RuntimeError("db failure")
        self.rowcount, self._row = 0, None
        if sql.startswith("SELECT schema_json"):
            self._row = db.schemas.get(tuple(params))
        elif sql.startswith("INSERT INTO catalog.schema_versions"):
            dataset, version, schema_json, sha = params
            db.schemas[(dataset, version)] = (json.loads(schema_json), sha)
        elif sql.startswith("SELECT dataset, tier"):
            self._row = db.versions.get(params[0])
        elif sql.startswith("INSERT INTO catalog.dataset_versions"):
            version_id, *rest = params
            rest[7] = json.loads(rest[7])
            db.versions[version_id] = tuple(rest)
        elif sql.startswith("INSERT INTO catalog.dataset_dependencies"):
            if tuple(params[:2]) not in db.deps:
                db.deps.add(tuple(params[:2]))
                self.rowcount = 1
        elif sql.startswith("INSERT INTO catalog.quality_results"):
            if tuple(params[:2]) not in db.quality:
                db.quality.add(tuple(params[:2]))
                self.rowcount = 1

    def fetchone(self):
        return self._row


class FakeConn:
    def __init__(self, db):
        self.db = db

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
                self.state = conn.db.snapshot()

            def __exit__(self, kind, *rest):
                if kind:
                    conn.db.restore(self.state)
                    conn.db.rollbacks += 1
                else:
                    conn.db.commits += 1
                return False

        return Tx()


class Schema:
    sha256 = "s" * 64

    def json(self):
        return {"x": 1}


def _published():
    files, objects = {}, {}

    def put(key, value):
        raw = json.dumps(value).encode() if not isinstance(value, bytes) else value
        files[key] = raw
        objects[key] = hashlib.sha256(raw).hexdigest()

    def silver(dataset, version, season):
        base = f"lake/silver/dataset={dataset}/version={version}"
        put(
            f"{base}/manifest.json",
            {
                "dataset": dataset,
                "version_id": version,
                "tier": "silver",
                "schema_version": f"{dataset}_v1",
                "content_sha": "c" * 64,
                "uri": f"{base}/data.parquet",
                "row_count": 5,
                "partitions": {"seasons": [season]},
                "as_of": "2026-08-31T23:46:49+00:00",
                "parent_versions": ["p1"],
                "code_sha": "a" * 40,
                "config_sha": "b" * 64,
                "validation": {"nonempty": True},
                "schema_sha": None,
            },
        )

    silver("byplay", "s2025b", 2025)
    silver("byplay", "s2015b", 2015)
    silver("drives", "s2015d", 2015)
    child = "lake/gold/dataset=ledger/version=child1/manifest.json"
    put(
        child,
        {
            "dataset": "ledger",
            "version_id": "child1",
            "tier": "gold",
            "schema_version": "ledger_v1",
            "content_sha": "d" * 64,
            "uri": "lake/gold/dataset=ledger/version=child1/data.parquet",
            "row_count": 2,
            "partitions": {},
            "as_of": "2026-08-31T23:46:49+00:00",
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
            "as_of": "2026-08-31T23:46:49+00:00",
            "parents": [{"version_id": "s2015b"}],
            "source_captures": [],
            "code_sha": "a" * 40,
            "config_sha": "b" * 64,
            "parts": [
                {
                    "partition": {"season": 2015},
                    "row_count": 2,
                    "ref": {"version_id": "child1"},
                }
            ],
        },
    )
    return files, objects


def _entries():
    files, objects = _published()
    return cp.collect_entries(objects, files.__getitem__)


def test_collect_entries_orders_silver_by_season_then_roots_and_skips_children():
    entries = _entries()
    assert [(e.kind, e.version_id) for e in entries] == [
        ("plain", "s2015b"),
        ("plain", "s2015d"),
        ("plain", "s2025b"),
        ("partitioned", "root1"),
    ]
    assert entries[-1].parents == ("s2015b",)
    assert entries[-1].partitions["partition_keys"] == ["season"]


def _register(db, entries):
    return cp.register_entries(
        "url",
        entries,
        schema_lookup=lambda *_: Schema(),
        connect=lambda _url: FakeConn(db),
    )


def test_registration_is_one_transaction_and_idempotent():
    db = FakeDB()
    first = _register(db, _entries())
    assert db.commits == 1 and len(db.versions) == 4 and first["versions"] == 4
    second = _register(db, _entries())
    assert second == {"schemas": 0, "versions": 0, "dependencies": 0, "quality": 0}
    assert len(db.versions) == 4


def test_failure_rolls_everything_back():
    db = FakeDB()
    db.fail_on = "INSERT INTO catalog.dataset_dependencies"
    with pytest.raises(RuntimeError):
        _register(db, _entries())
    assert db.rollbacks == 1 and not db.versions and not db.schemas and not db.deps


def test_a_changed_existing_version_is_an_immutable_conflict_and_rolls_back():
    db = FakeDB()
    _register(db, _entries())
    changed = list(db.versions)[0]
    row = list(db.versions[changed])
    row[2] = "e" * 64  # content_sha differs
    db.versions[changed] = tuple(row)
    before = copy.deepcopy(db.versions)
    with pytest.raises(GateError, match="immutable dataset version conflict"):
        _register(db, _entries())
    assert db.versions == before


def test_before_write_hook_runs_first_and_can_block():
    db = FakeDB()

    def block(_cursor):
        raise GateError("wrong database identity")

    with pytest.raises(GateError, match="identity"):
        cp.register_entries(
            "url",
            _entries(),
            schema_lookup=lambda *_: Schema(),
            before_write=block,
            connect=lambda _url: FakeConn(db),
        )
    assert not db.versions and db.rollbacks == 1


def test_module_writes_only_catalog_tables():
    assert cp.write_scope_ok()
