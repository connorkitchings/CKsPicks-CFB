# Modeling Baseline (MVP)

This document defines the initial, minimal modeling approach to generate weekly ATS recommendations.

## Objectives

- Hit rate target: ≥ 52.4% (breakeven threshold)
- Current performance: 54.7% spreads, 54.5% totals (2024 holdout)
- Scope: FBS regular season only, include Week 0
- Training window: 2019–2023 seasons (exclude 2020); 2024 as holdout/test
- In-season predictions begin once both teams have ≥ 4 games played

## Targets

- Spread model: home_final_points − away_final_points (final margin)
- Total model: home_final_points + away_final_points (total points)

## Features

- Per-play and per-possession rate features (pace-aware)
- Opponent-adjusted statistics via iterative averaging (4 iterations)
- Season-to-date aggregates with extra weight on last 3 games
- Home/away indicator included in the model (not baked into raw stats)

## Model Architecture

### Current Configuration (as of 2025-10-01)

To improve prediction stability and reduce week-to-week variance, the project uses an ensemble approach, averaging the predictions of multiple diverse models for each target.

- **Spreads Ensemble**: An average of three linear models with different regularization and robustness properties.
  - `Ridge(alpha=0.1)`
  - `ElasticNet(alpha=0.1, l1_ratio=0.5)`
  - `HuberRegressor(epsilon=1.35)`

- **Totals Ensemble**: An average of two powerful tree-based models.
  - `RandomForestRegressor(n_estimators=200, max_depth=8, ...)`
  - `GradientBoostingRegressor(n_estimators=200, learning_rate=0.1, ...)`

### Training Strategy

- Point-in-time feature generation prevents data leakage.
- All models in an ensemble are trained on the same dataset (2019–2023, excluding 2020).
- The final prediction is the simple average of the predictions from all models in the respective ensemble.

## Validation Strategy

- Historical testing: fit on the designated training window and report RMSE/MAE on holdout seasons.
- Final test: report RMSE/MAE on 2024 as the last pre-deployment measurement.
- Anti-leakage: all season-to-date features are computed up to (but not including) the current game; enforce via unit tests.
- Policy: betting lines are not model features; home-field is excluded from raw stats and may be added as a model feature.

## Feature Selection (MVP Plan)

- Start broad with the documented feature set; prune based on holdout performance to avoid multicollinearity and heteroskedasticity.
- Avoid target leakage and preserve interpretability; defer SHAP/explainability to post-MVP.

## Configuration

- Centralize defaults for data roots, season ranges, and seeds via CLI args or a small config file; all scripts must be deterministic for a given config.

## Artifacts and Metrics

- **Model Artifacts**
  - Spread Models: `models/<year>/spread_ridge.joblib`, `models/<year>/spread_elastic_net.joblib`, etc.
  - Total Models: `models/<year>/total_random_forest.joblib`, `models/<year>/total_gradient_boosting.joblib`, etc.
  - Weekly adjusted stats cache: `processed/team_week_adj/year=<Y>/week=<W>/`

- **Metrics Reports**
  - Training metrics: RMSE/MAE on training and test sets
  - Weekly predictions: `reports/<year>/CFB_week<WW>_bets.csv`
  - Scored results: `reports/<year>/CFB_week<WW>_bets_scored.csv`
  - Season summary: `reports/<year>/CFB_season_<year>_all_bets_scored.csv`
  - Calibration analysis: `reports/calibration/*.csv`

- **Reproducibility**
  - Training: `uv run python src/cfb_model/models/train_model.py --train-years 2019,2021,2022,2023 --test-year 2024`
  - All scripts accept `--data-root` for custom data locations
  - Random seeds fixed for deterministic outputs

## Betting Policy (MVP)

- Compute edge = |model_prediction − sportsbook_line|
- Spreads: configurable threshold (default ≥ 6.0 points via `--spread-threshold`); policy previously 3.5
- Totals: configurable threshold (default ≥ 6.0 points via `--total-threshold`)
- Enforce no-bet policy if either team has < 4 games played
- Flat staking (e.g., 1 unit) for MVP

## Outputs

- Weekly CSV: `reports/YYYY/CFB_weekWW_bets.csv`
- Suggested columns:
  - season, week, game_id, game_date
  - home_team, away_team, neutral_site
  - sportsbook
  - spread_line, total_line
  - model_spread, model_total
  - edge_spread, edge_total
  - bet_spread (home/away/none), bet_total (over/under/none)
  - bet_units

## Links

- Project Charter: `docs/project_org/project_charter.md`
- Weekly Pipeline: `docs/operations/weekly_pipeline.md`
- CFBD Data Ingestion: `docs/cfbd/data_ingestion.md`
- Feature Catalog: `docs/project_org/feature_catalog.md`
