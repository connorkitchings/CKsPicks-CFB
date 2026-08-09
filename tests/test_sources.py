from datetime import datetime, timezone

import pytest

from cks_picks_cfb.data.sources import (
    FailureCategory,
    RetryPolicy,
    SourceError,
    SourceResponse,
    fetch_with_retry,
)


class FlakyAdapter:
    provider = "test"

    def __init__(self):
        self.calls = 0

    def fetch(self, entity, request):
        self.calls += 1
        if self.calls < 3:
            raise SourceError("later", FailureCategory.RATE_LIMIT, retryable=True)
        return SourceResponse(
            provider="test",
            entity=entity,
            records=({"id": 1},),
            request=request,
            captured_at=datetime.now(timezone.utc),
        )


def test_retry_is_bounded_and_eventually_succeeds():
    adapter = FlakyAdapter()
    delays = []
    result = fetch_with_retry(
        adapter,
        "games",
        {},
        policy=RetryPolicy(max_attempts=3, base_delay_seconds=0, jitter_seconds=0),
        sleep=delays.append,
    )
    assert result.records == ({"id": 1},)
    assert adapter.calls == 3
    assert len(delays) == 2


def test_partial_pagination_fails_closed():
    class Partial:
        provider = "test"

        def fetch(self, entity, request):
            return SourceResponse(
                provider="test",
                entity=entity,
                records=({"id": 1},),
                request=request,
                captured_at=datetime.now(timezone.utc),
                page_count=1,
                expected_page_count=2,
            )

    with pytest.raises(SourceError, match="Partial pagination"):
        fetch_with_retry(Partial(), "games", {})


def test_rate_limit_honors_retry_after_header():
    class RateLimited:
        provider = "test"

        def __init__(self):
            self.calls = 0

        def fetch(self, entity, request):
            self.calls += 1
            if self.calls == 1:
                error = RuntimeError("slow down")
                error.status = 429
                error.headers = {"Retry-After": "3"}
                raise error
            return SourceResponse(
                provider="test",
                entity=entity,
                records=({"id": 1},),
                request=request,
                captured_at=datetime.now(timezone.utc),
            )

    delays = []
    fetch_with_retry(
        RateLimited(),
        "games",
        {},
        policy=RetryPolicy(max_attempts=2),
        sleep=delays.append,
    )
    assert delays == [3.0]
