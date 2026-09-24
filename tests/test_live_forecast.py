from __future__ import annotations

import ast
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from cks_picks_cfb.data.data_first_live_forecast_v1 import (
    LIVE_FORECAST_COLUMNS,
    LIVE_FORECAST_DATASET,
    LiveForecastContractError,
    validate_config,
    validate_prediction_frame,
)
from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.data.lake import canonical_frame_digest
from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame
from cks_picks_cfb.forecast.live import (
    DEVELOPMENT_SEASONS,
    LiveForecastError,
    apply_exported_bridge,
    apply_frozen_bridge,
    build_live_application_frame,
    export_frozen_bridge,
)
from cks_picks_cfb.forecast.live_verification import (
    reconstruct_predictions,
    verify_bundle_predictions,
    verify_predictions,
)
from scripts.research import run_v5_live_forecast as live_runner


def _config() -> dict[str, object]:
    return {
        "schema_version": "data_first_live_forecast_config_v1",
        "environment": "preview",
        "bridge_manifest_uri": "artifacts/research/data-first-football-v1/forecasts/runs/forecast-v1-20260921-5afd577-11c/forecast-manifest.json",
        "horizon": "expanding",
        "reference_alpha": 10.0,
        "development_seasons": list(DEVELOPMENT_SEASONS),
        "forbidden_seasons": [2020],
        "production_activation_authorized": False,
    }


def _frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    features = (
        "home_offense",
        "home_defense",
        "away_offense",
        "away_defense",
        "home_host",
        "venue_unknown",
    )
    history: list[dict[str, float | int]] = []
    for season in DEVELOPMENT_SEASONS:
        for index in range(6):
            row: dict[str, float | int] = {
                "season": season,
                "actual_margin": float(index - 2),
                "actual_total": float(38 + index * 2),
                "offset_margin": 0.0,
                "offset_total": 1.0,
            }
            row.update(
                {name: float(index + i + season % 3) for i, name in enumerate(features)}
            )
            history.append(row)
    live = pd.DataFrame(
        [
            {
                "season": 2026,
                "week": 5,
                "game_id": 1001,
                "offset_margin": 0.5,
                "offset_total": 1.5,
                "completed_game_stage": 4,
                **{name: float(i + 2) for i, name in enumerate(features)},
            },
            {
                "season": 2026,
                "week": 5,
                "game_id": 1002,
                "offset_margin": -0.5,
                "offset_total": 0.5,
                "completed_game_stage": 0,
                **{name: float(i - 2) for i, name in enumerate(features)},
            },
        ]
    )
    return pd.DataFrame(history), live


def test_live_config_pins_only_frozen_through_2025_application() -> None:
    validate_config(_config())
    invalid = _config()
    invalid["reference_alpha"] = 1.0
    with pytest.raises(LiveForecastContractError, match="bridge definition"):
        validate_config(invalid)


def test_outcome_free_prediction_contract_and_schedule_schema() -> None:
    row = {
        "run_id": "live-test",
        "season": 2026,
        "week": 5,
        "game_id": 1001,
        "target": "margin",
        "mean": 1.0,
        "variance": 4.0,
        "interval_lower_95": -2.92,
        "interval_upper_95": 4.92,
        "offset": 0.0,
        "completed_game_stage": 4,
        "timing_class": "live",
        "model_ref": "model",
        "state_ref": "state",
        "source_ref": "source",
    }
    frame = pd.DataFrame([row])
    assert tuple(frame.columns) == LIVE_FORECAST_COLUMNS
    validate_prediction_frame(frame, run_id="live-test")
    validate_frame(frame, schema_for(*LIVE_FORECAST_DATASET))
    with pytest.raises(LiveForecastContractError, match="outcomes"):
        validate_prediction_frame(frame.assign(actual=2.0), run_id="live-test")
    with pytest.raises(LiveForecastContractError, match="2026"):
        validate_prediction_frame(frame.assign(season=2020), run_id="live-test")


