import json
import sys

import pytest

from scripts.research.capture_weather_pilot import coverage, instant, main


def test_only_prekickoff_forecasts_retrieved_at_cutoff_are_eligible():
    base = {
        "status": "captured",
        "forecast_hour": {
            "windSpeed": "0 mph",
            "probabilityOfPrecipitation": {"value": 0},
        },
        "kickoff": "2026-11-28T17:00:00Z",
        "retrieved_at": "2026-11-22T17:00:00Z",
        "issued_at": "2026-11-22T11:00:00Z",
    }
    rows = [
        base,
        {**base, "retrieved_at": "2026-11-22T17:00:01Z"},
        {**base, "issued_at": None},
        {**base, "issued_at": "2026-11-22T18:00:00Z"},
        {**base, "forecast_hour": {"windSpeed": "0 mph"}},
        {"status": "missing_forecast_hour"},
        {"status": "unknown_roof"},
    ]
    assert coverage(rows, instant("2026-11-22T17:00:00Z")) == {
        "captured": 5,
        "missing_forecast_hour": 1,
        "unknown_roof": 1,
        "usable_at_issuance": 1,
        "missing_weather_fields": 1,
        "retrieved_after_cutoff": 1,
        "missing_issue_time": 1,
        "invalid_forecast_timing": 1,
    }


def test_report_rejects_later_market_refresh(tmp_path, monkeypatch, capsys):
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps({"season": 2026, "week": 13, "games": []}))
    revision = tmp_path / "revision_manifest_w13_v2.json"
    revision.write_text(json.dumps({"season": 2026}))
    monkeypatch.setattr(sys, "argv", ["weather", "report", str(receipt), str(revision)])
    with pytest.raises(SystemExit, match="2"):
        main()
    assert "initial rollover revision" in capsys.readouterr().err
