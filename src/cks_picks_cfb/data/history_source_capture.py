"""Capture-only, resumable non-play CFBD observations for successor R1."""

from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping

from omegaconf import OmegaConf

from cks_picks_cfb.data.catalog import (
    begin_or_resume_request_set,
    completed_request_capture_ids,
    finish_ingestion_run,
    next_source_request_attempt,
    record_source_request_attempt,
    register_source_capture,
    source_capture_by_id,
    source_request_sha,
)
from cks_picks_cfb.data.game_stats import GameStatsIngester
from cks_picks_cfb.data.games import GamesIngester
from cks_picks_cfb.data.lake import capture_provider_records, read_source_capture
from cks_picks_cfb.data.sources import RetryPolicy
from cks_picks_cfb.data.storage import StorageBackend
from cks_picks_cfb.data.teams import TeamsIngester
from cks_picks_cfb.data.venues import VenuesIngester

POLICY_PATH = Path("conf/ratings/history_source_capture_v2.yaml")
MANIFEST_VERSION = "source-capture-entity-set-v2"
INGESTERS = {
    "teams": TeamsIngester,
    "games": GamesIngester,
    "game_stats": GameStatsIngester,
    "venues": VenuesIngester,
}


class HistorySourceCaptureError(RuntimeError):
    """Raised when a non-play successor capture set cannot be completed."""


@dataclass(frozen=True)
class HistorySourceCapturePolicy:
    version: str
    provider: str
    max_concurrency: int
    sdk_request_timeout_seconds: int
    worker_timeout_seconds: int
    max_attempts: int
    retry: Mapping[str, float]

    @property
    def sha256(self) -> str:
        return hashlib.sha256(
            json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    @property
    def retry_policy(self) -> RetryPolicy:
        return RetryPolicy(
            max_attempts=self.max_attempts,
            base_delay_seconds=float(self.retry["base_delay_seconds"]),
            max_delay_seconds=float(self.retry["max_delay_seconds"]),
            jitter_seconds=float(self.retry.get("jitter_seconds", 0.0)),
        )


def load_history_source_capture_policy(
    path: Path = POLICY_PATH,
) -> HistorySourceCapturePolicy:
    raw = OmegaConf.to_container(OmegaConf.load(path), resolve=True)
    if not isinstance(raw, dict):
        raise ValueError("history source capture policy must be a mapping")
    policy = HistorySourceCapturePolicy(**raw)
    if policy.max_concurrency != 1 or policy.max_attempts < 1:
        raise ValueError("successor R1 source capture must be sequential and retryable")
    if policy.sdk_request_timeout_seconds <= 0 or policy.worker_timeout_seconds <= 0:
        raise ValueError("source capture timeouts must be positive")
    return policy


def _code_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _write_immutable(storage: StorageBackend, uri: str, payload: bytes) -> None:
    if storage.exists(uri):
        if storage.read_bytes(uri) != payload:
            raise FileExistsError(f"Immutable source capture manifest collision: {uri}")
        return
    storage.write_bytes(payload, uri)


def _terminate_process_group(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=5)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)


