import pandas as pd
import pytest

from cks_picks_cfb.data.schema_contracts import (
    DatasetSchemaError,
    schema_for,
    validate_frame,
)


def test_games_schema_accepts_typed_canonical_rows():
    frame = pd.DataFrame(
        [
            {
                "season": 2026,
                "game_id": 1,
                "week": 0,
                "provider_week": 1,
                "kickoff_utc": "2026-08-29T18:00:00Z",
                "home_team": "Home",
                "away_team": "Away",
            }
        ]
    )
    validation = validate_frame(frame, schema_for("games", "games_v2"))
    assert validation["schema_valid"] is True


def test_games_schema_rejects_non_integral_game_id():
    frame = pd.DataFrame(
        [
            {
                "season": 2026,
                "game_id": 1.5,
                "week": 0,
                "provider_week": 1,
                "kickoff_utc": "2026-08-29T18:00:00Z",
                "home_team": "Home",
                "away_team": "Away",
            }
        ]
    )
    with pytest.raises(DatasetSchemaError, match="game_id"):
        validate_frame(frame, schema_for("games", "games_v2"))


def _byplay_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "season": 2015,
                "week": 1,
                "game_id": 1,
                "drive_number": 1,
                "play_number": 1,
                "offense": "Home",
                "defense": "Away",
                "st": 0,
                "penalty": 0,
                "twopoint": 0,
                "play_type": "Rush",
                "garbage": 0,
                "ppa": 0.1,
                "success": 1,
                "yards_gained": 5,
                "turnover": 0,
                "quarter": 1,
                "offense_score": 0,
                "defense_score": 0,
            }
        ]
    )


def _drives_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "season": 2015,
                "week": 1,
                "game_id": 1,
                "drive_number": 1,
                "offense": "Home",
                "defense": "Away",
                "start_yards_to_goal": 75,
                "had_scoring_opportunity": 0,
                "points": 0,
                "points_on_opps": 0,
            }
        ]
    )


def _reconciliation_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "reconciliation_id": "abc",
                "season": 2015,
                "game_id": 1,
                "classification": "exact_match",
                "blocking": False,
                "details": "{}",
                "policy_version": "team_game_reconciliation_v1",
            }
        ]
    )


def test_derived_silver_schemas_accept_r1_measurement_inputs():
    validate_frame(_byplay_frame(), schema_for("byplay", "byplay_v1"))
    validate_frame(_drives_frame(), schema_for("drives", "drives_v1"))
    validate_frame(
        _reconciliation_frame(),
        schema_for("source_reconciliation", "reconciliation_v1"),
    )


def test_derived_silver_schemas_reject_wrong_versions_and_bad_keys():
    with pytest.raises(DatasetSchemaError, match="must use schema version byplay_v1"):
        schema_for("byplay", "byplay_v2")

    duplicate = pd.concat([_drives_frame(), _drives_frame()], ignore_index=True)
    with pytest.raises(DatasetSchemaError, match="duplicate keys"):
        validate_frame(duplicate, schema_for("drives", "drives_v1"))


def test_reconciliation_schema_rejects_unknown_classification():
    frame = _reconciliation_frame()
    frame.loc[0, "classification"] = "ignored"
    with pytest.raises(DatasetSchemaError, match="unsupported values"):
        validate_frame(frame, schema_for("source_reconciliation", "reconciliation_v1"))
