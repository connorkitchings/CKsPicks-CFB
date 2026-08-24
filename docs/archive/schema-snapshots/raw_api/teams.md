# Raw Team Schema

This schema describes the team data as returned by the `teams` endpoint of the CollegeFootballData.com API.

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
