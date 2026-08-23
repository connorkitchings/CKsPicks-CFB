import json

import pytest

from cks_picks_cfb.ops.__main__ import build_steps
from cks_picks_cfb.ops.state_machine import (
    InjectedCrashError,
    InMemoryStateStore,
    PipelineStep,
    StateMachine,
    WebhookFailureNotifier,
    new_context,
)


class RecordingNotifier:
    def __init__(self, error: Exception | None = None):
        self.calls = []
        self.error = error

    def notify(self, context, step, *, category, detail):
        self.calls.append((context, step, category, detail))
        if self.error:
            raise self.error


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


def test_failed_publish_step_records_then_notifies_without_masking_error():
    store = InMemoryStateStore()
    notifier = RecordingNotifier()
    context = new_context(
        command="publish-week",
        environment="preview",
        season=2026,
        week=1,
        as_of=None,
        pipeline_run_id="notify-publish",
    )

    with pytest.raises(ValueError, match="original failure"):
        StateMachine(store, notifier=notifier, logger=lambda _: None).run(
            context,
            [
                PipelineStep(
                    "predict",
                    lambda _: (_ for _ in ()).throw(ValueError("original failure")),
                )
            ],
        )

    assert store.runs[context.pipeline_run_id] == "failed"
    assert [
        (step, category, detail) for _, step, category, detail in notifier.calls
    ] == [("predict", "ValueError", "original failure")]


def test_alert_delivery_failure_preserves_original_pipeline_error():
    store = InMemoryStateStore()
    messages = []
    context = new_context(
        command="freeze-week",
        environment="preview",
        season=2026,
        week=1,
        as_of=None,
        pipeline_run_id="notify-error",
    )
    with pytest.raises(RuntimeError, match="pipeline failure"):
        StateMachine(
            store,
            notifier=RecordingNotifier(RuntimeError("webhook down")),
            logger=messages.append,
        ).run(
            context,
            [
                PipelineStep(
                    "freeze",
                    lambda _: (_ for _ in ()).throw(RuntimeError("pipeline failure")),
                )
            ],
        )
    assert any("alert_delivery_failed" in message for message in messages)


def test_alerts_are_scoped_to_publication_commands():
    store = InMemoryStateStore()
    notifier = RecordingNotifier()
    context = new_context(
        command="prepare-week",
        environment="preview",
        season=2026,
        week=1,
        as_of=None,
        pipeline_run_id="no-notify",
    )
    with pytest.raises(ValueError):
        StateMachine(store, notifier=notifier, logger=lambda _: None).run(
            context,
            [
                PipelineStep(
                    "prepare", lambda _: (_ for _ in ()).throw(ValueError("fail"))
                )
            ],
        )
    assert notifier.calls == []


def test_webhook_notifier_is_optional_and_truncates_detail(monkeypatch):
    monkeypatch.delenv("CFB_OPS_ALERT_WEBHOOK_URL", raising=False)
    assert WebhookFailureNotifier.from_env() is None
    captured = {}

    class Response:
        status = 204

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def fake_urlopen(request, timeout):
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr("cks_picks_cfb.ops.state_machine.urlopen", fake_urlopen)
    notifier = WebhookFailureNotifier("https://example.invalid/hook", timeout_seconds=2)
    context = new_context(
        command="close-week",
        environment="production",
        season=2026,
        week=2,
        as_of=None,
        pipeline_run_id="payload",
    )
    notifier.notify(context, "close", category="ValueError", detail="x" * 3000)
    assert captured["timeout"] == 2
    assert captured["payload"]["event"] == "pipeline_step_failed"
    assert captured["payload"]["error_detail"] == "x" * 2000
    assert "url" not in captured["payload"]


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


def test_prepare_week_rebuilds_gold_from_completed_canonical_weeks():
    context = new_context(
        command="prepare-week",
        environment="preview",
        season=2026,
        week=1,
        as_of="2026-09-01T12:00:00Z",
        pipeline_run_id="prepare-week-one",
    )

    steps = build_steps(context, conn_url="postgresql://unused")

    names = [step.name for step in steps]
    assert names[:3] == [
        "ingest_schedule",
        "ingest_plays_week_0",
        "ingest_game_stats_week_0",
    ]
    assert names[-4:] == [
        "combine_team_game",
        "build_temporal_matchups",
        "build_gold",
        "target_week_readiness",
    ]
    gold = next(step for step in steps if step.name == "build_gold")
    assert any(
        value.endswith("baselines-selection.json") for value in gold.definition["argv"]
    )


def test_publish_after_week_zero_requires_explicit_prepared_gold():
    context = new_context(
        command="publish-week",
        environment="preview",
        season=2026,
        week=1,
        as_of="2026-09-01T12:00:00Z",
        pipeline_run_id="publish-week-one",
    )

    with pytest.raises(ValueError, match="prepared-gold-ref-uri"):
        build_steps(context, conn_url="postgresql://unused")
