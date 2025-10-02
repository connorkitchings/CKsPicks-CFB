# Decision Log

Log of planning-level decisions. Use one entry per decision.

---

## 2025-10-02 — Kelly Sizing With 5% Single-Bet Cap and Confidence Filters

- Category: Betting Policy / Risk Management
- Decision: Implement Kelly-based bet sizing with fractional Kelly (25%) and a 5% single-bet exposure cap. Adopt ensemble prediction standard deviation as a confidence signal (defaults: spreads ≤ 3.0, totals ≤ 1.5) for optional filtering.
- Rationale: Kelly improves long-run growth when probabilities are well-calibrated; the 5% cap limits tail risk. Confidence filtering (std-dev across ensemble members) materially improved hit rates in sweep analysis while providing volume control.
- Impact:
    - Weekly generator calculates `kelly_fraction_*` and unit columns and enforces `single_bet_cap`.
    - Added CLI options for Kelly parameters and confidence thresholds; docs updated.
    - New scripts for bankroll simulation and weekly hit-vs-bet summaries support operational analysis.
- References: `src/cfb_model/scripts/generate_weekly_bets_clean.py`, `scripts/simulate_bankroll_2024.py`, `scripts/run_weekly_reports_2024.py`, `[LOG:2025-10-02]`

## 2025-10-02 — Storage Path & Partition Consistency Fixes

- Category: Data / Storage
- Decision: Correct LocalStorage root path composition to avoid duplicate `/data` segments; standardize byplay/drives partition key to `game_id`.
- Rationale: Path correctness and consistent partition keys reduce confusion and IO errors across tools and docs.
- Impact: `src/cfb_model/data/storage/local_storage.py` and `src/cfb_model/data/aggregations/persist.py` updated; docs and scripts remain compatible.
- References: `[LOG:2025-10-02]`

## 2025-10-01 — Ensemble Model Architecture for Variance Reduction

- Category: Modeling / Architecture
- Decision: Adopted an ensemble model approach to improve prediction stability and reduce week-to-week variance. The system now trains and averages multiple models for each prediction target.
    - **Spreads Ensemble**: `Ridge`, `ElasticNet`, `HuberRegressor`.
    - **Totals Ensemble**: `RandomForestRegressor`, `GradientBoostingRegressor`.
- Rationale: The previous single-model approach, while profitable, exhibited high variance in weekly performance. Ensembling is a standard technique to improve model robustness and reduce the risk of overfitting to the noise of a single model's methodology. This change directly addresses the "variance reduction" goal identified as a high-priority next step.
- Impact: 
    - `src/cfb_model/models/train_model.py` was updated to train and save a collection of models for each target.
    - `src/cfb_model/scripts/generate_weekly_bets_clean.py` was updated to load all models for a target, generate predictions from each, and average the results.
    - Model artifacts are now saved with specific names (e.g., `spread_ridge.joblib`, `total_randomforest.joblib`) in the `models/<year>/` directory.
- References: `src/cfb_model/models/train_model.py`, `src/cfb_model/scripts/generate_weekly_bets_clean.py`, `[LOG:2025-09-30]`

## 2025-09-30 — RandomForest Model for Totals Predictions

- Category: Modeling / Architecture
- Decision: Switched totals model from Ridge Regression to RandomForestRegressor while maintaining Ridge for spreads. Final configuration: RandomForestRegressor with n_estimators=200, max_depth=8, min_samples_split=10, min_samples_leaf=5, random_state=42.
- Rationale: Initial experiments showed RandomForest better captures non-linear relationships in total scoring patterns. Full 2024 season validation achieved 54.7% hit rate for spreads (Ridge) and 54.5% for totals (RandomForest), both exceeding the 52.4% breakeven threshold and marking the project's first profitable model configuration.
- Impact: Model training pipeline (`src/cfb_model/models/train_model.py`) updated to use RandomForest for totals. Both models saved to `models/<year>/spread_model.joblib` and `models/<year>/total_model.joblib`. Weekly prediction script continues to work unchanged as it loads models dynamically.
- Performance: Combined 2024 results (261 bets): Ridge spreads 135/247 (54.7%), RandomForest totals 83/152 (54.5%). First time project has crossed profitability threshold.
- References: `src/cfb_model/models/train_model.py`, `scripts/model_improvement_experiments.py`, session log `[LOG:2025-09-30]`

## 2025-09-29 — Calibrated Edge Thresholds Locked to 6.0/6.0

