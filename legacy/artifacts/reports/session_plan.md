# Data Science Navigator - Initial Report

## 1) Project + Recent-Work TL;DR

- **Modeling Stack**: Transitioning from separate Spread/Total ensembles to a unified "Points-For" architecture (predicting Home/Away scores).
- **Status**: "Points-For" prototype showed 53.3% spread hit rate on 2024 data (Session 11-23), but **failed** multi-year walk-forward validation (2019-2024) with ~51.4% hit rate (Session 11-24).
- **Totals**: Totals model remains profitable (~54-55%) and stable.
- **Features**: Feature pruning (SHAP) identified a robust 40-feature subset. Recency and interaction features are critical.
- **Calibration**: Systematic spread bias (+1.4 points) identified in 2024, but its stability across years is unverified.
- **Infra**: Hydra/Optuna framework is robust. MLflow registry is active. Walk-forward validation is the gold standard.

## 2) Candidate Focus Areas

### Option A: Pruned Model & Bias Stability Validation

- **Description**: Run multi-year walk-forward validation specifically on the _pruned_ (40-feature) Points-For model. Concurrently, analyze calibration bias year-over-year to see if the +1.4 correction is universal or year-specific.
- **Expected Impact**: Could recover profitability by reducing overfitting (pruning) and applying dynamic/correct bias adjustments.
- **Effort Estimate**: Medium (Run existing scripts with new configs/analysis).
- **Dependencies**: `scripts/walk_forward_validation.py`, Pruned feature sets.
- **Betting Policy Alignment**: Directly targets >52.4% hit rate and robust edge calculation.

### Option B: XGBoost / Heterogeneous Ensemble

- **Description**: Introduce XGBoost models for Home/Away points to complement CatBoost. Create a mixed ensemble (e.g., 3 CatBoost + 3 XGBoost seeds).
- **Expected Impact**: Reduces model-specific variance; XGBoost often handles linear relationships differently than CatBoost.
- **Effort Estimate**: High (New model class integration, hyperparam tuning, validation).
- **Dependencies**: `src/models/` refactor to support XGBoost.
- **Betting Policy Alignment**: Diversification reduces risk of single-model failure.

### Option C: Probabilistic Power Ratings (Research)

- **Description**: Begin the "Future Sprint" research into Elo/Bayesian ratings to drive spreads.
- **Expected Impact**: Long-term stability and interpretability, but unlikely to yield immediate betting candidates this session.
- **Effort Estimate**: Medium (Research/Prototyping).
- **Dependencies**: None.
- **Betting Policy Alignment**: Future foundation for uncertainty quantification.

## 3) Recommended Plan

- **Focus**: **Option A: Pruned Model & Bias Stability Validation**
- **Justification**:
  - The "failure" of the Points-For model might be due to overfitting the full 116-feature set. The pruned (40-feature) version performed well in 2024 but wasn't explicitly validated across 2019-2023.
  - The +1.4 bias correction was derived _only_ from 2024. If 2023 had a -1.0 bias, our correction is making things worse. We need to know the bias stability.
  - This leverages existing caches and scripts immediately.
  - It directly addresses the "not consistently profitable" blocker from the last session.
- **Step-by-Step Execution Plan**:
  1.  **Configure**: Verify Hydra config for `points_for_pruned` experiment.
  2.  **Validate**: Run `scripts/walk_forward_validation.py` with `model=points_for` and `features=pruned` for years 2019, 2021-2024.
  3.  **Analyze**: Run `scripts/analyze_calibration.py` on the walk-forward outputs to generate year-by-year bias reports.
  4.  **Compare**: Contrast "Pruned" vs. "Baseline" performance.
  5.  **Report**: Synthesize results into `artifacts/reports/pruned_model_validation.md`.

## 4) Execution Checklist

1.  [ ] Verify/Create Hydra config for `points_for_pruned`.
2.  [ ] Run `scripts/walk_forward_validation.py` (Pruned, 2019-2024).
3.  [ ] Run `scripts/analyze_calibration.py` (Bias Analysis).
4.  [ ] Generate summary report `artifacts/reports/pruned_model_validation.md`.
5.  [ ] Update `docs/decisions/decision_log.md`.
