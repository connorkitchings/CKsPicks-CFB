# Feature Catalog

This catalog defines the engineered features and fields used by the MVP modeling pipeline.
It complements `docs/project_org/modeling_baseline.md` and the runbook in
`docs/operations/weekly_pipeline.md`.

## Conventions

- Level: team-season, team-week, game-level, or team-game.
- Types: numeric (int/float), categorical, boolean, datetime, string.
- Naming: snake_case; prefixes encouraged (e.g., `off_`, `def_`, `adj_`).
- All features should be reproducible from source CSV and deterministic given a seed.

### Play filters and definitions

- Success Rate: CFBD standard thresholds
  - 1st down: gain ≥ 50% to-go
  - 2nd down: gain ≥ 70% to-go
  - 3rd/4th down: gain 100% of to-go
- Include offensive scrimmage plays only.
- Exclude penalties-only, kneels, spikes, 2-point tries, and non-scrimmage returns.
- Explosive plays:
  - Rush explosive: yards_gained ≥ 15
  - Pass explosive: yards_gained ≥ 20
  - Overall buckets tracked: 10+, 20+, 30+

## Pre-aggregation pipeline (plays → drives → games → season)

### Plays: required columns and canonicalization

- Required identifiers: `season`, `week`, `game_id`, `period` (aka quarter), `play_number`
- Teams: `offense`, `defense`, `home`, `away`, `home_away` (derived)
- Situation: `down`, `distance` (aka yards_to_first), `yard_line`, `yards_to_goal`
- Timing: `clock_minutes`, `clock_seconds`, normalized `time_remaining_before`,
   `time_remaining_after`, `play_duration`
- Outcome: `yards_gained`, `play_type`, `play_text`, `ppa` (proxy for EPA), `scoring`
- Derived flags:
  - Play taxonomy: `rush_attempt`, `pass_attempt`, `dropback`, `sack`, `penalty`, `turnover`, `st`
  (special teams), `twopoint`
  - Quality: `success` (CFBD thresholds by down), `explosive` (rush ≥15, pass ≥20), `garbage`
  (half/score-based), `red_zone`, `eckel`
  - Conversions: `thirddown_conversion`, `fourthdown_conversion`
- Source/implementation notes:
  - Canonicalization and by-play enrichment are implemented in `src/cfb_model/data/aggregations/byplay.py`
    (function `allplays_to_byplay`) and related helpers.
  - Standardize yards on fumbles and sacks; treat sacks as passes for split metrics.

### Drives: segmentation rules and schema

- Segmentation: assign `drive_number` within `game_id` by detecting possession changes and
   end-of-drive events:
  - Start of half, kickoff, punt, turnover (INT/FUM), safety, turnover on downs, successful FG/TD,
   end of period/half/game
  - Consecutive penalties without a snap remain in the same drive
- Drive keys: `game_id`, `drive_number`, `offense`, `defense`
- Start fields: `drive_start_period`, `drive_start_clock_seconds`, `start_yardline`, `start_yards_to_goal`
- End fields: `drive_end_period`, `drive_end_clock_seconds`, `end_yardline`, `end_yards_to_goal`, `drive_result`
- Aggregates: `drive_plays`, `drive_yards`, `drive_time`, `points`
- Possession metrics:
  - `is_eckel_drive`: drive gained ≥2 first downs or reached opponent 40
  - `had_scoring_opportunity`: first down at or inside opponent 40 during drive
  - `points_on_opps`: points scored on drives with a scoring opportunity
  - `is_successful_drive`: boolean flag based on scoring, field position gain, and total yards
  - `is_busted_drive`: boolean flag based on turnovers or minimal yardage
  - `is_explosive_drive`: boolean flag based on yards per play

### Games: team-game aggregation

- Level: team-game (one row per team per game)
- From plays (offense perspective unless noted):
  - Volume: `n_off_plays`, `n_rush_plays`, `n_pass_plays`
  - Efficiency: `off_sr` (mean of `success`), `off_ypp` (sum `yards_gained` / `n_off_plays`),
   `off_epa_pp` (sum `ppa` / `n_off_plays`)
  - Explosiveness: `off_expl_rate_overall_10/20/30`, `off_expl_rate_rush`, `off_expl_rate_pass`
  - Negatives: `stuff_rate` (rush ≤ 0), `havoc_rate` (INT+FUM+TFL etc.)
  - Defensive mirrors computed from opponent plays: `def_sr`, `def_ypp`, `def_epa_pp`, explosive
   rates allowed
