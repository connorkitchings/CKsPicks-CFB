from datetime import date, datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from scripts.pipeline import generate_v5_weekly_bets

_PREFLIGHT_PATH = Path(__file__).parents[1] / "scripts/pipeline/preflight.py"
_SPEC = spec_from_file_location("preflight", _PREFLIGHT_PATH)
assert _SPEC and _SPEC.loader
_PREFLIGHT = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_PREFLIGHT)
_parse_as_of = _PREFLIGHT._parse_as_of


def test_parse_as_of_uses_end_of_day_for_date_cutoff():
    snapshot_date, cutoff = _parse_as_of("2026-08-14")

    assert snapshot_date == date(2026, 8, 14)
    assert cutoff == datetime(2026, 8, 14, 23, 59, 59, 999999, tzinfo=timezone.utc)


def test_parse_as_of_accepts_utc_timestamp_for_exact_cutoff():
    snapshot_date, cutoff = _parse_as_of("2026-08-14T13:15:00Z")

    assert snapshot_date == date(2026, 8, 14)
    assert cutoff == datetime(2026, 8, 14, 13, 15, tzinfo=timezone.utc)


def test_v5_preflight_requires_verified_forecast_before_cutoff(tmp_path, monkeypatch):
    config = tmp_path / "v5.yaml"
    config.write_text("v5_live_forecast:\n  schema_version: v5_weekly_serving_v1\n")
    monkeypatch.setattr(_PREFLIGHT, "get_storage", lambda: object())
    monkeypatch.setattr(
        generate_v5_weekly_bets,
        "verify_v5_source",
        lambda _spec, _storage: (
            {"identity": {"as_of": "2026-10-02T00:00:00Z"}},
            None,
            {},
        ),
    )
    failures = []
    _PREFLIGHT.check_model_bundle(config, "2026-10-01T00:00:00Z", failures)
    assert len(failures) == 1
    assert "forecast cutoff" in failures[0]


def test_v5_week_data_skips_v4_preseason_snapshot(tmp_path, monkeypatch):
    config = tmp_path / "v5.yaml"
    config.write_text("v5_live_forecast:\n  schema_version: v5_weekly_serving_v1\n")

    class Storage:
        def read_index(self, name, _filters):
            if name == "raw/teams":
                return [
                    {"school": "A", "classification": "fbs"},
                    {"school": "B", "classification": "fbs"},
                ]
            return [{"id": 101, "week": 5, "home_team": "A", "away_team": "B"}]

    monkeypatch.setattr(_PREFLIGHT, "get_storage", lambda: Storage())
    monkeypatch.setattr(
        _PREFLIGHT,
        "snapshot_is_complete",
        lambda *_: (_ for _ in ()).throw(AssertionError("V4 preseason check called")),
    )
    failures = []
    _PREFLIGHT.check_week_data(2026, 5, "2026-10-01T00:00:00Z", config, failures)
    assert failures == []