def test_bridge_apply_is_deterministic_and_has_no_live_outcome_dependency() -> None:
    historical, live = _frames()
    recipes = {
        "margin": {"head": "reference", "alpha": 10.0},
        "total": {"head": "reference", "alpha": 10.0},
    }
    kwargs = {
        "recipes": recipes,
        "calibration_variances": {"margin": 9.0, "total": 16.0},
        "run_id": "live-test",
        "model_ref": "11c-final-fit",
        "state_refs": {1001: "team-state/1001", 1002: "team-state/1002"},
        "source_ref": "week4-refresh",
    }
    first = apply_frozen_bridge(historical, live, **kwargs).predictions
    second = apply_frozen_bridge(historical, live.copy(), **kwargs).predictions
    pd.testing.assert_frame_equal(first, second)
    assert len(first) == 4
    assert (
        "actual" not in first
        and "absolute_error" not in first
        and "gaussian_crps" not in first
    )
    assert first["timing_class"].eq("live").all()


def test_exported_inference_bundle_matches_historical_reconstruction() -> None:
    historical, live = _frames()
    recipes = {
        "margin": {"head": "reference", "alpha": 10.0},
        "total": {"head": "reference", "alpha": 10.0},
    }
    variances = {"margin": 9.0, "total": 16.0}
    kwargs = {
        "run_id": "live-test",
        "model_ref": "11c-final-fit",
        "state_refs": {1001: "state/1001", 1002: "state/1002"},
        "source_ref": "week4-refresh",
    }
    original = apply_frozen_bridge(
        historical,
        live,
        recipes=recipes,
        calibration_variances=variances,
        **kwargs,
    ).predictions
    bundle = export_frozen_bridge(
        historical,
        recipes=recipes,
        calibration_variances=variances,
    )
    loaded = json.loads(json.dumps(bundle))
    exported = apply_exported_bridge(loaded, live, **kwargs).predictions
    independent = verify_bundle_predictions(loaded, live, **kwargs)
    pd.testing.assert_frame_equal(
        original, exported, check_exact=False, atol=1e-12, rtol=1e-12
    )
    pd.testing.assert_frame_equal(
        original, independent, check_exact=False, atol=1e-12, rtol=1e-12
    )
    for target, sigma in (("margin", 3.0), ("total", 4.0)):
        rows = original[original["target"].eq(target)]
        assert np.allclose(
            rows["interval_upper_95"] - rows["mean"],
            1.959963984540054 * sigma,
        )


def test_independent_verifier_reconstructs_and_detects_prediction_perturbation() -> (
    None
):
    historical, live = _frames()
    recipes = {
        "margin": {"head": "reference", "final_alpha": 10.0},
        "total": {"head": "reference", "final_alpha": 10.0},
    }
    kwargs = {
        "recipes": recipes,
        "calibration_variances": {"margin": 9.0, "total": 16.0},
        "run_id": "live-test",
        "model_ref": "11c-final-fit",
        "state_refs": {1001: "team-state/1001", 1002: "team-state/1002"},
        "source_ref": "week4-refresh",
    }
    produced = apply_frozen_bridge(historical, live, **kwargs).predictions
    reconstructed = reconstruct_predictions(
        historical,
        live,
        recipes=recipes,
        variances=kwargs["calibration_variances"],
        run_id=kwargs["run_id"],
        model_ref=kwargs["model_ref"],
        state_refs=kwargs["state_refs"],
        source_ref=kwargs["source_ref"],
    )
    signed = {
        "row_count": len(produced),
        "prediction_records_sha256": canonical_frame_digest(
            produced, columns=LIVE_FORECAST_COLUMNS
        ),
        "identity": {"run_id": "live-test"},
    }
    assert verify_predictions(
        manifest=signed, stored=produced, reconstructed=reconstructed
    )["verified"]
    rounded_differently = reconstructed.copy()
    rounded_differently.loc[0, "mean"] += 1e-13
    assert verify_predictions(
        manifest=signed, stored=produced, reconstructed=rounded_differently
    )["verified"]
    rounded_differently.loc[0, "mean"] += 1e-5
    with pytest.raises(ValueError, match="mean differs"):
        verify_predictions(
            manifest=signed, stored=produced, reconstructed=rounded_differently
        )
    perturbed = produced.copy()
    perturbed.loc[0, "mean"] += 0.25
    with pytest.raises(ValueError, match="differ"):
        verify_predictions(
            manifest=signed, stored=perturbed, reconstructed=reconstructed
        )