- From drives (offense perspective):
  - `off_eckel_rate` = mean(`is_eckel_drive`)
  - `off_finish_pts_per_opp` = sum(`points_on_opps`) / count(`had_scoring_opportunity`)
  - Pace proxies: `off_drives`, `plays_per_game`, `sec_per_play`
- Keys and joins:
  - Join plays- and drives-derived aggregates by `game_id` + team role; ensure consistent
  `home/away` labeling for modeling stage.

### Season: team-season aggregation (season-to-date)

- Level: team-season; computed from team-game rows
- Recency: weight last three games 3/2/1; all earlier games weight = 1
- Means: weighted means for rates (success, explosive, EPA/play, ypp, eckel, finishing)
- Sums: keep auxiliary counts (games played, opportunities) for diagnostics and validation
- Preconditions used downstream: exclude teams with < 4 games from weekly betting outputs

## 1) Team-season aggregates (offense/defense)

<!-- markdownlint-disable MD013 -->
| feature_name | level       | dtype  | definition                                         | inputs                                   | transform                                 | notes |
|--------------|-------------|--------|----------------------------------------------------|------------------------------------------|--------------------------------------------|-------|
| off_epa_pp   | team-season | float  | Season-to-date offensive EPA per play              | plays.parquet (offense team, EPA)        | sum(EPA)/n_plays                           | pace-aware |
| def_epa_pp   | team-season | float  | Season-to-date defensive EPA per play              | plays.parquet (defense team, EPA)        | sum(EPA_allowed)/n_plays_defended          | pace-aware |
| off_sr       | team-season | float  | Offensive success rate                             | plays.parquet                            | mean(success_bool)                         | CFBD thresholds |
| def_sr       | team-season | float  | Defensive success rate allowed                     | plays.parquet                            | mean(success_bool_allowed)                 | CFBD thresholds |
| off_ypp      | team-season | float  | Offensive yards per play                           | plays.parquet                            | sum(yards_gained)/n_plays                  | split below |
| def_ypp      | team-season | float  | Defensive yards per play allowed                   | plays.parquet                            | sum(yards_allowed)/n_plays_defended        |             |
| off_rush_ypp | team-season | float  | Offensive rush yards per play                      | plays.parquet (rush only)                | sum(yards_gained)/n_rush_plays             |             |
| off_pass_ypp | team-season | float  | Offensive pass yards per play                      | plays.parquet (pass only)                | sum(yards_gained)/n_pass_plays             | sack-as-pass policy documented in code |
| off_expl_rate_overall_10 | team-season | float | % plays gaining ≥10 yards (any type)     | plays.parquet                            | mean(yards_gained >= 10)                   | explosive bucket |
| off_expl_rate_overall_20 | team-season | float | % plays gaining ≥20 yards (any type)     | plays.parquet                            | mean(yards_gained >= 20)                   | explosive bucket |
| off_expl_rate_overall_30 | team-season | float | % plays gaining ≥30 yards (any type)     | plays.parquet                            | mean(yards_gained >= 30)                   | explosive bucket |
| off_expl_rate_rush       | team-season | float | % rush plays gaining ≥15 yards           | plays.parquet (rush only)                | mean(yards_gained >= 15)                   |             |
| off_expl_rate_pass       | team-season | float | % pass plays gaining ≥20 yards           | plays.parquet (pass only)                | mean(yards_gained >= 20)                   | split threshold |
| off_eckel_rate | team-season | float | % of drives that either gain ≥2 first downs or reach opp 40 | drives.parquet | mean(is_eckel_drive) | possession metric |
| off_finish_pts_per_opp | team-season | float | Points per scoring opportunity (first down at or inside opp 40) | drives.parquet, scoring | sum(points_on_opps)/n_opportunities | finishing drives |
| def_eckel_rate_allowed | team-season | float | % of opponent drives meeting eckel definition   | drives.parquet | mean(is_eckel_drive_allowed) | possession metric |
| def_finish_pts_per_opp_allowed | team-season | float | Points allowed per opponent scoring opportunity | drives.parquet, scoring | sum(points_allowed_on_opps)/n_opportunities | finishing drives |

Notes:

- Drive-level features depend on raw `plays.parquet` → drive segmentation; see feature build helpers under `src/cfb_model/data/aggregations/`.

