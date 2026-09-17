"""Focused V5-05A shadow contract tests."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from cks_picks_cfb.data import data_first_shadow_v1 as shadow_contracts
from cks_picks_cfb.data.data_first_forecast_v1 import (
    FORECAST_DATASETS,
    REQUIRED_RATING_MANIFEST_URI,
)
from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.data.data_first_possession_rating_v1 import RATING_DATASETS
from cks_picks_cfb.data.schema_contracts import schema_for
from cks_picks_cfb.forecast.shadow import (
    ShadowError,
    build_readiness_report,
    check_source_availability,
    perturbation_invariance_proof,
    readiness_overall,
    replay_frozen_forecast,
)

_MEASUREMENT_URI = (
    "artifacts/research/data-first-football-v1/possession-v1/measurements/runs/"
    "possession-v1-measurements-20260915-18fb0aa-r6/measurement-manifest.json"
)
_REPAIR_URI = (
    "artifacts/research/data-first-football-v1/repair/v2/runs/"
    "repair-v2-20260909T1417Z/repair-manifest.json"
)
_FORECAST_URI = shadow_contracts.REQUIRED_FORECAST_MANIFEST_URI


def _base_config() -> dict:
    return {
        "schema_version": "data_first_shadow_config_v1",
        "environment": "preview",
        "candidate_manifest_uri": _FORECAST_URI,
        "rating_candidate": "ppp__rho_0_60__exposure",
        "freeze_target_lead_seconds": 7200,
        "freeze_hard_lead_seconds": 3600,
        "score_stabilization_seconds": 86400,
        "minimum_paired_games": 40,
        "diagnostic_class": "diagnostic_only",
        "production_activation_authorized": False,
    }


def test_shadow_schemas_resolve():
    for name, (_dataset, version) in shadow_contracts.SHADOW_DATASETS.items():
        schema = schema_for(_dataset, version)
        assert schema.schema_version == version, name


def test_shadow_config_accepts_sealed_values():
    shadow_contracts.validate_shadow_config(_base_config())


def test_shadow_config_rejects_drift():
    drifted = json.loads(json.dumps(_base_config()))
    drifted["freeze_target_lead_seconds"] = 3600
    with pytest.raises(shadow_contracts.ShadowContractError, match="target lead"):
        shadow_contracts.validate_shadow_config(drifted)
    drifted = json.loads(json.dumps(_base_config()))
    drifted["minimum_paired_games"] = 30
    with pytest.raises(shadow_contracts.ShadowContractError, match="paired-game"):
        shadow_contracts.validate_shadow_config(drifted)
    drifted = json.loads(json.dumps(_base_config()))
    drifted["production_activation_authorized"] = True
    with pytest.raises(shadow_contracts.ShadowContractError, match="production"):
        shadow_contracts.validate_shadow_config(drifted)
    drifted = json.loads(json.dumps(_base_config()))
    drifted["candidate_manifest_uri"] = "wrong/candidate.json"
    with pytest.raises(shadow_contracts.ShadowContractError, match="certified 04"):
        shadow_contracts.validate_shadow_config(drifted)


def _forecast_manifest() -> dict:
    return signed_payload(
        {
            "schema_version": "data_first_forecast_manifest_v1",
            "state": "frozen",
            "identity": {
                "environment": "preview",
                "run_id": "forecast-v1-20260917-4600ddd-04b",
            },
            "selected_horizon": "expanding",
            "production_activation_authorized": False,
            "parents": {
                "rating_manifest_uri": REQUIRED_RATING_MANIFEST_URI,
                "rating_manifest_raw_sha256": "a" * 64,
                "measurement_manifest_uri": _MEASUREMENT_URI,
                "measurement_manifest_raw_sha256": "m" * 64,
                "repair_manifest_uri": _REPAIR_URI,
                "repair_manifest_raw_sha256": "r" * 64,
            },
            "output_refs": {
                name: {} for name in FORECAST_DATASETS if name != "candidate_manifest"
            },
        }
    )


def _rating_manifest() -> dict:
    return signed_payload(
        {
            "schema_version": "data_first_possession_retained_rating_v1",
            "state": "frozen",
            "identity": {
                "environment": "preview",
                "run_id": "possession-v1-ratings-20260917-d029526-cert",
            },
            "selected_candidate": "ppp__rho_0_60__exposure",
            "production_activation_authorized": False,
            "parents": {
                "measurement_manifest_uri": _MEASUREMENT_URI,
                "measurement_manifest_raw_sha256": "m" * 64,
                "repair_manifest_uri": _REPAIR_URI,
                "repair_manifest_raw_sha256": "r" * 64,
            },
            "output_refs": {name: {} for name in RATING_DATASETS},
        }
    )


def _verify_candidate(
    *,
    forecast_manifest_uri: str = _FORECAST_URI,
    rating_manifest_uri: str = REQUIRED_RATING_MANIFEST_URI,
    measurement_manifest_uri: str = _MEASUREMENT_URI,
    repair_manifest_uri: str = _REPAIR_URI,
):
    return shadow_contracts.verify_candidate_parents(
        _forecast_manifest(),
        _rating_manifest(),
        {"identity": {"run_id": "measurement-parent"}},
        {"identity": {"run_id": "repair-parent"}},
        forecast_manifest_uri=forecast_manifest_uri,
        forecast_raw_sha256="f" * 64,
        rating_manifest_uri=rating_manifest_uri,
        rating_raw_sha256="a" * 64,
        measurement_manifest_uri=measurement_manifest_uri,
        measurement_raw_sha256="m" * 64,
        repair_manifest_uri=repair_manifest_uri,
        repair_raw_sha256="r" * 64,
    )


def test_candidate_parent_uri_substitution_is_rejected(monkeypatch):
    with pytest.raises(
        shadow_contracts.ShadowContractError, match="not the certified 04"
    ):
        _verify_candidate(forecast_manifest_uri="other/forecast-manifest.json")
    with pytest.raises(shadow_contracts.ShadowContractError, match="pinned parent"):
        _verify_candidate(measurement_manifest_uri=_MEASUREMENT_URI + "/substituted")
    with pytest.raises(shadow_contracts.ShadowContractError, match="pinned parent"):
        _verify_candidate(repair_manifest_uri="wrong/" + _REPAIR_URI)
    import cks_picks_cfb.data.data_first_forecast_v1 as forecast_module

    monkeypatch.setattr(
        forecast_module,
        "verify_parents",
        lambda measurement, repair: (dict(measurement), dict(repair)),
    )
    parents = _verify_candidate()
    assert parents["forecast_manifest_uri"] == _FORECAST_URI
    assert parents["rating_manifest_uri"] == REQUIRED_RATING_MANIFEST_URI
    assert parents["measurement_manifest_uri"] == _MEASUREMENT_URI
    assert parents["repair_manifest_uri"] == _REPAIR_URI


def test_candidate_manifest_tamper_is_rejected(monkeypatch):
    import cks_picks_cfb.data.data_first_forecast_v1 as forecast_module

    monkeypatch.setattr(
        forecast_module,
        "verify_parents",
        lambda measurement, repair: (dict(measurement), dict(repair)),
    )
    tampered = _forecast_manifest()
    tampered["selected_horizon"] = "latest_five"
    with pytest.raises(shadow_contracts.ShadowContractError, match="checksum mismatch"):
        shadow_contracts.verify_candidate_parents(
            tampered,
            _rating_manifest(),
            {"identity": {"run_id": "measurement-parent"}},
            {"identity": {"run_id": "repair-parent"}},
            forecast_manifest_uri=_FORECAST_URI,
            forecast_raw_sha256="f" * 64,
            rating_manifest_uri=REQUIRED_RATING_MANIFEST_URI,
            rating_raw_sha256="a" * 64,
            measurement_manifest_uri=_MEASUREMENT_URI,
            measurement_raw_sha256="m" * 64,
            repair_manifest_uri=_REPAIR_URI,
            repair_raw_sha256="r" * 64,
        )
    wrong_horizon = signed_payload(
        {
            "schema_version": "data_first_forecast_manifest_v1",
            "state": "frozen",
            "identity": {
                "environment": "preview",
                "run_id": "forecast-v1-20260917-4600ddd-04b",
            },
            "selected_horizon": "latest_five",
            "production_activation_authorized": False,
            "parents": {
                "rating_manifest_uri": REQUIRED_RATING_MANIFEST_URI,
                "rating_manifest_raw_sha256": "a" * 64,
                "measurement_manifest_uri": _MEASUREMENT_URI,
                "measurement_manifest_raw_sha256": "m" * 64,
                "repair_manifest_uri": _REPAIR_URI,
                "repair_manifest_raw_sha256": "r" * 64,
            },
            "output_refs": {
                name: {} for name in FORECAST_DATASETS if name != "candidate_manifest"
            },
        }
    )
    with pytest.raises(
        shadow_contracts.ShadowContractError, match="exact certified 04"
    ):
        shadow_contracts.verify_candidate_parents(
            wrong_horizon,
            _rating_manifest(),
            {"identity": {"run_id": "measurement-parent"}},
            {"identity": {"run_id": "repair-parent"}},
            forecast_manifest_uri=_FORECAST_URI,
            forecast_raw_sha256="f" * 64,
            rating_manifest_uri=REQUIRED_RATING_MANIFEST_URI,
            rating_raw_sha256="a" * 64,
            measurement_manifest_uri=_MEASUREMENT_URI,
            measurement_raw_sha256="m" * 64,
            repair_manifest_uri=_REPAIR_URI,
            repair_raw_sha256="r" * 64,
        )


def test_shadow_identity_requires_pinned_parent_uris():
    kwargs = {
        "run_id": "shadow-v1-test",
        "as_of": "2026-09-17T00:00:00Z",
        "code_sha": "a" * 40,
        "config_sha": "b" * 64,
    }
    parents = {
        "forecast_manifest_uri": _FORECAST_URI,
        "forecast_raw_sha256": "f" * 64,
        "rating_manifest_uri": REQUIRED_RATING_MANIFEST_URI,
        "rating_raw_sha256": "a" * 64,
        "measurement_manifest_uri": _MEASUREMENT_URI,
        "measurement_raw_sha256": "m" * 64,
        "repair_manifest_uri": _REPAIR_URI,
        "repair_raw_sha256": "r" * 64,
    }
    identity = shadow_contracts.shadow_identity(parents=parents, **kwargs)
    assert identity["parents"]["forecast_manifest_uri"] == _FORECAST_URI
    assert identity["candidate"] == "forecast-v1-20260917-4600ddd-04b"
    incomplete = {
        key: value for key, value in parents.items() if key != "repair_manifest_uri"
    }
    with pytest.raises(shadow_contracts.ShadowContractError, match="exact URIs"):
        shadow_contracts.shadow_identity(parents=incomplete, **kwargs)


def test_shadow_manifest_requires_readiness_output():
    identity = {"identity_sha256": "i" * 64}
    parents = {"forecast_manifest_uri": _FORECAST_URI}
    refs = {"readiness": {"dataset": "shadow_readiness"}}
    manifest = shadow_contracts.shadow_manifest(
        identity=identity,
        parents=parents,
        output_refs=refs,
        readiness_overall="blocked",
    )
    assert manifest["readiness_overall"] == "blocked"
    assert manifest["production_activation_authorized"] is False
    with pytest.raises(shadow_contracts.ShadowContractError, match="unknown"):
        shadow_contracts.shadow_manifest(
            identity=identity,
            parents=parents,
            output_refs=refs,
            readiness_overall="maybe",
        )
    with pytest.raises(
        shadow_contracts.ShadowContractError, match="exactly the readiness"
    ):
        shadow_contracts.shadow_manifest(
            identity=identity,
            parents=parents,
            output_refs={},
            readiness_overall="ready",
        )


def _available_inputs():
    forecast = {"identity": {"as_of": "2026-09-17T01:55:00Z"}}
    rating_states = pd.DataFrame([{"season": 2025, "team": "Alpha"}])
    schedule = pd.DataFrame([{"season": 2025, "week": 10, "game_id": 1}])
    outcomes = pd.DataFrame([{"season": 2025, "week": 9, "game_id": 2}])
    scoring = pd.DataFrame([{"season": 2025, "game_id": 2}])
    priors = pd.DataFrame([{"season": 2025}])
    return {
        "candidate": "forecast-v1-20260917-4600ddd-04b",
        "season": 2025,
        "week": 10,
        "cutoff": "2026-09-17T16:40:02Z",
        "forecast": forecast,
        "rating_states": rating_states,
        "schedule": schedule,
        "outcomes": outcomes,
        "scoring_events": scoring,
        "priors": priors,
        "measurement_as_of": "2026-09-15T19:16:30Z",
        "rating_as_of": "2026-09-17T01:55:00Z",
    }


def test_readiness_is_ready_on_complete_inputs():
    statuses = check_source_availability(**_available_inputs())
    assert {status.source for status in statuses} == {
        "candidate",
        "schedule",
        "completed_games",
        "scoring",
        "priors",
        "team_states",
    }
    assert readiness_overall(statuses) == "ready"
    records, overall = build_readiness_report(
        candidate="forecast-v1-20260917-4600ddd-04b",
        season=2025,
        week=10,
        run_id="shadow-v1-test",
        statuses=statuses,
    )
    assert overall == "ready"
    assert set(records.columns) == set(shadow_contracts.READINESS_COLUMNS)
    assert len(records) == 6
    assert (records["overall"] == "ready").all()


def test_readiness_is_blocked_on_missing_mandatory_input():
    inputs = _available_inputs()
    inputs["rating_states"] = pd.DataFrame()
    statuses = check_source_availability(**inputs)
    assert readiness_overall(statuses) == "blocked"
    by_source = {status.source: status for status in statuses}
    assert by_source["team_states"].blocked_reason == "no team states for 2025"
    records, overall = build_readiness_report(
        candidate="forecast-v1-20260917-4600ddd-04b",
        season=2025,
        week=10,
        run_id="shadow-v1-test",
        statuses=statuses,
    )
    assert overall == "blocked"
    assert (records["overall"] == "blocked").all()


def test_readiness_uses_neutral_fallback_for_missing_priors():
    inputs = _available_inputs()
    inputs["priors"] = pd.DataFrame()
    statuses = check_source_availability(**inputs)
    by_source = {status.source: status for status in statuses}
    assert by_source["priors"].status == "unavailable"
    assert by_source["priors"].fallback == "neutral"
    assert by_source["priors"].blocked_reason == ""
    assert readiness_overall(statuses) == "ready"


def test_readiness_rejects_post_cutoff_evidence():
    inputs = _available_inputs()
    inputs["measurement_as_of"] = "2026-09-18T00:00:00Z"
    statuses = check_source_availability(**inputs)
    assert readiness_overall(statuses) == "blocked"
    by_source = {status.source: status for status in statuses}
    assert by_source["schedule"].timing_class == "post_cutoff"


def test_readiness_rejects_reconstructed_as_authentic():
    inputs = _available_inputs()
    inputs["schedule"] = pd.DataFrame()
    statuses = check_source_availability(**inputs)
    by_source = {status.source: status for status in statuses}
    assert by_source["schedule"].status == "unavailable"
    assert "2025 week 10" in by_source["schedule"].blocked_reason
    assert readiness_overall(statuses) == "blocked"


def _replay_frame() -> pd.DataFrame:
    rows = []
    seasons = (2015, 2016, 2017, 2018, 2019, 2021, 2022)
    game_id = 0
    for season in seasons:
        for week in (1, 2):
            game_id += 1
            value = float(season - 2014 + week)
            rows.append(
                {
                    "season": season,
                    "week": week,
                    "game_id": game_id,
                    "home_offense": value,
                    "home_defense": value / 2,
                    "away_offense": -value / 3,
                    "away_defense": value / 4,
                    "home_host": 1.0,
                    "venue_unknown": True,
                    "actual_margin": value * 1.5,
                    "actual_total": 35 + value,
                    "offset_margin": 0.2,
                    "offset_total": 0.4,
                    "completed_game_stage": min(week, 4),
                }
            )
    return pd.DataFrame.from_records(rows)


_REPLAY_KWARGS = {
    "horizon": "expanding",
    "development_seasons": (2015, 2016, 2017, 2018, 2019, 2021, 2022),
    "replay_seasons": (2021, 2022),
    "alpha_grid": (0.1, 1.0, 10.0, 100.0),
    "floor": 0.05,
    "cutoff_season": 2022,
    "bootstrap_seed": 2,
    "bootstrap_samples": 25,
}


def test_replay_is_deterministic_and_reference_bound():
    frame = _replay_frame()
    first = replay_frozen_forecast(features=frame, **_REPLAY_KWARGS)
    assert len(first.predictions_sha) == 64
    second = replay_frozen_forecast(
        features=frame, reference_sha=first.predictions_sha, **_REPLAY_KWARGS
    )
    assert second.identical is True
    with pytest.raises(ShadowError, match="differs from the reference"):
        replay_frozen_forecast(features=frame, reference_sha="0" * 64, **_REPLAY_KWARGS)


def test_replay_rejects_beyond_cutoff_rows():
    frame = _replay_frame()
    with pytest.raises(ShadowError, match="beyond the frozen cutoff"):
        replay_frozen_forecast(
            features=frame,
            **{**_REPLAY_KWARGS, "cutoff_season": 2021},
        )


def test_replay_proves_perturbation_invariance():
    frame = _replay_frame()
    assert (
        perturbation_invariance_proof(
            features=frame, perturb_season=2022, **_REPLAY_KWARGS
        )
        is True
    )
