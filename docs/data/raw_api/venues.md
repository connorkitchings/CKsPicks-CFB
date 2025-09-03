# Raw Venue Schema

This schema describes the venue data as returned by the `venues` endpoint of the CollegeFootballData.com API.

*Note: The API response for venues is a list of dictionaries, but the structure of each dictionary is not explicitly defined in the same way as other schemas. The fields listed below are based on observed responses.*

- **Key Fields:**
    - `name`: str
    - `capacity`: int
    - `city`: str
    - `state`: str
    - `zip`: str
    - `country_code`: str
    - `location`: dict (contains latitude, longitude, elevation)
    - `year_constructed`: int
    - `dome`: bool
    - `grass`: bool
    - `surface`: str