def test_live_verifier_rejects_code_config_or_parent_identity_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = "live-verify-test"
    manifest_uri = (
        f"{live_runner.LIVE_FORECAST_OUTPUT_ROOT}/{run_id}/{live_runner.MANIFEST_NAME}"
    )
    parents = {
        "measurement_uri": "measurement.json",
        "measurement_raw_sha256": "measurement-sha",
        "rating_replay_uri": "rating.json",
        "rating_replay_raw_sha256": "rating-sha",
        "bridge_uri": "bridge.json",
        "bridge_raw_sha256": "bridge-sha",
        "schedule_ref_uri": "schedule.parquet",
        "schedule_raw_sha256": "schedule-sha",
    }
    identity = {
        "run_id": run_id,
        "environment": "preview",
        "season": 2026,
        "parents": parents,
    }
    manifest = signed_payload(
        {
            "schema_version": "data_first_live_forecast_manifest_v1",
            "state": "frozen",
            "identity": identity,
            "parents": parents,
            "row_count": 2,
            "population_sha256": "population-sha",
            "production_activation_authorized": False,
        }
    )

    class Storage:
        def read_bytes(self, uri: str) -> bytes:
            assert uri == manifest_uri
            return json.dumps(manifest, sort_keys=True).encode()

    monkeypatch.setattr(
        live_runner,
        "_identity",
        lambda *_args: {**identity, "code_sha": "different-code"},
    )
    args = SimpleNamespace(
        run_id=run_id,
        verify_manifest_uri=manifest_uri,
        measurement_manifest_uri="measurement.json",
        rating_manifest_uri="rating.json",
        schedule_ref_uri="schedule.parquet",
    )
    with pytest.raises(live_runner.LiveForecastRunError, match="identity differs"):
        live_runner.verify(args, _config(), Storage())


