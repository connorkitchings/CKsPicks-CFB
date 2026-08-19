# V2 Production Deployment Guide

> **⚠️ SUPERSEDED (historical reference).** Describes the retired
> local-joblib/MLflow deployment. Production is Vercel + Neon + R2 — see the
> [Production Runbook](../ops/production_runbook.md).

**Version:** 2.0  
**Last Updated:** 2026-02-18  
**Status:** Superseded

---

## Overview

This guide covers the complete deployment process for the V2 champion model to production. The V2 system uses a linear regression (Ridge) model with matchup_v1 features and Phase 4 optimizations.

### Champion Model Configuration

- **Model:** Linear Regression (Ridge, alpha=1.0)
- **Features:** matchup_v1 (16 features)
- **Target:** spread_target (also supports total_target)
- **Optimizations:**
  - Bias correction: +1.14 points
  - Dual-threshold betting: 0.0 (default) / 8.0 (high confidence)
  - Totals threshold: 1.5 points

### Expected Performance

Based on 2024 holdout validation:
- **Spread ROI:** +0.78% (default), +2.03% (high confidence)
- **Totals ROI:** +6.35%
- **Hit Rate:** ~52-55%

---

## Pre-Deployment Checklist

Before deploying to production, ensure:

- [ ] Champion validation completed successfully
- [ ] Performance metrics match expected values
- [ ] All lint checks pass (`make health`)
- [ ] Configuration files validated
- [ ] Model artifacts saved and accessible
- [ ] Betting thresholds configured correctly
- [ ] Rollback plan documented

---

## Deployment Steps

### Step 1: Validate Champion Model

Run the champion validation experiment to verify post-refactoring performance:

```bash
PYTHONPATH=src uv run python -m cks_picks_cfb.train experiment=v2_champion_validation
```

**Expected Results:**
```
Spread ROI: ~+0.78%
Totals ROI: ~+6.35%
Hit Rate: 52-55%
RMSE: ~18-19
```

### Step 2: Register Model in MLflow

Once validation succeeds, register the model with the production tag:

```bash
# Start MLflow UI (optional, for verification)
mlflow ui --backend-store-uri file:///Users/connorkitchings/Desktop/Repositories/ckspicks-cfb/artifacts/mlruns

# Register model via script or manually in UI
# TODO: Create registration script
```

### Step 3: Save Model Artifacts

Ensure model artifacts are saved in the expected locations:

```bash
# Spread model
models/linear_spread_target.joblib

# Totals model  
models/linear_total_target.joblib
```

### Step 4: Update Production Configuration

Verify `conf/weekly_bets/v2_champion.yaml` has correct paths:

```yaml
models:
  spread:
    path: models/linear_spread_target.joblib
    calibration_offset: 1.14
  total:
    path: models/linear_total_target.joblib
```

### Step 5: Deploy to Production

No formal deployment needed - the model is used directly from the repository. Production usage involves:

1. **Generate weekly predictions:**
   ```bash
   PYTHONPATH=. uv run python scripts/pipeline/generate_weekly_bets.py --year 2025 --week 1
   ```

2. **Review predictions** in generated CSV

3. **Place bets** manually based on recommendations

4. **Score results** after games complete:
   ```bash
   PYTHONPATH=. uv run python scripts/pipeline/score_weekly_bets.py --year 2025 --week 1
   ```

---

## Production Workflow

### Weekly Cycle

```
Monday/Tuesday: Generate predictions for upcoming week
Wednesday: Review and place bets
Saturday/Sunday: Games played
Monday: Score results, update tracking
```

### Command Reference

#### Generate Predictions

```bash
# Default: Use current week from config
PYTHONPATH=. uv run python scripts/pipeline/generate_weekly_bets.py

# Override year and week
PYTHONPATH=. uv run python scripts/pipeline/generate_weekly_bets.py --year 2025 --week 10

# Use specific config
PYTHONPATH=. uv run python scripts/pipeline/generate_weekly_bets.py --config conf/weekly_bets/v2_champion.yaml
```

#### Score Results

```bash
# Score a specific week
PYTHONPATH=. uv run python scripts/pipeline/score_weekly_bets.py --year 2025 --week 10

# Score all weeks in a season
PYTHONPATH=. uv run python scripts/pipeline/score_weekly_bets.py --year 2025 --all-weeks
```

---

## Monitoring

### Key Metrics to Track

1. **ROI (Return on Investment)**
   - Rolling 4-week average
   - Season-to-date cumulative
   - Compare to backtest performance

2. **Hit Rate**
   - Percentage of winning bets
   - Should maintain 52-55% range
   - Alert if drops below 48%

3. **Volume**
   - Number of bets placed per week
   - Expected: 40-60 bets (full threshold)
   - High confidence: 15-25 bets (8.0 threshold)

4. **Calibration**
   - Predicted vs actual spreads
   - Bias should be minimal after correction

### Alert Thresholds

| Metric | Green 🟢 | Yellow 🟡 | Orange 🟠 | Red 🔴 |
|--------|----------|-----------|-----------|--------|
| ROI (4-week) | >+2% | 0% to +2% | -2% to 0% | <-2% |
| Hit Rate | >52% | 50-52% | 48-50% | <48% |
| Bets/Week | 40-70 | 30-40 or 70-80 | 20-30 or 80-100 | <20 or >100 |

