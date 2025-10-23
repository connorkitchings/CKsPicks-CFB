# Decision Log

Log of planning-level decisions. Use one entry per decision.

---

## 2025-10-20 — Exploration Kickoff: Unified Points-For Modeling

- Category: Modeling / Architecture
- Decision: Begin documentation and design work to evaluate replacing the separate spread and total pipelines with a unified points-for modeling approach that predicts home and away scoring directly.
- Rationale: A single scoring model could simplify feature maintenance, enable richer uncertainty calibration, and support both spread and total bets from one set of predictions. The team needs a written plan before altering production code.
- Impact: Draft design note outlining data requirements, modeling options (multi-output regression vs. paired single-target models), evaluation strategy, and rollout considerations. Identify downstream docs that must change once the approach is approved.
- Next Steps: Finalize the design note, resolve open questions (model form, fallback expectations, tuning strategy), then scope implementation tasks.
- References: `docs/planning/points_for_model.md`

---

## 2025-10-10 — MLOps Reorientation: MLflow Integration

- Category: MLOps / Tooling / Architecture
- Decision: Began an incremental reorientation of the project towards a more formal MLOps structure. The first step was to integrate **MLflow** for experiment tracking.
- Rationale: The existing method of tracking experiments via CSVs and manual logs is not scalable. MLflow provides a robust, centralized solution for tracking parameters, metrics, and model artifacts, which is critical for reproducible research and development.
- Impact:
  - Added `mlflow`, `hydra-core`, `hydra-optuna-sweeper`, and `optuna` to `pyproject.toml`.
  - Created a `conf/` directory for future Hydra configurations.
  - Refactored `src/cfb_model/models/train_model.py` to use nested MLflow runs for tracking the training of the model ensemble.
  - This sets the foundation for subsequent integration of Hydra and Optuna.
- References: `docs/guides/MLOps_Integration_Guide.md`, `src/cfb_model/models/train_model.py`

---

## 2025-10-10 — Re-tune Confidence Thresholds

- Category: Modeling / Betting Policy
- Decision: After the latest advanced features increased model variance, the confidence thresholds (ensemble prediction standard deviation) were re-tuned using the 2024 holdout season. The optimal thresholds were found to be **2.0 for spreads** and **1.5 for totals**.
- Rationale: The previous spread threshold of 3.0 was too loose with the new features, resulting in a lower hit rate. The new threshold of 2.0 provides a better balance of bet volume and accuracy (57.0% hit rate over 114 bets). The totals threshold of 1.5 remained optimal, now yielding a 59.1% hit rate over 115 bets.
- Impact: The default `--spread-std-dev-threshold` was updated to `2.0` in `scripts/cli.py` and `src/scripts/generate_weekly_bets_clean.py`. Documentation in `docs/operations/weekly_pipeline.md` and `docs/project_org/betting_policy.md` was updated to reflect the new default.
- References: `scripts/analysis_cli.py confidence`, `reports/2024/confidence_threshold_sweep_spread.csv`

---

## 2025-10-10 — Advanced Feature Implementation & Findings

- Category: Feature Engineering / Modeling
- Decision: Implemented advanced situational efficiency features, specifically `off_third_down_conversion_rate` and `def_third_down_conversion_rate`. The other requested features (rushing analytics) were already present in the codebase.
- Rationale: To improve model performance by capturing more granular, situational aspects of team performance, as outlined in the project roadmap (ID 32, 33).
- Impact: After retraining the models with the new features, a full 2024 season simulation was run. The new features increased the variance of the ensemble model's predictions, causing the confidence filter (based on prediction standard deviation) to reject most potential bets. This resulted in a significant decrease in the number of bets placed (4 total bets for the season). While the hit rate on these few bets was high (3/4 = 75%), the sample size is too small to be meaningful.
- Next Steps: The confidence thresholds (`--spread-std-dev-threshold` and `--total-std-dev-threshold`) may need to be re-tuned to account for the higher variance of the new model. Alternatively, the new features may need to be re-evaluated for their contribution to model stability.
- References: `src/cfb_model/data/aggregations/core.py`, `reports/2024/weekly_hit_summary_2024.csv`

---

## 2025-10-09 — Modular Caching Pipeline Refactor

- Category: Data / Pipeline / Architecture
- Decision: Refactor the weekly feature caching process into a two-stage pipeline. 
  1. The caching utility now supports a `--stage running` mode to create a `processed/running_team_season` asset with non-adjusted, point-in-time weekly aggregations.
  2. The same utility supports `--stage adjusted`, reading the running aggregates, applying opponent adjustment, and persisting `processed/team_week_adj/iteration=<n>/` outputs.
