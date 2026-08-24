# Session: Classifier CV Results & Strategic Analysis

**Date:** 2026-02-18
**Status:** Complete

---

## TL;DR

- **CatBoost Classifier CV:** ROI -5.88% ± 3.48%, **0/4 profitable folds**
- **Conclusion:** Classification pivot failed — WORSE than regression approaches
- **Root cause:** Market is too efficient for publicly available efficiency metrics
- **All 3 approaches exhausted** with current feature set
- **Next step:** Fundamental rethink required (see options below)

---

## Classifier CV Results

**File:** `artifacts/cross_validation/classifier/crossval_report.txt`
**Generated:** 2026-02-18 16:05:19

| Fold | Test Year | Train Years | Hit Rate | ROI | AUC | Log Loss | N Bets |
|------|-----------|-------------|----------|-----|-----|----------|--------|
| fold_2019 | 2019 | 2021,2022,2023 | 48.7% | -7.07% | 0.480 | 0.829 | 643 |
| fold_2021 | 2021 | 2019,2022,2023 | 47.1% | -10.14% | 0.478 | 0.823 | 665 |
| fold_2022 | 2022 | 2019,2021,2023 | 50.2% | -4.10% | 0.511 | 0.782 | 647 |
| fold_2023 | 2023 | 2019,2021,2022 | 51.2% | -2.20% | 0.508 | 0.795 | 650 |
| **Mean** | | | **49.3% ± 1.8%** | **-5.88% ± 3.48%** | **0.494** | **0.807** | **651** |

### Diagnosis

1. **AUC ≈ 0.494**: Nearly random discriminatory power. Folds 2019 and 2021 have AUC < 0.5 (anti-predictive).
2. **Log loss = 0.78-0.83 > 0.693**: Predictions are worse than always predicting 50%. Model is actively harmful.
3. **avg_edge = 18-19%**: Model predicts extreme probabilities (P≈0.68 or 0.32) but is wrong at coin-flip rates. Wildly overconfident.
4. **0/4 profitable folds**: Complete failure across all evaluated seasons.

---

## Full Model Comparison

| Model | Mean ROI | Std ROI | Profitable Folds | Best Fold |
|-------|----------|---------|------------------|-----------|
| Ridge Regression | -5.22% | ±6.09% | 1/4 | 2022: +3.64% |
| CatBoost Regression | -4.55% | ±5.08% | 1/4 | 2021: +0.91% |
| **CatBoost Classifier** | **-5.88%** | **±3.48%** | **0/4** | 2023: -2.20% |

**All three fundamentally different approaches failed with the same feature set.**

---

## Root Cause: Market Efficiency

The consistent failure across all approaches points to a single core issue:

**The spread market already prices in EPA, success rate, and YPP.**

These are publicly available Box Score Stats metrics. Professional oddsmakers and sophisticated bettors use the same data. Our model cannot find information the market doesn't already have.

Evidence:
- Log loss > 0.693 = our probability estimates are WORSE than just saying "50% always"
- Including `spread_line` as a feature didn't help the classifier learn when to disagree with the market
- The pattern holds across all model architectures (linear, boosted trees, classification)

---

## Why the 2024 Single-Holdout Showed +0.11%

1. **Single-holdout is unreliable**: A single year is insufficient to estimate generalization
2. **2024 may be an anomaly**: The model happened to align with 2024's characteristics
3. **Future information in LOSO CV**: The LOSO folds use future years in training (e.g., 2023 data to predict 2021). Walk-forward CV would be more rigorous.
4. **Variance**: ±6.09% standard deviation means a +0.11% holdout is well within noise range

---

## Phase 2 Infrastructure Built (Not Wasted)

The classification pivot infrastructure is complete and committed:
- `src/cks_picks_cfb/models/v2_classifier.py`
- `conf/model/catboost_classifier.yaml`
- `conf/features/cover_classifier_v1.yaml`
- `conf/experiment/v2_classifier_crossval.yaml`

This infrastructure remains useful for future experiments.

---

## Options for Next Steps

### Option B: Feature Stability Analysis (1 week)

**Question:** Do ANY of our current features have consistent signal across years?

**Approach:**
1. Compute SHAP values per fold
2. Identify features with consistent SHAP importance across all folds
3. Remove high-variance, low-importance features
4. Re-run CV with reduced feature set (e.g., just EPA + success rate, no YPP)

**Hypothesis:** Pass YPP may add noise without signal. A 4-feature model (EPA + SR for home/away) might generalize better.

### Option C: PPR Integration (2-3 weeks)

**Question:** Does a Bayesian dynamic ratings model outperform static season averages?

**Already built:** `scripts/ratings/train_ppr.py` (PyMC, Gaussian Random Walk, uncertainty quantification)

**Key advantage:** PPR outputs rating distributions, not just point estimates. This enables uncertainty-aware betting.

### New Option E: Totals Market

**Question:** Is the over/under market less efficient than the spread market?

**Rationale:**
- Different bettor demographics — fewer sophisticated totals bettors
- Totals depend on pace/style, weather, game script — factors our features partly capture
- Would require new pipeline: predict total points scored, not margin

### New Option F: Non-Public Data

**Question:** Does information the market CAN'T fully price in provide edge?

**Possibilities:**
- Injury reports (beat reporter sources)
- Weather (wind speed, precipitation — especially impacts kicking)
- Travel distance / timezone crossings
- Transfer portal / roster composition
- Vegas line movement (sharp vs. square money)

### Option G: Pause Modeling / Rethink Scope

**Question:** Is spread betting the right market to target?

**Alternative scopes:**
- Player prop betting (individual performance, less public modeling)
- Live/in-game betting (dynamic edge opportunities)
- Different sport with less sophisticated market

---

## Decision Required

Given the comprehensive failure of all spread-betting approaches with public efficiency metrics, we need to decide:

1. **Continue with spreads**: Pursue B, C, E, or F above
2. **Pivot to totals**: Different target, different dynamics
3. **Add proprietary data**: Non-public information sources
4. **Scope change**: Different betting market or sport

**Recommendation:** Option B (feature stability analysis) first — cheapest, fastest, uses existing infrastructure. If no features show consistent signal, that tells us the current data fundamentally can't beat the market.

---

## Files Created/Modified This Session

| File | Action | Purpose |
|------|--------|---------|
| `artifacts/cross_validation/classifier/crossval_report.txt` | Generated | Classifier CV results |
| `artifacts/cross_validation/classifier/crossval_fold_results.csv` | Generated | Per-fold data |
| `artifacts/cross_validation/classifier/crossval_aggregated.json` | Generated | Aggregated metrics |
| `session_logs/2026-02-18/04-classifier-cv-results-and-analysis.md` | Created | This log |

---

**tags:** ["classifier-cv", "results", "market-efficiency", "strategic-analysis", "phase5", "failed-pivot"]
