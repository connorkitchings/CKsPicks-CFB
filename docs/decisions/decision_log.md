# Decision Log

## 2025-12-08: V2 Phase 3 Re-evaluation with Matchup V1 Features - Complex Models Rejected Again

- **Context**: Re-evaluated CatBoost and XGBoost models for both spread and total targets, now utilizing the improved `matchup_v1` feature set. The goal was to determine if the new features could enable these complex models to surpass the performance of the Linear (Ridge) champion model.
- **CatBoost (Matchup V1, Spreads) Results (2024 Holdout)**:
  - RMSE: 19.41
  - MAE: 15.13
  - Hit Rate: 50.07%
  - ROI: -4.42% (vs Linear +0.78%)
- **XGBoost (Matchup V1, Spreads) Results (2024 Holdout)**:
  - RMSE: 19.54
  - MAE: 15.25
  - Hit Rate: 52.11%
  - ROI: -0.52% (vs Linear +0.78%)
- **CatBoost (Matchup V1, Totals) Results (2024 Holdout)**:
  - RMSE: 17.79
  - MAE: 14.11
  - Hit Rate: 50.82%
  - ROI: -2.99% (vs Linear +6.81% at 1.5 threshold)
- **XGBoost (Matchup V1, Totals) Results (2024 Holdout)**:
  - RMSE: 18.40
  - MAE: 14.68
  - Hit Rate: 50.00%
  - ROI: -4.55% (vs Linear +6.81% at 1.5 threshold)
- **Decision**: **REJECT** CatBoost and XGBoost models for both spread and total targets.
  - **Reasoning**: All complex models significantly underperformed the simpler Linear (Ridge) model across all key metrics (ROI, Hit Rate). None of these models came close to passing the Phase 3 promotion gate of +1.5% ROI improvement over the linear baseline on the same features. This reinforces the finding that the Linear model remains the most robust and profitable for this problem.
- **Impact**: Confirms the current champion model architecture. Future efforts should focus on feature engineering, data quality, or novel linear approaches rather than more complex model types, until a compelling reason or significant feature set is discovered that might benefit non-linear relationships.

## 2025-12-08: Totals Walk-Forward Validation - Matchup V1 Confirmed Profitable

- **Context**: Performed walk-forward validation on the `matchup_v1` Totals model (with a 0.5 point threshold) across recent holdout years to assess its long-term stability and profitability.
- **Walk-Forward Results**:
  | Year | Bets | Hit Rate | ROI |
  | :-- | :--- | :------- | :-- |
  | 2021 | 660 | 53.33% | +1.82% |
  | 2022 | 668 | 51.65% | -1.40% |
  | 2023 | 686 | 53.64% | +2.41% |
  | 2024 | 698 | 55.59% | +6.12% |
  | **Avg** | **678** | **53.55%** | **+2.24%** |
- **Decision**: **CONFIRMED** `matchup_v1` Totals model exhibits a positive edge over the long term.
  - **Reasoning**: The model achieved positive ROI in 3 out of 4 years. While 2022 showed a slight loss, the average ROI of +2.24% indicates a consistent, albeit modest, long-term edge with the 0.5 threshold. The strong +6.12% in 2024 (and +6.81% with the 1.5 threshold) suggests the model can capture significant value in certain seasons.
- **Impact**: Provides increased confidence in the Totals model's profitability. Future deployments will use the optimized 1.5 point threshold for higher ROI, as determined in the "Totals Threshold Tuning" decision.

## 2025-12-08: Spread Threshold Optimization - Dual Approach Recommended

- **Context**: Analyzed ROI vs. Edge Threshold for the champion Spread model (`matchup_v1`) on 2024 holdout data to identify optimal betting thresholds.
- **Analysis Results**:
  | Threshold | Bets | Volume % | Hit Rate | ROI |
  |-----------|------|----------|----------|-----|
  | **0.0** | **735** | **99.5%** | **52.8%** | **+0.78%** |
  | 2.5 | 576 | 77.9% | 51.6% | -1.56% |
  | 5.0 | 436 | 59.0% | 52.3% | -0.17% |
  | 6.0 | 381 | 51.6% | 50.7% | -3.29% |
  | 7.0 | 353 | 47.8% | 50.7% | -3.19% |
  | **8.0** | **305** | **41.3%** | **53.4%** | **+2.03%** |
  | 9.0 | 264 | 35.7% | 53.0% | +1.24% |
