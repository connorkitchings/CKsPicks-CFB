import json
from types import SimpleNamespace

import pytest

from cks_picks_cfb.ops.__main__ import _history_silver_steps, build_steps
from cks_picks_cfb.ops.state_machine import (
    InjectedCrashError,
    InMemoryStateStore,
    PipelineStep,
    PostgresStateStore,
    StateMachine,
    WebhookFailureNotifier,
    new_context,
    subprocess_step,
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

    monkeypatch.setattr("cks_picks_cfb.ops.notifier.urlopen", fake_urlopen)
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
    team_game = next(step for step in steps if step.name == "build_current_team_game")
    assert "--output-ref-set-uri" in team_game.definition["argv"]
    assert any(
        value.endswith("rating_input_ref_set.json")
        for value in team_game.definition["argv"]
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


def test_command_builders_preserve_optional_arguments_and_scoped_commands(monkeypatch):
    """Every direct CLI command composes its deterministic subprocess contract."""
    options = SimpleNamespace(
        entity="plays",
        dataset="games",
        output_ref_uri="artifacts/preview/fixture.json",
        capture_id=["capture-a", "capture-b"],
        games_ref_uri="games.json",
        week_policy_ref_uri="policy.json",
        plays_ref_uri="plays.json",
        teams_ref_uri="teams.json",
        venues_ref_uri="venues.json",
        weather_ref_uri="weather.json",
        game_stats_ref_uri="stats.json",
        corrections_ref_uri="corrections.json",
        matchups_ref_uri="matchups.json",
        schedule_ref_uri="schedule.json",
        baselines_ref_uri="baselines.json",
        core_ref_uri="core.json",
        include_locked_2025=True,
        frozen_design_sha="sealed",
        markets_ref_uri="markets.json",
        preseason_features_ref_uri="preseason.json",
        feature_track="strict",
        cancellation_waiver=["weather", "cancelled"],
        mode="structural",
        config="conf/fixture.yaml",
        prepared_gold_ref_uri="prepared.json",
    )
    commands = {
        "fetch-source": 1,
        "build-silver": 1,
        "build-team-game": 1,
        "build-features": 1,
        "build-baselines": 1,
        "assemble-model-ready": 1,
        "readiness": 3,
        "replay-season": 1,
        "reconcile": 1,
        "audit-data": 1,
    }
    for command, expected_count in commands.items():
        context = new_context(
            command=command,
            environment="preview",
            season=2026,
            week=1,
            as_of="2026-09-01T12:00:00Z",
            pipeline_run_id=f"builder-{command}",
        )
        steps = build_steps(context, conn_url="postgresql://unused", options=options)
        assert len(steps) == expected_count

    freeze = build_steps(
        new_context(
            command="freeze-week",
            environment="preview",
            season=2026,
            week=1,
            as_of=None,
            pipeline_run_id="builder-freeze",
        ),
        conn_url="postgresql://unused",
        waiver="operator-approved",
    )
    assert "--waiver" in freeze[0].definition["argv"]

    monkeypatch.setattr(
        "cks_picks_cfb.ops.__main__._resolve_frozen_run", lambda *_: "run"
    )
    close = build_steps(
        new_context(
            command="close-week",
            environment="preview",
            season=2026,
            week=1,
            as_of="2026-09-01T12:00:00Z",
            pipeline_run_id="builder-close",
        ),
        conn_url="postgresql://unused",
        options=options,
    )
    assert [step.name for step in close] == [
        "ingest_finals",
        "build_game_outcomes",
        "ingest_completed_week",
        "score",
        "publish_grades",
    ]
    assert "--cancellation-waiver" in close[3].definition["argv"]


def test_fetch_source_requires_a_week_only_for_weekly_entities():
    season_context = new_context(
        command="fetch-source",
        environment="preview",
        season=2026,
        week=None,
        as_of=None,
        pipeline_run_id="season-source",
    )
    assert (
        build_steps(
            season_context,
            conn_url="postgresql://unused",
            options=SimpleNamespace(entity="teams"),
        )[0].name
        == "fetch_teams"
    )
    with pytest.raises(ValueError, match="requires --week"):
        build_steps(
            season_context,
            conn_url="postgresql://unused",
            options=SimpleNamespace(entity="plays"),
        )


def test_historical_silver_composition_covers_all_allowed_seasons_and_dependencies():
    steps = _history_silver_steps("preview")
    names = [step.name for step in steps]

    assert "silver_preseason_team_inputs_2019" in names
    assert "silver_schedule_week_policy_2026" in names
    assert "silver_games_2026" in names
    assert "combine_games_2021_2026" in names
    assert "build_temporal_matchups" in names
    assert "assemble_selection_gold" in names
    assert not any("_2020" in name for name in names)

    games_2026 = next(step for step in steps if step.name == "silver_games_2026")
    assert "--week-policy-ref-uri" in games_2026.definition["argv"]
    team_aliases = next(
        step for step in steps if step.name == "silver_team_aliases_2025"
    )
    assert "--optional" in team_aliases.definition["argv"]


def test_successor_history_capture_uses_one_catalog_run_per_source_entity():
    context = new_context(
        command="prepare-rating-history",
        environment="preview",
        season=2026,
        week=None,
        as_of="2026-08-27T12:00:00Z",
        pipeline_run_id="successor-history",
    )
    options = SimpleNamespace(skip_capture=True, prefix="")
    skipped = build_steps(context, conn_url="postgresql://unused", options=options)
    assert all("capture_successor_history" not in step.name for step in skipped)

    # Build the capture graph without querying a historical source archive.
    options.skip_capture = False
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "cks_picks_cfb.ops.__main__._history_objects",
            lambda _: (None, None, [], []),
        )
        steps = build_steps(context, conn_url="postgresql://unused", options=options)
    captures = [step for step in steps if step.name.startswith("capture_successor")]
    assert len(captures) == 20
    assert len({step.definition["entity"] for step in captures}) == 20
    games_before_plays = [step.name for step in captures].index(
        "capture_successor_history_2015_games"
    ) < [step.name for step in captures].index("capture_successor_history_2015_plays")
    assert games_before_plays


def test_postgres_state_store_preserves_lease_and_step_semantics_with_fake_connection(
    monkeypatch,
):
    class Cursor:
        rowcount = 1

        def __init__(self):
            self.executed = []

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, sql, params=()):
            self.executed.append((sql, params))

        def fetchone(self):
            sql = self.executed[-1][0]
            if "pg_try_advisory_lock" in sql:
                return (True,)
            if "RETURNING lease_epoch" in sql:
                return (7,)
            if "SELECT 1 FROM ops.pipeline_runs" in sql:
                return (1,)
            return None

        def fetchall(self):
            return [("prior", [{"uri": "immutable"}])]

    class Connection:
        closed = False

        def __init__(self):
            self.cursor_instance = Cursor()
            self.commits = 0

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def cursor(self):
            return self.cursor_instance

        def commit(self):
            self.commits += 1

        def close(self):
            self.closed = True

    connections = []

    def connect(_url):
        connection = Connection()
        connections.append(connection)
        return connection

    monkeypatch.setattr("cks_picks_cfb.ops.state_machine.psycopg.connect", connect)
    context = new_context(
        command="publish-week",
        environment="preview",
        season=2026,
        week=1,
        as_of="2026-08-23T00:00:00Z",
        pipeline_run_id="postgres-fixture",
    )
    step = PipelineStep("snapshot_inputs", lambda _: [], definition={"kind": "fixture"})
    with PostgresStateStore("postgresql://fixture") as store:
        store.begin_run(context, {"steps": ["snapshot_inputs"]})
        assert store.acquire_lease(context) == 7
        store.heartbeat(context)
        assert store.successful_steps(context.pipeline_run_id) == {
            "prior": [{"uri": "immutable"}]
        }
        store.begin_step(context, step, 0)
        store.finish_step(context, step, outputs=[{"uri": "immutable"}])
        store.fail_step(context, step, category="ValueError", detail="x" * 5000)
        store.finish_run(context)
        with store.advisory_lock(context.lock_key):
            pass
        store.release_lease(context)
    assert any(connection.commits for connection in connections)


def test_subprocess_step_scopes_pythonpath_and_propagates_command_failure(monkeypatch):
    calls = []

    def successful(argv, check, env):
        calls.append((argv, check, env))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("cks_picks_cfb.ops.state_machine.subprocess.run", successful)
    context = new_context(
        command="readiness",
        environment="preview",
        season=2026,
        week=1,
        as_of=None,
        pipeline_run_id="subprocess-fixture",
    )
    step = subprocess_step("fixture", ["python", "fixture.py"])
    assert step.action(context) == (
        {"argv": ["python", "fixture.py"], "returncode": 0},
    )
    assert calls[0][1] is False
    assert calls[0][2]["PYTHONPATH"] == ".:src"

    monkeypatch.setattr(
        "cks_picks_cfb.ops.state_machine.subprocess.run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=9),
    )
    with pytest.raises(Exception, match="9"):
        step.action(context)
