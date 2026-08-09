import inspect

import cfbd


def test_pinned_cfbd_client_exposes_required_endpoint_contract():
    assert cfbd.__version__ == "5.20.1"
    expected = {
        (cfbd.GamesApi, "get_games"): {"year", "week", "season_type", "classification"},
        (cfbd.GamesApi, "get_game_team_stats"): {
            "year",
            "week",
            "season_type",
            "classification",
        },
        (cfbd.PlaysApi, "get_plays"): {
            "year",
            "week",
            "season_type",
            "classification",
        },
        (cfbd.BettingApi, "get_lines"): {"year", "week", "season_type"},
        (cfbd.TeamsApi, "get_teams"): {"year"},
    }
    for (api, method), required in expected.items():
        parameters = set(inspect.signature(getattr(api, method)).parameters)
        assert required.issubset(parameters), f"{api.__name__}.{method} changed"
