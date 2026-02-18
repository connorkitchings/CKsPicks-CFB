# Session: Strategic Pivot - CatBoost CV + Classification Infrastructure

**Date:** 2026-02-18
**Duration:** ~2 hours
**Status:** In progress - CatBoost CV running (4 parallel folds)

---

## TL;DR

- **Worked On:** Post-CV-revelation strategic pivot implementation
- **Completed:**
  - Diagnosed root causes of V2 model failure
  - Made `cross_validation.py` reusable (parameterized experiment name)
  - Fixed duplicate code bug in `cross_validation.py`
  - Created CatBoost CV configuration (`v2_catboost_crossval.yaml`)
  - Built complete Classification Pivot infrastructure (Phase 2)
  - CatBoost CV currently running in background (4 parallel folds, ~25-30 min)
- **Blockers:** None - waiting for CV results
- **Next:** Compare CatBoost CV vs Ridge, then run classifier CV

---

## Context

Following the critical cross-validation revelation (ROI: -5.22% ± 6.09%, only 1/4 folds profitable),
we planned a two-phase strategic pivot:

**Phase 1:** Quick test - Does CatBoost do better with proper CV? (previously rejected using flawed 2024 single-holdout)
**Phase 2:** Classification pivot - Predict P(Cover) directly instead of point margin

---

## Changes Made

### Phase 1: CatBoost CV Test

#### Modified: `scripts/training/cross_validation.py`
- Added `--experiment` argument (defaults to config filename stem)
- Experiment name now passed to `run_single_fold()` as parameter
- `train_final_model()` now takes `experiment_name` and `final_model_name` params
- **Fixed bug:** Removed duplicate exception handler blocks (dead code after return statements)
- Backward compatible: existing `v2_champion_crossval` still works with default args

#### Created: `conf/experiment/v2_catboost_crossval.yaml`
- Identical fold structure to champion CV
- Uses `catboost_v1` model instead of `linear`
- Same `matchup_v1` features for fair comparison
- Same betting config for consistent evaluation

**Run command:**
```bash
source .env && PYTHONPATH=. uv run python scripts/training/cross_validation.py \
  --config conf/experiment/v2_catboost_crossval.yaml \
  --experiment v2_catboost_crossval \
  --output-dir artifacts/cross_validation/catboost
```

### Phase 2: Classification Pivot Infrastructure

#### Created: `src/cks_picks_cfb/models/v2_classifier.py`
- `V2ClassifierModel` using `CatBoostClassifier` (Logloss)
- Creates binary cover target internally: `home_covered = (spread_target > -spread_line)`
- `predict_proba(df)` → P(Home Covers) for each game
- `evaluate(df, threshold=0.024)` → hit_rate, roi, n_bets, auc, log_loss, calibration_error
- Betting logic: bet when P(Cover) > 0.524 or < 0.476 (2.4% edge threshold)
- ROI stubs (rmse/mae=0) for MLflow schema consistency

#### Created: `conf/model/catboost_classifier.yaml`
- Type: `catboost_classifier`
- Loss: Logloss, Eval metric: AUC
- Target: `cover_target` (kept for interface compatibility, derived internally)

#### Created: `conf/features/cover_classifier_v1.yaml`
- All 16 matchup_v1 features
- **Plus: `spread_line`** — market signal letting model learn when efficiency metrics disagree with the market

#### Created: `conf/experiment/v2_classifier_crossval.yaml`
- Same 4-fold structure
- Uses `catboost_classifier` model + `cover_classifier_v1` features
- Classifier betting thresholds: 0.024 default, 0.05 high-confidence

#### Modified: `src/cks_picks_cfb/train.py`
- Added `catboost_classifier` model type to `get_model()` factory
- Updated model save extension handler for `.cbm` files

---

## Root Cause Analysis (Documented)

**Why V2 failed:**
1. Single-holdout validation (2024) was an outlier year - gave false confidence
2. Regression target (RMSE) is misaligned with betting goal (maximize ROI)
3. Pass YPP features are temporally unstable (already requires clipping)
4. Complex models were rejected using flawed single-holdout validation
5. No adaptation to year-over-year temporal shifts

---

## Testing

### Code Quality
```bash
$ uv run ruff check .
All checks passed!
```

### Smoke Tests
- Classifier model: ✅ Fits and evaluates correctly on dummy data
- Full test suite: 141 passed, same pre-existing failures (external drive unavailable)

---

## CatBoost CV Status (Running)

**Started:** ~3:29 PM today
**Processes:** 4 parallel train.py processes running
**Expected completion:** ~4:00 PM (25-30 minutes per fold)

**What to expect:**
- Best case: CatBoost shows >-5.22% mean ROI or ≥2/4 profitable folds
  → Proceed with CatBoost-based classifier as Phase 2
- Likely case: CatBoost comparable to Ridge on regression
  → Confirms we need classification pivot (Phase 2)
- Either way: Phase 2 (classifier) is fully implemented and ready to run

**Check results:**
```bash
cat artifacts/cross_validation/catboost/crossval_report.txt
```

---

## Files Created/Modified

| File | Action | Purpose |
|------|--------|---------|
| `scripts/training/cross_validation.py` | Modified | Parameterized experiment name, fixed bug |
| `conf/experiment/v2_catboost_crossval.yaml` | Created | CatBoost CV config |
| `src/cks_picks_cfb/models/v2_classifier.py` | Created | CatBoost classifier for P(Cover) |
| `conf/model/catboost_classifier.yaml` | Created | Classifier model config |
| `conf/features/cover_classifier_v1.yaml` | Created | Classification features (+ spread_line) |
| `conf/experiment/v2_classifier_crossval.yaml` | Created | Classifier CV config |
| `src/cks_picks_cfb/train.py` | Modified | Support catboost_classifier type |

---

## Notes for Next Session

### After CatBoost CV Completes

Check results:
```bash
cat artifacts/cross_validation/catboost/crossval_report.txt
```

**Decision tree:**
1. If CatBoost regression does significantly better than Ridge (-5.22%) → maybe tune CatBoost
2. Regardless → run classifier CV:
   ```bash
   source .env && PYTHONPATH=. uv run python scripts/training/cross_validation.py \
     --config conf/experiment/v2_classifier_crossval.yaml \
     --experiment v2_classifier_crossval \
     --output-dir artifacts/cross_validation/classifier
   ```

### Context to Carry Forward
1. V2 model failure was fundamentally due to single-holdout validation
2. Cross-validation is now the standard - never trust single-holdout
3. Classification pivot is fully implemented and ready
4. Key hypothesis: predicting P(Cover) with spread_line as feature will be more stable

### Success Criteria (Classifier Must Meet)
- ✅ Positive ROI in ≥3 of 4 CV folds
- ✅ Hit rate > 52.4% on average
- ✅ Calibration error < 5%
- ✅ Standard deviation < 3% ROI

---

**tags:** ["strategic-pivot", "catboost-cv", "classification", "v2", "phase2", "infrastructure"]
