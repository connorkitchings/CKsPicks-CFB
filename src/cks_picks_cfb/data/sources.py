"""Provider-neutral source adapter contracts and retry policy."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Callable, Mapping, Protocol, Sequence


class FailureCategory(StrEnum):
    RATE_LIMIT = "rate_limit"
    TRANSIENT = "transient"
    AUTHENTICATION = "authentication"
    CONTRACT = "contract"
    DATA_UNAVAILABLE = "data_unavailable"
    UNKNOWN = "unknown"


class SourceError(RuntimeError):
    def __init__(
        self,
        message: str,
        category: FailureCategory,
        *,
        retryable: bool,
        retry_after_seconds: float | None = None,
    ):
        super().__init__(message)
        self.category = category
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True)
class SourceRequest:
    """One reproducible provider request.

    ``parameters`` contains provider-facing query arguments.  The endpoint is
    recorded separately so two API methods with identical arguments cannot be
    mistaken for the same observation.
    """

    provider: str
    entity: str
    endpoint: str
    parameters: Mapping[str, Any]
    requested_at: datetime

    def manifest(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "entity": self.entity,
            "endpoint": self.endpoint,
            "parameters": dict(self.parameters),
            "requested_at": self.requested_at.astimezone(timezone.utc).isoformat(),
        }


@dataclass(frozen=True)
class SourceResponse:
    provider: str
    entity: str
    records: tuple[Any, ...]
    request: Mapping[str, Any]
    captured_at: datetime
    effective_at: datetime | None = None
    provider_api_version: str | None = None
    page_count: int = 1
    expected_page_count: int | None = None
    response_metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate_pagination(self) -> None:
        if self.expected_page_count is not None and (
            self.page_count != self.expected_page_count
        ):
            raise SourceError(
                f"Partial pagination: received {self.page_count}/"
                f"{self.expected_page_count} pages",
                FailureCategory.CONTRACT,
                retryable=False,
            )


class SourceAdapter(Protocol):
    provider: str

    def fetch(self, entity: str, request: Mapping[str, Any]) -> SourceResponse: ...


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 4
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 8.0
    jitter_seconds: float = 0.25

    def delay(self, attempt: int) -> float:
        exponential = min(
            self.max_delay_seconds, self.base_delay_seconds * (2 ** (attempt - 1))
        )
        return exponential + random.uniform(0, self.jitter_seconds)


def classify_source_exception(exc: Exception) -> SourceError:
    """Classify common HTTP/provider failures without binding to one SDK."""
    status = getattr(exc, "status", None) or getattr(exc, "status_code", None)
    if status == 429:
        headers = getattr(exc, "headers", None) or {}
        retry_after = headers.get("Retry-After") if hasattr(headers, "get") else None
        try:
            retry_after_seconds = (
                float(retry_after) if retry_after is not None else None
            )
        except (TypeError, ValueError):
            retry_after_seconds = None
        return SourceError(
            str(exc),
            FailureCategory.RATE_LIMIT,
            retryable=True,
            retry_after_seconds=retry_after_seconds,
        )
    if status in {401, 403}:
        return SourceError(str(exc), FailureCategory.AUTHENTICATION, retryable=False)
    if status is not None and 500 <= int(status) < 600:
        return SourceError(str(exc), FailureCategory.TRANSIENT, retryable=True)
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return SourceError(str(exc), FailureCategory.TRANSIENT, retryable=True)
    if isinstance(exc, (TypeError, ValueError, KeyError)):
        return SourceError(str(exc), FailureCategory.CONTRACT, retryable=False)
    return SourceError(str(exc), FailureCategory.UNKNOWN, retryable=False)


def fetch_with_retry(
    adapter: SourceAdapter,
    entity: str,
    request: Mapping[str, Any],
    *,
    policy: RetryPolicy | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> SourceResponse:
    """Fetch with bounded exponential backoff and fail-closed pagination checks."""
    policy = policy or RetryPolicy()
    if policy.max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    last_error: SourceError | None = None
    for attempt in range(1, policy.max_attempts + 1):
        original: Exception | None = None
        try:
            response = adapter.fetch(entity, request)
            response.validate_pagination()
            return response
        except SourceError as exc:
            error = exc
        except Exception as exc:
            original = exc
            error = classify_source_exception(exc)
        last_error = error
        if not error.retryable or attempt == policy.max_attempts:
            if original is not None and error.category == FailureCategory.UNKNOWN:
                raise original
            raise error
        sleep(
            error.retry_after_seconds
            if error.retry_after_seconds is not None
            else policy.delay(attempt)
        )
    assert last_error is not None
    raise last_error


def call_with_retry(
    operation: Callable[[], Any],
    *,
    policy: RetryPolicy | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    """Apply the source retry policy while legacy ingesters migrate to adapters."""
    policy = policy or RetryPolicy()
    for attempt in range(1, policy.max_attempts + 1):
        original: Exception | None = None
        try:
            return operation()
        except SourceError as exc:
            error = exc
        except Exception as exc:
            original = exc
            error = classify_source_exception(exc)
        if not error.retryable or attempt == policy.max_attempts:
            if original is not None and not error.retryable:
                raise original
            raise error
        sleep(
            error.retry_after_seconds
            if error.retry_after_seconds is not None
            else policy.delay(attempt)
        )
    raise AssertionError("unreachable")


class CFBDSourceAdapter:
    """CFBD implementation using injected entity fetchers.

    Existing ingesters can migrate one endpoint at a time by passing their normalized
    fetch/transform callable.  This keeps CFBD primary while the interface remains
    ready for a second provider.
    """

    provider = "cfbd"

    def __init__(
        self,
        fetchers: Mapping[str, Callable[[Mapping[str, Any]], Sequence[Any]]],
        *,
        api_version: str | None = None,
    ) -> None:
        self.fetchers = dict(fetchers)
        self.api_version = api_version

    def fetch(self, entity: str, request: Mapping[str, Any]) -> SourceResponse:
        if entity not in self.fetchers:
            raise SourceError(
                f"Unsupported CFBD entity: {entity}",
                FailureCategory.CONTRACT,
                retryable=False,
            )
        records = tuple(self.fetchers[entity](request))
        if not records:
            raise SourceError(
                f"CFBD returned no rows for {entity}",
                FailureCategory.DATA_UNAVAILABLE,
                retryable=False,
            )
        return SourceResponse(
            provider=self.provider,
            entity=entity,
            records=records,
            request=dict(request),
            captured_at=datetime.now(timezone.utc),
            provider_api_version=self.api_version,
            response_metadata={},
        )
