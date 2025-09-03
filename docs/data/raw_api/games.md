# Raw Game Schema

This schema describes the game data as returned by the `games` endpoint of the CollegeFootballData.com API.

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
