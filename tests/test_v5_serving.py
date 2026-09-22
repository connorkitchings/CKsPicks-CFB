"""A verified live V5 forecast can be served without weakening timing gates."""

from __future__ import annotations

import argparse
import hashlib
import json

import pandas as pd
import pytest
from omegaconf import OmegaConf

from cks_picks_cfb.inference.v5_serving import V5ServingError, build_v5_serving_rows
from scripts.pipeline import generate_v5_weekly_bets as serving_script


def _forecast() -> pd.DataFrame:
    rows = []
    for game_id, margin, total in ((101, 7.0, 51.0), (102, -3.0, 45.0)):
        for target, mean, variance in (
            ("margin", margin, 16.0),
            ("total", total, 25.0),
        ):
            rows.append(
                {
                    "run_id": "v5-test",
                    "season": 2026,
                    "week": 5,
                    "game_id": game_id,
                    "target": target,
                    "mean": mean,
                    "variance": variance,
                    "interval_lower_95": mean - 1.96 * variance**0.5,
                    "interval_upper_95": mean + 1.96 * variance**0.5,
                    "offset": 0.0,
                    "completed_game_stage": 4,
                    "timing_class": "live",
                    "model_ref": "frozen-11c",
                    "state_ref": "verified-08",
                    "source_ref": "verified-07",
                }
            )
    return pd.DataFrame(rows)


def _schedule() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "season": [2026, 2026],
            "week": [5, 5],
            "game_id": [101, 102],
            "home_team": ["Home A", "Home B"],
            "away_team": ["Away A", "Away B"],
            "start_date": ["2026-10-02T23:00:00Z", "2026-10-03T20:00:00Z"],
        }
    )


def _run(
    forecast: pd.DataFrame | None = None,
    schedule: pd.DataFrame | None = None,
    forecast_schedule: pd.DataFrame | None = None,
    markets: pd.DataFrame | None = None,
):
    default_markets = pd.DataFrame(
        {
            "game_id": [101, 102],
            "spread_line": [-3.0, 4.0],
            "total": [48.0, 49.0],
            "market_captured_at": ["2026-10-01T12:00:00Z"] * 2,
        }
    )
    return build_v5_serving_rows(
        _forecast() if forecast is None else forecast,
        _schedule() if schedule is None else schedule,
        _schedule().rename(columns={"start_date": "kickoff_utc"})
        if forecast_schedule is None
        else forecast_schedule,
        default_markets if markets is None else markets,
        forecast_run_id="v5-test",
        forecast_manifest_sha256="a" * 64,
        year=2026,
        week=5,
        as_of="2026-10-01T13:00:00Z",
        run_id="2026w5-preview",
        spread_threshold=0.0,
        spread_threshold_high=8.0,
        total_threshold=1.5,
    )


def test_v5_serving_preserves_home_margin_sign_and_uncertainty():
    rows = _run().set_index("game_id")
    assert rows.loc[101, "Spread Prediction"] == 7.0
    assert rows.loc[101, "Spread Bet"] == "Home"
    assert rows.loc[101, "predicted_spread_std_dev"] == 4.0
    assert rows.loc[102, "Spread Prediction"] == -3.0
    assert rows.loc[102, "Spread Bet"] == "Home"
    assert rows.loc[102, "predicted_total_std_dev"] == 5.0
    assert rows["high_confidence_eligible"].eq(False).all()


def test_v5_serving_requires_complete_schedule_pair():
    forecast = _forecast().drop(index=0)
    with pytest.raises(V5ServingError, match="coverage mismatch"):
        _run(forecast=forecast)


def test_v5_serving_rejects_kickoff_at_cutoff():
    schedule = _schedule()
    schedule.loc[0, "start_date"] = "2026-10-01T13:00:00Z"
    with pytest.raises(V5ServingError, match="at or before cutoff"):
        _run(schedule=schedule)


