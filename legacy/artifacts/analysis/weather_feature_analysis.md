# Weather Feature Analysis

## Current Status

- **Infrastructure**: Complete. Weather data (temp, wind, precip) is ingested and flowing through the pipeline.
- **Model Usage**: Weather features _are_ present in the current standard model, but only as **recency aggregates** (e.g., `home_temperature_last_3`).
- **Performance**: Weather features rank relatively low in importance (Rank ~44-100).
  - `home_temperature_last_3`: Rank 44 (Spread), Rank ~100 (Total)
  - `away_wind_speed_last_3`: Rank 47 (Spread)

## The Critical Gap

The standard model configuration (`standard_v1`) **excludes** the `weather_stats` group, which contains the _current game's_ weather forecast (`temperature`, `precipitation`, `wind_speed`).

However, it **includes** `recency_stats`, which effectively grabs _all_ columns ending in `_last_3`. Since weather features are now in the `team_week_adj` cache, their recency versions are automatically included.

**Result**: The model knows if a team played in the rain _last week_, but it doesn't know if it's raining _today_.

## Why This Matters

- **Low Predictive Value**: Past weather is a poor predictor of future game outcomes unless it captures a team's "weather identity" (e.g., "bad weather team").
- **Missing Signal**: The actual impact of weather (wind affecting passing, rain affecting turnovers) is driven by the _current_ conditions, which are missing from the model inputs.
- **Noise**: Including only past weather likely adds noise, potentially degrading performance (as seen in the +0.22 RMSE regression).

## Recommendations

1.  **Immediate Fix**: Add `weather_stats` group to the production feature pack (`standard_v1.yaml`) to include current game forecasts.
2.  **Interaction Terms**: Weather impact is rarely linear. Wind speed matters more for passing teams. Rain matters more for turnover-prone teams.
    - Candidate: `wind_speed * passing_rate`
    - Candidate: `precipitation * fumble_rate`
3.  **Dome Indicator**: Explicitly model dome games (where weather = 0/controlled). The current ingestion maps stadiums, so we should ensure `is_dome` is a feature.

## Conclusion

Weather features haven't "failed"; they haven't really been tried yet. We've only tested "weather history," which is expected to be low-impact. The next step is to enable current weather forecasts and test interactions.