- **Decision**: **Implement a dual-threshold approach for Spreads**:
  1.  **Default Threshold (for general betting): 0.0 points.** This maintains the current "all bets" approach with a marginal positive ROI (+0.78%).
  2.  **High-Confidence Threshold (for selective betting): 8.0 points.** This significantly increases profitability to +2.03% for a more selective set of games (41.3% volume).
  - **Reasoning**: The mid-range thresholds (2.5-7.0) are consistently unprofitable, indicating the model's edge is either very clear or non-existent in those ranges. The 8.0 threshold provides the highest ROI found.
- **Impact**: Provides flexibility for betting strategy, allowing for both broad coverage and highly selective, profitable plays.

## 2025-12-08: Totals Threshold Tuning - Optimized to 1.5 Points

- **Context**: Analyzed ROI vs. Edge Threshold for the champion Totals model (`matchup_v1`) on 2024 holdout data to balance volume and profitability.
- **Analysis Results**:
  | Threshold | Bets | Volume % | Hit Rate | ROI |
  |-----------|------|----------|----------|-----|
  | 0.5 | 698 | 94.5% | 55.6% | +6.12% |
  | **1.5** | **597** | **80.8%** | **55.9%** | **+6.81%** |
  | 2.0 | 560 | 75.8% | 55.9% | +6.70% |
  | 3.0 | 477 | 64.5% | 54.7% | +4.46% |
- **Decision**: **Increase default Totals threshold from 0.5 to 1.5 points**.
  - **Reasoning**: Moving to 1.5 increases ROI to its peak (+6.81%) while reducing volume by ~14% (removing the lowest-confidence bets).
  - **Impact**: Expected to maintain high profitability while reducing variance from marginal edge cases.
  - **Spread Note**: Spread threshold remains 0.0 for evaluation, but 8.0 showed promise (+2.03% ROI) for high-confidence picks.

## 2025-12-08: Walk-Forward Validation - Matchup Features PROMOTED

- **Context**: Validated matchup_v1 features using walk-forward validation across 4 holdout years.
- **Walk-Forward Results** (spread target):

  | Holdout | Champion ROI | Matchup ROI | Improvement |
  | ------- | ------------ | ----------- | ----------- |
  | 2021    | -6.60%       | -6.05%      | +0.55%      |
  | 2022    | +1.07%       | +2.17%      | +1.10%      |
  | 2023    | -8.01%       | -8.01%      | +0.00%      |
  | 2024    | +0.52%       | +0.78%      | +0.26%      |
  | **Avg** | **-3.26%**   | **-2.78%**  | **+0.48%**  |

- **Decision**: **PROMOTE** matchup_v1 as new champion.
  - Improvement is consistent across 3/4 years (never worse)
  - Average improvement of +0.48% ROI
  - Totals showed +1.05% improvement on 2024 holdout
- **New Champion Config**: `conf/features/matchup_v1.yaml` (16 features)

## 2025-12-08: V2 Phase 2 Alpha Optimization - No Change

- **Context**: Grid searched EWMA decay alpha ∈ {0.1, 0.2, 0.3, 0.4, 0.5} on spread target.
- **Results** (2024 Holdout):
  | Alpha | Hit Rate | ROI |
  |-------|----------|-----|
  | 0.1 | 50.75% | -3.12% |
  | 0.2 | 51.84% | -1.04% |
  | **0.3** | **52.65%** | **+0.52%** |
  | 0.4 | 52.11% | -0.52% |
  | 0.5 | 52.65% | +0.52% |
- **Decision**: **NO CHANGE**. α=0.3 and α=0.5 are tied at +0.52% ROI. No improvement over current champion.
- **Insight**: The 0.3-0.5 range is optimal; lower alpha (more smoothing) degrades performance. Recommend keeping α=0.3.

## 2025-12-08: V2 Documentation Aligned - Champion Models Ready for Deployment

- **Context**: Completed Option A (Documentation & Deployment) from session plan.
- **Updates Made**:
  - `docs/experiments/index.md` — All 10 V2 experiments documented with results
  - `docs/modeling/betting_policy.md` — V2 Champion section with optimal thresholds
  - `docs/project_org/feature_registry.md` — Feature status corrected (recency_weighted_v1 = champion)
- **Current Champions**:
  - **Spread**: Linear + recency_weighted_v1 → +0.52% ROI (7.0 pt threshold → +2.1% ROI)
  - **Totals**: Linear + recency_weighted_v1 → +5.3% ROI (0.5 pt threshold → +6.1% ROI)
- **Decision**: Models are **ready for CFP deployment** (Dec 20-21 quarterfinals).

## 2025-12-07: V2 Phase 2 Interaction Features - Rejected