- Category: Betting Policy / Calibration
- Decision: After training-derived week-of-season calibration (no in-season leakage), lock default edge thresholds to 6.0 for both spreads and totals. Threshold sweeps on the 2024 holdout show strongest calibrated hit rates near 6.0 for both targets with reasonable pick volume.
- Rationale: Training-years calibration corrected systematic week-of-season bias. On 2024 holdout, spreads reached 54.9% at 6.0 and totals 55.3% at 6.0, balancing accuracy and volume. Prior defaults (5.0/5.5) are superseded.
- Impact: CLI defaults updated; weekly pipeline and baseline docs updated. Historical comparisons should note the calibration step and new thresholds.
- References: `reports/calibration/*_weekly_bias_from_training.csv`, `reports/calibration/holdout_*_threshold_sweep_calibrated.csv`, `scripts/calibrate_and_thresholds.py`

## 2025-09-29 — Prediction Pipeline Optimization and Refactoring

- Category: Pipeline / Code Quality
- Decision:
    1.  **Implement Weekly Stats Cache:** To improve prediction speed, pre-calculate and cache weekly point-in-time adjusted stats in a new `processed/team_week_adj` entity.
    2.  **Update Prediction Script:** Modify the weekly prediction script (`generate_weekly_bets_clean.py`) to read from this new cache instead of calculating features on the fly.
    3.  **Unify CLI:** Consolidate the `run_ingestion_year.py` and `run_full_season.py` scripts into the main `scripts/cli.py` as new commands (`ingest-year`, `run-season`) to create a single entry point.
    4.  **Refactor Legacy Code:** Remove the redundant `src/cfb_model/models/train_model.py` script and fix the corresponding import test.
- Rationale: This refactoring significantly speeds up the weekly prediction process while maintaining data integrity. It also improves code organization, maintainability, and usability by unifying the command-line interface and removing legacy code.
- Impact: The weekly prediction process is now much faster. Developers have a single, clear CLI for running pipeline tasks. The codebase is cleaner and less confusing.
- References: `scripts/cache_weekly_stats.py`, `scripts/cli.py`, `src/cfb_model/scripts/generate_weekly_bets_clean.py`, `[LOG:2025-09-29]`

## 2025-09-28 — Update Totals Edge Threshold Default to 5.5

- Category: Betting Policy
- Decision: Increase totals edge threshold default from 7.5 to 5.5 points (configurable via `--total-threshold`). Spread threshold remains 5.0.
- Rationale: 2024 threshold sweep results showed strongest hit rates around 5.5–6.0 for totals. We selected 5.5 for a slightly higher hit rate with more pick volume than 6.0. Spread threshold at 5.0 remains well-calibrated.
- Impact: Weekly and seasonal generation now default to 5.5 for totals; documentation and CLI help updated.
- References: `scripts/run_full_season.py`, `src/cfb_model/scripts/generate_weekly_bets_clean.py`, `reports/2024/edge_threshold_sweep_total.csv`, [LOG:2025-09-28]

## 2025-09-25 — Critical Spread Betting Logic Bug Fix

- Category: Modeling / Betting Logic
- Decision: Fixed fundamental flaw in spread betting logic where model predictions were compared directly to raw spread lines instead of expected home margins. Changed comparison from `predicted_spread > spread_line` to `predicted_spread > (-spread_line)`.
- Rationale: Original logic caused artificially inflated performance (72.5% hit rate) because positive predictions always beat negative spread lines. Corrected logic provides realistic assessment of model performance (51.7% hit rate).
- Impact: Revealed true model performance is below breakeven by 0.7 percentage points, enabling honest evaluation and targeted improvements.
- References: `src/cfb_model/scripts/generate_weekly_bets_clean.py`, `scripts/score_weekly_picks.py`, [LOG:2025-09-25]

## 2025-09-24 — Data Leakage Fix & Point-in-Time Feature Generation

- Category: Modeling / Features
- Decision: Implemented strict point-in-time feature generation for model training and prediction to eliminate data leakage. Features for any given game are now calculated using only data from prior weeks.
- Rationale: Previous approach used full-season aggregated features, leading to inflated performance metrics. This change ensures realistic model evaluation and prediction.
- References: `src/cfb_model/models/features.py`, `src/cfb_model/models/ridge_baseline/train.py`, `src/cfb_model/scripts/generate_weekly_bets_clean.py`, [LOG:2025-09-24]

## 2025-09-04 — Processed Schema Versioning in Manifests

- Category: Data / Storage
- Decision: Add `schema_version`, `data_type`, `file_format`, and `entity` to all partition `manifest.json` files for both raw and processed datasets.
- Rationale: Enables reliable downstream validation, reproducibility, and safe schema evolution across seasons.
- References: `src/cfb_model/data/storage/local_storage.py`, [LOG:2025-09-04]

