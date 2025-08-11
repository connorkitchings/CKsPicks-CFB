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
- Train on 2014–2024 (except 2020), apply to 2025 in-season
- Use Ridge Regression as the baseline estimator for both targets

## Artifacts and Metrics (Plan)

- Artifacts
  - Models per season: `models/<year>/ridge_spread.joblib`, `models/<year>/ridge_total.joblib`
  - Feature extracts (optional cache): `features/<year>/*.parquet`
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
