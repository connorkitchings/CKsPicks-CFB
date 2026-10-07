"""Run namespaces: 6B reuses the harness while 6A plans, roots and guards stay unchanged."""

from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.rebuild import published
from cks_picks_cfb.rebuild.errors import (
    GateError,
    InputPinError,
    PlanError,
    TargetError,
)
from cks_picks_cfb.rebuild.inputs import LEGACY_PARENT_TOKENS, reject_legacy_parents
from cks_picks_cfb.rebuild.orchestrator import Orchestrator, Stage, StageOutput
from cks_picks_cfb.rebuild.plan import (
    HISTORICAL_SEASONS,
    InputPin,
    RebuildPlan,
    StagePlan,
)
from cks_picks_cfb.rebuild.targets import GuardedStore, InMemoryStore

REPO = Path(__file__).resolve().parents[1]
IDENTITY = "memory:preview"
CODE_SHA = "a" * 40
# plan_sha values recorded in the signed 6A preflight records (2026-10-05)
SIGNED_6A_PLAN_SHAS = {
    "conf/rebuild/6a_v1.yaml": "fc263834be68f4ddb9760876df3e8c9e721258adc498a1b4069d1508f7e096b9",
    "conf/rebuild/6a_task4_v1.yaml": "dff398aaf15454ade9002b41f79329cc4aef13b3fc45f2a18e20b692ec6154a5",
}


def _plan(tmp_path: Path, **overrides) -> RebuildPlan:
    data = b"decision-bytes"
    (tmp_path / "decisions.csv").write_bytes(data)
    pin = InputPin(
        "decisions", "decisions.csv", hashlib.sha256(data).hexdigest(), "git_file"
    )
    stage_output = (
        "lake/gold/dataset=reconstruction_test/"
        if overrides.get("namespace") == "rebuild/6b/"
        else "lake/gold/a/"
    )
    values = dict(
        run_id="run1",
        storage_identity=IDENTITY,
        seasons=HISTORICAL_SEASONS,
        inputs=(pin,),
        stages=(StagePlan("a", inputs=("decisions",), outputs=(stage_output,)),),
        registry_checksum="b" * 64,
    )
    values.update(overrides)
    return RebuildPlan(**values)


@pytest.mark.parametrize("path", sorted(SIGNED_6A_PLAN_SHAS))
def test_published_6a_plans_keep_their_signed_hash(path):
    plan = RebuildPlan.from_dict(yaml.safe_load((REPO / path).read_text()))
    assert plan.namespace == "rebuild/6a/"
    assert "namespace" not in plan.as_dict()
    assert plan.plan_sha() == SIGNED_6A_PLAN_SHAS[path]


def test_namespace_enters_the_signed_plan_only_when_not_default(tmp_path):
    default = _plan(tmp_path)
    six_b = _plan(tmp_path, namespace="rebuild/6b/")
    assert six_b.as_dict()["namespace"] == "rebuild/6b/"
    assert six_b.plan_sha() != default.plan_sha()
    assert six_b.run_prefix() == "rebuild/6b/run1/"
    assert RebuildPlan.from_dict(six_b.as_dict()).namespace == "rebuild/6b/"
    with pytest.raises(PlanError, match="namespace"):
        dataclasses.replace(default, namespace="rebuild/other/").validate()
    with pytest.raises(PlanError, match="namespace"):
        _plan(tmp_path, namespace="serving/").validate()


def test_guard_permits_only_its_own_run_namespace():
    six_b = GuardedStore(
        InMemoryStore(IDENTITY),
        run_id="run1",
        expected_identity=IDENTITY,
        run_namespace="rebuild/6b/",
    )
    six_b.create_once("rebuild/6b/run1/report.json", b"{}")
    six_b.create_once(
        "lake/gold/dataset=reconstruction_offsets_2026/data.parquet", b"1"
    )
    with pytest.raises(TargetError, match="outside permitted"):
        six_b.create_once("rebuild/6a/run1/report.json", b"{}")
    with pytest.raises(TargetError, match="outside permitted"):
        six_b.create_once("rebuild/6b/other/report.json", b"{}")
    with pytest.raises(TargetError, match="outside permitted"):
        six_b.create_once("lake/silver/dataset=games/data.parquet", b"1")
    with pytest.raises(TargetError, match="outside permitted"):
        six_b.create_once("lake/gold/dataset=football_possessions/data.parquet", b"1")
    with pytest.raises(TargetError, match="outside permitted"):
        six_b.create_once("quality/receipts/x.json", b"1")
    with pytest.raises(TargetError, match="forbidden"):
        six_b.create_once("predictions/run1/x.csv", b"x")
    default = GuardedStore(
        InMemoryStore(IDENTITY), run_id="run1", expected_identity=IDENTITY
    )
    with pytest.raises(TargetError, match="outside permitted"):
        default.create_once("rebuild/6b/run1/report.json", b"{}")


