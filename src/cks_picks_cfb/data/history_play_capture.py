"""Preview-only, resumable weekly Bronze capture for successor R1 plays."""

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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

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
from cks_picks_cfb.data.lake import capture_provider_records, read_source_capture
from cks_picks_cfb.data.plays import PlaysIngester
from cks_picks_cfb.data.sources import RetryPolicy, SourceRequest
from cks_picks_cfb.data.storage import StorageBackend

POLICY_PATH = Path("conf/ratings/history_play_capture_v2.yaml")
MANIFEST_VERSION = "play-capture-set-v1"


class HistoryPlayCaptureError(RuntimeError):
    """A complete, manifest-backed historical play capture could not be made."""


@dataclass(frozen=True)
class HistoryPlayCapturePolicy:
    version: str
    provider: str
    entity: str
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


def load_history_play_capture_policy(
    path: Path = POLICY_PATH,
) -> HistoryPlayCapturePolicy:
    raw = OmegaConf.to_container(OmegaConf.load(path), resolve=True)
    if not isinstance(raw, dict):
        raise ValueError("history play capture policy must be a mapping")
    policy = HistoryPlayCapturePolicy(**raw)
    if policy.max_concurrency != 1:
        raise ValueError("successor R1 play capture must remain sequential")
    if policy.sdk_request_timeout_seconds <= 0 or policy.worker_timeout_seconds <= 0:
        raise ValueError("history play capture timeouts must be positive")
    if policy.max_attempts < 1:
        raise ValueError("history play capture requires at least one attempt")
    return policy


def _code_sha() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return completed.stdout.strip() if completed.returncode == 0 else "unknown"


def _manifest_payload(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, indent=2, sort_keys=True).encode("utf-8")


def _immutable_write(storage: StorageBackend, uri: str, payload: bytes) -> None:
    if storage.exists(uri):
        if storage.read_bytes(uri) != payload:
            raise FileExistsError(f"Immutable play capture manifest collision: {uri}")
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


def run_isolated_play_worker(
    request: Mapping[str, Any],
    *,
    policy: HistoryPlayCapturePolicy,
) -> dict[str, Any]:
    """Run one provider week outside the repo and return its atomic result."""

    with tempfile.TemporaryDirectory(prefix="ckspicks-r1-play-") as temp_dir:
        root = Path(temp_dir)
        request_path = root / "request.json"
        result_path = root / "result.json"
        request_path.write_text(json.dumps(dict(request), sort_keys=True), encoding="utf-8")
        env = {
            **os.environ,
            "PYTHONPATH": ".:src",
            "CFB_CFBD_REQUEST_TIMEOUT_SECONDS": str(policy.sdk_request_timeout_seconds),
            "CFB_SOURCE_MAX_ATTEMPTS": "1",
        }
        process = subprocess.Popen(
            [
                sys.executable,
                "scripts/data/history_play_capture_worker.py",
                "--request",
                str(request_path),
                "--result",
                str(result_path),
            ],
            cwd=Path.cwd(),
            env=env,
            start_new_session=True,
        )
        try:
            process.wait(timeout=policy.worker_timeout_seconds)
        except BaseException:
            _terminate_process_group(process)
            raise
        if not result_path.exists():
            raise HistoryPlayCaptureError(
                f"play worker exited {process.returncode} without an atomic result"
            )
        result = json.loads(result_path.read_text(encoding="utf-8"))
        if result.get("state") != "succeeded":
            detail = str(result.get("error_detail", "worker failed"))
            error = HistoryPlayCaptureError(detail)
            setattr(error, "category", result.get("error_category", "worker_failed"))
            setattr(error, "retryable", bool(result.get("retryable", False)))
            raise error
        if process.returncode != 0:
            raise HistoryPlayCaptureError("play worker failed after reporting success")
        return result


