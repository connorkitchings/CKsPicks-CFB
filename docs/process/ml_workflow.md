# CFB Model ML Workflow

## Standard Training Process

This document defines the **standard machine learning workflow** for the CFB modeling project. All model development should follow this process to ensure rigorous evaluation and prevent data leakage.

## Data Split Strategy

### Training Years: 2019, 2021-2023

- **Purpose:** Train all models on historical data
- **Note:** 2020 is excluded (COVID-impacted season)
- **Data Quality:** FBS vs FBS games only (no FCS opponents)

### Test Year: 2024

- **Purpose:** Hold-out year for model evaluation and selection
- **Critical:** Never include 2024 in training data
- **Use Cases:**
  - Compare different model architectures
  - Tune hyperparameters
  - Select optimal betting thresholds
  - Evaluate feature sets

### Deployment Year: 2025

- **Purpose:** Live production betting with best model from 2024 testing
- **Evaluation:** True out-of-sample performance measurement

## Workflow Steps

### 1. Model Development (Train on 2019, 2021-2023)

```bash
# Train PPR ratings (FBS only)
for year in 2019 2021 2022 2023; do
    uv run python scripts/ratings/train_ppr.py --year $year
done

# Export consolidated ratings
uv run python scripts/ratings/export_ratings_history.py

# Regenerate features with PPR ratings
for year in 2019 2021 2022 2023; do
    uv run python scripts/pipeline/run_pipeline_generic.py --year $year
done

# Train models
uv run python scripts/pipeline/train_and_register.py \
    --config-name=config experiment=spread_catboost_ppr_v1

uv run python scripts/pipeline/train_and_register.py \
    --config-name=config experiment=totals_xgboost_ppr_v1
```

### 2. Model Evaluation (Test on 2024)

```bash
# Generate 2024 predictions for all weeks
for week in 2 3 4 5 6 7 8 9 10 11 12 13 14; do
    # Update config for week
    # Generate predictions
    # Score predictions
done

# Analyze 2024 performance
# - Win rates by threshold
# - ROI analysis
# - Calibration metrics
```

### 3. Model Selection

Based on 2024 test performance:

- Select best model architecture (CatBoost vs XGBoost)
- Choose optimal feature set (PPR vs standard)
- Determine betting thresholds (spread/total edge)
- Validate calibration and reliability

### 4. Production Deployment (2025)

```bash
# Use selected model for 2025 weekly predictions
uv run python scripts/pipeline/generate_weekly_bets.py

# Monitor live performance
# Compare 2024 (test) vs 2025 (live) metrics
```

## Critical Rules

### ❌ NEVER Do This

- Include 2024 in training data
- Tune hyperparameters on 2025 data
- Change models mid-season based on 2025 performance
- Mix FBS and FCS opponents in training

### ✅ ALWAYS Do This

- Train only on 2019, 2021-2023
- Evaluate on 2024 before deploying
- Use FBS vs FBS games only
- Document model selection rationale
- Track both test (2024) and live (2025) performance

## Performance Comparison

The System Info in weekly emails should show:

- **Last Year (2024):** Test set performance (unbiased estimate)
- **Current (2025):** Live performance (true out-of-sample)
- **Hist. Wk N:** Same week in 2024 (week-specific comparison)

This allows fair comparison between test and live performance using the same model.

## Model Registry

Production models should be tagged with:

- Training years: `[2019, 2021, 2022, 2023]`
- Test year performance: 2024 metrics
- Feature set: PPR, standard, etc.
- Hyperparameters: seed, learning rate, etc.

## Retraining Schedule

Models should be retrained:

- **Annually:** After each season ends, retrain on updated historical data
- **Mid-season:** Only for critical bug fixes or data quality issues
- **Never:** Based on current season performance (wait until season end)

## Example: 2026 Season

When 2026 arrives:

1. **Train:** 2019, 2021-2024 (add 2024 to training set)
2. **Test:** 2025 (new hold-out year)
3. **Deploy:** 2026 (live betting)

This maintains the train/test/deploy split while incorporating new data.
