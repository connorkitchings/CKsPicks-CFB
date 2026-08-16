import pytest

from cks_picks_cfb.ops.__main__ import build_steps
from cks_picks_cfb.ops.state_machine import (
    InjectedCrashError,
    InMemoryStateStore,
    PipelineStep,
    StateMachine,
    new_context,
)


def test_pipeline_reruns_unverified_step_after_forced_crash():
    store = InMemoryStateStore()
    calls = []
    context = new_context(
        command="publish-week",
        environment="preview",
        season=2026,
        week=1,
        as_of="2026-08-20T00:00:00Z",
        pipeline_run_id="pipeline-1",
    )
    steps = [
        PipelineStep("one", lambda _: calls.append("one") or []),
        PipelineStep("two", lambda _: calls.append("two") or []),
    ]
    with pytest.raises(InjectedCrashError):
        StateMachine(store, crash_after_step="one", logger=lambda _: None).run(
            context, steps
        )
    StateMachine(store, logger=lambda _: None).run(context, steps)
    assert calls == ["one", "one", "two"]
    assert store.runs["pipeline-1"] == "succeeded"
    assert context.lease_epoch == 0


def test_pipeline_rejects_changed_step_definition_on_resume():
    store = InMemoryStateStore()
    context = new_context(
        command="publish-week",
        environment="preview",
        season=2026,
        week=1,
        as_of="2026-08-20T00:00:00Z",
        pipeline_run_id="pipeline-definition",
    )
    StateMachine(store, logger=lambda _: None).run(
        context, [PipelineStep("one", lambda _: [], definition={"version": 1})]
    )
    with pytest.raises(RuntimeError, match="definition"):
        StateMachine(store, logger=lambda _: None).run(
            context, [PipelineStep("one", lambda _: [], definition={"version": 2})]
        )


def test_pipeline_skips_step_only_when_output_validator_passes():
    store = InMemoryStateStore()
    calls = []
    context = new_context(
        command="publish-week",
        environment="preview",
        season=2026,
        week=1,
        as_of="2026-08-20T00:00:00Z",
        pipeline_run_id="pipeline-verified",
    )
    step = PipelineStep(
        "one",
        lambda _: calls.append("one") or [{"uri": "immutable"}],
        resume_validator=lambda _, outputs: outputs == [{"uri": "immutable"}],
    )
    StateMachine(store, logger=lambda _: None).run(context, [step])
    StateMachine(store, logger=lambda _: None).run(context, [step])
    assert calls == ["one"]


def test_week_lock_rejects_concurrent_owner():
    store = InMemoryStateStore()
    with store.advisory_lock("scope"):
        with pytest.raises(RuntimeError, match="owns lock"):
            with store.advisory_lock("scope"):
                pass


def test_publish_pipeline_accepts_live_week_zero():
    context = new_context(
        command="publish-week",
        environment="preview",
        season=2026,
        week=0,
        as_of="2026-08-20T00:00:00Z",
        pipeline_run_id="week-zero-pipeline",
    )
    assert context.prediction_run_id == "2026w0-week-zero-pi"
    steps = build_steps(context, conn_url="postgresql://unused")
    assert [step.name for step in steps] == [
        "preflight",
        "audit_data",
        "ingest_schedule",
        "ingest_market",
        "build_market_snapshot",
        "snapshot_inputs",
        "predict",
        "activate",
    ]
