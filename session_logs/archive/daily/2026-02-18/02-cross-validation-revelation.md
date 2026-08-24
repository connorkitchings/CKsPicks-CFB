# Session: Cross-Validation Revelation - Strategic Pivot Required

**Date:** 2026-02-18  
**Duration:** ~4 hours  
**Status:** Session complete - Critical findings documented

---

## TL;DR

- **Worked On:** Cross-validation implementation and execution
- **Completed:**
  - Implemented leave-one-season-out cross-validation framework
  - Ran 4-fold parallel validation across 2019, 2021-2023
  - **CRITICAL FINDING:** Model unstable - ROI: -5.22% ± 6.09%
  - 3 of 4 folds negative, hit rate 49.6% (below breakeven)
  - 2024 single-holdout was misleading (+0.11%)
- **Blockers:** Model fundamentally flawed - requires strategic pivot
- **Next:** Return to drawing board with ROI-focused approach

---

## Cross-Validation Execution

### Implementation

Created parallel cross-validation system:
- **Config:** `conf/experiment/v2_champion_crossval.yaml`
- **Script:** `scripts/training/cross_validation.py`
- **Folds:** 4 parallel jobs (30 min total)

**Fold Configuration:**
| Fold | Train | Test |
|------|-------|------|
| 1 | 2021-2023 | 2019 |
| 2 | 2019, 2022-2023 | 2021 |
| 3 | 2019, 2021, 2023 | 2022 |
| 4 | 2019-2021, 2022 | 2023 |

### Results

**Aggregate Performance:**
```
ROI: -5.22% ± 6.09% [Range: -9.68% to +3.64%]
Hit Rate: 49.6% ± 3.2% [Range: 47.3% to 54.3%]
RMSE: 19.25 ± 0.98
N Bets: 706 ± 9
```

**Per-Fold Breakdown:**
| Fold | ROI | Hit Rate | Assessment |
|------|-----|----------|------------|
| 2019 | -9.68% | 47.3% | ❌ Terrible |
| 2021 | -6.18% | 49.1% | ❌ Poor |
| 2022 | +3.64% | 54.3% | ✅ Good |
| 2023 | -8.66% | 47.8% | ❌ Terrible |

**Only 1 of 4 folds profitable!**

### Comparison to Single-Holdout

| Method | ROI | Hit Rate | Verdict |
|--------|-----|----------|---------|
| 2024 Single-Holdout | +0.11% | 52.44% | ❌ Misleading |
| 4-Fold Cross-Validation | -5.22% | 49.6% | ✅ Truth |

**Key Insight:** 2024 was an **outlier year** - gave false confidence.

---

## Strategic Implications

### What Went Wrong

1. **Single-holdout validation is unreliable** for this problem
2. **Features lack temporal stability** - work in some years, fail in others
3. **Linear model too simple** - Ridge regression cannot capture complex patterns
4. **Current approach fundamentally flawed** - loses money on 75% of seasons

### User Feedback (Critical)

**Final Goal Clarified:**
> "Maximize ROI on gambling considering 1) accuracy of bets and 2) number of bets placed based on edge viewed based on market lines"

**This means:**
- Not just prediction accuracy
- Volume matters (more edge = more bets)
- Market-aware (relative to lines, not absolute)
- ROI = accuracy × volume with edge

### New Constraints

1. **New infrastructure** - Cloud storage changes data access patterns
2. **New processes** - Cross-validation now standard
3. **ROI-focused** - Not just accuracy, but profitable betting
4. **Go back to drawing board** - Current approach not viable

---

## Decisions Made

### ✅ Keep
- Cross-validation framework (proved its value!)
- Cloud storage integration (working well)
- Phase 4 optimizations (ready when model works)
- Deployment documentation (prepared for future)

### ❌ Discard
- Current champion model (matchup_v1 + Ridge)
- Single-holdout validation (unreliable)
- Deploy to production (would lose money)

### 🔄 Pivot To
- Re-examine entire feature engineering pipeline
- Test non-linear models (CatBoost, XGBoost)
- ROI-focused optimization (not just RMSE)
- Edge-based bet volume optimization
- Alternative targets/approaches

