import pandas as pd

from cks_picks_cfb.features.situational import merge_situational_features
from cks_picks_cfb.features.weather import merge_weather_features


def test_neutral_site_travel_uses_registered_home_venues_and_dst():
    team_game = pd.DataFrame(
        [
            {"game_id": 1, "team": "A"},
            {"game_id": 1, "team": "B"},
        ]
    )
    games = pd.DataFrame(
        [
            {
                "id": 1,
                "start_date": "2026-08-29T16:00:00Z",
                "venue_id": 100,
                "home_team": "A",
                "away_team": "B",
                "neutral_site": True,
            }
        ]
    )
    teams = pd.DataFrame(
        [
            {"school": "A", "venue_id": 200},
            {"school": "B", "venue_id": 300},
        ]
    )
    venues = pd.DataFrame(
        [
            {
                "id": 100,
                "latitude": 40.7,
                "longitude": -74.0,
                "timezone": "America/New_York",
            },
            {
                "id": 200,
                "latitude": 34.0,
                "longitude": -118.2,
                "timezone": "America/Los_Angeles",
            },
            {
                "id": 300,
                "latitude": 41.9,
                "longitude": -87.6,
                "timezone": "America/Chicago",
            },
        ]
    )
    result = merge_situational_features(team_game, games, teams, venues).set_index(
        "team"
    )
    assert result.loc["A", "travel_distance_km"] > 3000
    assert result.loc["B", "travel_distance_km"] > 1000
    assert result.loc["A", "timezone_diff"] == 3
    assert result.loc["A", "eastward_travel"] == 1
    assert not result["travel_distance_missing"].any()


def test_weather_imputation_is_distinguishable_from_observed_calm_weather():
    team_game = pd.DataFrame([{"game_id": 1, "team": "A"}])
    result = merge_weather_features(team_game, pd.DataFrame())
    assert result.loc[0, "temperature"] == 70.0
    assert bool(result.loc[0, "weather_missing"])
    assert bool(result.loc[0, "temperature_missing"])