def _orchestrator(tmp_path, plan, guard):
    gold_key = (
        "lake/gold/dataset=reconstruction_test/x"
        if plan.namespace == "rebuild/6b/"
        else "lake/gold/a/x"
    )
    stages = [
        Stage(
            plan.stages[0],
            lambda ctx: StageOutput([(gold_key, b"1")]),
            lambda c: [],
        )
    ]
    orch = Orchestrator(
        plan,
        stages,
        staging=InMemoryStore("stage"),
        code_sha=CODE_SHA,
        repo_root=tmp_path,
    )
    return orch


def _preflight(orch, tmp_path, guard):
    return orch.preflight(
        repo_root=tmp_path,
        config_sha="c" * 64,
        worktree_clean=True,
        guard=guard,
        is_tracked=lambda *_: True,
    )


def test_preflight_refuses_a_guard_without_the_plans_namespace(tmp_path):
    plan = _plan(tmp_path, namespace="rebuild/6b/")
    guard = GuardedStore(
        InMemoryStore(IDENTITY), run_id="run1", expected_identity=IDENTITY
    )
    with pytest.raises(GateError, match="run namespace"):
        _preflight(_orchestrator(tmp_path, plan, guard), tmp_path, guard)


def _published_root(tmp_path, namespace):
    plan = _plan(tmp_path, namespace=namespace)
    guard = GuardedStore(
        InMemoryStore(IDENTITY),
        run_id="run1",
        expected_identity=IDENTITY,
        run_namespace=namespace,
    )
    orch = _orchestrator(tmp_path, plan, guard)
    _preflight(orch, tmp_path, guard)
    orch.build()
    assert orch.verify()["passed"]
    result = orch.publish(guard)
    return result, json.loads(guard.read(result.root_key))


def test_6b_root_manifest_lives_in_its_namespace_and_records_it(tmp_path):
    result, root = _published_root(tmp_path, "rebuild/6b/")
    assert result.root_key == "rebuild/6b/run1/root-manifest.json"
    assert root["namespace"] == "rebuild/6b/"


def test_6a_root_manifest_is_unchanged(tmp_path):
    result, root = _published_root(tmp_path, "rebuild/6a/")
    assert result.root_key == "rebuild/6a/run1/root-manifest.json"
    assert "namespace" not in root


@pytest.mark.parametrize(
    ("root_extra", "prefix"),
    [({}, "rebuild/6a/r/"), ({"namespace": "rebuild/6b/"}, "rebuild/6b/r/")],
)
def test_published_run_derives_its_prefix_from_the_root(
    monkeypatch, root_extra, prefix
):
    root = signed_payload(
        {"kind": "rebuild_root_v1", "run_id": "r", "objects": {}, **root_extra}
    )
    monkeypatch.setattr(published.common, "preview_storage", lambda context: None)
    context = SimpleNamespace(read_input=lambda name: json.dumps(root).encode())
    assert published.PublishedRun(context).prefix == prefix


def test_served_chain_is_denylisted_outside_legacy_stages(tmp_path):
    for token in (
        "intended-update/2026-runs/20260929",
        "intended-update/2026-serving/2026w",
        "e80ae3473d88d0c458325c19343e7dae6447924d9abad29b15089bc19cacd26b",
        "30c4f1eb0ef5b3c1e30b2a877b4553923c3b5ff68832eea0282e37e625b13531",
    ):
        assert token in LEGACY_PARENT_TOKENS
    uri = (
        "artifacts/research/data-first-football-v1/forecasts/intended-update/"
        "2026-serving/2026w3-v5repair-20260929-p1/serving-manifest.json"
    )
    pin = InputPin("served", uri, "d" * 64, "r2_object")

    def plan(legacy: bool) -> RebuildPlan:
        return _plan(
            tmp_path,
            inputs=(pin,),
            stages=(StagePlan("compare", inputs=("served",), legacy_allowed=legacy),),
        )

    with pytest.raises(InputPinError, match="legacy parent"):
        reject_legacy_parents(plan(False))
    reject_legacy_parents(plan(True))
