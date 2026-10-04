"""Rebuild harness: pins, targets, create-once, verify-gated publication."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from cks_picks_cfb.rebuild.errors import (
    GateError,
    ImmutableCollisionError,
    InputPinError,
    PlanError,
    TargetError,
)
from cks_picks_cfb.rebuild.inputs import (
    LEGACY_PARENT_TOKENS,
    no_implicit_latest,
    resolve_input,
)
from cks_picks_cfb.rebuild.orchestrator import Orchestrator, Stage, StageOutput
from cks_picks_cfb.rebuild.plan import (
    HISTORICAL_SEASONS,
    InputPin,
    RebuildPlan,
    StagePlan,
)
from cks_picks_cfb.rebuild.targets import (
    GuardedStore,
    InMemoryStore,
    assert_preview_database,
)

CODE_SHA = "a" * 40
IDENTITY = "memory:preview"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _plan(tmp_path: Path, **overrides) -> tuple[RebuildPlan, Path]:
    data = b"decision-bytes"
    (tmp_path / "decisions.csv").write_bytes(data)
    pin = InputPin("decisions", "decisions.csv", _sha(data), "git_file")
    values = dict(
        run_id="run1",
        storage_identity=IDENTITY,
        seasons=HISTORICAL_SEASONS,
        inputs=(pin,),
        stages=(
            StagePlan("a", inputs=("decisions",), outputs=("lake/gold/a/",)),
            StagePlan("b", parents=("a",), outputs=("lake/gold/b/",)),
        ),
        registry_checksum="b" * 64,
    )
    values.update(overrides)
    return RebuildPlan(**values), tmp_path


def _stages(plan: RebuildPlan, *, bad_verify: bool = False) -> list[Stage]:
    def build(name):
        return lambda ctx: StageOutput(
            artifacts=[(f"lake/gold/{name}/part.bin", name.encode())]
        )

    def verify(ctx):
        return ["boom"] if bad_verify and ctx.stage.name == "b" else []

    return [Stage(s, build(s.name), verify) for s in plan.stages]


def _harness(tmp_path, **kwargs):
    plan, root = _plan(tmp_path)
    staging = InMemoryStore("stage")
    orch = Orchestrator(
        plan, _stages(plan, **kwargs), staging=staging, code_sha=CODE_SHA
    )
    guard = GuardedStore(
        InMemoryStore(IDENTITY), run_id="run1", expected_identity=IDENTITY
    )
    orch.preflight(
        repo_root=root,
        config_sha="c" * 64,
        worktree_clean=True,
        guard=guard,
        is_tracked=lambda *_: True,
    )
    return orch, guard


def test_plan_rejects_2020_and_wrong_seasons(tmp_path):
    plan, _ = _plan(tmp_path, seasons=HISTORICAL_SEASONS + (2020,))
    with pytest.raises(PlanError, match="2020"):
        plan.validate()
    plan, _ = _plan(tmp_path, seasons=(2015, 2016))
    with pytest.raises(PlanError, match="exactly"):
        plan.validate()


@pytest.mark.parametrize(
    "uri",
    [
        "artifacts/rebuild/x.csv",
        "data/x.csv",
        "/tmp/x.csv",
        "x/latest/y.csv",
        "a/cache/b",
    ],
)
def test_pin_rejects_scratch_and_implicit_latest(uri):
    with pytest.raises(PlanError):
        InputPin("n", uri, "d" * 64, "git_file").validate()


def test_pin_requires_hash():
    with pytest.raises(PlanError):
        InputPin("n", "docs/x.csv", "xyz", "git_file").validate()


def test_untracked_or_changed_input_rejected(tmp_path):
    plan, root = _plan(tmp_path)
    pin = plan.inputs[0]
    with pytest.raises(InputPinError, match="not git-tracked"):
        resolve_input(pin, repo_root=root, is_tracked=lambda *_: False)
    (root / "decisions.csv").write_bytes(b"changed")
    with pytest.raises(InputPinError, match="hash mismatch"):
        resolve_input(pin, repo_root=root, is_tracked=lambda *_: True)


def test_legacy_parent_denied_outside_baseline_stage(tmp_path):
    token = LEGACY_PARENT_TOKENS[1]
    pin = InputPin("measurements", f"lake/x/{token}.json", "e" * 64, "r2_object")
    plan, root = _plan(
        tmp_path,
        inputs=_plan(tmp_path)[0].inputs + (pin,),
        stages=(StagePlan("a", inputs=("decisions", "measurements")),),
    )
    from cks_picks_cfb.rebuild.inputs import reject_legacy_parents

    with pytest.raises(InputPinError, match="legacy parent"):
        reject_legacy_parents(plan)
    allowed = RebuildPlan(
        **{
            **plan.__dict__,
            "stages": (
                StagePlan(
                    "a", inputs=("decisions", "measurements"), legacy_allowed=True
                ),
            ),
        }
    )
    reject_legacy_parents(allowed)


def test_implicit_latest_selection_is_blocked():
    from cks_picks_cfb.data import catalog

    with no_implicit_latest():
        with pytest.raises(InputPinError):
            catalog.dataset_ref_as_of("url", "x", None)
    assert catalog.dataset_ref_as_of.__name__ != "refuse"


def test_guarded_store_namespaces_and_identity():
    with pytest.raises(TargetError, match="identity"):
        GuardedStore(InMemoryStore("r2:other"), run_id="r", expected_identity=IDENTITY)
    guard = GuardedStore(
        InMemoryStore(IDENTITY), run_id="r", expected_identity=IDENTITY
    )
    guard.create_once("lake/gold/x/y", b"1")
    for key in (
        "serving/x",
        "predictions/x",
        "lake/bronze/x",
        "../lake/gold/x",
        "other/x",
    ):
        with pytest.raises(TargetError):
            guard.create_once(key, b"1")


def test_create_once_idempotent_and_conflict():
    guard = GuardedStore(
        InMemoryStore(IDENTITY), run_id="r", expected_identity=IDENTITY
    )
    guard.create_once("lake/gold/x", b"1")
    guard.create_once("lake/gold/x", b"1")
    assert guard.ledger.writes == 1 and guard.ledger.unchanged == ["lake/gold/x"]
    with pytest.raises(ImmutableCollisionError):
        guard.create_once("lake/gold/x", b"2")


def test_database_identity_fail_closed():
    class Cur:
        def __init__(self, row):
            self.row = row

        def execute(self, _sql):
            pass

        def fetchone(self):
            return self.row

    assert_preview_database(Cur(("cks_preview_pipeline",) * 2 + ("db",)))
    with pytest.raises(TargetError):
        assert_preview_database(Cur(("cks_prod_pipeline", "cks_prod_pipeline", "db")))
    with pytest.raises(TargetError):
        assert_preview_database(Cur(("cks_preview_pipeline", "owner", "db")))


def test_preflight_requires_clean_worktree(tmp_path):
    plan, root = _plan(tmp_path)
    orch = Orchestrator(plan, _stages(plan), staging=InMemoryStore(), code_sha=CODE_SHA)
    guard = GuardedStore(
        InMemoryStore(IDENTITY), run_id="run1", expected_identity=IDENTITY
    )
    with pytest.raises(PlanError, match="clean"):
        orch.preflight(
            repo_root=root,
            config_sha="c" * 64,
            worktree_clean=False,
            guard=guard,
            is_tracked=lambda *_: True,
        )


def test_full_cycle_publish_and_idempotent_retry(tmp_path):
    orch, guard = _harness(tmp_path)
    orch.build()
    assert orch.verify()["passed"]
    registered = []
    first = orch.publish(guard, registrar=registered.append)
    assert first.writes == first.objects + 1 and registered
    second = orch.publish(guard)
    assert second.writes == 0 and second.root_sha == first.root_sha


def test_build_is_resumable_and_conflicts_fail(tmp_path):
    orch, _ = _harness(tmp_path)
    first = orch.build()
    assert orch.build() == first
    key = "stages/a/manifest.json"
    manifest = json.loads(orch.staging.read(key))
    manifest["parents"] = {"x": "y"}
    orch.staging.objects[key] = json.dumps(manifest).encode()
    with pytest.raises(Exception):
        orch.build()


def test_failed_verify_blocks_publish_and_root(tmp_path):
    orch, guard = _harness(tmp_path, bad_verify=True)
    orch.build()
    assert not orch.verify()["passed"]
    with pytest.raises(GateError, match="did not pass"):
        orch.publish(guard)
    assert not guard.store.objects


def test_publish_requires_verify_record(tmp_path):
    orch, guard = _harness(tmp_path)
    orch.build()
    with pytest.raises(GateError, match="verify record"):
        orch.publish(guard)


def test_tampered_staged_bytes_fail_verify_and_publish(tmp_path):
    orch, guard = _harness(tmp_path)
    orch.build()
    orch.staging.objects["stages/a/artifacts/lake/gold/a/part.bin"] = b"tampered"
    assert not orch.verify()["passed"]
    with pytest.raises(GateError):
        orch.publish(guard)
    assert not guard.store.objects


def test_undeclared_output_and_missing_parent_rejected(tmp_path):
    plan, root = _plan(tmp_path)
    stages = [
        Stage(
            plan.stages[0],
            lambda ctx: StageOutput([("lake/gold/zzz/x", b"1")]),
            lambda ctx: [],
        ),
        Stage(plan.stages[1], lambda ctx: StageOutput([]), lambda ctx: []),
    ]
    orch = Orchestrator(plan, stages, staging=InMemoryStore(), code_sha=CODE_SHA)
    guard = GuardedStore(
        InMemoryStore(IDENTITY), run_id="run1", expected_identity=IDENTITY
    )
    orch.preflight(
        repo_root=root,
        config_sha="c" * 64,
        worktree_clean=True,
        guard=guard,
        is_tracked=lambda *_: True,
    )
    with pytest.raises(GateError, match="undeclared"):
        orch.build()
    with pytest.raises(GateError, match="not built"):
        orch.build(only=["b"])


def test_stage_plan_mismatch_rejected(tmp_path):
    plan, _ = _plan(tmp_path)
    with pytest.raises(GateError):
        Orchestrator(
            plan, _stages(plan)[:1], staging=InMemoryStore(), code_sha=CODE_SHA
        )


class _FakeCursor:
    def __init__(self, log, fail_on=None):
        self.log, self.fail_on = log, fail_on

    def execute(self, sql, params=None):
        if self.fail_on and self.fail_on in sql:
            raise RuntimeError("db failure")
        self.log.append(sql.split("(")[0].strip())

    def fetchone(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeConn:
    def __init__(self, log, fail_on=None):
        self.log, self.fail_on, self.state = log, fail_on, "open"

    def cursor(self):
        return _FakeCursor(self.log, self.fail_on)

    def transaction(self):
        conn = self

        class Tx:
            def __enter__(self):
                return None

            def __exit__(self, kind, *rest):
                conn.state = "rolled_back" if kind else "committed"
                return False

        return Tx()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _root_manifest():
    return {
        "dataset": "football_scoring_ledger_v1",
        "schema_version": "v1",
        "version_id": "v" * 24,
        "uri": "lake/gold/dataset=football_scoring_ledger_v1/version=x/partitioned-manifest.json",
        "artifact_kind": "partitioned_dataset",
        "partition_keys": ["season"],
        "row_count": 3,
        "tier": "gold",
        "as_of": "2026-10-04T00:00:00+00:00",
        "parents": [],
        "source_captures": [],
    }


@pytest.mark.parametrize("fail_on", [None, "catalog.dataset_versions"])
def test_catalog_registration_is_one_transaction(monkeypatch, fail_on):
    from cks_picks_cfb.data import catalog

    log, conns = [], []

    def connect(_url):
        conns.append(_FakeConn(log, fail_on))
        return conns[-1]

    class _Schema:
        sha256 = "s" * 64

        def json(self):
            return {"x": 1}

    monkeypatch.setattr(catalog.psycopg, "connect", connect)
    monkeypatch.setattr(catalog, "schema_for", lambda *_: _Schema())
    call = lambda: catalog.register_partitioned_dataset_versions(  # noqa: E731
        "url", [(_root_manifest(), "c" * 64)]
    )
    if fail_on:
        with pytest.raises(RuntimeError):
            call()
        assert conns[0].state == "rolled_back"
    else:
        call()
        assert len(conns) == 1 and conns[0].state == "committed"


def test_baseline_gate_requires_every_check():
    from cks_picks_cfb.rebuild import baseline

    decisions, report = b"d", b"r"
    pinned = {
        "admission_decisions_csv": hashlib.sha256(decisions).hexdigest(),
        "admission_report_json": hashlib.sha256(report).hexdigest(),
    }
    counts = {
        "baseline_events": 86937,
        "candidate_events": 82416,
        "admitted_events": 85457,
        "decisions": dict(baseline.EXPECTED["decisions"]),
    }

    def gate(**override):
        args = dict(
            counts=counts,
            decisions_bytes=decisions,
            report_bytes=report,
            pinned=pinned,
            verifier_ok=True,
            v1_problem_count=0,
        )
        args.update(override)
        return baseline.evaluate_gate(**args)

    assert gate()["passed"]
    assert not gate(decisions_bytes=b"x")["passed"]
    assert not gate(report_bytes=b"x")["passed"]
    assert not gate(verifier_ok=False)["passed"]
    assert not gate(v1_problem_count=1)["passed"]
    assert not gate(counts={**counts, "admitted_events": 85456})["passed"]
    assert not gate(
        counts={
            **counts,
            "decisions": {
                "admitted": 1417,
                "reverted_contradicted": 27,
                "reverted_unverified": 1749,
            },
        }
    )["passed"]


def test_stage_read_input_is_declared_and_hash_checked(tmp_path):
    plan, root = _plan(tmp_path)
    seen = {}

    def build(ctx):
        seen["data"] = ctx.read_input("decisions")
        return StageOutput([("lake/gold/a/x", b"1")])

    stages = [
        Stage(plan.stages[0], build, lambda c: []),
        Stage(plan.stages[1], lambda c: StageOutput([]), lambda c: []),
    ]
    orch = Orchestrator(
        plan, stages, staging=InMemoryStore(), code_sha=CODE_SHA, repo_root=root
    )
    guard = GuardedStore(
        InMemoryStore(IDENTITY), run_id="run1", expected_identity=IDENTITY
    )
    orch.preflight(
        repo_root=root,
        config_sha="c" * 64,
        worktree_clean=True,
        guard=guard,
        is_tracked=lambda *_: True,
    )
    orch.build()
    assert seen["data"] == b"decision-bytes"
