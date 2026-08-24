# Raw Play Schema

This schema describes the play-by-play data as returned by the `plays` endpoint of the CollegeFootballData.com API.

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
