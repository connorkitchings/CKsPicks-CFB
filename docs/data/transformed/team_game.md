# Transformed Team-Game Schema

This schema describes the team-game dataset, which represents a team's performance in a single game. It is aggregated from the `byplay` and `drives` data.

**Derived From:** `transformed/plays.md`, `transformed/drives.md`

## Schema

The key for this dataset is `(season, week, game_id, team)`.

**Offensive Metrics:**

- `n_off_plays`
- `n_rush_plays`
- `n_pass_plays`
- `off_sr` (Success Rate)
- `off_ypp` (Yards Per Play)
- `off_epa_pp` (EPA Per Play)
- `off_expl_rate_overall_10` (Explosive Play Rate >= 10 yards)
- `off_expl_rate_overall_20`
- `off_expl_rate_overall_30`
- `off_expl_rate_rush`
- `off_expl_rate_pass`
- `stuff_rate` (Percentage of rushes stopped for zero or negative yards)
- `havoc_rate` (Rate of plays resulting in TFL, forced fumble, interception, or pass breakup)
- `off_drives`
- `off_eckel_rate`
- `off_finish_pts_per_opp` (Points per scoring opportunity)
- `off_avg_line_yards`
- `off_power_success_rate`
- `off_avg_second_level_yards`
- `off_avg_open_field_yards`

**Defensive Metrics (Allowed by the team's defense):**

- `def_sr`
- `def_ypp`
- `def_epa_pp`
- `def_expl_rate_overall_10`
- `def_expl_rate_overall_20`
- `def_expl_rate_overall_30`
- `def_expl_rate_rush`
- `def_expl_rate_pass`
- `def_successful_drive_rate_allowed`
- `def_busted_drive_rate_forced`
- `def_explosive_drive_rate_allowed`
- `def_power_success_rate_allowed`
- `def_avg_line_yards_allowed`
- `def_avg_second_level_yards_allowed`
- `def_avg_open_field_yards_allowed`
- `def_avg_net_punt_yards_allowed`
- `def_fg_rate_allowed_short`
- `def_fg_rate_allowed_mid`
- `def_fg_rate_allowed_long`

**Variance Metrics:**

- `luck_factor`: The difference between the actual game margin and the PPA-based expected margin.
