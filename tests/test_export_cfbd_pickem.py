from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from scripts.pipeline.export_cfbd_pickem import (
    build_api_payload,
    format_cfbd_pickem_dataframe,
    submit_picks_to_api,
)


def test_format_cfbd_pickem_dataframe_success():
    raw_df = pd.DataFrame(
        [
            {
                "game_id": 401636830,
                "Home Team": "Georgia",
                "Away Team": "Clemson",
                "Spread Prediction": 13.54,
                "Total Prediction": 48.50,
            },
            {
                "game_id": 401636831,
                "Home Team": "Florida State",
                "Away Team": "Georgia Tech",
                "Spread Prediction": -2.30,
                "Total Prediction": 55.20,
            },
        ]
    )

    formatted = format_cfbd_pickem_dataframe(raw_df)

    assert len(formatted) == 2
    assert list(formatted["game_id"]) == [401636830, 401636831]
    assert list(formatted["gameId"]) == [401636830, 401636831]
    assert list(formatted["home_team"]) == ["Georgia", "Florida State"]
    assert list(formatted["away_team"]) == ["Clemson", "Georgia Tech"]
    assert list(formatted["projected_margin"]) == [13.54, -2.30]
    assert list(formatted["margin"]) == [13.54, -2.30]
    assert list(formatted["projected_total"]) == [48.50, 55.20]


def test_format_cfbd_pickem_dataframe_missing_column_raises():
    raw_df = pd.DataFrame(
        [
            {
                "game_id": 401636830,
                "Home Team": "Georgia",
                # missing away team & spread prediction
            }
        ]
    )

    with pytest.raises(KeyError, match="Away Team"):
        format_cfbd_pickem_dataframe(raw_df)


def test_build_api_payload():
    pickem_df = pd.DataFrame(
        [
            {
                "game_id": 401636830,
                "projected_margin": 14.5,
                "projected_total": 51.0,
            },
            {
                "game_id": 401636831,
                "projected_margin": -3.0,
                "projected_total": 45.5,
            },
        ]
    )

    payload = build_api_payload(pickem_df)

    assert len(payload) == 2
    assert payload[0] == {"gameId": 401636830, "margin": 14.5, "projectedTotal": 51.0}
    assert payload[1] == {"gameId": 401636831, "margin": -3.0, "projectedTotal": 45.5}


def test_submit_picks_to_api_missing_key_raises():
    with pytest.raises(
        ValueError, match="CFBD_API_KEY environment variable is required"
    ):
        submit_picks_to_api([], api_key="", api_url="https://example.com/api/picks")


@patch("urllib.request.urlopen")
def test_submit_picks_to_api_success(mock_urlopen):
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = b'{"success": true, "count": 2}'
    mock_urlopen.return_value.__enter__.return_value = mock_response

    payload = [{"gameId": 401636830, "margin": 14.5}]
    res = submit_picks_to_api(
        payload, api_key="test_token", api_url="https://example.com/api/picks"
    )

    assert res["status"] == 200
    assert res["response"] == {"success": True, "count": 2}
    mock_urlopen.assert_called_once()