### Dashboard

Start monitoring dashboard:

```bash
streamlit run dashboard/monitoring.py
```

Access at: http://localhost:8501

---

## Rollback Procedures

### When to Rollback

**Immediate rollback recommended if:**
- 🔴 RED status for 2+ consecutive weeks
- ROI drops >5% below test set performance
- Hit rate falls below 48% for 3+ weeks
- Systematic bias detected (>2 points)

**Rollback process:**

1. **Identify previous champion** in MLflow
   ```bash
   # List all model versions
   mlflow models list --registered-model-name champion_model
   
   # View specific version
   mlflow models get --registered-model-name champion_model --version 1
   ```

2. **Update production config** to point to previous version:
   ```yaml
   # conf/weekly_bets/v2_champion.yaml
   models:
     spread:
       path: models/linear_spread_target_v1.joblib  # Previous version
   ```

3. **Verify rollback** by running validation on previous version

4. **Document rollback** in decision log with reason

### Emergency Rollback (Quick)

If immediate action needed:

```bash
# Copy backup model to production location
cp models/backup/linear_spread_target_$(date +%Y%m%d).joblib models/linear_spread_target.joblib

# Regenerate predictions with previous model
PYTHONPATH=. uv run python scripts/pipeline/generate_weekly_bets.py
```

---

## Troubleshooting

### Common Issues

#### Issue: Model predictions seem off

**Diagnosis:**
```bash
# Check feature magnitudes
PYTHONPATH=. uv run python -c "
from cks_picks_cfb.features.v2_recency import load_v2_recency_data
df = load_v2_recency_data(2025, alpha=0.3, for_prediction=True)
print(df[['home_adj_off_epa_pp', 'away_adj_def_epa_pp']].describe())
"
```

**Solution:**
- Verify alpha parameter (should be 0.3)
- Check opponent adjustment iteration (should be 2 or 4)
- Ensure cloud storage is accessible

#### Issue: No bets generated

**Diagnosis:**
```bash
# Check if data loaded correctly
PYTHONPATH=. uv run python scripts/pipeline/generate_weekly_bets.py --year 2025 --week 1
# Look for "No games found" or "No data found" messages
```

**Solution:**
- Verify week number is correct
- Check if games data exists in cloud storage
- Ensure betting lines are available

#### Issue: Performance degradation

**Diagnosis:**
- Compare current metrics to baseline
- Check for data quality issues
- Review recent decision log entries

**Solution:**
- Run validation on recent weeks
- Compare feature distributions to training set
- Consider rollback if significant degradation

---

## Configuration Reference

### Champion Model Config

**File:** `conf/model/champion.yaml`

Key settings:
- `params.alpha`: Ridge regularization (1.0)
- `features.alpha`: EWMA decay (0.3)
- `optimizations.bias_correction.spread_offset`: +1.14
- `optimizations.thresholds.spread.default`: 0.0
- `optimizations.thresholds.spread.high_confidence`: 8.0
- `optimizations.thresholds.totals.default`: 1.5

### Weekly Bets Config

**File:** `conf/weekly_bets/v2_champion.yaml`

Key settings:
- `year`: Current season (2025)
- `week`: Current week (update weekly)
- `spread_edge_threshold`: 0.0
- `spread_edge_threshold_high_conf`: 8.0
- `total_edge_threshold`: 1.5
- `models.spread.calibration_offset`: 1.14

---

## Maintenance

### Regular Tasks

**Weekly:**
- [ ] Generate predictions
- [ ] Review and place bets
- [ ] Score previous week's results
- [ ] Update tracking spreadsheet/dashboard

**Monthly:**
- [ ] Review performance metrics
- [ ] Check for systematic bias
- [ ] Validate feature distributions
- [ ] Update decision log if needed

**Seasonally:**
- [ ] Re-train model with new data
- [ ] Validate on recent holdout year
- [ ] Update feature set if needed
- [ ] Archive old model versions

### Data Quality Checks

Run monthly:

```bash
# Check data completeness
PYTHONPATH=. uv run python -c "
from cks_picks_cfb.data.storage import get_storage
storage = get_storage()
for year in [2023, 2024, 2025]:
    games = storage.read_index('raw/games', {'year': year})
    print(f'{year}: {len(games)} games')
"
```

---

## Support & Resources

### Documentation
- [V2 Workflow](experimentation_workflow.md) - Full experimentation process
- [Decision Log](../decisions/decision_log.md) - Historical decisions
- [Feature Registry](../project_org/feature_registry.md) - Active feature sets

### Key Files
- Champion config: `conf/model/champion.yaml`
- Weekly bets config: `conf/weekly_bets/v2_champion.yaml`
- Training script: `src/cks_picks_cfb/train.py`
- Prediction script: `scripts/pipeline/generate_weekly_bets.py`
- Scoring script: `scripts/pipeline/score_weekly_bets.py`

### Contacts
- Primary: connor.kitchings@gmail.com
- Repository: https://github.com/connorkitchings/CKsPicks-CFB

---

**Last Updated:** 2026-02-18  
**Next Review:** Before 2025 season start