def test_live_verifier_has_no_forecast_producer_or_selection_imports() -> None:
    path = Path(__file__).parents[1] / "src/cks_picks_cfb/forecast/live_verification.py"
    tree = ast.parse(path.read_text())
    imported = {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "cks_picks_cfb.forecast.live" not in imported
    assert not any(name.startswith("scripts.research.") for name in imported)
    assert not any(
        name.endswith(("forecast_selection", "forecast_fitting")) for name in imported
    )


def test_live_forecast_apply_repeat_is_immutable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Storage:
        def __init__(self, values: dict[str, bytes]) -> None:
            self.values = values

        def exists(self, uri: str) -> bool:
            return uri in self.values

        def read_bytes(self, uri: str) -> bytes:
            return self.values[uri]

    run_id = "live-repeat-test"
    identity = {"identity_sha256": "frozen-identity"}
    manifest_uri = (
        f"{live_runner.LIVE_FORECAST_OUTPUT_ROOT}/{run_id}/{live_runner.MANIFEST_NAME}"
    )
    storage = Storage(
        {manifest_uri: json.dumps({"identity": identity}, sort_keys=True).encode()}
    )
    before = dict(storage.values)
    evidence_path = tmp_path / "preflight.json"
    evidence_path.write_text(
        json.dumps(
            {
                "state": "dry_run",
                "identity": identity,
                "production_activation_authorized": False,
            }
        )
    )
    args = SimpleNamespace(run_id=run_id, verify_manifest_uri=manifest_uri)
    monkeypatch.setattr(live_runner, "_identity", lambda *args: identity)
    monkeypatch.setattr(
        live_runner, "verify", lambda *args: {"verified": True, "row_count": 4}
    )
    result = live_runner.apply(args, {}, storage, evidence_path)
    assert result["state"] == "already_applied"
    assert result["verified"] is True
    assert storage.values == before


def test_apply_rejects_changed_preflight_partition_digests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Storage:
        def exists(self, _uri: str) -> bool:
            return False

        def list_files(self, _prefix: str) -> list[str]:
            return []

    historical, live = _frames()
    recipes = {
        "margin": {"head": "reference", "alpha": 10.0},
        "total": {"head": "reference", "alpha": 10.0},
    }
    result = apply_frozen_bridge(
        historical,
        live,
        recipes=recipes,
        calibration_variances={"margin": 9.0, "total": 16.0},
        run_id="live-apply-test",
        model_ref="11c-final-fit",
        state_refs={1001: "state/1001", 1002: "state/1002"},
        source_ref="week4-refresh",
    )
    frame = result.predictions
    population_sha = "population-digest"
    identity = {"identity_sha256": "frozen-identity"}
    evidence = {
        "state": "dry_run",
        "identity": identity,
        "prediction_count": len(frame),
        "prediction_records_sha256": canonical_frame_digest(
            frame, columns=LIVE_FORECAST_COLUMNS
        ),
        "population_sha256": population_sha,
        "bridge_recipes": dict(result.recipes),
        "partitions": live_runner._partition_evidence(frame),
        "production_activation_authorized": False,
    }
    evidence["partitions"][0]["records_sha256"] = "tampered-partition-digest"
    evidence_path = tmp_path / "preflight.json"
    evidence_path.write_text(json.dumps(evidence))
    monkeypatch.setattr(live_runner, "_identity", lambda *args: identity)
    monkeypatch.setattr(
        live_runner,
        "_compute",
        lambda *args: ({}, result, population_sha),
    )

    with pytest.raises(live_runner.LiveForecastRunError, match="preflight"):
        live_runner.apply(
            SimpleNamespace(run_id="live-apply-test"),
            {},
            Storage(),
            evidence_path,
        )


def test_bridge_rejects_forbidden_fit_year_and_missing_state_ref() -> None:
    historical, live = _frames()
    bad_history = pd.concat(
        [historical, historical.iloc[[0]].assign(season=2020)], ignore_index=True
    )
    recipes = {
        "margin": {"head": "reference", "alpha": 10.0},
        "total": {"head": "reference", "alpha": 10.0},
    }
    kwargs = {
        "recipes": recipes,
        "calibration_variances": {"margin": 9.0, "total": 16.0},
        "run_id": "live-test",
        "model_ref": "11c-final-fit",
        "state_refs": {1001: "team-state/1001"},
        "source_ref": "week4-refresh",
    }
    with pytest.raises(LiveForecastError, match="forbidden season"):
        apply_frozen_bridge(bad_history, live, **kwargs)
    with pytest.raises(LiveForecastError, match="state reference"):
        apply_frozen_bridge(historical, live, **kwargs)


def test_application_uses_only_states_and_completed_games_before_cutoff() -> None:
    schedule = pd.DataFrame(
        [
            {
                "season": 2026,
                "week": 5,
                "game_id": 700,
                "kickoff_utc": "2026-10-01T20:00:00Z",
                "home_team": "Home",
                "away_team": "Away",
            }
        ]
    )
    completed = pd.DataFrame(
        [
            {
                "season": 2026,
                "kickoff_utc": "2026-09-20T12:00:00Z",
                "home_team": "Home",
                "away_team": "Other",
                "schedule_completed": True,
                "outcome_valid": True,
            },
            {
                "season": 2026,
                "kickoff_utc": "2026-09-25T12:00:00Z",
                "home_team": "Home",
                "away_team": "Other",
                "schedule_completed": True,
                "outcome_valid": True,
            },
        ]
    )
    states = pd.DataFrame(
        [
            {
                "season": 2026,
                "game_id": 600,
                "cutoff_utc": "2026-09-21T00:00:00Z",
                "team": team,
                "offense_rating": 1.0,
                "defense_rating": 2.0,
            }
            for team in ("Home", "Away")
        ]
        + [
            {
                "season": 2026,
                "game_id": 650,
                "cutoff_utc": "2026-09-26T00:00:00Z",
                "team": team,
                "offense_rating": 99.0,
                "defense_rating": 99.0,
            }
            for team in ("Home", "Away")
        ]
    )
    offsets = pd.DataFrame(
        [
            {
                "season": 2026,
                "week": 5,
                "game_id": 700,
                "offset_margin": 0.0,
                "offset_total": 0.0,
            }
        ]
    )
    frame, _ = build_live_application_frame(
        schedule,
        completed.iloc[[0]],
        states,
        offsets,
        as_of="2026-09-24T00:00:00Z",
    )
    assert frame.loc[0, "home_offense"] == 1.0
    assert frame.loc[0, "completed_game_stage"] == 0
    later = schedule.iloc[[0]].assign(
        week=6, game_id=701, kickoff_utc="2026-10-08T20:00:00Z"
    )
    selected, _ = build_live_application_frame(
        pd.concat([schedule, later], ignore_index=True),
        completed.iloc[[0]],
        states,
        offsets,
        as_of="2026-09-24T00:00:00Z",
        target_week=5,
    )
    assert selected["game_id"].tolist() == [700]

    future_final = completed.iloc[[1]].assign(kickoff_utc="2026-09-25T12:00:00Z")
    with pytest.raises(LiveForecastError, match="after the forecast cutoff"):
        build_live_application_frame(
            schedule,
            future_final,
            states,
            offsets,
            as_of="2026-09-24T00:00:00Z",
        )