- Rationale: This change, suggested by the user, decouples the initial aggregation from the opponent-adjustment logic. It makes the pipeline more modular, easier to debug, and simplifies experimentation with different opponent-adjustment methodologies in the future.
- Impact: `scripts/cache_weekly_stats.py` exposes `--stage` flags to run the running-only, adjusted-only, or combined process, keeping the pipeline modular while reducing script sprawl. Documentation reflects the revised workflow.
- References: `[LOG:2025-10-09/01]`, `scripts/cache_weekly_stats.py`

---

## 2025-10-07 — Betting Line Ingestion Fix & Email Safety Check

- Category: Data / Operations / Reporting
- Decision: Removed faulty skipping logic from `BettingLinesIngester` to ensure fresh betting lines are always fetched. Implemented a safety check in `publish_picks.py` to prevent sending emails if recommended bets are missing line data.
- Rationale: The previous logic in `BettingLinesIngester` incorrectly skipped fetching new betting lines once a season was partially ingested, leading to stale data. The email safety check prevents publishing incomplete or misleading recommendations.
- Impact: `src/cfb_model/data/ingestion/betting_lines.py` modified. `scripts/publish_picks.py` modified.
- References: `[LOG:2025-10-07/03]`

## 2025-10-07 — Email Content Refinements (Hit Rate Only, Moneyline Consideration, Logos)

- Category: Reporting / User Experience
- Decision: Removed ROI calculation from weekly picks email, displaying only hit rates and counts. Added a `consider_moneyline` column to the spreads table for specific "wrong team favored" scenarios. Integrated team logos into the "Game" column of email tables.
- Rationale: ROI was confusing and prone to misinterpretation. Focusing on hit rate simplifies the message. The moneyline consideration highlights specific high-value opportunities. Logos improve visual appeal and readability.
- Impact: `scripts/publish_picks.py` modified. `templates/email_weekly_picks.html` modified. `generate_weekly_bets_clean.py` modified to include moneyline columns.
- References: `[LOG:2025-10-07/03]`

---

## 2025-10-07 — Weekly Scoring & Reporting Corrections (2025 Wk6)

- Category: Operations / Reporting / Logic
- Decisions:
  1) Correct scoring data source to use week-partitioned raw games at `raw/games/year=<YYYY>/week=<WW>/data.csv` (project-root `data_type=raw`) instead of aggregated `data/raw/games/year=<YYYY>/data.csv`.
  2) Fix spread scoring logic so away bets win when the home favorite fails to cover (and vice versa). Example: USF -28.5 vs Charlotte, final margin 28 → away bet wins.
  3) Update weekly review email to render times in ET by localizing report Date/Time as ET (no UTC conversion).
  4) Update email columns to: Date, Time, Game, Line, Model Prediction, Bet, Final Score, Final Result, Bet Result.
- Rationale: During Wk6 scoring, duplicates and incomplete results stemmed from merging against stale/aggregated games. Adjusting the data root and week-partition ensured accuracy. Spread grading was corrected to match sportsbook conventions. Email display improved clarity and time correctness.
- Impact:
  - Scripts: `score_fresh.py` (new), `validate_scoring.py` (new), `scripts/score_weekly_picks.py` (merge behavior clarified), `scripts/publish_review.py` (ET localization, columns), `templates/email_last_week_review.html` (columns).
  - Docs: `docs/operations/weekly_pipeline.md` updated for outputs, ET handling, and data source note.
- References: session log `[LOG:2025-10-07/01]`, `raw/games/year=2025/week=6/data.csv`, `reports/2025/CFB_week6_bets_scored.csv`.

## 2025-10-07 — Revert Systematic Feature Selection Experiment

- Category: Modeling / Feature Engineering
- Decision: The systematic feature selection experiment, which reduced the feature set to 16 for spreads and 25 for totals, was reverted. The project will continue using the full feature set for modeling.
- Rationale: A full 2024 season backtest using the selected features resulted in a combined hit rate of 52.3%. This was a decline from the 54.6% hit rate achieved with the full feature set. To maintain the highest performing model, the decision was made to revert the code to its pre-experiment state.
- Impact:
  - `src/cfb_model/models/train_model.py` was reverted to use `build_feature_list` for all models.
  - The experimental script `scripts/run_feature_selection.py` and its output in `reports/feature_selection/` will be kept for reference, but not used in the production pipeline.
  - This outcome serves as a key learning: feature reduction does not always yield better performance, and the full feature set, despite potential noise, contains more predictive power for the current ensemble models.
