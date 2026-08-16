import pytest

from cks_picks_cfb.data.runtime import resolve_runtime_target


def test_preview_never_falls_back_to_production(monkeypatch):
    monkeypatch.delenv("PREVIEW_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://production")
    with pytest.raises(RuntimeError, match="PREVIEW_DATABASE_URL"):
        resolve_runtime_target("preview")


def test_preview_must_be_distinct_from_production(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://same")
    monkeypatch.setenv("PREVIEW_DATABASE_URL", "postgresql://same")
    with pytest.raises(RuntimeError, match="must differ"):
        resolve_runtime_target("preview")
