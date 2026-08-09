# V2 Deployment Checklist

**Date:** 2026-02-18  
**Deploying:** V2 Champion Model with Phase 4 Optimizations  
**Status:** ⏳ In Progress

---

## Pre-Deployment Validation

### Code Quality
- [x] All lint checks pass (`uv run ruff check .`)
- [x] Code formatted (`uv run ruff format .`)
- [x] Tests passing (where applicable)
- [x] No secrets in code
- [x] Configuration files validated

### Model Validation
- [ ] Champion validation experiment completed successfully
- [ ] Performance metrics match expected values:
  - [ ] Spread ROI: ~+0.78% (default), +2.03% (high confidence)
  - [ ] Totals ROI: ~+6.35%
  - [ ] Hit Rate: 52-55%
  - [ ] RMSE: ~18-19
- [ ] Model artifacts saved correctly
- [ ] Feature importance validated

### Configuration
- [x] `conf/model/champion.yaml` created and validated
- [x] `conf/weekly_bets/v2_champion.yaml` paths correct
- [x] Bias correction (+1.14) configured
- [x] Dual thresholds (0.0/8.0) configured
- [x] Totals threshold (1.5) configured
- [x] Feature params (alpha=0.3) configured

---

## Deployment Steps

### Step 1: Final Validation
- [ ] Run champion validation: `PYTHONPATH=src uv run python -m cks_picks_cfb.train experiment=v2_champion_validation`
- [ ] Verify metrics in MLflow
- [ ] Compare to expected performance
- [ ] Document any deviations

### Step 2: Register Model
- [ ] Tag model as `production` in MLflow
- [ ] Save model artifacts to `models/` directory
- [ ] Create backup of previous champion (if exists)
- [ ] Verify model can be loaded: `joblib.load("models/linear_spread_target.joblib")`

### Step 3: Update Production Config
- [ ] Verify `conf/weekly_bets/v2_champion.yaml` has correct paths
- [ ] Update week number to current week
- [ ] Confirm thresholds are set correctly
- [ ] Test config loading: `OmegaConf.load("conf/weekly_bets/v2_champion.yaml")`

### Step 4: Test Prediction Pipeline
- [ ] Run prediction for current week: `PYTHONPATH=. uv run python scripts/pipeline/generate_weekly_bets.py`
- [ ] Verify output CSV is created
- [ ] Check predictions look reasonable (feature magnitudes, edges)
- [ ] Confirm bias correction is applied

### Step 5: Deploy Documentation
- [ ] Review production guide
- [ ] Update quick start guide with any changes
- [ ] Verify rollback procedures documented
- [ ] Ensure all links work

### Step 6: Go Live
- [ ] Generate first production predictions
- [ ] Review and approve bets
- [ ] Place bets
- [ ] Update tracking spreadsheet
- [ ] Announce deployment (if team)

---

## Post-Deployment Verification

### Immediate (First Week)
- [ ] Predictions generated successfully
- [ ] Bets placed and recorded
- [ ] No errors in logs
- [ ] Performance tracking started

### Short-term (First Month)
- [ ] Weekly predictions generating consistently
- [ ] Scoring working correctly
- [ ] ROI within expected range
- [ ] Dashboard showing accurate data
- [ ] No alerts triggered

### Ongoing Monitoring
- [ ] Weekly: Generate predictions and track performance
- [ ] Monthly: Review metrics, check for drift
- [ ] Seasonally: Retrain model with new data

---

## Rollback Plan

### Rollback Triggers
- [ ] Performance degrades significantly (>5% below expected)
- [ ] Hit rate drops below 48% for 3+ weeks
- [ ] Systematic bias detected (>2 points)
- [ ] Critical bug discovered

### Rollback Steps
1. [ ] Identify previous stable version
2. [ ] Restore previous model artifacts
3. [ ] Update config to point to previous version
4. [ ] Regenerate predictions
5. [ ] Document rollback in decision log
6. [ ] Analyze root cause

---

## Sign-Off

**Deployed By:** _________________  
**Date:** _________________  
**Validated By:** _________________  

**Notes:**

---

**Related Documents:**
- [Production Guide](production_guide.md)
- [Quick Start](quick_start.md)
- [V2 Workflow](../process/experimentation_workflow.md)