class HistoryPlayCaptureSet:
    """Create, resume, verify, and close one season's ordered play capture set."""

    def __init__(
        self,
        *,
        conn_url: str,
        storage: StorageBackend,
        pipeline_run_id: str,
        season: int,
        manifest_uri: str,
        identity: Mapping[str, Any] | None = None,
        games_manifest_uri: str | None = None,
        write_compatibility_projection: bool = False,
        policy: HistoryPlayCapturePolicy | None = None,
        worker: Callable[..., dict[str, Any]] = run_isolated_play_worker,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.conn_url = conn_url
        self.storage = storage
        self.pipeline_run_id = pipeline_run_id
        self.season = season
        self.manifest_uri = manifest_uri
        self.identity = dict(identity or {})
        self.games_manifest_uri = games_manifest_uri
        self.write_compatibility_projection = write_compatibility_projection
        self.policy = policy or load_history_play_capture_policy()
        self.worker = worker
        self.sleep = sleep
        self.ingestion_run_id = f"{pipeline_run_id}:successor_history_{season}_plays"

    def _games_records_from_manifest(self) -> list[dict[str, Any]]:
        """Read the exact same-run game set without consulting ``raw/games``."""

        if not self.games_manifest_uri:
            raise HistoryPlayCaptureError(
                "successor play capture requires an exact games capture manifest"
            )
        raw = json.loads(self.storage.read_bytes(self.games_manifest_uri).decode())
        if (
            raw.get("contract_version") != "source-capture-entity-set-v2"
            or raw.get("state") != "complete"
            or int(raw.get("season", -1)) != self.season
            or raw.get("entity") != "games"
        ):
            raise HistoryPlayCaptureError(
                "successor play capture games manifest is incomplete or mismatched"
            )
        records: list[dict[str, Any]] = []
        for entry in raw.get("requests", []):
            capture = source_capture_by_id(self.conn_url, str(entry["capture_id"]))
            records.extend(read_source_capture(self.storage, capture).to_dict("records"))
        if not records:
            raise HistoryPlayCaptureError("successor play capture games manifest is empty")
        return records

    def _planned_requests(self) -> list[dict[str, Any]]:
        """Plan CFBD weeks from the exact captured FBS games for this R1 run."""

        games_by_week: dict[int, set[int]] = {}
        for game in self._games_records_from_manifest():
            season_type = str(
                game.get("season_type", game.get("seasonType", "regular"))
            ).lower()
            game_id = game.get("game_id", game.get("id"))
            week = game.get("week")
            if season_type != "regular" or game_id is None or week is None:
                continue
            games_by_week.setdefault(int(week), set()).add(int(game_id))
        if not games_by_week:
            raise HistoryPlayCaptureError(
                "successor play capture found no regular-season games"
            )
        ingester = PlaysIngester(year=self.season, storage=self.storage)
        requested_at = datetime.now(timezone.utc)
        return [
            SourceRequest(
                provider=self.policy.provider,
                entity="plays",
                endpoint=ingester.source_endpoint,
                parameters={
                    "year": self.season,
                    "season_type": "regular",
                    "week": week,
                    "classification": "fbs",
                    "expected_game_ids": sorted(game_ids),
                },
                requested_at=requested_at,
            ).manifest()
            for week, game_ids in sorted(games_by_week.items())
        ]

    def _completed(self) -> dict[str, str]:
        capture_ids = completed_request_capture_ids(self.conn_url, self.ingestion_run_id)
        for request_sha, capture_id in capture_ids.items():
            capture = source_capture_by_id(self.conn_url, capture_id)
            if capture.state != "registered" or source_request_sha(capture.request) != request_sha:
                raise HistoryPlayCaptureError("completed capture is not verified")
            read_source_capture(self.storage, capture)
        return capture_ids

    def _attempt(self, request: Mapping[str, Any], request_sha: str) -> tuple[str, dict[str, Any]]:
        policy = self.policy.retry_policy
        last_error: BaseException | None = None
        for _ in range(policy.max_attempts):
            attempt = next_source_request_attempt(
                self.conn_url,
                ingestion_run_id=self.ingestion_run_id,
                request_sha=request_sha,
            )
            record_source_request_attempt(
                self.conn_url,
                ingestion_run_id=self.ingestion_run_id,
                request_sha=request_sha,
                attempt=attempt,
                state="running",
            )
            try:
                result = self.worker(request, policy=self.policy)
                if result.get("extra_game_ids"):
                    raise HistoryPlayCaptureError("worker returned unexpected game IDs")
                captured_at = datetime.fromisoformat(
                    str(result["captured_at"]).replace("Z", "+00:00")
                )
                capture = capture_provider_records(
                    self.storage,
                    provider=self.policy.provider,
                    entity=self.policy.entity,
                    records=list(result["records"]),
                    captured_at=captured_at,
                    effective_at=None,
                    request=dict(request),
                    response_metadata={
                        "returned_game_ids": list(result["returned_game_ids"]),
                        "missing_game_ids": list(result["missing_game_ids"]),
                        "extra_game_ids": list(result["extra_game_ids"]),
                        "capture_profile": self.policy.version,
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
                if not bool(getattr(exc, "retryable", True)) or attempt >= policy.max_attempts:
                    break
                self.sleep(policy.delay(attempt))
        assert last_error is not None
        raise HistoryPlayCaptureError(
            f"weekly play request {request_sha} exhausted {policy.max_attempts} attempts: {last_error}"
        ) from last_error

    def _rebuild_projection(self, capture_ids: Sequence[str]) -> None:
        ingester = PlaysIngester(year=self.season, storage=self.storage)
        records: list[dict[str, Any]] = []
        for capture_id in capture_ids:
            capture = source_capture_by_id(self.conn_url, capture_id)
            records.extend(read_source_capture(self.storage, capture).to_dict("records"))
        if not records:
            raise HistoryPlayCaptureError("complete play capture set has no records")
        ingester.ingest_data(records)

    def run(self) -> dict[str, Any]:
        requests = self._planned_requests()
        stored_requests = begin_or_resume_request_set(
            self.conn_url,
            ingestion_run_id=self.ingestion_run_id,
            provider=self.policy.provider,
            entity=f"successor_history_{self.season}_plays",
            requests=requests,
            policy={"version": self.policy.version, "sha256": self.policy.sha256},
            contract_version="play_capture_set_v2",
            identity=self.identity,
        )
        try:
            completed = self._completed()
            if self.storage.exists(self.manifest_uri):
                existing = json.loads(
                    self.storage.read_bytes(self.manifest_uri).decode("utf-8")
                )
                expected_request_shas = [
                    source_request_sha(request) for request in stored_requests
                ]
                existing_entries = existing.get("requests", [])
                if (
                    existing.get("contract_version") == "play-capture-set-v2"
                    and existing.get("state") == "complete"
                    and existing.get("identity") == self.identity
                    and [entry.get("request_sha") for entry in existing_entries]
                    == expected_request_shas
                    and [entry.get("capture_id") for entry in existing_entries]
                    == [completed.get(request_sha) for request_sha in expected_request_shas]
                ):
                    return existing
                raise HistoryPlayCaptureError(
                    "existing play capture manifest conflicts with verified request set"
                )
            entries: list[dict[str, Any]] = []
            for request in stored_requests:
                request_sha = source_request_sha(request)
                capture_id = completed.get(request_sha)
                result: Mapping[str, Any] = {}
                if capture_id is None:
                    capture_id, result = self._attempt(request, request_sha)
                    completed[request_sha] = capture_id
                capture = source_capture_by_id(self.conn_url, capture_id)
                metadata = dict(capture.response_metadata)
                entries.append(
                    {
                        "request_sha": request_sha,
                        "request": dict(request),
                        "capture_id": capture_id,
                        "content_sha256": capture.content_sha,
                        "object_sha256": capture.object_sha,
                        "row_count": capture.row_count,
                        "returned_game_ids": metadata.get("returned_game_ids", result.get("returned_game_ids", [])),
                        "missing_game_ids": metadata.get("missing_game_ids", result.get("missing_game_ids", [])),
                        "extra_game_ids": metadata.get("extra_game_ids", result.get("extra_game_ids", [])),
                    }
                )
            if len(completed) != len(stored_requests):
                raise HistoryPlayCaptureError("capture set is incomplete")
            capture_ids = [entry["capture_id"] for entry in entries]
            if self.write_compatibility_projection:
                self._rebuild_projection(capture_ids)
            payload: dict[str, Any] = {
                "contract_version": "play-capture-set-v2",
                "state": "complete",
                "pipeline_run_id": self.pipeline_run_id,
                "ingestion_run_id": self.ingestion_run_id,
                "season": self.season,
                "policy_version": self.policy.version,
                "policy_sha256": self.policy.sha256,
                "code_sha": _code_sha(),
                "identity": self.identity,
                "games_capture_manifest_uri": self.games_manifest_uri,
                "compatibility_projection_written": self.write_compatibility_projection,
                "requests": entries,
            }
            payload["manifest_sha256"] = hashlib.sha256(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            _immutable_write(self.storage, self.manifest_uri, _manifest_payload(payload))
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


def manifest_capture_ids(storage: StorageBackend, uri: str) -> list[str]:
    """Return the ordered, verified capture IDs from a complete R1 manifest."""

    raw = json.loads(storage.read_bytes(uri).decode("utf-8"))
    if raw.get("contract_version") not in {MANIFEST_VERSION, "play-capture-set-v2"} or raw.get("state") != "complete":
        raise HistoryPlayCaptureError("play capture manifest is not complete")
    entries = raw.get("requests")
    if not isinstance(entries, list) or not entries:
        raise HistoryPlayCaptureError("play capture manifest has no request entries")
    capture_ids = [str(entry.get("capture_id", "")) for entry in entries]
    if not all(capture_ids) or len(set(capture_ids)) != len(capture_ids):
        raise HistoryPlayCaptureError("play capture manifest has invalid capture IDs")
    return capture_ids


def manifest_declared_missing_game_ids(
    storage: StorageBackend, uri: str, *, season: int
) -> set[int]:
    """Return exact provider-declared omissions from one completed R1 play manifest."""

    raw = json.loads(storage.read_bytes(uri).decode("utf-8"))
    try:
        manifest_season = int(raw.get("season", -1))
    except (TypeError, ValueError) as exc:
        raise HistoryPlayCaptureError(
            "play capture manifest is incomplete or mismatched"
        ) from exc
    if (
        raw.get("contract_version") != "play-capture-set-v2"
        or raw.get("state") != "complete"
        or manifest_season != season
    ):
        raise HistoryPlayCaptureError("play capture manifest is incomplete or mismatched")
    entries = raw.get("requests")
    if not isinstance(entries, list) or not entries:
        raise HistoryPlayCaptureError("play capture manifest has no request entries")

    def game_ids(value: Any, *, label: str) -> set[int]:
        if not isinstance(value, list):
            raise HistoryPlayCaptureError(f"play capture manifest {label} is invalid")
        parsed: list[int] = []
        for item in value:
            if isinstance(item, bool):
                raise HistoryPlayCaptureError(
                    f"play capture manifest {label} has an invalid game ID"
                )
            try:
                parsed.append(int(item))
            except (TypeError, ValueError) as exc:
                raise HistoryPlayCaptureError(
                    f"play capture manifest {label} has an invalid game ID"
                ) from exc
        if len(parsed) != len(set(parsed)):
            raise HistoryPlayCaptureError(f"play capture manifest {label} has duplicates")
        return set(parsed)

    capture_ids: set[str] = set()
    expected_all: set[int] = set()
    missing_all: set[int] = set()
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise HistoryPlayCaptureError("play capture manifest request entry is invalid")
        capture_id = str(entry.get("capture_id", ""))
        if not capture_id or capture_id in capture_ids:
            raise HistoryPlayCaptureError("play capture manifest has invalid capture IDs")
        capture_ids.add(capture_id)
        request = entry.get("request")
        if not isinstance(request, Mapping) or not isinstance(
            request.get("parameters"), Mapping
        ):
            raise HistoryPlayCaptureError("play capture manifest request is invalid")
        parameters = request["parameters"]
        try:
            request_season = int(parameters.get("year", -1))
        except (TypeError, ValueError) as exc:
            raise HistoryPlayCaptureError(
                "play capture manifest request season mismatches"
            ) from exc
        if request_season != season:
            raise HistoryPlayCaptureError("play capture manifest request season mismatches")
        expected = game_ids(
            parameters.get("expected_game_ids"), label="expected_game_ids"
        )
        if expected_all & expected:
            raise HistoryPlayCaptureError("play capture manifest repeats expected game IDs")
        expected_all |= expected
        returned = game_ids(entry.get("returned_game_ids"), label="returned_game_ids")
        missing = game_ids(entry.get("missing_game_ids"), label="missing_game_ids")
        extra = game_ids(entry.get("extra_game_ids"), label="extra_game_ids")
        if extra:
            raise HistoryPlayCaptureError("play capture manifest records extra game IDs")
        if returned & missing or returned | missing != expected:
            raise HistoryPlayCaptureError("play capture manifest request coverage mismatches")
        missing_all |= missing
    return missing_all