## 2) Opponent-adjusted features (iterative averaging)

- Iterations: 4 passes over schedule graph per season.
- Recency: linear last-3 weights at game level: most recent three games weights = 3, 2, 1; all earlier = 1.
- Centering: use league means per season to remove level effects.

Algorithm (per season s, team t, base metric x ∈ {epa_pp, sr, ypp, rush_ypp, pass_ypp, expl_rates, eckel_rate, finish_pts_per_opp}):

1. Compute season-to-date base rates for each team using game-level recency weights.
2. Initialize adjusted metrics with base metrics: adj_x^(0)(t) ← x_base(t).
3. For k in 1..4 (iterations):
   - Compute league mean μ_x = mean_t adj_x^(k-1)(t).
   - For each team t with opponents Opp(t):
     - Offense: adj_off_x^(k)(t) = off_x_base(t) − mean_{o ∈ Opp(t)} (adj_def_x^(k-1)(o) − μ_x)
     - Defense: adj_def_x^(k)(t) = def_x_base(t) − mean_{o ∈ Opp(t)} (adj_off_x^(k-1)(o) − μ_x)
   - Means over opponents are weighted by the game-level recency weights.
4. Output adj_off_x = adj_off_x^(4), adj_def_x = adj_def_x^(4).

| feature_name                  | base_feature                     | level       | dtype | definition                                        | notes |
|-------------------------------|----------------------------------|-------------|------|---------------------------------------------------|-------|
| adj_off_epa_pp               | off_epa_pp                        | team-season | float| Opponent-adjusted offensive EPA/play              | 4 iters, recency weights |
| adj_def_epa_pp               | def_epa_pp                        | team-season | float| Opponent-adjusted defensive EPA/play              | 4 iters, recency weights |
| adj_off_sr                   | off_sr                            | team-season | float| Opponent-adjusted offensive success rate          | centered by league mean |
| adj_def_sr                   | def_sr                            | team-season | float| Opponent-adjusted defensive success rate allowed  | centered by league mean |
| adj_off_ypp                  | off_ypp                           | team-season | float| Opponent-adjusted offensive yards per play        | |
| adj_def_ypp                  | def_ypp                           | team-season | float| Opponent-adjusted defensive yards per play        | |
| adj_off_rush_ypp             | off_rush_ypp                      | team-season | float| Opponent-adjusted offensive rush ypp              | |
| adj_off_pass_ypp             | off_pass_ypp                      | team-season | float| Opponent-adjusted offensive pass ypp              | |
| adj_off_expl_overall_10      | off_expl_rate_overall_10          | team-season | float| Opponent-adjusted overall 10+ explosive rate      | bucketed |
| adj_off_expl_overall_20      | off_expl_rate_overall_20          | team-season | float| Opponent-adjusted overall 20+ explosive rate      | bucketed |
| adj_off_expl_overall_30      | off_expl_rate_overall_30          | team-season | float| Opponent-adjusted overall 30+ explosive rate      | bucketed |
| adj_off_expl_rush            | off_expl_rate_rush                | team-season | float| Opponent-adjusted rush explosive rate             | rush ≥15 |
| adj_off_expl_pass            | off_expl_rate_pass                | team-season | float| Opponent-adjusted pass explosive rate             | pass ≥20 |
| adj_off_eckel_rate           | off_eckel_rate                    | team-season | float| Opponent-adjusted Eckel rate                      | possession |
| adj_off_finish_pts_per_opp   | off_finish_pts_per_opp            | team-season | float| Opponent-adjusted finishing points per opportunity| possession |

## 3) Pace and possession-aware features

| feature_name              | level       | dtype | definition                                           | inputs                  | transform |
|---------------------------|-------------|------|------------------------------------------------------|-------------------------|-----------|
| plays_per_game            | team-season | float | Avg offensive plays per game                         | plays.parquet, games    | n_off_plays / n_games |
| sec_per_play              | team-season | float | Avg seconds per play (offense)                       | plays.parquet, game clocks | total_off_seconds / n_off_plays |
| drives_per_game           | team-season | float | Avg offensive drives per game                        | drives.parquet, games   | n_off_drives / n_games |
| possessions_per_game      | team-season | float | Proxy via offensive drives per game                  | drives.parquet, games   | = drives_per_game |
| avg_start_field_pos_ydln  | team-season | float | Avg starting field position (own-yardline scale)     | drives.parquet          | mean(start_ydln_own_side) |
| avg_scoring_opps_per_game | team-season | float | Avg scoring opportunities per game (opp 40+ first down) | drives.parquet       | n_opportunities / n_games |

