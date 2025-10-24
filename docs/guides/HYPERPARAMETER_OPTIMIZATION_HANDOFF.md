# Hyperparameter Optimization - Session Handoff

**Date**: 2025-09-30  
**Status**: Optimization jobs running in background  
**Session**: Priority 2 - Hyperparameter Optimization

> **2025-10-22 Update:** The active workflow now uses Hydra + Optuna sweeps (`scripts/optimize_hyperparameters.py` with `hydra/sweeper=optuna`). The details below capture the historical grid-search handoff; follow `docs/guides/hydra_guide.md` for the current process and artifact layout.

> **Path update:** References to modules formerly under `src/cfb_model/...` should now be interpreted under `src/...`.

---

## Current State

### Running Processes

Two optimization jobs are currently running in the background:

1. **Totals (RandomForest)** - PID 68370
   - Started: ~3:16 PM
   - Log: `/tmp/hyperopt.log`
   - Expected duration: 15-25 minutes (fast mode)
   - Parameter grid size: ~108 combinations (fast mode)

2. **Spreads (Ridge)** - PID 68979
   - Started: ~3:22 PM
   - Log: `/tmp/hyperopt_spreads.log`
   - Expected duration: 2-5 minutes (Ridge is fast)
   - Parameter grid size: 8 alpha values

### Check Progress

```bash
# Check if still running
ps aux | grep "optimize_hyperparameters" | grep -v grep

# View logs (once written)
tail -f /tmp/hyperopt.log        # Totals
tail -f /tmp/hyperopt_spreads.log  # Spreads

# Check for results
ls -lh reports/optimization/
```

---

## What Was Created

### 1. Hyperparameter Optimization Script

**File**: `scripts/optimize_hyperparameters.py`

**Features**:

- GridSearchCV with TimeSeriesSplit (time-series aware CV)
- Optimizes both Ridge (spreads) and RandomForest (totals)
- `--fast` mode for quicker iteration (smaller grid)
- `--skip-spreads` / `--skip-totals` to run individually
- Outputs JSON and CSV results

**Usage**:

```bash
# Optimize both (full grid)
uv run python scripts/optimize_hyperparameters.py \
  --data-root "/Volumes/CK SSD/Coding Projects/cfb_model"

# Fast mode (smaller grid)
uv run python scripts/optimize_hyperparameters.py \
  --data-root "/Volumes/CK SSD/Coding Projects/cfb_model" \
  --fast

# Spreads only
uv run python scripts/optimize_hyperparameters.py \
  --data-root "/Volumes/CK SSD/Coding Projects/cfb_model" \
  --skip-totals

# Totals only
uv run python scripts/optimize_hyperparameters.py \
  --data-root "/Volumes/CK SSD/Coding Projects/cfb_model" \
  --skip-spreads
```

### 2. Results Monitor Script

**File**: `scripts/apply_hyperparameter_results.py`

**Purpose**: Waits for optimization to complete, then generates summary report

**Usage**:

```bash
uv run python scripts/apply_hyperparameter_results.py
```

This will:

- Wait for results file to appear
- Load and parse results
- Generate comparison report
- Display summary with next steps

---

## Expected Outputs

### Directory Structure

```
reports/optimization/
├── hyperparameter_optimization_results.json  # Detailed results
├── hyperparameter_optimization_summary.csv   # CSV summary
└── comparison.md                             # Generated comparison report
```

### Results Format

**JSON** (`hyperparameter_optimization_results.json`):

```json
[
  {
    "model_name": "Ridge",
    "target": "spread",
    "best_params": { "alpha": 0.1, "fit_intercept": true, "solver": "auto" },
    "best_cv_score": 13.456,
    "cv_std": 0.234,
    "train_rmse": 12.345,
    "test_rmse": 13.456,
    "test_mae": 10.123,
    "improvement_vs_baseline": 2.34
  },
  {
    "model_name": "RandomForest",
    "target": "total",
    "best_params": {
      "n_estimators": 250,
      "max_depth": 10,
      "min_samples_split": 10,
      "min_samples_leaf": 2,
      "max_features": "sqrt",
      "random_state": 42
    },
    "best_cv_score": 16.234,
    "cv_std": 0.345,
    "train_rmse": 15.123,
    "test_rmse": 16.234,
    "test_mae": 12.456,
    "improvement_vs_baseline": 2.76
  }
]
```

**CSV** (`hyperparameter_optimization_summary.csv`):
| model | target | cv*rmse | cv_std | test_rmse | test_mae | improvement*% |
|-------|--------|---------|--------|-----------|----------|---------------|
| Ridge | spread | 13.456 | 0.234 | 13.456 | 10.123 | 2.34 |
| RandomForest | total | 16.234 | 0.345 | 16.234 | 12.456 | 2.76 |

---

## Next Steps (When Complete)

### 1. Review Results

```bash
# Run the monitor script (if not already running)
uv run python scripts/apply_hyperparameter_results.py

# Or manually check
cat reports/optimization/hyperparameter_optimization_results.json
cat reports/optimization/comparison.md
```

### 2. Evaluate Improvements

**Decision criteria**:

- **Significant improvement**: >2% RMSE reduction on test set
- **Marginal improvement**: 0.5-2% RMSE reduction
- **No improvement**: <0.5% reduction

### 3. Apply Best Parameters (if improvements are significant)

