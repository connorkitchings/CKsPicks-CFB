# Raw Betting Schema

This schema describes the betting data as returned by the `lines` endpoint of the CollegeFootballData.com API. It consists of a `BettingGame` object that contains a list of `BettingLine` objects.

## BettingGame Schema

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

## BettingLine (Line) Schema

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
