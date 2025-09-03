# Raw Coach Schema

This schema describes the coach data as returned by the `coaches` endpoint of the CollegeFootballData.com API.

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
