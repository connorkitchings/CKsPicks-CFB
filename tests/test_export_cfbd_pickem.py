from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from scripts.pipeline.export_cfbd_pickem import (
    PICKEM_API_URL,
    build_api_payload,
    fetch_pickem_games,
    format_cfbd_pickem_dataframe,
    reconcile_pickem_games,
    submit_picks_to_api,
)


def test_format_pickem_uses_documented_game_id_and_pick_fields():
    formatted = format_cfbd_pickem_dataframe(
        pd.DataFrame(
            [{"game_id": 401636830, "Spread Prediction": 13.54, "Home Team": "Georgia"}]
        )
    )
    assert formatted.loc[0, "gameId"] == 401636830
    assert formatted.loc[0, "pick"] == 13.54
    assert "projected_total" not in formatted


def test_build_payload_excludes_non_contest_fields():
    payload = build_api_payload(pd.DataFrame([{"gameId": 1, "pick": -3.5, "total": 52.0}]))
    assert payload == [{"gameId": 1, "pick": -3.5}]


def test_format_pickem_accepts_reviewed_export_as_exact_input():
    reviewed = pd.DataFrame(
        [{"gameId": 401636830, "pick": 13.54, "home_team": "Georgia"}]
    )

    assert format_cfbd_pickem_dataframe(reviewed).to_dict("records") == [
        {"gameId": 401636830, "pick": 13.54, "home_team": "Georgia"}
    ]


def test_reconciliation_never_fills_unsupported_contest_games():
    frame = pd.DataFrame([{"gameId": 1, "pick": 2.0}, {"gameId": 3, "pick": -1.0}])
    result = reconcile_pickem_games(frame, [{"id": 1}, {"id": 2}])
    assert result.to_dict() == {
        "matched_game_ids": [1],
        "unsupported_contest_game_ids": [2],
        "unavailable_model_game_ids": [3],
        "matched_count": 1,
        "unsupported_contest_count": 1,
        "unavailable_model_count": 1,
    }


@patch("urllib.request.urlopen")
def test_fetch_uses_prediction_token_and_pickem_host(mock_urlopen):
    response = MagicMock()
    response.read.return_value = b'[{"id": 123}]'
    mock_urlopen.return_value.__enter__.return_value = response
    assert fetch_pickem_games("prediction-token") == [{"id": 123}]
    request = mock_urlopen.call_args.args[0]
    assert request.full_url == PICKEM_API_URL
    assert request.get_method() == "GET"
    assert request.get_header("Authorization") == "Bearer prediction-token"


@patch("urllib.request.urlopen")
def test_submit_posts_one_documented_payload_per_game(mock_urlopen):
    response = MagicMock()
    response.read.return_value = b""
    mock_urlopen.return_value.__enter__.return_value = response
    submit_picks_to_api(
        [{"gameId": 1, "pick": 2.5}, {"gameId": 2, "pick": -1.0}],
        "prediction-token",
        request_delay_seconds=0,
    )
    assert mock_urlopen.call_count == 2
    first = mock_urlopen.call_args_list[0].args[0]
    assert first.get_method() == "POST"
    assert json_loads(first.data) == {"gameId": 1, "pick": 2.5}


def json_loads(value):
    import json

    return json.loads(value.decode("utf-8"))


def test_api_operations_require_prediction_token():
    with pytest.raises(ValueError, match="CFBD_PREDICTION_TOKEN"):
        fetch_pickem_games("")
