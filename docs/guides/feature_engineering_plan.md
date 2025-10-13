# Feature Engineering Plan

This note outlines the staged aggregation flow for turning raw CFBD play-by-play into
season-to-date features ready for opponent adjustment.

---

## Goals

- Produce reliable, reproducible team-game and team-season feature sets.
- Follow a staged pipeline with clear inputs/outputs and validation points.
- Stay aligned with `docs/project_org/modeling_baseline.md` and `docs/project_org/feature_catalog.md`.

---

## Staged Aggregation

1. Plays → Enhanced Plays

- Input: Raw plays for a season.
- Transformations: normalize fields (clock → seconds, yardline/possession fields), create boolean
  indicators (rush/pass, success, explosiveness, penalty, sack, turnover, garbage_time flag),
  standardize team columns (`offense`, `defense`).
- Output: CSV partitions under `processed/byplay/year/<YYYY>/...`
- Schema basis: see `docs/cfbd/schemas.md` ("Play Schema").

1. Enhanced Plays → Drives

- Group by continuous possessions to summarize per-drive metrics (plays, yards, points, success
  rate, EPA/PPA totals/means, time of possession, result).
- If a canonical drive table is available, align to that; otherwise reconstruct via possession
  changes and scoring events.
- Output: CSV partitions under `processed/drives/year/<YYYY>/...`

1. Drives → Team-Game

- Aggregate by game and team: tempo, success rates, explosiveness, early/late down splits,
  red zone, penalties, turnovers, special teams, field position, finishing drives.
- Output: CSV partitions under `processed/team_game/year/<YYYY>/...`

1. Team-Game → Team-Season-to-Date

- Cumulative and rolling aggregates through each week (exclude current game when training/predicting).
- Apply recency weights (3/2/1) per `docs/project_org/feature_catalog.md`.
- Output: CSV partitions under `processed/team_season/year/<YYYY>/...`

1. Opponent Adjustment (next phase)

- Iterative opponent adjustment per feature catalog (4 passes, league-mean centering), producing
   opponent-adjusted season features.
- Output: CSV partitions under `processed/team_season_adj/year/<YYYY>/...`

---

## Feature Engineering Source of Truth

The definitive and canonical implementation of all feature engineering logic resides in the Python modules within the `src/cfb_model/data/aggregations/` directory. This includes play-level transformations, aggregations to drives and games, and the point-in-time feature generation required to prevent data leakage.

The `CFB_Functions.ipynb` notebook, which previously contained exploratory work, is now considered deprecated. It should only be used as a historical or conceptual reference. For any development or validation work, the code in the `src` directory is the single source of truth.

---

## Validation & Manifests

- Each processed partition includes a `manifest.json` with row counts and metadata.
- Add a season summary CSV under `reports/metrics/` (e.g., `features_<year>_summary.csv`).

---

## References

- Modeling baseline: `docs/project_org/modeling_baseline.md`
- Feature catalog: `docs/project_org/feature_catalog.md`
- CFBD schemas: `docs/cfbd/schemas.md`

---

## Advanced Feature Engineering (Implemented)

This section details the high-value features that have been implemented in the model.

### 1. Advanced Rushing Analytics

These metrics go beyond simple yards-per-carry to evaluate the quality of a team's rushing attack and run defense by attributing credit to the offensive line and the runner.

*   **Source Data**: `processed/byplay/` (Enhanced Plays)
*   **Aggregation Level**: Plays -> Team-Game -> Team-Season-to-Date

**Feature Definitions:**

*   **`off_line_yards` / `def_line_yards`**:
    *   **Definition**: The portion of a rush credited to the offensive line. It's calculated based on the yards gained on the play, capped at a certain threshold (e.g., 0-3 yards: 100% of yards, 4-8 yards: 50%, 9+ yards: 0%).
    *   **Logic**: For each rushing play, calculate `line_yards`. Then, aggregate the average `line_yards_per_rush` at the team-game level for both offense and defense.

*   **`off_second_level_yards` / `def_second_level_yards`**:
    *   **Definition**: Yards gained between 5-10 yards past the line of scrimmage, credited to the runner for breaking past the front seven.
    *   **Logic**: For each rushing play, calculate yards gained in this zone. Aggregate the average `second_level_yards_per_rush` at the team-game level.

*   **`off_open_field_yards` / `def_open_field_yards`**:
    *   **Definition**: Yards gained 10+ yards past the line of scrimmage, representing explosive, breakaway runs.
    *   **Logic**: For each rushing play, calculate yards gained beyond 10 yards. Aggregate the average `open_field_yards_per_rush` at the team-game level.

*   **`off_power_success_rate` / `def_power_success_rate`**:
    *   **Definition**: The percentage of runs on 3rd or 4th down with 2 or fewer yards to go that result in a first down or touchdown.
    *   **Logic**: Filter plays based on down and distance. Calculate the success rate at the team-game level.

### 2. Situational Efficiency

These features measure a team's performance in high-leverage situations, which can often be the difference in close games.

*   **Source Data**: `processed/byplay/` (Enhanced Plays)
*   **Aggregation Level**: Plays -> Team-Game -> Team-Season-to-Date

**Feature Definitions:**

*   **`off_red_zone_efficiency` / `def_red_zone_efficiency`**:
    *   **Definition**: Average points scored per trip inside the opponent's 20-yard line.
    *   **Logic**: Identify all drives that enter the red zone. For each of those drives, find the total points scored on that possession (touchdown, field goal, or zero). Calculate the average `points_per_red_zone_trip` at the team-game level.

*   **`off_third_down_conversion_rate` / `def_third_down_conversion_rate`**:
    *   **Definition**: The percentage of third downs that are successfully converted into a first down or touchdown.
    *   **Logic**: Filter for all 3rd down plays. Calculate the conversion rate at the team-game level. This can be further broken down by distance (e.g., 3rd & short, 3rd & medium, 3rd & long).