**Update `src/models/train_model.py`**:

For Ridge (spreads) - around line 180:

```python
spread_model = Ridge(alpha=<BEST_ALPHA>)  # Update from optimization results
```

For RandomForest (totals) - around line 185:

```python
total_model = RandomForestRegressor(
    n_estimators=<BEST_N_ESTIMATORS>,
    max_depth=<BEST_MAX_DEPTH>,
    min_samples_split=<BEST_MIN_SAMPLES_SPLIT>,
    min_samples_leaf=<BEST_MIN_SAMPLES_LEAF>,
    max_features=<BEST_MAX_FEATURES>,
    random_state=42,
)
```

### 4. Retrain Models

```bash
uv run python src/models/train_model.py \
  --train-years 2019,2021,2022,2023 \
  --test-year 2024 \
  --data-root "/Volumes/CK SSD/Coding Projects/cfb_model"
```

### 5. Evaluate on Full 2024 Season

```bash
# Run full season with new models
python scripts/cli.py run-season \
  --year 2024 \
  --start-week 5 \
  --end-week 16 \
  --data-root "/Volumes/CK SSD/Coding Projects/cfb_model" \
  --spread-threshold 6.0 \
  --total-threshold 6.0
```

### 6. Update Documentation

If improvements are substantial:

1. **Update decision log** (`docs/decisions/decision_log.md`):
   - Add entry for hyperparameter optimization results
   - Document new parameters and performance gains

2. **Update modeling baseline** (`docs/project_org/modeling_baseline.md`):
   - Update Ridge alpha value
   - Update RandomForest parameters
   - Update performance metrics

3. **Update performance summary** (`reports/2024/PERFORMANCE_SUMMARY.md`):
   - Add section on hyperparameter optimization
   - Update hit rates and ROI if changed
   - Compare before/after metrics

4. **Create session log** (`session_logs/2025-09-30/03.md`):
   - Document hyperparameter optimization process
   - Record best parameters found
   - Note performance improvements

---

## Parameter Grids Used

### Ridge (Spreads) - Fast Mode

```python
{
    "alpha": [0.001, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0],
    "fit_intercept": [True],
    "solver": ["auto"],
}
```

Current baseline: `alpha=0.1`

### RandomForest (Totals) - Fast Mode

```python
{
    "n_estimators": [150, 200, 250],
    "max_depth": [8, 10, None],
    "min_samples_split": [5, 10, 15],
    "min_samples_leaf": [2, 5],
    "max_features": ["sqrt", "log2"],
    "random_state": [42],
}
```

Current baseline:

- n_estimators=200
- max_depth=8
- min_samples_split=10
- min_samples_leaf=5
- max_features not set (defaults to 1.0 = all features)
- random_state=42

**Grid size**: 3 × 3 × 3 × 2 × 2 = 108 combinations × 5 CV folds = 540 model fits

---

## Troubleshooting

### If Processes Crash

```bash
# Check for error logs
cat /tmp/hyperopt.log
cat /tmp/hyperopt_spreads.log

# Restart optimization
uv run python scripts/optimize_hyperparameters.py \
  --data-root "/Volumes/CK SSD/Coding Projects/cfb_model" \
  --fast
```

### If Results Look Worse

This can happen due to:

1. **Overfitting to CV folds**: Check if CV score improved but test score degraded
2. **Wrong baseline comparison**: Ensure baseline uses same train/test split
3. **Hyperparameter grid misalignment**: Verify grid includes sensible values

**Solution**: Run with full parameter grid (no `--fast` flag) for more exploration

### If Taking Too Long

Fast mode should complete in:

- Ridge: 2-5 minutes
- RandomForest: 15-25 minutes

If much longer:

- Check CPU usage with `top` or `htop`
- Verify data is accessible (external drive connected)
- Consider killing and running with even smaller grid

---

## Performance Expectations

### Current Baseline (2024 Holdout)

- **Spreads (Ridge alpha=0.1)**: 54.7% hit rate
- **Totals (RandomForest)**: 54.5% hit rate
- **Combined**: 54.6% hit rate

### Realistic Improvement Targets

- **Conservative**: +0.3-0.5 percentage points (55.0-55.2% combined)
- **Optimistic**: +0.8-1.2 percentage points (55.5-55.8% combined)
- **Best case**: +1.5-2.0 percentage points (56.0-56.5% combined)

**Note**: Even small improvements are valuable. A 0.5pp gain on 400 bets = +2 wins, which significantly impacts ROI.

---

## Session Summary

**What We Accomplished**:

1. ✅ Created comprehensive hyperparameter optimization framework
2. ✅ Implemented fast mode for quicker iteration
3. ✅ Started parallel optimizations for both models
4. ✅ Created monitoring and reporting scripts
5. ✅ Documented complete workflow for applying results

**Current Status**:

- Optimizations running in background
- Expected completion: 3:30-3:40 PM for spreads, 3:35-3:45 PM for totals
- Results will be saved automatically
- Ready for review and application

**Next Session**:

- Review optimization results
- Apply best parameters if improvements are significant
- Retrain models and validate on full 2024 season
- Update documentation with new baseline performance

---

**Last Updated**: 2025-09-30 19:25:00 UTC  
**Session Duration**: ~20 minutes  
**Status**: ✅ Jobs queued and running
