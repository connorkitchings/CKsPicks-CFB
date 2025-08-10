# CollegeFootballData API Schemas

This document catalogs the data schemas for all major endpoints relevant to the cfb_model project.
Use these as the reference for structuring the local Parquet dataset and ingestion logic.

---

## 1. Game Schema

```python
{
    'attendance': int,
    'awayClassification': str,
    'awayConference': str,
    'awayId': int,
    'awayLineScores': List[int],
    'awayPoints': int,
    'awayPostgameElo': int,
    'awayPostgameWinProbability': float,
    'awayPregameElo': int,
    'awayTeam': str,
    'completed': bool,
    'conferenceGame': bool,
    'excitementIndex': float,
    'highlights': str,
    'homeClassification': str,
    'homeConference': str,
    'homeId': int,
    'homeLineScores': List[int],
    'homePoints': int,
    'homePostgameElo': int,
    'homePostgameWinProbability': float,
    'homePregameElo': int,
    'homeTeam': str,
    'id': int,
    'neutralSite': bool,
    'notes': Optional[str],
    'season': int,
    'seasonType': str,
    'startDate': datetime,
    'startTimeTBD': bool,
    'venue': str,
    'venueId': int,
    'week': int
}
```

## 2. Play Schema

```python
{
    'away': str,
    'clock': {'minutes': int, 'seconds': int},
    'defense': str,
    'defenseConference': str,
    'defenseScore': int,
    'defenseTimeouts': int,
    'distance': int,
    'down': int,
    'driveId': str,
    'driveNumber': int,
    'gameId': int,
    'home': str,
    'id': str,
    'offense': str,
    'offenseConference': str,
    'offenseScore': int,
    'offenseTimeouts': int,
    'period': int,
    'playNumber': int,
    'playText': str,
    'playType': str,
    'ppa': float,
    'scoring': bool,
    'wallclock': str,
    'yardline': int,
    'yardsGained': int,
    'yardsToGoal': int
}
```

## 3. Drive Schema

```python
{
    'defense': str,
    'defenseConference': str,
    'driveNumber': int,
    'driveResult': str,
    'endDefenseScore': int,
    'endOffenseScore': int,
    'endPeriod': int,
    'endTime': {'minutes': int, 'seconds': int},
    'endYardline': int,
    'endYardsToGoal': int,
    'gameId': int,
    'id': str,
    'isHomeOffense': bool,
    'offense': str,
    'offenseConference': str,
    'plays': int,
    'scoring': bool,
    'startDefenseScore': int,
    'startOffenseScore': int,
    'startPeriod': int,
    'startTime': {'minutes': int, 'seconds': int},
    'startYardline': int,
    'startYardsToGoal': int,
    'yards': int
}
```

## 4. BettingLine (Game) Schema

```python
{
    'awayClassification': str,
    'awayConference': str,
    'awayScore': int,
    'awayTeam': str,
    'homeClassification': str,
    'homeConference': str,
    'homeScore': int,
    'homeTeam': str,
    'id': int,
    'lines': List[BettingLine],
    'season': int,
    'seasonType': str,
    'startDate': datetime,
    'week': int
}
```

## 5. BettingLine (Line) Schema

```python
{
    'awayMoneyline': Optional[float],
    'formattedSpread': str,
    'homeMoneyline': Optional[float],
    'overUnder': float,
    'overUnderOpen': Optional[float],
    'provider': str,
    'spread': float,
    'spreadOpen': Optional[float]
}
```

## 6. TeamInfo Schema

```python
{
    'abbreviation': str,
    'alternateColor': str,
    'alternateNames': List[str],
    'classification': str,
    'color': str,
    'conference': str,
    'division': Optional[str],
    'id': int,
    'location': {
        'capacity': int,
        'city': str,
        'constructionYear': int,
        'countryCode': str,
        'dome': bool,
        'elevation': str,
        'grass': bool,
        'id': int,
        'latitude': float,
        'longitude': float,
        'name': str,
        'state': str,
        'timezone': str,
        'zip': str
    },
    'logos': List[str],
    'mascot': str,
    'school': str,
    'twitter': str
}
```

## 7. RosterInfo Schema

```python
{
    'firstName': str,
    'height': int,
    'homeCity': str,
    'homeCountry': str,
    'homeCountyFIPS': str,
    'homeLatitude': float,
    'homeLongitude': float,
    'homeState': str,
    'id': str,
    'jersey': int,
    'lastName': str,
    'position': str,
    'recruitIds': List[str],
    'team': str,
    'weight': int,
    'year': int
}
```

## 8. AdvancedGameStat Schema

```python
{
    'defense': dict,  # Nested stats for defense (see sample output)
    'gameId': int,
    'offense': dict,  # Nested stats for offense (see sample output)
    'opponent': str,
    'season': int,
    'team': str,
    'week': int
}
```

---

## 9. Coach Schema

```python
{
    'firstName': str,
    'hireDate': datetime,
    'lastName': str,
    'seasons': [
        {
            'games': int,
            'losses': int,
            'postseasonRank': Optional[int],
            'preseasonRank': Optional[int],
            'school': str,
            'spDefense': float,
            'spOffense': float,
            'spOverall': float,
            'srs': float,
            'ties': int,
            'wins': int,
            'year': int
        }
    ]
}
```

---

**Note:**

- The following endpoints are NOT available in cfbd-python 5.9.1 and could not be documented:
  - Metrics (get_metrics, get_advanced_team_metrics)
  - Ratings (get_ratings)
  - Recruiting (get_recruiting_players)
- If you upgrade cfbd-python, revisit these endpoints to extract and document their schemas.
- All schemas are based on actual API responses from 2023 Week 1. Types may be inferred from
  observed values and cfbd-python models.
- For nested fields (like defense/offense in AdvancedGameStat), see the sample output or cfbd-python
  docs for detailed structure.
- Use these schemas as the source of truth for structuring Parquet files and ingestion logic.
