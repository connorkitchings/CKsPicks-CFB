# Feature Catalog

This catalog defines the engineered features and fields used by the MVP modeling pipeline.
It complements `docs/project_org/modeling_baseline.md` and the runbook in
`docs/operations/weekly_pipeline.md`.

## Conventions

- Level: team-season, team-week, game-level, or team-game.
- Types: numeric (int/float), categorical, boolean, datetime, string.
- Naming: snake_case; prefixes encouraged (e.g., `off_`, `def_`, `adj_`).
- All features should be reproducible from source Parquet and deterministic given a seed.

### Play filters and definitions

- Success Rate: CFBD standard thresholds
  - 1st down: gain ≥ 50% to-go
  - 2nd down: gain ≥ 70% to-go
  - 3rd/4th down: gain 100% of to-go
- Include offensive scrimmage plays only.
- Exclude penalties-only, kneels, spikes, 2-point tries, and non-scrimmage returns.
- Explosive plays:
  - Rush explosive: yards_gained ≥ 10
  - Pass explosive: yards_gained ≥ 15
  - Overall buckets tracked: 10+, 20+, 30+

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
| off_expl_rate_rush       | team-season | float | % rush plays gaining ≥10 yards           | plays.parquet (rush only)                | mean(yards_gained >= 10)                   | split threshold |
| off_expl_rate_pass       | team-season | float | % pass plays gaining ≥15 yards           | plays.parquet (pass only)                | mean(yards_gained >= 15)                   | split threshold |
| off_eckel_rate | team-season | float | % of drives that either gain ≥2 first downs or reach opp 40 | drives.parquet | mean(is_eckel_drive) | possession metric |
| off_finish_pts_per_opp | team-season | float | Points per scoring opportunity (first down at or inside opp 40) | drives.parquet, scoring | sum(points_on_opps)/n_opportunities | finishing drives |
| def_eckel_rate_allowed | team-season | float | % of opponent drives meeting eckel definition   | drives.parquet | mean(is_eckel_drive_allowed) | possession metric |
| def_finish_pts_per_opp_allowed | team-season | float | Points allowed per opponent scoring opportunity | drives.parquet, scoring | sum(points_allowed_on_opps)/n_opportunities | finishing drives |

Notes:

- Drive-level features depend on raw `plays.parquet` → drive segmentation; see `src/cfb_model/transforms/` for drive builder.

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
| adj_off_expl_rush            | off_expl_rate_rush                | team-season | float| Opponent-adjusted rush explosive rate             | rush ≥10 |
| adj_off_expl_pass            | off_expl_rate_pass                | team-season | float| Opponent-adjusted pass explosive rate             | pass ≥15 |
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

Definitions:

- Scoring opportunity = first down at or inside opponent 40.
- Eckel drive = drive that either gains ≥2 first downs or reaches opponent 40.

## 4) Game-level merge and keys

- Primary keys: `game_id`, `season`, `week`.
- Team identifiers: `home_team`, `away_team`, `team` (normalized casing).
- Join rules documented in feature build script (home/away control added at modeling stage).

## 5) Targets (reference)

- Spread target: `home_final_points - away_final_points` (final margin).
- Total target: `home_final_points + away_final_points` (total points).
- See `docs/project_org/modeling_baseline.md` → Targets.

## 6) Validation checks

- Row counts per season and per team within expected ranges; manifest.json present per partition.
- No nulls in required fields; dtypes are correct.
- Expected ranges:
  - Rates in [0, 1]; yards/play in [0, 15]; EPA/play roughly in [-5, 5].
  - Finishing points per opportunity in [0, 7].
  - Explosive bucket monotonicity: 30+ ≤ 20+ ≤ 10+.
- Reproducibility: deterministic outputs for given `--year` and `--data-root`.
- Summary CSV per season generated under `reports/metrics/features_<year>_summary.csv`.

## 7) Change management

- Any material change to feature definitions must be recorded in
  `docs/decisions/decision_log.md` with rationale and effective date.
- Keep this catalog up to date alongside code changes in `src/cfb_model/features/`.