- References: `scripts/run_feature_selection.py`, `src/cfb_model/models/train_model.py`, `[LOG:2025-10-07/01]`

---

## 2025-10-03 — Email Template Spread Display Convention

- Category: Reporting / User Experience
- Decision: Display model spread predictions using betting line convention (negated home team margin) rather than raw home team margin. E.g., if model predicts home team wins by 10.46 points, display as "Home Team -10.46" instead of "Home Team +10.46".
- Rationale: Raw home team margin (positive = home wins) was confusing when displayed alongside betting lines where negative indicates favorite. Negating the margin makes the model prediction directly comparable to the Vegas line in the same format, improving user comprehension.
- Impact:
  - Updated `templates/email_weekly_picks.html` to negate spread predictions in display (using `-r.predicted_spread` in Jinja2 templates)
  - Applied to Best Bet box, Spread Bets table, and Full Schedule table
  - Total predictions remain unchanged (no team perspective, just point total)
  - Added "Line:" prefix to Best Bet box for additional clarity
- References: `templates/email_weekly_picks.html`, `scripts/publish_picks.py`, session log `[LOG:2025-10-03/02]`

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

## 2025-10-02 — 2025 Season Predictions Using 2024 Models (No 2025 Training)

- Category: Modeling / Operations
- Decision: For the 2025 season, do not train on 2025 data. Generate 2025 predictions using the previously trained 2024 ensemble models. To accommodate the current script interface (which loads models from `artifacts/models/<year>/`), create a symlink `artifacts/models/2025 -> artifacts/models/2024`.
- Rationale: Preserve an honest out-of-sample evaluation for 2025 by avoiding in-season training. Using the 2024-trained models maintains continuity while new 2025 data accrues.
- Impact:
    - Operational step added to weekly runbook to ensure `artifacts/models/2025` resolves to 2024 artifacts when predicting 2025.
    - All 2025 weekly reports use the 2024-trained ensemble without code changes.
- References: `src/cfb_model/scripts/generate_weekly_bets_clean.py`, `reports/2025/CFB_week{WW}_bets.csv`, session log `[LOG:2025-10-02]`

## 2025-10-02 — SHAP Fallback for Non-callable Pipelines

- Category: Explainability / Tooling
- Decision: Add a robust fallback in the weekly generator so that if SHAP cannot wrap a model (e.g., sklearn Pipeline not directly callable or feature name mismatch), the script proceeds without explanations rather than failing.
- Rationale: Some ensemble members (e.g., Huber inside a Pipeline) are not directly supported by SHAP’s default explainer. Failing fast blocked report generation.
- Impact: Weekly report generation is resilient; explanation columns are left blank when SHAP fails. No change to model predictions.
- References: `src/cfb_model/scripts/generate_weekly_bets_clean.py` (try/except around SHAP with predict fallback), `[LOG:2025-10-02]`

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
    - Model artifacts are now saved with specific names (e.g., `spread_ridge.joblib`, `total_randomforest.joblib`) in the `artifacts/models/<year>/` directory.
- References: `src/cfb_model/models/train_model.py`, `src/cfb_model/scripts/generate_weekly_bets_clean.py`, `[LOG:2025-09-30]`

## 2025-09-30 — RandomForest Model for Totals Predictions

- Category: Modeling / Architecture
- Decision: Switched totals model from Ridge Regression to RandomForestRegressor while maintaining Ridge for spreads. Final configuration: RandomForestRegressor with n_estimators=200, max_depth=8, min_samples_split=10, min_samples_leaf=5, random_state=42.
- Rationale: Initial experiments showed RandomForest better captures non-linear relationships in total scoring patterns. Full 2024 season validation achieved 54.7% hit rate for spreads (Ridge) and 54.5% for totals (RandomForest), both exceeding the 52.4% breakeven threshold and marking the project's first profitable model configuration.
- Impact: Model training pipeline (`src/cfb_model/models/train_model.py`) updated to use RandomForest for totals. Both models saved to `artifacts/models/<year>/spread_model.joblib` and `artifacts/models/<year>/total_model.joblib`. Weekly prediction script continues to work unchanged as it loads models dynamically.
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
    1.  **Implement Weekly Stats Cache:** To improve prediction speed, pre-calculate and cache weekly point-in-time adjusted stats in a new `processed/team_week_adj/iteration=<n>/` entity.
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
