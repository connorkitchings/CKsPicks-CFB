# Feature Pack Discrepancy Analysis

## Executive Summary

We investigated the feature count discrepancies and the presence of weather features in the standard model. Key findings:

1.  **Unintentional Feature Inclusion**: The `standard_v1` feature pack automatically includes _all_ columns ending in `_last_3` via a wildcard in `src/features/selector.py`. This means once weather features were added to the pipeline and `team_week_adj` cache, their recency aggregates (`home_temperature_last_3`, etc.) were immediately ingested into the standard model, even though the `weather_stats` group was not explicitly enabled.
2.  **Missing Forecast Data**: The `standard_v1` pack does **not** include the `weather_stats` group (`temperature`, `precipitation`, `wind_speed`). Consequently, the model trains on _past_ weather conditions (via recency) but lacks information about the _current_ game's weather forecast.
3.  **Feature Count Volatility**: The "79 vs 87" discrepancy noted in previous logs likely stems from this dynamic expansion. As new features (like weather or advanced rushing stats) are added to the upstream pipeline, the feature count for `standard_v1` grows automatically unless explicitly excluded.

## Technical Root Cause

In `src/features/selector.py`:

```python
    # Expand recency stats dynamically if requested
    if "recency_stats" in groups:
        # ...
        suffix = suffix_map.get(recency_window, "_last_3")

        # Scan dataframe for all columns matching the recency pattern
        recency_cols = [c for c in df.columns if c.endswith(suffix)]

        # Add to feature list
        feature_cols.extend(recency_cols)
```

This logic is "greedy"—it grabs every available recency feature.

## Implications

- **Noise Injection**: We are feeding the model "weather history" (which has low predictive value for a single game) without the corresponding "current weather" context. This likely adds noise without signal.
- **Evaluation Validity**: Previous "weather vs baseline" comparisons were flawed. The "baseline" actually contained partial weather data (recency), while the "weather" model added the current forecast.
- **Configuration Drift**: The definition of "standard" changes whenever the upstream pipeline adds features.

## Recommendations

1.  **Explicit Feature Allow-listing**: Move away from wildcard expansion for `recency_stats`. Define explicit lists of base features that should have recency versions included.
2.  **Fix Standard Model**: Either remove weather recency features from `standard_v1` (to make it a true baseline) or add the current `weather_stats` group (to properly utilize weather info).
3.  **Re-evaluate Weather**: Run a proper experiment comparing:
    - Baseline: No weather features (exclude `*temperature*`, `*wind*`, `*precipitation*`).
    - Weather: Current forecast + Recency history.
