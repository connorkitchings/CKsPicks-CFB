## Ridge Baseline Model

This document describes the MVP ridge regression model used for ATS and totals predictions.

### Objective

- Predict game final margin (spread) and total points using opponent-adjusted team-season features.
- Achieve a simple, reproducible baseline aligned with the project’s betting policy.

### Data

- Source: CollegeFootballData.com (CFBD)
- Scope: FBS regular season; training years: 2014–2023 (exclude 2020); test year: 2024
- Features are built from processed CSVs produced by the aggregation pipeline:
  - `processed/team_game`: team-game level metrics
  - `processed/team_season`: season-to-date aggregates with last-3 weighting (3/2/1)
  - `processed/team_season_adj`: iterative opponent-adjusted metrics (4 iterations)

### Features

- Adjusted offense and defense metrics per team from `team_season_adj`:
  - `adj_off_*`, `adj_def_*` for metrics: `epa_pp`, `sr`, `ypp`,
    `expl_rate_overall_10`, `expl_rate_overall_20`, `expl_rate_overall_30`,
    `expl_rate_rush`, `expl_rate_pass`.
- Selected unadjusted offense extras if present: `off_eckel_rate`, `off_finish_pts_per_opp`,
  `stuff_rate`, `havoc_rate`.
- For modeling, features are merged twice per game (home*\*, away*\*). No explicit home-field
  dummy is added in MVP (can be added later as `home_field=1`).

### Targets

- Spread: `home_points - away_points`
- Total: `home_points + away_points`

### Training/Evaluation Protocol

- Train on concatenated seasons: 2014–2023 (exclude 2020)
- Test on 2024 (final holdout for historical evaluation)
- Estimator: `sklearn.linear_model.Ridge(alpha=1.0)` (baseline; framework supports swapping estimators)
- Metrics: RMSE and MAE on the holdout year (reported per target)
- Anti-leakage: season-silo features must be up-to-week and exclude the current game.

### Storage Layout

- Models are saved under `artifacts/models/ridge_baseline/<test_year>/`:
  - `ridge_spread.joblib`, `ridge_total.joblib`
- Evaluation metrics under `reports/metrics/ridge_baseline_eval_<test_year>.csv`

### CLI

Run training and evaluation:

```bash
uv run python src/models/train_model.py \
  --train-years 2019,2021,2022,2023 \
  --test-year 2024 \
  --data-root /absolute/data/root \
  --model-dir ./artifacts/models \
  --metrics-dir artifacts/reports/metrics
```

### Weekly Predictions

- The weekly script `src/scripts/generate_weekly_bets_clean.py` loads the above models,
  merges `team_season_adj` with `games` for the target week, joins `betting_lines`, generates
  predictions, applies the betting policy, and writes CSV to `reports/YYYY/CFB_weekWW_bets.csv`.

### Notes & Next Steps

- Consider adding a simple home-field indicator feature.
- Cross-validate alpha per season or pooled across seasons.
- Add SHAP summaries post-MVP.
