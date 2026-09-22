"""Focused contracts for the Contract 07 2026 extension (Repair-2026 + live timing).

Covers Task 1 acceptance: live timing admitted in its scope with historical
guarantees intact, 2026 season validation with 2020 forbidden everywhere, and
2026 population boundaries. Historical paths are asserted unchanged.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
import yaml

from cks_picks_cfb.data.data_first_phase2 import FORBIDDEN_SEASONS
from cks_picks_cfb.data.data_first_phase2d import canonical_bytes, signed_payload
from cks_picks_cfb.data.data_first_possession_v1 import (
    EXTENSION_2026_FIXED_SETTINGS,
    PossessionContractError,
    build_population,
    certification,
    possession_identity,
    validate_config,
)
from cks_picks_cfb.data.data_first_repair_v2 import (
    EXTENSION_2026_SEASONS,
    LIVE_TIMING,
    RECONSTRUCTED_TIMING,
    REPAIR_MANIFEST_SCHEMA,
    REPAIR_POPULATION_SCHEMA,
    REPAIRED_LIVE_STATE,
    RepairV2Error,
    build_team_universe,
    reconcile_population,
    repair_identity,
    repair_manifest,
)
from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame

ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_CONFIG = (
    ROOT / "conf/research/data_first_football_v1/possession_measurement_v1.yaml"
)
CONFIG_2026 = (
    ROOT / "conf/research/data_first_football_v1/possession_measurement_2026_v1.yaml"
)


def _repair_population_frame(season: int, timing: str, n: int = 2) -> pd.DataFrame:
    rows = []
    for i in range(n):
        rows.append(
            {
                "season": season,
                "week": 1,
                "game_id": 401800000 + i,
                "kickoff_utc": "2026-08-29T16:00:00Z",
                "home_team": "A",
                "away_team": "B",
                "schedule_completed": True,
                "outcome_valid": True,
                "forecast_eligible": True,
                "measurement_usable": True,
                "missing_reason": None,
                "disposition": "eligible_with_measurements",
                "timing_class": timing,
            }
        )
    return pd.DataFrame(rows)


def _coverage_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"measurement_id": "ppp", "slice": "all"},
            {"measurement_id": "epa_per_possession", "slice": "all"},
        ]
    )


# --- measurement config ---


def test_historical_measurement_config_still_validates() -> None:
    validate_config(yaml.safe_load(HISTORICAL_CONFIG.read_text()))


def test_2026_measurement_config_validates() -> None:
    payload = yaml.safe_load(CONFIG_2026.read_text())
    validate_config(payload)
    assert list(payload["development_seasons"]) == [2026]
    assert payload["availability_policy"]["classification"] == "live"
    assert payload["forbidden_seasons"] == [2020]
    for key, expected in EXTENSION_2026_FIXED_SETTINGS.items():
        assert float(payload["fixed_settings"][key]) == expected


def test_2026_config_rejects_wrong_seasons_or_classification() -> None:
    payload = yaml.safe_load(CONFIG_2026.read_text())
    changed = dict(payload, development_seasons=[2025])
    with pytest.raises(PossessionContractError, match="development seasons"):
        validate_config(changed)
    changed = dict(
        payload, availability_policy={"classification": "historically_reconstructed"}
    )
    with pytest.raises(PossessionContractError, match="live timing"):
        validate_config(changed)


def test_2026_config_rejects_altered_settings_or_missing_population() -> None:
    payload = yaml.safe_load(CONFIG_2026.read_text())
    fixed = dict(payload["fixed_settings"], ppp_scale_floor=0.99)
    with pytest.raises(PossessionContractError, match="fixed setting"):
        validate_config(dict(payload, fixed_settings=fixed))
    changed = dict(payload)
    changed.pop("expected_population")
    with pytest.raises(PossessionContractError, match="expected_population|positive"):
        validate_config(changed)


# --- measurement producer scope ---


def test_build_population_2026_scope_accepts_live_and_pins_counts() -> None:
    frame = _repair_population_frame(2026, LIVE_TIMING, n=3)
    result = build_population(
        frame, scope="season_2026", expected_rows=3, expected_eligible=3
    )
    assert (len(result), int(result["forecast_eligible"].sum())) == (3, 3)
    assert result["timing_class"].eq(LIVE_TIMING).all()


def test_build_population_2026_scope_rejects_reconstructed_2020_and_counts() -> None:
    live = _repair_population_frame(2026, LIVE_TIMING, n=2)
    with pytest.raises(PossessionContractError, match="timing class"):
        build_population(
            live.assign(
                timing_class=[
                    LIVE_TIMING,
                    RECONSTRUCTED_TIMING,
                ]
            ),
            scope="season_2026",
            expected_rows=2,
            expected_eligible=2,
        )
    bad_season = _repair_population_frame(2026, LIVE_TIMING, n=1)
    bad_season.loc[0, "season"] = 2020
    with pytest.raises(PossessionContractError, match="impermissible season"):
        build_population(
            bad_season, scope="season_2026", expected_rows=1, expected_eligible=1
        )
    with pytest.raises(PossessionContractError, match="reconciliation"):
        build_population(
            live, scope="season_2026", expected_rows=2, expected_eligible=1
        )
    with pytest.raises(PossessionContractError, match="pinned reconciliation"):
        build_population(live, scope="season_2026")
    with pytest.raises(PossessionContractError, match="unknown scope"):
        build_population(
            live, scope="season_2027", expected_rows=2, expected_eligible=2
        )


def test_build_population_historical_scope_rejects_live() -> None:
    frame = _repair_population_frame(2024, LIVE_TIMING, n=1)
    with pytest.raises(PossessionContractError, match="timing class"):
        build_population(frame)


def test_certification_2026_scope_requires_live_only() -> None:
    population = _repair_population_frame(2026, LIVE_TIMING, n=2)
    built = build_population(
        population, scope="season_2026", expected_rows=2, expected_eligible=2
    )
    signed = certification(
        population=built,
        output_rows={},
        output_digests={},
        coverage=_coverage_frame(),
        scale_diagnostics={},
        scope="season_2026",
        expected_rows=2,
        expected_eligible=2,
    )
    assert signed["all_checks_passed"] is True
    assert signed["timing_class"] == LIVE_TIMING
    mixed = built.copy()
    mixed.loc[0, "timing_class"] = RECONSTRUCTED_TIMING
    failed = certification(
        population=mixed,
        output_rows={},
        output_digests={},
        coverage=_coverage_frame(),
        scale_diagnostics={},
        scope="season_2026",
        expected_rows=2,
        expected_eligible=2,
    )
    assert failed["all_checks_passed"] is False
    assert not failed["checks"]["live_timing_only"]


def test_possession_identity_records_config_seasons() -> None:
    identity = possession_identity(
        run_id="r",
        as_of="2026-09-22T00:00:00Z",
        code_sha="a",
        config_sha="b",
        repair_manifest_uri="m",
        repair_manifest_raw_sha256="c",
        repair_manifest_canonical_sha256="d",
        development_seasons=(2026,),
    )
    assert identity["development_seasons"] == [2026]


# --- repair producer scope ---


def _repair_inputs(season: int = 2026) -> dict[str, pd.DataFrame]:
    schedule = pd.DataFrame(
        [
            {
                "season": season,
                "week": 1,
                "game_id": 401800001,
                "kickoff_utc": "2026-08-29T16:00:00Z",
                "home_team": "Georgia",
                "away_team": "Clemson",
                "home_classification": "FBS",
                "away_classification": "FBS",
                "completed": True,
            },
            {
                "season": season,
                "week": 1,
                "game_id": 401800002,
                "kickoff_utc": "2026-08-29T19:30:00Z",
                "home_team": "Texas",
                "away_team": "Colorado State",
                "home_classification": "FBS",
                "away_classification": "FBS",
                "completed": True,
            },
        ]
    )
    outcomes = pd.DataFrame(
        [
            {
                "season": season,
                "game_id": 401800001,
                "completed": True,
                "home_points": 34,
                "away_points": 3,
            },
            {
                "season": season,
                "game_id": 401800002,
                "completed": True,
                "home_points": 52,
                "away_points": 0,
            },
        ]
    )
    observed = pd.DataFrame(
        [
            {"season": season, "game_id": 401800001},
            {"season": season, "game_id": 401800002},
        ]
    )
    reconciliation = pd.DataFrame(
        [
            {
                "season": season,
                "game_id": 401800001,
                "classification": "prepare_week_concordant",
            },
            {
                "season": season,
                "game_id": 401800002,
                "classification": "prepare_week_concordant",
            },
        ]
    )
    return {
        "schedule": schedule,
        "outcomes": outcomes,
        "observed": observed,
        "reconciliation": reconciliation,
    }


def test_repair_reconcile_2026_scope_stamps_live() -> None:
    frames = _repair_inputs(2026)
    population, _ = reconcile_population(
        schedule=frames["schedule"],
        outcomes=frames["outcomes"],
        observed_games=frames["observed"],
        reconciliation=frames["reconciliation"],
        omissions={},
        scope="season_2026",
    )
    assert len(population) == 2
    assert population["timing_class"].eq(LIVE_TIMING).all()
    assert int(population["forecast_eligible"].sum()) == 2


def test_repair_reconcile_2026_scope_rejects_history_and_2020() -> None:
    frames = _repair_inputs(2024)
    with pytest.raises(RepairV2Error, match="impermissible seasons"):
        reconcile_population(
            schedule=frames["schedule"],
            outcomes=frames["outcomes"],
            observed_games=frames["observed"],
            reconciliation=frames["reconciliation"],
            omissions={},
            scope="season_2026",
        )
    frames = _repair_inputs(2020)
    with pytest.raises(RepairV2Error, match="impermissible seasons"):
        reconcile_population(
            schedule=frames["schedule"],
            outcomes=frames["outcomes"],
            observed_games=frames["observed"],
            reconciliation=frames["reconciliation"],
            omissions={},
            scope="season_2026",
        )


def test_repair_universe_identity_manifest_2026_scope() -> None:
    frames = _repair_inputs(2026)
    universe = build_team_universe(frames["schedule"], scope="season_2026")
    assert set(universe["season"].unique()) == {2026}
    assert len(universe) == 4
    with pytest.raises(RepairV2Error, match="impermissible season"):
        build_team_universe(_repair_inputs(2024)["schedule"], scope="season_2026")
    identity = repair_identity(
        run_id="repair-2026-test",
        environment="preview",
        as_of="2026-09-22T00:00:00Z",
        code_sha="a",
        config_sha="b",
        core_eligibility_uri="c",
        core_eligibility_raw_sha256="d",
        auxiliary_eligibility_uri="e",
        auxiliary_eligibility_raw_sha256="f",
        phase3_retained_uri="g",
        phase3_retained_raw_sha256="h",
        scope="season_2026",
        historical_anchor={"uri": "anchor"},
        season_2026_inputs={"uri": "bundle"},
    )
    assert identity["development_seasons"] == [2026]
    assert identity["scope"] == "season_2026"
    assert identity["historical_anchor"] == {"uri": "anchor"}
    assert identity["season_2026_inputs"] == {"uri": "bundle"}


def test_repair_manifest_state_timing_cross_check() -> None:
    population = pd.DataFrame(
        [
            {
                "season": 2026,
                "week": 1,
                "game_id": 1,
                "kickoff_utc": "2026-08-29T16:00:00Z",
                "home_team": "A",
                "away_team": "B",
                "schedule_completed": True,
                "outcome_valid": True,
                "forecast_eligible": True,
                "measurement_usable": True,
                "measurement_exposure": 1,
                "missing_measurement_sources": "[]",
                "home_points": 34.0,
                "away_points": 3.0,
                "missing_reason": None,
                "reconciliation_classification": "prepare_week_concordant",
                "disposition": "eligible_with_measurements",
                "timing_class": LIVE_TIMING,
            }
        ]
    )
    manifest = repair_manifest(
        identity={"run_id": "x"},
        parents={},
        output_refs={},
        output_rows={},
        population=population,
        family_admission={},
        capture_plan_ref=None,
        state=REPAIRED_LIVE_STATE,
        timing_class=LIVE_TIMING,
    )
    assert manifest["state"] == REPAIRED_LIVE_STATE
    assert manifest["timing_class"] == LIVE_TIMING
    assert manifest["production_activation_authorized"] is False
    with pytest.raises(RepairV2Error, match="disagree"):
        repair_manifest(
            identity={"run_id": "x"},
            parents={},
            output_refs={},
            output_rows={},
            population=population,
            family_admission={},
            capture_plan_ref=None,
            state=REPAIRED_LIVE_STATE,
            timing_class=RECONSTRUCTED_TIMING,
        )
    with pytest.raises(RepairV2Error, match="unknown state"):
        repair_manifest(
            identity={"run_id": "x"},
            parents={},
            output_refs={},
            output_rows={},
            population=population,
            family_admission={},
            capture_plan_ref=None,
            state="bogus",
            timing_class=LIVE_TIMING,
        )


# --- schema gates ---


def test_possession_and_repair_schemas_admit_live() -> None:
    from cks_picks_cfb.data.data_first_possession_v1 import POSSESSION_DATASETS

    for name in POSSESSION_DATASETS:
        dataset, version = POSSESSION_DATASETS[name]
        allowed = schema_for(dataset, version).allowed_values["timing_class"]
        assert set(allowed) == {"historically_reconstructed", "live"}, name
    from cks_picks_cfb.data.data_first_repair_v2 import (
        REPAIR_AUXILIARY_DATASET,
        REPAIR_AUXILIARY_SCHEMA,
        REPAIR_COVERAGE_DATASET,
        REPAIR_COVERAGE_SCHEMA,
        REPAIR_POPULATION_DATASET,
        REPAIR_POPULATION_SCHEMA,
    )

    for dataset, version in (
        (REPAIR_POPULATION_DATASET, REPAIR_POPULATION_SCHEMA),
        (REPAIR_AUXILIARY_DATASET, REPAIR_AUXILIARY_SCHEMA),
        (REPAIR_COVERAGE_DATASET, REPAIR_COVERAGE_SCHEMA),
    ):
        allowed = schema_for(dataset, version).allowed_values["timing_class"]
        assert set(allowed) == {"historically_reconstructed", "live"}, dataset


def test_other_registries_still_reject_live() -> None:
    live_row = {
        "season": 2025,
        "team": "Home",
        "timing_class": "live",
        "recruiting_4yr": 1.0,
        "recruiting_current": 1.0,
        "recruiting_trend": 0.0,
        "missing_reason": None,
    }
    with pytest.raises(Exception, match="timing_class|allowed"):
        validate_frame(
            pd.DataFrame([live_row]),
            schema_for("phase2e_recruiting", "phase2e_recruiting_v1"),
        )


def test_live_row_passes_possession_population_schema() -> None:
    from cks_picks_cfb.data.data_first_possession_v1 import POSSESSION_DATASETS

    dataset, version = POSSESSION_DATASETS["population"]
    schema = schema_for(dataset, version)
    row: dict[str, Any] = {col: None for col in schema.required}
    row.update(
        {
            "season": 2026,
            "week": 1,
            "game_id": 1,
            "kickoff_utc": "2026-08-29T16:00:00Z",
            "home_team": "A",
            "away_team": "B",
            "schedule_completed": True,
            "outcome_valid": True,
            "forecast_eligible": True,
            "measurement_usable": True,
            "population_disposition": "eligible_with_measurements",
            "measurement_disposition": "eligible_with_measurements",
            "timing_class": "live",
        }
    )
    validate_frame(pd.DataFrame([row]), schema)


# --- runner seals and pins ---


def test_measurement_runner_sealed_configs() -> None:
    from scripts.research.run_data_first_possession_measurements import (
        CONFIG_2026,
        DEFAULT_CONFIG,
        SEALED_CONFIGS,
    )

    assert set(SEALED_CONFIGS) == {DEFAULT_CONFIG.resolve(), CONFIG_2026.resolve()}
    assert CONFIG_2026.name == "possession_measurement_2026_v1.yaml"


def test_repair_runner_2026_silver_pins_match_verified_versions() -> None:
    from scripts.research.run_data_first_repair_v2 import SEASON_2026_SILVER_INPUTS

    assert (
        SEASON_2026_SILVER_INPUTS["games"]["version_id"] == "e3ead5813aaf3e7a983f49f3"
    )
    assert SEASON_2026_SILVER_INPUTS["game_outcomes"]["version_id"].startswith(
        "669856aa"
    )
    assert SEASON_2026_SILVER_INPUTS["byplay"]["version_id"].startswith("7a79eb05")
    assert SEASON_2026_SILVER_INPUTS["byplay"]["dataset"] == "byplay"
    assert SEASON_2026_SILVER_INPUTS["team_games"]["version_id"].startswith("2f58910d")
    assert EXTENSION_2026_SEASONS == (2026,)
    assert 2020 in FORBIDDEN_SEASONS


# --- repair v3 verifier state gate ---


class _MemStorage:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    def read_bytes(self, uri: str) -> bytes:
        if uri not in self.files:
            raise FileNotFoundError(uri)
        return self.files[uri]

    def write_bytes(self, data: bytes, uri: str) -> None:
        self.files[uri] = data

    def exists(self, uri: str) -> bool:
        return uri in self.files


def _make_live_repair_mock() -> tuple[_MemStorage, str]:
    from cks_picks_cfb.data.schema_contracts import schema_for

    storage = _MemStorage()
    pop_rows = []
    for game_id, hp, ap in [(401800001, 34, 3), (401800002, 52, 0)]:
        row = {
            col: 0
            for col in schema_for(
                "repair_population", REPAIR_POPULATION_SCHEMA
            ).required
        }
        row.update(
            {
                "season": 2026,
                "week": 1,
                "game_id": game_id,
                "kickoff_utc": "2026-08-29T16:00:00Z",
                "home_team": "Georgia",
                "away_team": "Clemson",
                "schedule_completed": True,
                "outcome_valid": True,
                "forecast_eligible": True,
                "measurement_usable": True,
                "measurement_exposure": 1,
                "missing_measurement_sources": "none",
                "home_points": hp,
                "away_points": ap,
                "disposition": "eligible_with_measurements",
                "timing_class": "live",
            }
        )
        pop_rows.append(row)
    pop_df = pd.DataFrame(pop_rows)
    pop_bytes = pop_df.to_parquet(index=False)
    pop_sha = hashlib.sha256(pop_bytes).hexdigest()
    pop_uri = "artifacts/mock/repair26/population/data.parquet"
    storage.write_bytes(pop_bytes, pop_uri)
    output_refs = {
        "population": {
            "dataset": "repair_population",
            "version_id": "v1",
            "schema_version": REPAIR_POPULATION_SCHEMA,
            "content_sha": pop_sha,
            "uri": pop_uri,
        }
    }
    output_rows = {"population": len(pop_df)}
    for name, ds in [
        ("auxiliary", "repair_auxiliary"),
        ("coverage", "repair_coverage"),
        ("issues", "repair_issue"),
        ("capture_plan", "repair_capture_plan"),
    ]:
        schema = schema_for(ds, f"data_first_{ds}_v2")
        row: dict[str, Any] = {}
        for col in schema.required:
            if col in schema.integer_columns:
                row[col] = 1
            elif col in schema.boolean_columns:
                row[col] = True
            elif schema.allowed_values and col in schema.allowed_values:
                row[col] = schema.allowed_values[col][0]
            else:
                row[col] = "test_val"
        if "season" in schema.required:
            row["season"] = 2026
        dummy_df = pd.DataFrame([row])
        dummy_bytes = dummy_df.to_parquet(index=False)
        dummy_sha = hashlib.sha256(dummy_bytes).hexdigest()
        uri = f"artifacts/mock/repair26/{name}/data.parquet"
        storage.write_bytes(dummy_bytes, uri)
        output_refs[name] = {
            "dataset": ds,
            "version_id": "v1",
            "schema_version": f"data_first_{ds}_v2",
            "content_sha": dummy_sha,
            "uri": uri,
        }
        output_rows[name] = len(dummy_df)
    manifest_payload = signed_payload(
        {
            "schema_version": REPAIR_MANIFEST_SCHEMA,
            "state": "repaired_live_only",
            "identity": {"run_id": "mock-repair-2026", "code_sha": "x"},
            "production_activation_authorized": False,
            "output_refs": output_refs,
            "output_rows": output_rows,
            "population": {
                "scheduled_games": 2,
                "forecast_eligible_games": 2,
                "measurement_usable_games": 2,
            },
        }
    )
    manifest_uri = "artifacts/mock/repair26/repair-manifest.json"
    storage.write_bytes(canonical_bytes(manifest_payload), manifest_uri)
    return storage, manifest_uri


def test_repair_v3_default_state_gate_rejects_live() -> None:
    from scripts.research.verify_data_first_repair_v3 import verify_repair_artifact

    storage, manifest_uri = _make_live_repair_mock()
    with pytest.raises(RepairV2Error, match="schema or state mismatch"):
        verify_repair_artifact(storage, manifest_uri)


def test_repair_v3_expected_state_override_verifies_live() -> None:
    from scripts.research.verify_data_first_repair_v3 import verify_repair_artifact

    storage, manifest_uri = _make_live_repair_mock()
    result = verify_repair_artifact(
        storage, manifest_uri, expected_state="repaired_live_only"
    )
    assert result["status"] == "verified"
    assert result["verified_games"] == 2
    assert result["forbidden_2020_rows"] == 0
    assert result["producer_imports_present"] is False
