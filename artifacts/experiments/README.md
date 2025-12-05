# Experiments Directory

This directory contains experiment outputs organized by V2 phase.

## Structure

- `phase1_baseline/` - Phase 1: Baseline establishment (Ridge experiments)
- `phase2_features/` - Phase 2: Feature engineering & selection
- `phase3_models/` - Phase 3: Model selection (CatBoost, XGBoost, etc.)
- `promotion_tests/` - Bootstrap test results for promotions

## Experiment Outputs

Each experiment directory (`v2-XXX/`) contains:

- `metrics.csv` - Performance metrics (RMSE, MAE, Hit Rate, ROI)
- `predictions.csv` - Test set predictions
- `plots/` - Diagnostic visualizations
  - `residuals.png`
  - `calibration.png`
  - `feature_importance.png`
- `config.yaml` - Hydra configuration snapshot
- `summary.json` - Quick reference metrics

## Naming Convention

**Experiment ID**: `v2-XXX` where XXX is zero-padded (001, 002, ...)

**Path**: `phase<N>_<description>/<experiment_id>/`

- Example: `phase1_baseline/v2-001/`
- Example: `phase2_features/v2-003_recency_weighted/`
- Example: `phase3_models/v2-006_catboost/`

## Promotion Tests

Bootstrap test results stored in `promotion_tests/`:

- `v2-002_vs_baseline.json` - Feature promotion test
- `v2-006_vs_baseline.json` - Model promotion test

Contains: p-values, confidence intervals, decision criteria

## .gitignore

Large files excluded (CSVs >1MB, PNGs).
Summary files and configs are committed.

---

**Related**: [Experiments Index](../docs/experiments/index.md) | [Promotion Framework](../docs/process/promotion_framework.md)