def run_isolated_source_worker(
    *, entity: str, season: int, request: Mapping[str, Any], policy: HistorySourceCapturePolicy
) -> dict[str, Any]:
    """Run one non-play request out of process without compatibility writes."""

    with tempfile.TemporaryDirectory(prefix="ckspicks-r1-source-") as temp_dir:
        root = Path(temp_dir)
        request_path = root / "request.json"
        result_path = root / "result.json"
        request_path.write_text(json.dumps(dict(request), sort_keys=True), encoding="utf-8")
        environment = {
            **os.environ,
            "PYTHONPATH": ".:src",
            "CFB_CFBD_REQUEST_TIMEOUT_SECONDS": str(policy.sdk_request_timeout_seconds),
            "CFB_SOURCE_MAX_ATTEMPTS": "1",
        }
        process = subprocess.Popen(
            [
                sys.executable,
                "scripts/data/history_source_capture_worker.py",
                "--entity",
                entity,
                "--year",
                str(season),
                "--request",
                str(request_path),
                "--result",
                str(result_path),
            ],
            cwd=Path.cwd(),
            env=environment,
            start_new_session=True,
        )
        try:
            process.wait(timeout=policy.worker_timeout_seconds)
        except BaseException:
            _terminate_process_group(process)
            raise
        if not result_path.exists():
            raise HistorySourceCaptureError(
                f"source worker exited {process.returncode} without an atomic result"
            )
        result = json.loads(result_path.read_text(encoding="utf-8"))
        if result.get("state") != "succeeded":
            error = HistorySourceCaptureError(str(result.get("error_detail", "worker failed")))
            setattr(error, "category", result.get("error_category", "worker_failed"))
            setattr(error, "retryable", bool(result.get("retryable", False)))
            raise error
        if process.returncode != 0:
            raise HistorySourceCaptureError("source worker failed after reporting success")
        return result


