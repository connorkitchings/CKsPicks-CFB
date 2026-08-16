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
