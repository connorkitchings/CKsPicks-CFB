# Opponent-Adjusted Schema

This schema describes the final opponent-adjusted dataset. These metrics are the primary features used for modeling.

**Derived From:** `transformed/team_season.md`

## Schema

The key for this dataset is `(season, team)`.

The columns are the opponent-adjusted versions of the core metrics from the `team_season` dataset, prefixed with `adj_`.

Example columns:
* `adj_off_epa_pp`
* `adj_def_sr`
* `adj_off_ypp`
* etc.
