"""Durable, resumable orchestration for weekly CFB operations."""

from __future__ import annotations

import json
import os
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Callable, ContextManager, Iterator, Mapping, Protocol, Sequence
from uuid import uuid4

import psycopg


class StepState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class OperationContext:
    command: str
    environment: str
    season: int
    week: int | None
    as_of: str | None
    pipeline_run_id: str
    prediction_run_id: str | None = None

    @property
    def lock_key(self) -> str:
        return f"cks:{self.environment}:{self.season}:{self.week or 0}"


StepAction = Callable[[OperationContext], Sequence[Mapping[str, Any]] | None]


@dataclass(frozen=True)
class PipelineStep:
    name: str
    action: StepAction


class StateStore(Protocol):
    def advisory_lock(self, key: str) -> ContextManager[None]: ...

    def begin_run(self, context: OperationContext) -> None: ...

    def successful_steps(self, pipeline_run_id: str) -> set[str]: ...

    def begin_step(
        self, context: OperationContext, step: PipelineStep, ordinal: int
    ) -> None: ...

    def finish_step(
        self,
        context: OperationContext,
        step: PipelineStep,
        *,
        outputs: Sequence[Mapping[str, Any]],
    ) -> None: ...

    def fail_step(
        self,
        context: OperationContext,
        step: PipelineStep,
        *,
        category: str,
        detail: str,
    ) -> None: ...

    def finish_run(self, context: OperationContext) -> None: ...


class PostgresStateStore:
    """Neon-backed workflow state using one connection for advisory lock lifetime."""

    def __init__(self, conn_url: str) -> None:
        self.conn_url = conn_url
        self._conn: psycopg.Connection | None = None

    def __enter__(self) -> PostgresStateStore:
        self._conn = psycopg.connect(self.conn_url)
        return self

    def __exit__(self, *_: object) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> psycopg.Connection:
        if self._conn is None:
            raise RuntimeError("PostgresStateStore must be used as a context manager")
        return self._conn

    @contextmanager
    def advisory_lock(self, key: str) -> Iterator[None]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(hashtextextended(%s, 0))", (key,))
            if cur.fetchone()[0] is not True:
                raise RuntimeError(f"Another pipeline owns lock {key}")
        try:
            yield
        finally:
            with self.conn.cursor() as cur:
                cur.execute(
                    "SELECT pg_advisory_unlock(hashtextextended(%s, 0))", (key,)
                )
            self.conn.commit()

    def begin_run(self, context: OperationContext) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO ops.pipeline_runs "
                "(pipeline_run_id, command, environment, season, week, state) "
                "VALUES (%s, %s, %s, %s, %s, 'running') "
                "ON CONFLICT (pipeline_run_id) DO UPDATE SET state = 'running', "
                "error_category = NULL, error_detail = NULL, finished_at = NULL",
                (
                    context.pipeline_run_id,
                    context.command,
                    context.environment,
                    context.season,
                    context.week,
                ),
            )
        self.conn.commit()

    def successful_steps(self, pipeline_run_id: str) -> set[str]:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT step_name FROM ops.pipeline_steps "
                "WHERE pipeline_run_id = %s AND state = 'succeeded'",
                (pipeline_run_id,),
            )
            return {str(row[0]) for row in cur.fetchall()}

    def begin_step(
        self, context: OperationContext, step: PipelineStep, ordinal: int
    ) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO ops.pipeline_steps "
                "(pipeline_run_id, step_name, ordinal, state, attempts, started_at) "
                "VALUES (%s, %s, %s, 'running', 1, NOW()) "
                "ON CONFLICT (pipeline_run_id, step_name) DO UPDATE SET "
                "state = 'running', attempts = ops.pipeline_steps.attempts + 1, "
                "started_at = NOW(), finished_at = NULL, error_category = NULL, "
                "error_detail = NULL",
                (context.pipeline_run_id, step.name, ordinal),
            )
        self.conn.commit()

    def finish_step(
        self,
        context: OperationContext,
        step: PipelineStep,
        *,
        outputs: Sequence[Mapping[str, Any]],
    ) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE ops.pipeline_steps SET state = 'succeeded', "
                "output_refs = %s::jsonb, finished_at = NOW() "
                "WHERE pipeline_run_id = %s AND step_name = %s",
                (json.dumps(list(outputs)), context.pipeline_run_id, step.name),
            )
            if step.name == "snapshot_inputs":
                cur.execute(
                    "UPDATE ops.pipeline_runs SET input_refs = %s::jsonb "
                    "WHERE pipeline_run_id = %s",
                    (json.dumps(list(outputs)), context.pipeline_run_id),
                )
        self.conn.commit()

    def fail_step(
        self,
        context: OperationContext,
        step: PipelineStep,
        *,
        category: str,
        detail: str,
    ) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE ops.pipeline_steps SET state = 'failed', finished_at = NOW(), "
                "error_category = %s, error_detail = %s "
                "WHERE pipeline_run_id = %s AND step_name = %s",
                (category, detail[-4000:], context.pipeline_run_id, step.name),
            )
            cur.execute(
                "UPDATE ops.pipeline_runs SET state = 'failed', finished_at = NOW(), "
                "error_category = %s, error_detail = %s WHERE pipeline_run_id = %s",
                (category, detail[-4000:], context.pipeline_run_id),
            )
        self.conn.commit()

    def finish_run(self, context: OperationContext) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE ops.pipeline_runs SET state = 'succeeded', finished_at = NOW(), "
                "error_category = NULL, error_detail = NULL WHERE pipeline_run_id = %s",
                (context.pipeline_run_id,),
            )
        self.conn.commit()