<!-- markdownlint-enable MD013 -->

## 4) Luck and Variance Features

| feature_name | level | dtype | definition | inputs | transform | notes |
|---|---|---|---|---|---|---|
| luck_factor | team-game | float | Actual score margin minus PPA-based expected score margin | byplay.ppa, games.points | `(actual_margin - ppa_margin)` | Identifies teams outperforming/underperforming their play-by-play stats |
| avg_luck_factor | team-season | float | Season-to-date average luck factor per game | team_game.luck_factor | recency-weighted mean | Signals potential for regression to the mean |

## 5) Rushing Analytics Features

| feature_name | level | dtype | definition | inputs | transform | notes |
|---|---|---|---|---|---|---|
| line_yards | by-play | float | Yards gained on a rush play credited to the offensive line | byplay.yards_gained | Weighted formula | Isolates OL performance |
| power_success_rate | team-game | float | Conversion rate on 3rd/4th and short | byplay.is_power_situation, byplay.power_success_converted | `sum(converted) / sum(situations)` | Measures short-yardage offense |
| second_level_yards | by-play | float | Yards gained 5-10 yards past the line of scrimmage | byplay.yards_gained | `clip(5, 10)` | Isolates RB elusiveness |
| open_field_yards | by-play | float | Yards gained 10+ yards past the line of scrimmage | byplay.yards_gained | `clip(10)` | Isolates RB breakaway speed |

## 6) Special Teams Features

| feature_name | level | dtype | definition | inputs | transform | notes |
|---|---|---|---|---|---|---|
| net_punt_yards | by-play | float | Net change in field position on a punt | punt play `yards_to_goal`, next drive `start_yards_to_goal` | `punt_ytg - (100 - next_drive_start_ytg)` | Captures punt and return |
| fg_rate_by_dist | team-game | float | Field goal success rate, bucketed by distance | byplay.kick_distance, byplay.is_fg_made | `sum(made) / sum(attempts)` | More granular than overall FG% |

Definitions:

- Scoring opportunity = first down at or inside opponent 40.
- Eckel drive = drive that either gains ≥2 first downs or reaches opponent 40.

## 5) Game-level merge and keys

- Primary keys: `game_id`, `season`, `week`.
- Team identifiers: `home_team`, `away_team`, `team` (normalized casing).
- Join rules documented in feature build script (home/away control
  added at modeling stage).

## 6) Targets & Evaluation (Reference)

- **`home_team_result`**: The final score margin from the home team's perspective. Calculated as `home_points - away_points`.
- **`home_team_spread_line`**: The betting point spread from the home team's perspective. A negative value indicates the home team is favored; a positive value indicates they are the underdog.
- **Spread Cover Logic**: A bet on the **home** team wins if `home_team_result > home_team_spread_line`. A bet on the **away** team wins if `home_team_result < home_team_spread_line`.
- **Model Target**: The spread prediction model is trained to predict the `home_team_result`.

- See `docs/project_org/modeling_baseline.md` → Targets.

## 7) Momentum and Trending Features

| feature_name | level | dtype | definition | inputs | transform | notes |
|---|---|---|---|---|---|---|
| metric_last_3 | team-season | float | Average of the metric over the last 3 games | team_game | `mean(last(3))` | Captures recent form |
| metric_last_1 | team-season | float | The metric's value from the most recent game | team_game | `last(1)` | Captures most recent performance |

## 8) Validation checks

- Row counts per season and per team within expected ranges; manifest.json
  present per partition.
- No nulls in required fields; dtypes are correct.
- Expected ranges:
  - Rates in [0, 1]; yards/play in [0, 15]; EPA/play roughly in [-5, 5].
  - Finishing points per opportunity in [0, 7].
  - Explosive bucket monotonicity: 30+ ≤ 20+ ≤ 10+.
- Reproducibility: deterministic outputs for given `--year` and `--data-root`.
- Summary CSV per season generated under `reports/metrics/features_<year>_summary.csv`.

## 8) Change management

- Any material change to feature definitions must be recorded in
  `docs/decisions/decision_log.md` with rationale and effective date.
- Keep this catalog up to date alongside code changes in `src/cfb_model/data/aggregations/`.
