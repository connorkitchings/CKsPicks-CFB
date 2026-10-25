"""Guards the root `.env.example`: only required placeholders may be active.

Copying the example to `.env` must not override code defaults, so every optional
setting stays commented out and the defaults are checked against the real readers.
No network, no `.env` file and no credential values are read.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# Imported at module load, before any fixture clears the environment: several of
# these modules call dotenv.load_dotenv() on import, which would otherwise read
# the developer's real .env and reintroduce values the test must not see.
import cks_picks_cfb.artifacts as artifacts
import cks_picks_cfb.data.base as base
import cks_picks_cfb.data.catalog as catalog
import cks_picks_cfb.data.sources as sources
from cks_picks_cfb.data.base import BaseIngester
from cks_picks_cfb.data.storage.base import StorageSettings
from cks_picks_cfb.ops.__main__ import _source_subprocess_timeout_seconds
from cks_picks_cfb.ops.notifier import WebhookFailureNotifier

ENV_EXAMPLE = Path(__file__).resolve().parents[1] / ".env.example"

ASSIGNMENT = re.compile(r"^([A-Z][A-Z0-9_]*)=(.*)$")
COMMENTED_ASSIGNMENT = re.compile(r"^#\s*([A-Z][A-Z0-9_]*)=(.*)$")

REQUIRED_ACTIVE = {
    "CFBD_API_KEY",
    "DATABASE_URL",
    "PREVIEW_DATABASE_URL",
    "CFB_MODEL_DATA_ROOT",
    "CFB_R2_BUCKET",
    "CFB_R2_ACCOUNT_ID",
    "CFB_R2_ACCESS_KEY",
    "CFB_R2_SECRET_KEY",
    "CFB_R2_ENDPOINT",
    "CFB_R2_PREVIEW_BUCKET",
    "CFB_R2_PREVIEW_ACCOUNT_ID",
    "CFB_R2_PREVIEW_ACCESS_KEY",
    "CFB_R2_PREVIEW_SECRET_KEY",
    "CFB_R2_PREVIEW_ENDPOINT",
}

# Optional settings with code defaults: each must be commented out in the example.
OPTIONAL_NAMED = {
    "CFB_STORAGE_BACKEND",
    "CFB_ARTIFACT_ENV",
    "CFB_ODDS_API_ENABLED",
    "CFB_CFBD_MAX_CONCURRENCY",
    "CFB_CFBD_REQUEST_TIMEOUT_SECONDS",
    "CFB_SOURCE_MAX_ATTEMPTS",
    "CFB_SOURCE_RETRY_BASE_SECONDS",
    "CFB_SOURCE_RETRY_MAX_SECONDS",
    "CFB_SOURCE_SUBPROCESS_TIMEOUT_SECONDS",
    "CFB_REQUIRE_CATALOG",
    "CFB_LAKE_DUAL_WRITE",
    "CFB_OPS_ALERT_TIMEOUT_SECONDS",
    "CFB_MATCHUP_ENABLED",
    "CFB_DATA_CACHE",
    "CFB_DISPLAY_ONLY_NOTICE",
    "CFB_QUERY_LOG",
    "CFB_UI_TEST_MODE",
    "CFB_CHART_VISUALS",
    "PLAYWRIGHT_PORT",
}

# Code defaults when the variable is unset.
DEFAULT_CFB_CFBD_MAX_CONCURRENCY = 2
DEFAULT_REQUEST_TIMEOUT_SECONDS = 60.0
DEFAULT_SUBPROCESS_TIMEOUT_SECONDS = 600.0
DEFAULT_OPS_ALERT_TIMEOUT_SECONDS = 5.0


class _Stop(BaseException):
    """Raised by stubs to halt ingestion after the value under test is captured."""


class _FakeStorage:
    def __init__(self, description: str):
        self._description = description

    def describe(self) -> str:
        return self._description


def _parse_env_example() -> tuple[dict[str, str], list[str], set[str]]:
    """Return (active assignments, active keys in file order, commented keys)."""
    active: dict[str, str] = {}
    active_order: list[str] = []
    commented: set[str] = set()
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            match = COMMENTED_ASSIGNMENT.match(line)
            if match:
                commented.add(match.group(1))
            continue
        match = ASSIGNMENT.match(line)
        if match:
            active[match.group(1)] = match.group(2)
            active_order.append(match.group(1))
    return active, active_order, commented


def _dummy_value(key: str, tmp_path: Path) -> str:
    if key == "CFB_MODEL_DATA_ROOT":
        return str(tmp_path)
    return f"dummy-{key.lower()}"


@pytest.fixture
def example_env(monkeypatch, tmp_path):
    """Replace the environment with the example's active assignments only.

    Every key the example mentions is cleared first, so values leaked from the
    developer shell or a dotenv loaded at import time cannot change a default.
    Required placeholders receive dummy values; nothing is read from disk.
    """
    active, _, commented = _parse_env_example()
    for key in set(active) | commented:
        monkeypatch.delenv(key, raising=False)
    for key, value in active.items():
        monkeypatch.setenv(key, value or _dummy_value(key, tmp_path))
    return active


def test_active_assignments_are_only_required_placeholders():
    active, _, _ = _parse_env_example()

    assert set(active) == REQUIRED_ACTIVE


def test_optional_settings_are_commented_out_not_assigned():
    active, _, commented = _parse_env_example()

    assert OPTIONAL_NAMED <= commented
    assert not (OPTIONAL_NAMED & set(active))


def test_every_documented_variable_is_either_required_or_commented():
    active, active_order, commented = _parse_env_example()

    assert len(active_order) == len(set(active_order))
    assert commented.isdisjoint(active)
    assert commented | set(active) >= OPTIONAL_NAMED | REQUIRED_ACTIVE


def test_storage_settings_default_to_local_production(example_env, tmp_path):
    settings = StorageSettings.from_env()

    assert settings.backend == "local"
    assert settings.environment == "production"
    assert settings.data_root == str(tmp_path)


def test_artifact_environment_defaults_to_production(example_env):
    assert artifacts._artifact_environment() == "production"


def test_ops_alert_webhook_stays_disabled_by_default(example_env):
    assert WebhookFailureNotifier.from_env() is None


def test_ops_alert_timeout_defaults_to_five_seconds_when_webhook_set(
    example_env, monkeypatch
):
    monkeypatch.setenv("CFB_OPS_ALERT_WEBHOOK_URL", "https://example.invalid/hook")

    notifier = WebhookFailureNotifier.from_env()

    assert notifier is not None
    assert notifier.timeout_seconds == DEFAULT_OPS_ALERT_TIMEOUT_SECONDS


def test_source_subprocess_timeout_defaults_to_600_seconds(example_env):
    assert _source_subprocess_timeout_seconds() == DEFAULT_SUBPROCESS_TIMEOUT_SECONDS


def test_cfbd_request_timeout_defaults_to_60_seconds(example_env):
    assert BaseIngester.request_timeout_seconds.fget(None) == (
        DEFAULT_REQUEST_TIMEOUT_SECONDS
    )


def _ingester(storage_description: str):
    class _StubIngester(BaseIngester):
        @property
        def entity_name(self) -> str:
            return "raw/games"

        def fetch_data(self):
            return []

        def transform_data(self, data):
            return []

    return _StubIngester(storage=_FakeStorage(storage_description))


def _dual_write_enabled(storage_description: str, monkeypatch) -> bool:
    """Run ingestion up to the dual-write decision and report whether it fired."""
    begin_calls: list[dict] = []

    def record_begin(*args, **kwargs):
        begin_calls.append(kwargs)
        raise _Stop

    monkeypatch.setattr(catalog, "begin_ingestion_run", record_begin)
    ingester = _ingester(storage_description)

    def stop_fetch(requests=None):
        raise _Stop

    monkeypatch.setattr(ingester, "fetch_source_responses", stop_fetch)
    with pytest.raises(_Stop):
        ingester.run()
    return bool(begin_calls)


def test_lake_dual_write_defaults_on_for_r2(example_env, monkeypatch):
    assert _dual_write_enabled("r2:bucket", monkeypatch) is True


def test_lake_dual_write_defaults_off_for_local(example_env, monkeypatch):
    assert _dual_write_enabled("local:/tmp/data", monkeypatch) is False


def test_source_retry_policy_defaults(example_env, monkeypatch):
    captured: dict[str, float] = {}

    class _RecordRetryPolicy:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            raise _Stop

    monkeypatch.setattr(sources, "RetryPolicy", _RecordRetryPolicy)
    with pytest.raises(_Stop):
        _ingester("local:/tmp/data").fetch_source_responses(requests=[])

    assert captured == {
        "max_attempts": 4,
        "base_delay_seconds": 0.5,
        "max_delay_seconds": 8.0,
    }


def test_cfbd_max_concurrency_defaults_to_two(example_env, monkeypatch):
    captured: dict[str, int] = {}

    class _RecordExecutor:
        def __init__(self, max_workers):
            captured["max_workers"] = max_workers
            raise _Stop

    monkeypatch.setattr(base, "ThreadPoolExecutor", _RecordExecutor)
    with pytest.raises(_Stop):
        _ingester("local:/tmp/data").fetch_source_responses(
            requests=[object(), object(), object()]
        )

    assert captured == {"max_workers": DEFAULT_CFB_CFBD_MAX_CONCURRENCY}
