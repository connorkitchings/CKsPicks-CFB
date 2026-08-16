"""Durable, resumable orchestration for weekly CFB operations."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Callable, ContextManager, Iterator, Mapping, Protocol, Sequence
from uuid import uuid4

import psycopg


class _NumpySafeEncoder(json.JSONEncoder):
    """Serialize numpy scalar types that the default encoder rejects."""

    def default(self, obj: Any) -> Any:
        # Import lazily so numpy is optional at import time.
        try:
            import numpy as np  # noqa: PLC0415

            if isinstance(obj, np.bool_):
                return bool(obj)
            if isinstance(obj, np.integer):
                return int(obj)
            if isinstance(obj, np.floating):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
        except ImportError:
            pass
        return super().default(obj)


def _json_dumps(value: Any) -> str:
    """json.dumps with numpy scalar support."""
    return json.dumps(value, cls=_NumpySafeEncoder)


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
    lease_epoch: int | None = None

    @property
    def lock_key(self) -> str:
        return f"cks:{self.environment}:{self.season}:{self.week or 0}"


StepAction = Callable[[OperationContext], Sequence[Mapping[str, Any]] | None]


@dataclass(frozen=True)
class PipelineStep:
    name: str
    action: StepAction
    definition: Mapping[str, Any] = field(default_factory=dict)
    resume_validator: (
        Callable[[OperationContext, Sequence[Mapping[str, Any]]], bool] | None
    ) = None


class StateStore(Protocol):
    def advisory_lock(self, key: str) -> ContextManager[None]: ...

    def begin_run(
        self, context: OperationContext, definition: Mapping[str, Any]
    ) -> None: ...

    def acquire_lease(self, context: OperationContext) -> int: ...

    def heartbeat(self, context: OperationContext) -> None: ...

    def release_lease(self, context: OperationContext) -> None: ...

    def successful_steps(
        self, pipeline_run_id: str
    ) -> Mapping[str, Sequence[Mapping[str, Any]]]: ...

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
    """Neon-backed workflow state with automatic reconnection.

    Long subprocess steps (e.g. plays Silver builds) can outlive a single
    Neon connection.  The ``conn`` property transparently reconnects when
    the previous connection was closed by the server.
    """

    def __init__(self, conn_url: str) -> None:
        self.conn_url = conn_url
        self._conn: psycopg.Connection | None = None
        self._lease_owner = uuid4().hex
        self._lease_epoch: int | None = None

    def __enter__(self) -> PostgresStateStore:
        self._conn = psycopg.connect(self.conn_url)
        return self

    def __exit__(self, *_: object) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> psycopg.Connection:
        if self._conn is None or self._conn.closed:
            self._conn = psycopg.connect(self.conn_url)
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

    def begin_run(
        self, context: OperationContext, definition: Mapping[str, Any]
    ) -> None:
        definition_json = _json_dumps(definition)
        definition_sha = hashlib.sha256(definition_json.encode()).hexdigest()
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT command, environment, season, week, definition_sha "
                "FROM ops.pipeline_runs WHERE pipeline_run_id = %s",
                (context.pipeline_run_id,),
            )
            existing = cur.fetchone()
            expected = (
                context.command,
                context.environment,
                context.season,
                context.week,
            )
            if existing:
                if tuple(existing[:4]) != expected or existing[4] is None:
                    raise RuntimeError(
                        "Pipeline run is legacy or has a conflicting operation definition"
                    )
                if str(existing[4]) != definition_sha:
                    raise RuntimeError(
                        "Pipeline run definition does not match resume request"
                    )
            cur.execute(
                "INSERT INTO ops.pipeline_runs "
                "(pipeline_run_id, command, environment, season, week, state, definition_json, definition_sha) "
                "VALUES (%s, %s, %s, %s, %s, 'running', %s::jsonb, %s) "
                "ON CONFLICT (pipeline_run_id) DO NOTHING",
                (
                    context.pipeline_run_id,
                    context.command,
                    context.environment,
                    context.season,
                    context.week,
                    definition_json,
                    definition_sha,
                ),
            )
        self.conn.commit()

    def acquire_lease(self, context: OperationContext) -> int:
        with psycopg.connect(self.conn_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE ops.pipeline_runs SET state = 'running', "
                    "error_category = NULL, error_detail = NULL, finished_at = NULL, "
                    "lease_owner = %s, "
                    "lease_epoch = lease_epoch + 1, heartbeat_at = NOW(), "
                    "lease_expires_at = NOW() + INTERVAL '120 seconds' "
                    "WHERE pipeline_run_id = %s AND "
                    "(lease_expires_at IS NULL OR lease_expires_at < NOW()) "
                    "RETURNING lease_epoch",
                    (self._lease_owner, context.pipeline_run_id),
                )
                row = cur.fetchone()
                if not row:
                    raise RuntimeError(f"Another pipeline owns lock {context.lock_key}")
                self._lease_epoch = int(row[0])
            conn.commit()
        return self._lease_epoch

    def _assert_lease(self, cur, context: OperationContext) -> None:
        cur.execute(
            "SELECT 1 FROM ops.pipeline_runs WHERE pipeline_run_id = %s "
            "AND lease_owner = %s AND lease_epoch = %s "
            "AND lease_expires_at >= NOW()",
            (context.pipeline_run_id, self._lease_owner, self._lease_epoch),
        )
        if cur.fetchone() is None:
            raise RuntimeError("Pipeline lease was lost")

    def heartbeat(self, context: OperationContext) -> None:
        if self._lease_epoch is None:
            raise RuntimeError("Pipeline lease has not been acquired")
        with psycopg.connect(self.conn_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE ops.pipeline_runs SET heartbeat_at = NOW(), "
                    "lease_expires_at = NOW() + INTERVAL '120 seconds' "
                    "WHERE pipeline_run_id = %s AND lease_owner = %s "
                    "AND lease_epoch = %s AND lease_expires_at >= NOW()",
                    (context.pipeline_run_id, self._lease_owner, self._lease_epoch),
                )
                if cur.rowcount != 1:
                    raise RuntimeError("Pipeline lease was lost")
            conn.commit()

    def release_lease(self, context: OperationContext) -> None:
        if self._lease_epoch is None:
            return
        with psycopg.connect(self.conn_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE ops.pipeline_runs SET lease_expires_at = NOW() "
                    "WHERE pipeline_run_id = %s AND lease_owner = %s AND lease_epoch = %s",
                    (context.pipeline_run_id, self._lease_owner, self._lease_epoch),
                )
            conn.commit()

    def successful_steps(
        self, pipeline_run_id: str
    ) -> Mapping[str, Sequence[Mapping[str, Any]]]:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT step_name, output_refs FROM ops.pipeline_steps "
                "WHERE pipeline_run_id = %s AND state = 'succeeded'",
                (pipeline_run_id,),
            )
            return {str(row[0]): list(row[1]) for row in cur.fetchall()}

    def begin_step(
        self, context: OperationContext, step: PipelineStep, ordinal: int
    ) -> None:
        with self.conn.cursor() as cur:
            self._assert_lease(cur, context)
            cur.execute(
                "INSERT INTO ops.pipeline_steps "
                "(pipeline_run_id, step_name, ordinal, state, attempts, started_at, definition_sha, lease_epoch) "
                "VALUES (%s, %s, %s, 'running', 1, NOW(), %s, %s) "
                "ON CONFLICT (pipeline_run_id, step_name) DO UPDATE SET "
                "state = 'running', attempts = ops.pipeline_steps.attempts + 1, "
                "started_at = NOW(), finished_at = NULL, error_category = NULL, "
                "error_detail = NULL",
                (
                    context.pipeline_run_id,
                    step.name,
                    ordinal,
                    _step_definition_sha(step),
                    self._lease_epoch,
                ),
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
            self._assert_lease(cur, context)
            cur.execute(
                "UPDATE ops.pipeline_steps SET state = 'succeeded', "
                "output_refs = %s::jsonb, finished_at = NOW() "
                "WHERE pipeline_run_id = %s AND step_name = %s",
                (_json_dumps(list(outputs)), context.pipeline_run_id, step.name),
            )
            if step.name == "snapshot_inputs":
                cur.execute(
                    "UPDATE ops.pipeline_runs SET input_refs = %s::jsonb "
                    "WHERE pipeline_run_id = %s",
                    (_json_dumps(list(outputs)), context.pipeline_run_id),
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
            self._assert_lease(cur, context)
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
            self._assert_lease(cur, context)
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
        self.definitions: dict[str, str] = {}

    @contextmanager
    def advisory_lock(self, key: str) -> Iterator[None]:
        if key in self.locks:
            raise RuntimeError(f"Another pipeline owns lock {key}")
        self.locks.add(key)
        try:
            yield
        finally:
            self.locks.remove(key)

    def begin_run(
        self, context: OperationContext, definition: Mapping[str, Any]
    ) -> None:
        definition_sha = hashlib.sha256(_json_dumps(definition).encode()).hexdigest()
        if context.pipeline_run_id in self.definitions and (
            self.definitions[context.pipeline_run_id] != definition_sha
        ):
            raise RuntimeError("Pipeline run definition does not match resume request")
        self.definitions[context.pipeline_run_id] = definition_sha
        self.runs[context.pipeline_run_id] = "running"

    def acquire_lease(self, context: OperationContext) -> int:
        return 0

    def heartbeat(self, context: OperationContext) -> None:
        return None

    def release_lease(self, context: OperationContext) -> None:
        return None

    def successful_steps(
        self, pipeline_run_id: str
    ) -> Mapping[str, Sequence[Mapping[str, Any]]]:
        return {
            name: list(record.get("outputs", []))
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
        definition = _operation_definition(context, steps)
        with self.store.advisory_lock(context.lock_key):
            self.store.begin_run(context, definition)
            object.__setattr__(
                context, "lease_epoch", self.store.acquire_lease(context)
            )
            heartbeat_error: list[Exception] = []
            stop_heartbeat = threading.Event()

            def keepalive() -> None:
                while not stop_heartbeat.wait(30):
                    try:
                        self.store.heartbeat(context)
                    except Exception as exc:  # pragma: no cover - timing dependent
                        heartbeat_error.append(exc)
                        return

            heartbeat_thread = threading.Thread(target=keepalive, daemon=True)
            heartbeat_thread.start()
            try:
                completed = self.store.successful_steps(context.pipeline_run_id)
                for ordinal, step in enumerate(steps):
                    if heartbeat_error:
                        raise RuntimeError(
                            "Pipeline lease was lost"
                        ) from heartbeat_error[0]
                    if step.name in completed and step.resume_validator:
                        if step.resume_validator(context, completed[step.name]):
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
            finally:
                stop_heartbeat.set()
                heartbeat_thread.join(timeout=1)
                self.store.release_lease(context)
        return context

    def _log(
        self,
        context: OperationContext,
        step: str | None,
        state: str,
        **extra: Any,
    ) -> None:
        self.logger(
            _json_dumps(
                {
                    "timestamp": self._clock().isoformat(),
                    "pipeline_run_id": context.pipeline_run_id,
                    "prediction_run_id": context.prediction_run_id,
                    "command": context.command,
                    "step": step,
                    "state": state,
                    **extra,
                }
            )
        )


class InjectedCrashError(RuntimeError):
    """Raised by acceptance tests to prove step resumption."""


def subprocess_step(name: str, argv: Sequence[str]) -> PipelineStep:
    """Create a fail-closed, shell-free subprocess pipeline step."""

    def action(context: OperationContext) -> Sequence[Mapping[str, Any]]:
        env = {**os.environ, "PYTHONPATH": ".:src"}
        if context.lease_epoch is not None:
            env.update(
                {
                    "CFB_PIPELINE_RUN_ID": context.pipeline_run_id,
                    "CFB_PIPELINE_LEASE_EPOCH": str(context.lease_epoch),
                }
            )
        completed = subprocess.run(list(argv), check=False, env=env)
        if completed.returncode != 0:
            raise subprocess.CalledProcessError(completed.returncode, list(argv))
        return ({"argv": list(argv), "returncode": completed.returncode},)

    return PipelineStep(name=name, action=action, definition={"argv": list(argv)})


def _step_definition_sha(step: PipelineStep) -> str:
    return hashlib.sha256(
        _json_dumps({"name": step.name, "definition": dict(step.definition)}).encode()
    ).hexdigest()


def _operation_definition(
    context: OperationContext, steps: Sequence[PipelineStep]
) -> dict[str, Any]:
    return {
        "command": context.command,
        "environment": context.environment,
        "season": context.season,
        "week": context.week,
        "as_of": context.as_of,
        "prediction_run_id": context.prediction_run_id,
        "steps": [
            {"name": step.name, "definition_sha": _step_definition_sha(step)}
            for step in steps
        ],
    }


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