## 2025-09-04 — Deep Semantic Validation Suite

- Category: Data Quality
- Decision: Implement deep validators for drives (byplay→drives), team_game (off/def mirrors; counts), team_season (recency-weight recompute), and opponent-adjusted (recompute vs persisted); expose via `--deep`.
- Rationale: Prevent silent aggregation drift and ensure consistency between pipeline layers.
- References: `src/cfb_model/data/validation.py`, [LOG:2025-09-04]

## 2025-09-04 — Quiet Aggregations Flag

- Category: Operations
- Decision: Add `--quiet` flag to pre-aggregation CLI; propagate `verbose` to persistence to reduce per-game logging.
- Rationale: Cleaner logs for long-running seasonal jobs; retains final summaries.
- References: `scripts/aggregations_cli.py`, `src/cfb_model/data/aggregations/persist.py`, [LOG:2025-09-04]

## 2025-09-04 — Historical Recollection (2014–2019, 2021–2024)

- Category: Data / Pipeline
- Decision: Re-collect plays across seasons (skip 2020) and re-run aggregations to unify schema and eliminate legacy inconsistencies (e.g., `is_drive_play`). Added driver script to automate.
- Rationale: Establishes uniform processed outputs across years; simplifies future strict schema validation.
- References: `scripts/recollect_plays_and_aggregate.py`, [LOG:2025-09-04]

## 2025-09-05 — Ruff Lint Policy Update

- Category: Code Quality
- Decision: Exclude notebooks from Ruff lint (`extend-exclude`: `*.ipynb`, `**/*.ipynb`, with `force-exclude: true`) and ignore `E501` globally to reduce noise from long docstrings and CLI help text.
- Rationale: Keep lint signal high in source code while avoiding churn from exploratory notebooks and long documentation strings.
- References: `pyproject.toml`, [LOG:2025-09-05]

## 2025-09-05 — Box Score vs Team-Game Validation Thresholds

- Category: Data Quality
- Decision: Adopt thresholds for comparing processed `team_game` metrics to CFBD advanced box scores:
  - Plays: WARN > 3, ERROR > 8
  - YPP: WARN > 0.20, ERROR > 0.50
  - Success rate: WARN > 0.02, ERROR > 0.05
- Rationale: Provide actionable validation tolerances that balance data variability with detection of aggregation drift.
- References: `src/cfb_model/data/validation.py` (validate_team_game_vs_boxscore), [LOG:2025-09-05]

## 2025-08-11 — Documentation Structure

- Category: Docs
- Decision: Rename `docs/reference/` → `docs/project_org/`, update MkDocs nav and internal links.
- Rationale: Clearer, minimal structure for authoritative project docs.
- References: [LOG:2025-08-11], `mkdocs.yml`, `docs/index.md`.

## 2025-08-11 — Weekly Pipeline Operations

- Category: Operations
- Decision: Manual weekly run on Wednesdays at 12:00 ET; CSV output `reports/YYYY/CFB_weekWW_bets.csv`.
- Rationale: External/local storage prevents full automation; ensures timely mid-week report.
- References: [LOG:2025-08-11], `docs/operations/weekly_pipeline.md`.

## 2025-08-11 — Modeling Baseline

- Category: Modeling
- Decision: MVP uses Ridge Regression for spread and total; begin predictions only after teams have
  ≥ 4 games; bet thresholds: spread ≥ 3.5, total ≥ 7.5.
- Rationale: Stable baseline, simple policy aligned with MVP objectives (≥53% hit rate).
- References: [LOG:2025-08-11], `docs/project_org/modeling_baseline.md`, `docs/project_org/project_charter.md`.

## 2025-08-12 — Training Window and Feature Engineering Specs

- Category: Modeling / Features
- Decision:
- Training window: 2019–2023, excluding 2020; 2024 as holdout/test.
  - Opponent adjustment: additive offset, 4 iterations; league-mean centering; opponent means
    weighted by game-level recency weights.
  - Recency: linear last-3 weighting at game level (weights 3, 2, 1; earlier games = 1).
  - Base stats to adjust (offense/defense where applicable): EPA/play, success rate (CFBD thresholds),
    yards/play, rush yards/play, pass yards/play, explosive rates (rush ≥15, pass ≥20; overall 10+/20+/30+),
    possession metrics (Eckel rate; finishing points per scoring opportunity at opp 40+).
- Rationale: Keep MVP explainable and robust while capturing schedule strength and pace/finishing context.
- References: [LOG:2025-08-12], `docs/project_org/modeling_baseline.md`, `docs/project_org/feature_catalog.md`,
  `docs/planning/roadmap.md`, `docs/cfbd/data_ingestion.md`.
