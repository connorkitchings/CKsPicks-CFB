# Modeling Baseline (MVP)

This document defines the initial, minimal modeling approach to generate weekly ATS recommendations.

## Objectives

- Hit rate target: ≥ 53%
- Scope: FBS regular season only, include Week 0
- Training window: 2014–2024 seasons, exclude 2020 (COVID)
- In-season predictions begin once both teams have ≥ 4 games played

## Targets

- Spread model: home_final_points − away_final_points (final margin)
- Total model: home_final_points + away_final_points (total points)

## Features

- Per-play and per-possession rate features (pace-aware)
- Opponent-adjusted statistics via iterative averaging (4 iterations)
- Season-to-date aggregates with extra weight on last 3 games
- Home/away indicator included in the model (not baked into raw stats)

## Training Strategy

- Treat each season as a silo for feature generation and training
- Train on 2014–2023 (exclude 2020); use 2024 as the final historical holdout for
  measurement; apply to 2025 in-season
- Estimators: Ridge Regression is the default baseline, but the framework is
  model-agnostic and supports swapping estimators (e.g., Linear/ElasticNet/XGB)
  without changing the data contracts

## Validation Strategy

- Historical testing: fit on the designated training window and report RMSE/MAE on holdout seasons
- Final test: report RMSE/MAE on 2024 as the last pre-deployment measurement
- Anti-leakage: all season-to-date features are computed up to (but not including)
  the current game; enforce via unit tests
- Optional (advanced): walk-forward validation = train on weeks ≤ k and test on
  week k+1 within a season, rolling forward; use only if/when needed for tuning
- Policy: betting lines are not model features; home-field is excluded from raw
  stats and may be added as a model feature

## Feature Selection (MVP Plan)

- Start broad with the documented feature set; prune based on holdout performance
  to avoid multicollinearity and heteroskedasticity
- Avoid target leakage and preserve interpretability; defer SHAP/explainability to post-MVP

## Configuration

- Centralize defaults for data roots, season ranges, and seeds via CLI args or a
  small config file; all scripts must be deterministic for a given config

## Artifacts and Metrics (Plan)

- Artifacts
  - Models per season: `models/<year>/ridge_spread.joblib`, `models/<year>/ridge_total.joblib`
  - Feature extracts (optional cache): `features/<year>/*` (CSV)
- Metrics
  - Training metrics table per season (RMSE/MAE vs baselines): `reports/metrics/training_<year>.csv`
  - Backtest outputs (edges, ROI, hit rate): `reports/backtests/backtest_weekly.csv`, `backtest_summary.csv`
- Reproducibility
  - Training and backtest scripts accept `--year` and `--data-root`; outputs include run metadata

## Betting Policy (MVP)

- Compute edge = |model_prediction − sportsbook_line|
- Spreads: bet if edge ≥ 3.5 points
- Totals: bet if edge ≥ 7.5 points
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