def test_v5_serving_rejects_schedule_drift():
    source = _schedule().rename(columns={"start_date": "kickoff_utc"})
    source.loc[0, "home_team"] = "Changed team"
    with pytest.raises(V5ServingError, match="differs from forecast parent"):
        _run(forecast_schedule=source)


def test_v5_serving_rejects_late_market_capture():
    market = pd.DataFrame(
        {
            "game_id": [101],
            "spread_line": [-3.0],
            "total": [48.0],
            "market_captured_at": ["2026-10-01T14:00:00Z"],
        }
    )
    with pytest.raises(V5ServingError, match="pre-cutoff capture"):
        _run(markets=market)


def test_v5_serving_rejects_untimestamped_market_snapshot():
    market = pd.DataFrame({"game_id": [101], "spread_line": [-3.0]})
    with pytest.raises(V5ServingError, match="capture timestamp"):
        _run(markets=market)


def test_v5_serving_rejects_outcome_bearing_forecasts():
    forecast = _forecast()
    forecast["actual"] = 0.0
    with pytest.raises(V5ServingError, match="outcomes"):
        _run(forecast=forecast)


def test_v5_source_rejects_manifest_checksum_before_verification(monkeypatch):
    spec = OmegaConf.create(
        {
            "schema_version": "v5_weekly_serving_v1",
            "forecast_manifest_uri": "forecast.json",
            "forecast_manifest_sha256": "0" * 64,
        }
    )

    class Storage:
        def read_bytes(self, _uri):
            return b"{}"

    monkeypatch.setattr(
        serving_script,
        "verify",
        lambda *_args: pytest.fail("verifier called after checksum mismatch"),
    )
    with pytest.raises(V5ServingError, match="checksum mismatch"):
        serving_script.verify_v5_source(spec, Storage())


def test_v5_source_calls_independent_reconstruction(monkeypatch, tmp_path):
    manifest = {
        "identity": {
            "run_id": "v5-test",
            "code_sha": "abc",
            "as_of": "2026-10-01T00:00:00Z",
        },
        "parents": {
            "measurement_uri": "m",
            "rating_replay_uri": "r",
            "schedule_ref_uri": "s",
        },
    }
    raw = json.dumps(manifest).encode()
    config = tmp_path / "forecast.yaml"
    config.write_text("bridge_manifest_uri: frozen-11c\n")
    spec = OmegaConf.create(
        {
            "schema_version": "v5_weekly_serving_v1",
            "forecast_manifest_uri": "forecast.json",
            "forecast_manifest_sha256": hashlib.sha256(raw).hexdigest(),
            "forecast_config": str(config),
        }
    )
    calls = []

    class Storage:
        def read_bytes(self, _uri):
            return raw

    def verifier(args, _config, _storage):
        calls.append(args)
        return {"verified": True, "records_sha256": "a" * 64}

    monkeypatch.setattr(serving_script, "verify", verifier)
    monkeypatch.setattr(
        serving_script, "_load_stored_predictions", lambda *_: _forecast()
    )
    _, forecasts, fields = serving_script.verify_v5_source(spec, Storage())
    assert len(calls) == 1
    assert calls[0].rating_manifest_uri == "r"
    assert len(forecasts) == 4
    assert fields["v5_live_forecast_manifest_sha256"] == hashlib.sha256(raw).hexdigest()


def test_v5_production_mode_requires_separate_decision(monkeypatch):
    monkeypatch.setenv("CFB_ARTIFACT_ENV", "production")
    cfg = OmegaConf.create(
        {
            "year": 2026,
            "week": 5,
            "v5_live_forecast": {
                "schema_version": "v5_weekly_serving_v1",
                "production_activation_authorized": False,
            },
        }
    )
    args = argparse.Namespace(
        year=2026,
        week=5,
        as_of="2026-10-01T00:00:00Z",
        dataset_refs_uri="refs.json",
        run_id="2026w5-test",
        run_state="preview",
    )
    with pytest.raises(V5ServingError, match="activation decision"):
        serving_script.run_v5_weekly_bets(args, cfg)
