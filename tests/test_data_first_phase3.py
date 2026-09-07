"""Pure contracts for the Preview-only data-first Phase 3 path."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest

from cks_picks_cfb.data.data_first_phase2 import DEVELOPMENT_SEASONS
from cks_picks_cfb.data.data_first_phase2d import PHASE3_DATASETS, signed_payload
from cks_picks_cfb.data.data_first_phase3 import (
    CORE_CANDIDATES,
    Phase3Error,
    retained_core,
    verify_core_eligibility,
)
from cks_picks_cfb.ratings.contracts import load_measurement_config

ROOT = Path(__file__).resolve().parents[1]


def _manifest() -> dict:
    refs = []
    for season in DEVELOPMENT_SEASONS:
        for dataset in sorted(PHASE3_DATASETS):
            refs.append({"season": season, "dataset": dataset, "version_id": f"{season}-{dataset}", "schema_version": "v1", "content_sha": f"sha-{season}-{dataset}", "uri": f"lake/{season}/{dataset}", "eligible": True, "permitted_uses": ["phase3_measurement_validation"]})
    return signed_payload({"schema_version": "data_first_phase2_eligibility_v3", "state": "eligible", "development_seasons": list(DEVELOPMENT_SEASONS), "forbidden_seasons": [2020], "production_activation_authorized": False, "phase3_input_refs": refs})


def _losses() -> pd.DataFrame:
    rows = []
    for candidate in CORE_CANDIDATES:
        error = 10.0 if candidate == "epa_only" else 9.8
        for target in ("margin", "total"):
            for game_id in (1, 2):
                rows.append({"candidate": candidate, "target": target, "season": 2024, "week": game_id, "game_id": game_id, "absolute_error": error, "bootstrap_excludes_zero": True, "coverage_equal": True, "seasonal_gate_passed": True})
    return pd.DataFrame(rows)


def test_core_eligibility_requires_the_exact_seventy_refs():
    assert len(verify_core_eligibility(_manifest())) == 70
    broken = deepcopy(_manifest())
    broken["phase3_input_refs"].pop()
    broken = signed_payload(broken)
    with pytest.raises(Phase3Error, match="exactly 70"):
        verify_core_eligibility(broken)


def test_core_eligibility_rejects_signature_drift():
    broken = _manifest()
    broken["state"] = "ineligible"
    with pytest.raises(Phase3Error):
        verify_core_eligibility(broken)


def test_retained_core_uses_simplicity_when_candidates_are_within_half_percent():
    result = retained_core(_losses())
    assert result["selected_candidate"] == "epa_pass_rush"


def test_retained_core_falls_back_to_epa_only_without_required_lift():
    losses = _losses()
    losses.loc[losses["candidate"] != "epa_only", "absolute_error"] = 9.99
    assert retained_core(losses)["selected_candidate"] == "epa_only"


def test_phase3_config_is_the_complete_ten_season_measurement_contract():
    config = load_measurement_config(
        ROOT / "conf/research/data_first_football_v1/phase3_measurement_core_v1.yaml"
    )
    assert config.historical_development_seasons == DEVELOPMENT_SEASONS
    assert config.forbidden_seasons == (2020,)
    assert config.research_prefix == "artifacts/research/data-first-football-v1/phase3"