---

## Files Created/Modified

### New Files
- `conf/experiment/v2_champion_crossval.yaml` - CV configuration
- `scripts/training/cross_validation.py` - Parallel CV runner
- `docs/deployment/` - Complete deployment docs (4 files)
- `conf/model/champion.yaml` - Model configuration
- `artifacts/cross_validation/` - CV results and reports

### Modified Files
- `src/cks_picks_cfb/utils/data_validation.py` - Lint fixes
- `tests/test_data_validation.py` - Lint fixes
- `tests/test_external_ratings.py` - Lint fixes
- `src/cks_picks_cfb/features/v2_recency.py` - Cloud storage support
- `scripts/pipeline/generate_weekly_bets.py` - Dual thresholds
- `REFACTORING_STATUS.md` - Updated status

### Archived
- `archive/experiments/*.yaml` - 6 legacy experiments

---

## Technical Details

### Cross-Validation Artifacts

**Location:** `artifacts/cross_validation/`
- `crossval_fold_results.csv` - Per-fold metrics
- `crossval_aggregated.json` - Summary statistics
- `crossval_report.txt` - Full report

### MLflow Experiments

Created 5 experiments:
- `crossval_fold_2019` - 2019 test results
- `crossval_fold_2021` - 2021 test results
- `crossval_fold_2022` - 2022 test results (only positive!)
- `crossval_fold_2023` - 2023 test results
- `v2_champion_final` - Final model (all years)

### Runtime

- Cross-validation: 38 minutes (4 parallel folds)
- Single fold: ~25-30 minutes
- Final model: ~30 minutes

---

## Notes for Next Session

### Resume At

**Strategic planning session** - Re-evaluate entire approach with ROI focus

### Context to Carry Forward

1. **Cross-validation is now standard** - Never trust single-holdout again
2. **Current model is not viable** - Start fresh with new approach
3. **ROI is the metric** - Not RMSE, not hit rate alone
4. **Infrastructure is solid** - Cloud storage, processes working well
5. **2024 was an outlier** - Don't let it bias future decisions

### Key Questions to Answer

1. What features are stable across years?
2. Can CatBoost/XGBoost capture non-linear patterns?
3. How to optimize for ROI vs just accuracy?
4. What's the relationship between edge magnitude and win probability?
5. Should we predict probability of cover vs margin?

### Potential Next Steps

**Option A: Quick Win (2-3 days)**
- Test CatBoost with current features
- Compare to Ridge baseline
- See if non-linearity helps

**Option B: Deep Dive (1 week)**
- Analyze feature stability across years
- Identify which features work consistently
- Engineer new stable features

**Option C: Alternative Approach (2-3 weeks)**
- Predict probability of cover (not margin)
- Binary classification vs regression
- Kelly criterion bet sizing

**Option D: Full Reset (1 month)**
- Literature review on sports betting models
- Re-design from first principles
- New feature pipeline

### Watch Out For

- **Overfitting to 2022** (only positive fold)
- **Chasing last year's winners**
- **Ignoring market efficiency**
- **Feature leakage across time**
- **Survivorship bias in data**

### Success Criteria

Next model must:
- ✅ Positive ROI in 3+ of 4 CV folds
- ✅ Hit rate > 52.4%
- ✅ Stable across years (σ < 3%)
- ✅ Justifiable edge logic
- ✅ Deployable to production

---

## Key Takeaways

1. **Cross-validation saved the project** - Caught what single-holdout missed
2. **Current model loses money** - 75% of seasons unprofitable
3. **Infrastructure is ready** - Just need a working model
4. **ROI focus changes everything** - Not just prediction accuracy
5. **Return to fundamentals** - Re-examine entire approach

### The Silver Lining

**Better to discover this now than after deploying!**
- No money lost on bad bets
- Framework in place for proper validation
- Clear direction for next iteration
- Infrastructure ready for future success

---

**tags:** ["v2", "cross-validation", "strategic-pivot", "roi-focused", "model-failure", "infrastructure-ready"]

---

*Session completed. Cross-validation framework proved its worth by catching a fundamentally flawed model before deployment. Time to return to drawing board with ROI-focused approach.*