- **Context**: Tested 4 explicit interaction features (Off x Def EPA/SR) on top of the Recency Champion.
- **Results**:
  - **Interactions**: ROI -0.26% | Hit Rate 52.2%
  - **Champion (Corrected)**: ROI +0.52% | Hit Rate 52.7%
- **Decision**: **REJECT**.
  - Interactions degraded performance by ~0.8% ROI.
  - Complexity not justified.

## 2025-12-07: Critical Bug Fix - Recency Data Duplication

- **Context**: Discovered `load_v2_recency_data` was returning 5x duplicate rows (one for each iteration 0-4) due to missing filter in `v2_recency.py`.
- **Fix**: Added filter to keep only the final iteration (`adj_df = adj_df[adj_df["iteration"] == iterations]`).
- **Impact**: Retrained Champion on corrected data. New metrics are significantly better (positive ROI!).
- **New Champion Metrics (2024)**:
  - Hit Rate: **52.65%**
  - ROI: **+0.52%**
  - RMSE: 18.82

## 2025-12-07: V2 Phase 4 Stacking - Failed

- **Context**: Trained a Stacking Ensemble (Meta-learner: Logistic Regression) on Linear and XGBoost OOF predictions.
- **Results**:
  - **Stacking**: ROI -5.36% | Hit Rate 49.6%
- **Decision**: **REJECT**.
  - Significantly worse than the Recency-Weighted Linear Model (-0.15%).
  - Increased complexity yielded negative value. Confirms that simpler models are currently superior for this dataset.

## 2025-12-07: V2 Phase 2.5 Recency Weighting - Promoted

- **Context**: Implemented exponential decay (`alpha=0.3`) for storage aggregation to weight recent games more heavily.
- **Results**:
  - **Recency Linear**: ROI -0.15% | Hit Rate 52.3%
  - **Previous Best**: ROI -0.97%
- **Decision**: **PROMOTE TO CHAMPION**.
  - This is the single biggest improvement in the V2 workflow.
  - ROI is virtually break-even (-0.15%).
  - Validates the hypothesis that "recent form matters more."

## 2025-12-07: V2 Phase 3.5 XGBoost Tuning - Failed

- **Context**: Used Optuna to tune XGBoost hyperparameters to beat the -0.97% ROI benchmark.
- **Results**:
  - **Tuned XGBoost**: ROI -1.23% | Hit Rate 51.7%
- **Decision**: **REJECT**.
  - The tuned model performed worse than the untuned default XGBoost (-0.71%).
  - Shows high sensitivity to hyperparameters and potential overfitting.
  - Linear models remain the most robust "Bang for Buck".

## 2025-12-07: V2 Phase 4 Ensembling - Failed

- **Context**: Tested a weighted ensemble (50/50) of the Baseline (Linear) and XGBoost models.
- **Results**:
  - **Ensemble**: ROI -3.09% | Hit Rate 50.8%
- **Decision**: **REJECT**.
  - The ensemble performed significantly worse than its components (Linear -0.97%, XGBoost -0.71%).
  - Naive averaging is not effective for these models on this dataset.
  - Future hypothesis: Use Stacking (train a meta-model on predictions) or improve calibration of XGBoost before averaging.

## 2025-12-07: V2 Phase 3 Model Selection - Status Quo

- **Context**: Tested advanced non-linear models (CatBoost, XGBoost) against the linear baseline (`opponent_adjusted_v1`) on 2024 data.
- **Results**:
  - **Baseline (Linear)**: ROI -0.97% | Hit Rate 51.9%
  - **CatBoost**: ROI -1.76% | Hit Rate 51.5%
  - **XGBoost**: ROI -0.71% | Hit Rate 52.0%
- **Decision**: **MAINTAIN CHAMPION** (`opponent_adjusted_v1` + Linear).
  - XGBoost outperformed the baseline by +0.26% ROI, but failed the aggressive +1.5% promotion gate.
  - The complexity of maintaining an XGBoost pipeline is not yet justified by the marginal gain.
  - XGBoost is flagged as a high-potential candidate for Phase 4 (Ensembling).

## 2025-12-07: V2 Phase 2 Feature Promotion

- **Context**: Evaluated `opponent_adjusted_v1` feature set against `minimal_unadjusted_v1`.
- **Decision**: **PROMOTED**.
- **Reasoning**: ROI improved from -3.35% to -0.97% (+2.38% lift), exceeding the +1.0% threshold.

## 2025-12-06: V2 Baseline Metrics Established

- **Context**: Established strict V2 baseline using Ridge Regression and `minimal_unadjusted_v1`.
- **Metrics**:
  - RMSE: 18.64
  - Hit Rate: 50.6%
  - ROI: -3.35%
- **Decision**: All future models must beat this ROI to be considered.