class InMemoryStateStore:
    """Test store with the same resume semantics as the Postgres implementation."""

    def __init__(self) -> None:
        self.runs: dict[str, str] = {}
        self.steps: dict[tuple[str, str], dict[str, Any]] = {}
        self.locks: set[str] = set()

    @contextmanager
    def advisory_lock(self, key: str) -> Iterator[None]:
        if key in self.locks:
            raise RuntimeError(f"Another pipeline owns lock {key}")
        self.locks.add(key)
        try:
            yield
        finally:
            self.locks.remove(key)

    def begin_run(self, context: OperationContext) -> None:
        self.runs[context.pipeline_run_id] = "running"

    def successful_steps(self, pipeline_run_id: str) -> set[str]:
        return {
            name
            for (run_id, name), record in self.steps.items()
            if run_id == pipeline_run_id and record["state"] == "succeeded"
        }

    def begin_step(
        self, context: OperationContext, step: PipelineStep, ordinal: int
    ) -> None:
        key = (context.pipeline_run_id, step.name)
        attempts = self.steps.get(key, {}).get("attempts", 0) + 1
        self.steps[key] = {
            "state": "running",
            "ordinal": ordinal,
            "attempts": attempts,
        }

    def finish_step(
        self,
        context: OperationContext,
        step: PipelineStep,
        *,
        outputs: Sequence[Mapping[str, Any]],
    ) -> None:
        self.steps[(context.pipeline_run_id, step.name)].update(
            state="succeeded", outputs=list(outputs)
        )

    def fail_step(
        self,
        context: OperationContext,
        step: PipelineStep,
        *,
        category: str,
        detail: str,
    ) -> None:
        self.steps[(context.pipeline_run_id, step.name)].update(
            state="failed", category=category, detail=detail
        )
        self.runs[context.pipeline_run_id] = "failed"

    def finish_run(self, context: OperationContext) -> None:
        self.runs[context.pipeline_run_id] = "succeeded"


@dataclass
class StateMachine:
    store: StateStore
    crash_after_step: str | None = None
    logger: Callable[[str], None] = print
    _clock: Callable[[], datetime] = field(
        default=lambda: datetime.now(timezone.utc), repr=False
    )

    def run(
        self, context: OperationContext, steps: Sequence[PipelineStep]
    ) -> OperationContext:
        with self.store.advisory_lock(context.lock_key):
            self.store.begin_run(context)
            completed = self.store.successful_steps(context.pipeline_run_id)
            for ordinal, step in enumerate(steps):
                if step.name in completed:
                    self._log(context, step.name, "resume_skip")
                    continue
                self.store.begin_step(context, step, ordinal)
                self._log(context, step.name, "running")
                try:
                    outputs = list(step.action(context) or [])
                    self.store.finish_step(context, step, outputs=outputs)
                    self._log(context, step.name, "succeeded")
                except Exception as exc:
                    self.store.fail_step(
                        context,
                        step,
                        category=type(exc).__name__,
                        detail=str(exc),
                    )
                    self._log(context, step.name, "failed", error=str(exc))
                    raise
                if self.crash_after_step == step.name:
                    raise InjectedCrashError(f"Injected crash after {step.name}")
            self.store.finish_run(context)
            self._log(context, None, "succeeded")
        return context

    def _log(
        self,
        context: OperationContext,
        step: str | None,
        state: str,
        **extra: Any,
    ) -> None:
        self.logger(
            json.dumps(
                {
                    "timestamp": self._clock().isoformat(),
                    "pipeline_run_id": context.pipeline_run_id,
                    "prediction_run_id": context.prediction_run_id,
                    "command": context.command,
                    "step": step,
                    "state": state,
                    **extra,
                },
                sort_keys=True,
            )
        )


class InjectedCrashError(RuntimeError):
    """Raised by acceptance tests to prove step resumption."""


def subprocess_step(name: str, argv: Sequence[str]) -> PipelineStep:
    """Create a fail-closed, shell-free subprocess pipeline step."""

    def action(_: OperationContext) -> Sequence[Mapping[str, Any]]:
        env = {**os.environ, "PYTHONPATH": ".:src"}
        completed = subprocess.run(list(argv), check=False, env=env)
        if completed.returncode != 0:
            raise subprocess.CalledProcessError(completed.returncode, list(argv))
        return ({"argv": list(argv), "returncode": completed.returncode},)

    return PipelineStep(name=name, action=action)


def new_context(
    *,
    command: str,
    environment: str,
    season: int,
    week: int | None,
    as_of: str | None,
    pipeline_run_id: str | None = None,
) -> OperationContext:
    if environment not in {"preview", "production"}:
        raise ValueError("environment must be preview or production")
    run_id = pipeline_run_id or uuid4().hex
    prediction_run_id = (
        f"{season}w{week}-{run_id[:12]}"
        if command == "publish-week" and week is not None
        else None
    )
    return OperationContext(
        command=command,
        environment=environment,
        season=season,
        week=week,
        as_of=as_of,
        pipeline_run_id=run_id,
        prediction_run_id=prediction_run_id,
    )
