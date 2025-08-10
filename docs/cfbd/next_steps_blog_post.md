# Blog Post: Use the CFBD Python Client to Extend Your Starter Pack

This document summarizes the key takeaways from the CFBD blog post on extending the Starter Pack data.

**Source:** [https://blog.collegefootballdata.com/starter-pack-next-steps/](https://blog.collegefootballdata.com/starter-pack-next-steps/)

---

## Key Steps & Examples

The post outlines a clear, three-step process for augmenting existing data with fresh, API-driven data.

### 1. Installation & Configuration

- **Install Client:** `pip install cfbd`
- **Set API Key:** Store the key as an environment variable (`BEARER_TOKEN` or `CFBD_API_KEY`) and
  configure the `cfbd.Configuration` object.

### 2. Fetching Data

The `cfbd.ApiClient` context manager is the standard way to interact with the API. The post provides
practical examples for fetching:

- **Recent Games:** `GamesApi.get_games()`
- **Team Box Scores:** `GamesApi.get_game_team_stats()`
- **Historical Betting Lines:** `BettingApi.get_lines()`

### 3. Combining Data & Watching Limits

- **Strategy:** The primary recommendation is to merge recent data fetched from the API with the
  historical data from the Starter Pack to keep models and analyses current.
- **Rate Limits:** Free tier users are limited to 1,000 calls/month. The `InfoApi.get_user_info()`
  endpoint can be used to check remaining calls without consuming a call.

---

This reinforces our strategy of using the `cfbd-python` client as the primary tool for data ingestion.
