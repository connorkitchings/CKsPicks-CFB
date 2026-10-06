"""The publication dry run plans without writing and refuses unverified or drifted state."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest

from cks_picks_cfb.rebuild.errors import GateError, TargetError
from cks_picks_cfb.rebuild.orchestrator import Orchestrator, Stage, StageOutput
from cks_picks_cfb.rebuild.plan import (
    HISTORICAL_SEASONS,
    InputPin,
    RebuildPlan,
    StagePlan,
)
from cks_picks_cfb.rebuild.targets import GuardedStore, InMemoryStore

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location(
    "publish_6a", ROOT / "scripts/pipeline/publish_6a.py"
)
publish = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publish)

IDENTITY = "memory:preview"


def _harness(tmp_path, *, bad_verify=False):
    data = b"pinned"
    (tmp_path / "pin.txt").write_bytes(data)
    plan = RebuildPlan(
        run_id="run1",
        storage_identity=IDENTITY,
        seasons=HISTORICAL_SEASONS,
        inputs=(
            InputPin("pin", "pin.txt", hashlib.sha256(data).hexdigest(), "git_file"),
        ),
        stages=(StagePlan("a", inputs=("pin",), outputs=("lake/gold/a/",)),),
        registry_checksum="b" * 64,
    )
    stage = Stage(
        plan.stages[0],
        lambda ctx: StageOutput([("lake/gold/a/part.bin", b"bytes")]),
        lambda ctx: ["bad"] if bad_verify else [],
    )
    orchestrator = Orchestrator(
        plan,
        [stage],
        staging=InMemoryStore("stage"),
        code_sha="a" * 40,
        repo_root=tmp_path,
    )
    guard = GuardedStore(
        InMemoryStore(IDENTITY), run_id="run1", expected_identity=IDENTITY
    )
    orchestrator.preflight(
        repo_root=tmp_path,
        config_sha="c" * 64,
        worktree_clean=True,
        guard=guard,
        is_tracked=lambda *_: True,
    )
    orchestrator.build()
    return orchestrator, guard


def test_dry_run_plans_without_writing(tmp_path):
    orchestrator, guard = _harness(tmp_path)
    orchestrator.verify()
    summary = publish.plan_publication(orchestrator, guard, orchestrator.staging)
    assert summary["objects"] == 1 and summary["bytes"] == 5
    assert summary["namespaces"] == {"lake/gold": 1}
    assert (
        summary["already_present_identical"] == 0 and summary["catalog_write_scope_ok"]
    )
    assert guard.ledger.writes == 0 and not guard.store.objects


def test_dry_run_refuses_without_a_full_passing_verify(tmp_path):
    orchestrator, guard = _harness(tmp_path)
    with pytest.raises(GateError, match="no verify record"):
        publish.plan_publication(orchestrator, guard, orchestrator.staging)
    failing, guard2 = _harness(
        tmp_path / "x" if (tmp_path / "x").mkdir() is None else tmp_path,
        bad_verify=True,
    )
    failing.verify()
    with pytest.raises(GateError, match="did not pass"):
        publish.plan_publication(failing, guard2, failing.staging)


def test_dry_run_refuses_when_a_remote_object_differs_and_counts_identical_ones(
    tmp_path,
):
    orchestrator, guard = _harness(tmp_path)
    orchestrator.verify()
    guard.store.put_if_absent("lake/gold/a/part.bin", b"bytes")
    assert (
        publish.plan_publication(orchestrator, guard, orchestrator.staging)[
            "already_present_identical"
        ]
        == 1
    )
    guard.store.objects["lake/gold/a/part.bin"] = b"different"
    with pytest.raises(GateError, match="differ from the staged bytes"):
        publish.plan_publication(orchestrator, guard, orchestrator.staging)


def test_apply_then_identical_retry_writes_nothing(tmp_path):
    orchestrator, guard = _harness(tmp_path)
    orchestrator.verify()
    first = orchestrator.publish(guard)
    second = orchestrator.publish(guard)
    assert first.writes == first.objects + 1 and second.writes == 0
    assert second.root_sha == first.root_sha


def test_publication_cannot_leave_the_allow_list(tmp_path):
    orchestrator, guard = _harness(tmp_path)
    with pytest.raises(TargetError):
        guard.create_once("serving/week5.json", b"x")


def test_root_manifest_records_the_publisher_commit_and_retry_is_stable(tmp_path):
    import json

    orchestrator, guard = _harness(tmp_path)
    orchestrator.verify()
    first = orchestrator.publish(guard, publisher_sha="d" * 40)
    root = json.loads(guard.read(first.root_key))
    assert root["code_sha"] == "a" * 40 and root["publisher_code_sha"] == "d" * 40
    second = orchestrator.publish(guard, publisher_sha="d" * 40)
    assert second.writes == 0 and second.root_sha == first.root_sha
    with pytest.raises(
        Exception
    ):  # another publisher commit would change the root bytes
        orchestrator.publish(guard, publisher_sha="e" * 40)


def test_catalog_retry_reuses_existing_root_from_ancestor_publisher(tmp_path):
    import json

    orchestrator, guard = _harness(tmp_path)
    orchestrator.verify()
    first = orchestrator.publish(guard, publisher_sha="d" * 40)

    second = orchestrator.publish(
        guard,
        publisher_sha="e" * 40,
        is_existing_publisher_ancestor=lambda previous: previous == "d" * 40,
    )
    root = json.loads(guard.read(first.root_key))
    assert second.writes == 0
    assert second.root_sha == first.root_sha
    assert root["publisher_code_sha"] == "d" * 40


def test_catalog_retry_rejects_existing_root_from_unrelated_publisher(tmp_path):
    orchestrator, guard = _harness(tmp_path)
    orchestrator.verify()
    orchestrator.publish(guard, publisher_sha="d" * 40)

    with pytest.raises(GateError, match="unrelated publisher commit"):
        orchestrator.publish(
            guard,
            publisher_sha="e" * 40,
            is_existing_publisher_ancestor=lambda _previous: False,
        )
