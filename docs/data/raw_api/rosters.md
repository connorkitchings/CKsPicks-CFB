# Raw Roster Schema

This schema describes the roster data as returned by the `roster` endpoint of the CollegeFootballData.com API.

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
