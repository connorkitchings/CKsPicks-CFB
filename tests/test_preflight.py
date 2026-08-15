from datetime import date, datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

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
