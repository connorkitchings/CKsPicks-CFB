# CollegeFootballData.com (CFBD) API Quickstart Guide

This guide summarizes how to collect college football data using the CFBD API and its official
Python client, following the Vibe Coding System and project standards.

---

## 1. API Overview

- **Base URL:** <https://api.collegefootballdata.com>
- **Swagger Docs:** [https://apinext.collegefootballdata.com/](https://apinext.collegefootballdata.com/)
- **Python Client:** [cfbd-python](https://github.com/CFBD/cfbd-python)

---

## 2. Authentication

- All requests require a Bearer API key.
- Store your API key in your `.env` file as `CFBD_API_KEY`.
- Example (Python):

  ```python
  import os
  import cfbd
  from cfbd.rest import ApiException

  configuration = cfbd.Configuration(
      access_token=os.environ["CFBD_API_KEY"]
  )
  ```

---

## 3. Python Client Installation

```bash
pip install cfbd
```

---

## 4. Example Usage

```python
import cfbd
from cfbd.rest import ApiException
from pprint import pprint
import os

configuration = cfbd.Configuration(
    access_token=os.environ["CFBD_API_KEY"]
)

with cfbd.ApiClient(configuration) as api_client:
    api_instance = cfbd.GamesApi(api_client)
    try:
        games = api_instance.get_games(year=2024, season_type="regular")
        pprint(games)
    except ApiException as e:
        print(f"Exception when calling GamesApi->get_games: {e}")
```

---

## 5. Key API Endpoints (Python Methods)

- **Games:** `GamesApi.get_games`, `GamesApi.get_advanced_box_score`,
  `GamesApi.get_game_player_stats`, `GamesApi.get_game_team_stats`
- **Plays:** `PlaysApi.get_plays`, `PlaysApi.get_play_stats`, `PlaysApi.get_play_types`
- **Teams:** `TeamsApi.get_teams`, `TeamsApi.get_roster`, `TeamsApi.get_team_talent`
- **Players:** `PlayersApi.search_players`, `PlayersApi.get_player_usage`, `PlayersApi.get_returning_production`
- **Betting:** `BettingApi.get_lines`
- **Recruiting:** `RecruitingApi.get_recruits`, `RecruitingApi.get_aggregated_team_recruiting_ratings`
- **Rankings:** `RankingsApi.get_rankings`
- **Conferences:** `ConferencesApi.get_conferences`
- **Metrics:** `MetricsApi.get_predicted_points`, `MetricsApi.get_win_probability`

See [cfbd-python API docs](https://github.com/CFBD/cfbd-python#documentation-for-api-endpoints) for
the full list.

---

## 6. Data Models

- Each endpoint returns Python objects or lists of objects (see [cfbd-python models](https://github.com/CFBD/cfbd-python#documentation-for-models)).
- Example models: `Game`, `Play`, `Team`, `Player`, `BettingGame`, `AdvancedBoxScore`, etc.

---

## 7. References

- [Swagger API Docs](https://apinext.collegefootballdata.com/)
- [cfbd-python GitHub](https://github.com/CFBD/cfbd-python)
- [cfbd-python API Endpoints](https://github.com/CFBD/cfbd-python#documentation-for-api-endpoints)
- [cfbd-python Models](https://github.com/CFBD/cfbd-python#documentation-for-models)

---

## 8. Next Steps

- Review the endpoints and models relevant to your project’s data needs.
- Prototype data pulls using the Python client.
- Document any custom queries or data transformations for your workflow.

---

_This file is maintained according to the Vibe Coding System. Link to this guide from your session
logs or planning docs as [CFBD-guide:Quickstart]._
