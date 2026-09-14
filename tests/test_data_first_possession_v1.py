"""Schema and population safeguards for V5 possession certification."""

import pandas as pd
import pytest

from cks_picks_cfb.data.data_first_possession_v1 import (
    POSSESSION_DATASETS,
    PossessionContractError,
    build_population,
)
from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame


def test_population_rejects_forbidden_2020_before_measurement_join():
    frame = pd.DataFrame(
        [
            {
                "season": 2020,
                "week": 1,
                "game_id": 1,
                "kickoff_utc": "2020-01-01T00:00:00Z",
                "home_team": "A",
                "away_team": "B",
                "schedule_completed": True,
                "outcome_valid": True,
                "forecast_eligible": True,
                "measurement_usable": True,
                "missing_reason": None,
                "disposition": "x",
                "timing_class": "historically_reconstructed",
            }
        ]
    )
    with pytest.raises(PossessionContractError, match="impermissible season"):
        build_population(frame)


def test_possession_observation_schema_rejects_duplicate_role_keys():
    dataset, version = POSSESSION_DATASETS["observations"]
    frame = pd.DataFrame(
        [
            {
                "season": 2025,
                "week": 1,
                "game_id": 1,
                "kickoff_utc": "2025-01-01T00:00:00Z",
                "team": "A",
                "opponent": "B",
                "side": "home",
                "measurement_id": "ppp",
                "unit_role": "offense",
                "numerator": 1.0,
                "denominator": 1.0,
                "raw_value": 1.0,
                "usable_exposure": 1.0,
                "exposure_unit": "possessions",
                "coverage_status": "observed",
                "missing_reason": None,
                "quality_flags": None,
                "timing_class": "historically_reconstructed",
            }
        ]
        * 2
    )
    with pytest.raises(Exception, match="duplicate"):
        validate_frame(frame, schema_for(dataset, version))
