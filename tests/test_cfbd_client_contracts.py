from __future__ import annotations

from importlib.metadata import version

import cfbd


def test_cfbd_client_is_on_the_validated_release_series():
    assert tuple(map(int, version("cfbd").split(".")[:3])) == (5, 20, 1)


def test_current_recruit_and_live_game_contract_shapes_parse():
    recruit = cfbd.Recruit.parse_obj(
        {
            "id": "synthetic-recruit",
            "athleteId": "1",
            "recruitType": "HighSchool",
            "year": 2025,
            "ranking": 1,
            "name": "Synthetic Recruit",
            "school": "Example High",
            "committedTo": "Example University",
            "position": "QB",
            "height": 72,
            "weight": 200,
            "stars": 4,
            "rating": 0.95,
            "city": "Example City",
            "stateProvince": "EX",
            "country": "USA",
            "hometownInfo": {"fipsCode": "00000", "longitude": 0.0, "latitude": 0.0},
        }
    )
    live_game = cfbd.LiveGame.parse_obj(
        {
            "id": 1,
            "status": "scheduled",
            "period": 0,
            "clock": "15:00",
            "possession": "Example University",
            "down": 1,
            "distance": 10,
            "yardsToGoal": 75,
            "teams": [],
            "drives": [],
        }
    )

    assert recruit.name == "Synthetic Recruit"
    assert live_game.status == "scheduled"