class HistorySourceCaptureSet:
    """Capture one non-play entity from exact requests without legacy writes."""

    def __init__(
        self,
        *,
        conn_url: str,
        storage: StorageBackend,
        pipeline_run_id: str,
        season: int,
        entity: str,
        manifest_uri: str,
        identity: Mapping[str, Any],
        policy: HistorySourceCapturePolicy | None = None,
        worker: Callable[..., dict[str, Any]] = run_isolated_source_worker,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if entity not in INGESTERS:
            raise ValueError(f"Unsupported successor R1 source entity: {entity}")
        self.conn_url = conn_url
        self.storage = storage
        self.pipeline_run_id = pipeline_run_id
        self.season = season
        self.entity = entity
        self.manifest_uri = manifest_uri
        self.identity = dict(identity)
        self.policy = policy or load_history_source_capture_policy()
        self.worker = worker
        self.sleep = sleep
        self.ingestion_run_id = f"{pipeline_run_id}:successor_history_{season}_{entity}"

    def _planned_requests(self) -> list[dict[str, Any]]:
        ingester = INGESTERS[self.entity](year=self.season, storage=self.storage)
        return [request.manifest() for request in ingester.source_requests()]

    def _completed(self) -> dict[str, str]:
        completed = completed_request_capture_ids(self.conn_url, self.ingestion_run_id)
        for request_sha, capture_id in completed.items():
            capture = read_source_capture(
                self.storage, source_capture_by_id(self.conn_url, capture_id)
            )
            if capture.empty:
                raise HistorySourceCaptureError(
                    f"completed {self.entity} capture {request_sha} has no records"
                )
        return completed

    def _attempt(self, request: Mapping[str, Any], request_sha: str) -> tuple[str, Mapping[str, Any]]:
        last_error: BaseException | None = None
        for _ in range(self.policy.retry_policy.max_attempts):
            attempt = next_source_request_attempt(
                self.conn_url, ingestion_run_id=self.ingestion_run_id, request_sha=request_sha
            )
            record_source_request_attempt(
                self.conn_url,
                ingestion_run_id=self.ingestion_run_id,
                request_sha=request_sha,
                attempt=attempt,
                state="running",
            )
            try:
                result = self.worker(
                    entity=self.entity, season=self.season, request=request, policy=self.policy
                )
                captured_at = datetime.fromisoformat(
                    str(result["captured_at"]).replace("Z", "+00:00")
                )
                capture = capture_provider_records(
                    self.storage,
                    provider=self.policy.provider,
                    entity=self.entity,
                    records=list(result["records"]),
                    captured_at=captured_at,
                    effective_at=None,
                    request=dict(request),
                    response_metadata={
                        "returned_game_ids": list(result.get("returned_game_ids", [])),
                        "capture_profile": self.policy.version,
                        "capture_only": True,
                    },
                )
                register_source_capture(
                    self.conn_url, capture, ingestion_run_id=self.ingestion_run_id
                )
                record_source_request_attempt(
                    self.conn_url,
                    ingestion_run_id=self.ingestion_run_id,
                    request_sha=request_sha,
                    attempt=attempt,
                    state="succeeded",
                    capture_id=capture.capture_id,
                )
                return capture.capture_id, result
            except BaseException as exc:
                last_error = exc
                record_source_request_attempt(
                    self.conn_url,
                    ingestion_run_id=self.ingestion_run_id,
                    request_sha=request_sha,
                    attempt=attempt,
                    state="failed",
                    error=exc if isinstance(exc, Exception) else RuntimeError(type(exc).__name__),
                )
                if not bool(getattr(exc, "retryable", True)) or attempt >= self.policy.max_attempts:
                    break
                self.sleep(self.policy.retry_policy.delay(attempt))
        assert last_error is not None
        raise HistorySourceCaptureError(
            f"{self.entity} request {request_sha} exhausted {self.policy.max_attempts} attempts: {last_error}"
        ) from last_error

    def run(self) -> dict[str, Any]:
        requests = self._planned_requests()
        stored = begin_or_resume_request_set(
            self.conn_url,
            ingestion_run_id=self.ingestion_run_id,
            provider=self.policy.provider,
            entity=f"successor_history_{self.season}_{self.entity}",
            requests=requests,
            policy={"version": self.policy.version, "sha256": self.policy.sha256},
            contract_version="source_capture_set_v2",
            identity=self.identity,
        )
        try:
            completed = self._completed()
            if self.storage.exists(self.manifest_uri):
                existing = json.loads(self.storage.read_bytes(self.manifest_uri).decode())
                expected = [source_request_sha(request) for request in stored]
                if (
                    existing.get("contract_version") == MANIFEST_VERSION
                    and existing.get("state") == "complete"
                    and existing.get("identity") == self.identity
                    and [entry.get("request_sha") for entry in existing.get("requests", [])] == expected
                    and [entry.get("capture_id") for entry in existing.get("requests", [])]
                    == [completed.get(value) for value in expected]
                ):
                    return existing
                raise HistorySourceCaptureError("existing source capture manifest conflicts with request set")
            entries = []
            for request in stored:
                request_sha = source_request_sha(request)
                capture_id = completed.get(request_sha)
                result: Mapping[str, Any] = {}
                if capture_id is None:
                    capture_id, result = self._attempt(request, request_sha)
                    completed[request_sha] = capture_id
                capture = source_capture_by_id(self.conn_url, capture_id)
                entries.append(
                    {
                        "request_sha": request_sha,
                        "request": dict(request),
                        "capture_id": capture_id,
                        "content_sha256": capture.content_sha,
                        "object_sha256": capture.object_sha,
                        "row_count": capture.row_count,
                        "returned_game_ids": dict(capture.response_metadata).get(
                            "returned_game_ids", result.get("returned_game_ids", [])
                        ),
                    }
                )
            if len(completed) != len(stored):
                raise HistorySourceCaptureError("source capture set is incomplete")
            payload: dict[str, Any] = {
                "contract_version": MANIFEST_VERSION,
                "state": "complete",
                "pipeline_run_id": self.pipeline_run_id,
                "ingestion_run_id": self.ingestion_run_id,
                "season": self.season,
                "entity": self.entity,
                "policy_version": self.policy.version,
                "policy_sha256": self.policy.sha256,
                "code_sha": _code_sha(),
                "identity": self.identity,
                "capture_only": True,
                "requests": entries,
            }
            payload["manifest_sha256"] = hashlib.sha256(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            _write_immutable(
                self.storage,
                self.manifest_uri,
                json.dumps(payload, indent=2, sort_keys=True).encode(),
            )
            finish_ingestion_run(self.conn_url, self.ingestion_run_id, succeeded=True)
            return payload
        except BaseException as exc:
            finish_ingestion_run(
                self.conn_url,
                self.ingestion_run_id,
                succeeded=False,
                error_category=type(exc).__name__,
                error_detail=str(exc),
            )
            raise
