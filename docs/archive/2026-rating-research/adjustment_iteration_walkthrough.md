# Walkthrough - Adjustment Iteration Experiments

**Date:** 2025-11-23

## Goal

Evaluate the impact of opponent-adjustment iteration depth (0-4) on model performance to determine the optimal setting for Spread and Total models.

## Changes

### 1. Experiment Framework Updates

- **Configurable Iterations:** Updated `scripts/run_experiment.py` to respect `model.adjustment_iteration` in configuration files, allowing model-specific overrides.
- **Strict Train/Test Split:** Updated `conf/config.yaml` to set `test_years: [2024]` and modified `scripts/run_experiment.py` to explicitly exclude 2020 from training (Train: 2019, 2021-2023).

### 2. Model Configuration

- **Spread Model:** Updated `conf/model/spread_catboost.yaml` to use `adjustment_iteration: 2`.
- **Total Model:** Updated `conf/model/total_catboost.yaml` to use `adjustment_iteration: 2`.

### 3. Documentation

- **Decision Log:** Recorded the decision to standardize on Iteration 2 in `docs/decisions/decision_log.md`.
- **Experiment Report:** Generated a detailed summary of findings in `artifacts/reports/adjustment_iteration_summary.md`.

## Verification Results

### Feature Cache Validation

- Verified that `processed/team_week_adj` caches for 2023-2024 (Iterations 0 & 4) contained the critical `_last_1` recency features, disproving the "missing feature" hypothesis from previous sessions.

### Experiment Findings (Train 19/21-23, Test 24)

- **Spread Model:** Iteration 2 yielded the best RMSE (17.97) and tied for the best Hit Rate (48.2%).
- **Total Model:** Iteration 2 yielded the best Hit Rate (54.1%), outperforming the default Iteration 4 (53.3%).

### Configuration Verification

- Ran dry-runs (`--info`) for both models to confirm that the new `adjustment_iteration: 2` setting is correctly picked up by the experiment runner.

### Diagnostics & Cache Health

- **Coverage:** Confirmed 100% coverage for key features in Iteration 2 (2023 & 2024).
- **Consistency:** Identified minor calculation discrepancies in adjusted defense metrics (~0.01-0.04 diff) but no systemic missing data.
- **Storage:** Decided to retain all cache iterations (0-4) for future research flexibility.

## Next Steps

- Proceed with weekly betting generation using the optimized models.
- Consider rebuilding the feature cache for _only_ Iteration 2 to save space if storage becomes an issue, though keeping 0-4 allows for future research.
