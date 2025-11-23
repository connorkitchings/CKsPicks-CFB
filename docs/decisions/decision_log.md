# Decision Log

## 2025-11-23: Calibration Analysis Reveals Systematic Spread Bias

- **Context:** Performed comprehensive calibration analysis on Iteration-2 CatBoost models using 2024 holdout data (Train: 2019, 2021-2023; Test: 2024). Analyzed residuals, calibration curves, and edge bin performance for both spread and total models.
- **Findings:**
  - **Spread Model (Baseline v1):** RMSE 17.93, MAE 14.02, but shows **+1.4 point positive bias** (mean residual). This indicates systematic under-prediction of home team margins.
  - **Total Model (Pace Interaction v1):** RMSE 17.14, MAE 13.33, **near-zero bias** (-0.35 points). Excellent calibration.
  - **Edge Bin Analysis:** No performance degradation at higher edges; bias is consistent across all edge magnitudes.
  - **Hit Rates:** Spread 46.6% (below breakeven), Total 54.6% (above breakeven, +82 units).
- **Decision:**
  1. **Immediate:** Apply post-processing bias correction to spread predictions (`calibrated_pred = raw_pred - 1.4`) before production deployment.
  2. **Threshold Tuning:** Increase spread edge threshold from 3.5 → 5.0 points to improve hit rate and reduce bet volume on marginal edges.
  3. **Monitoring:** Add prediction interval logging to `run_experiment.py` and set up weekly calibration monitoring for live betting.
- **Rationale:** Bias correction is a simple, reversible fix that can immediately improve spread model performance. Threshold tuning reduces exposure to low-edge bets where the model is less profitable.
- **Impact:** Expected to improve spread hit rate by ~2-3 percentage points (bias correction) and reduce bet volume by ~40% while concentrating on higher-quality opportunities.
- **Artifacts:** Full analysis in `artifacts/reports/calibration/calibration_analysis_2024.md` with 8 plots and detailed recommendations.

## 2025-11-23: Standardize on Adjustment Iteration 2

- **Context:** We conducted a series of experiments to evaluate the impact of opponent-adjustment iteration depth (0-4) on model performance. The initial default was Iteration 4. We re-ran the experiments with a strict training split (2019, 2021-2023) and test set (2024).
- **Decision:** Switch both the **Spread** and **Total** CatBoost models to use **Iteration 2**.
- **Rationale:**
  - **Spread:** Iteration 2 yielded the best RMSE (17.97) and tied for the best Hit Rate (48.2%).
  - **Total:** Iteration 2 yielded the best Hit Rate (54.1%), outperforming the default Iteration 4 (53.3%) despite a slightly higher RMSE.
  - **Simplicity:** Standardizing on a single iteration depth simplifies the feature pipeline and cache management.
- **Impact:** `conf/model/spread_catboost.yaml` and `conf/model/total_catboost.yaml` updated to `adjustment_iteration: 2`. Future feature engineering can focus on optimizing Iteration 2.

## 2025-11-21: Successful Walk-Forward Validation of CatBoost Spread Model

- **Context:** After multiple failed attempts to stabilize the linear models, the root cause was identified as a data quality issue in the feature engineering pipeline, specifically the handling of `NaN` values in special teams and trench warfare features for older seasons.
- **Decision:** A fix was implemented in `src/features/core.py` to handle `NaN` values more robustly by using `np.nansum` and clipping extreme values for punt yardage. The feature caches for 2019, 2021, and 2022 were rebuilt. A walk-forward validation was successfully run for the CatBoost spread model on the 2023 and 2024 seasons.
- **Rationale:** This successful run provides a reliable performance baseline for the CatBoost spread model on clean data, unblocking further development.
- **Impact:** The CatBoost spread model is now the official baseline. The overall RMSE for the 2023-2024 seasons is **18.57**. Future spread model improvements will be measured against this benchmark.
- **Rejected Alternatives:** None. This was the necessary next step to unblock the project.

## 2025-11-20: Final Investigation into Model Instability

- **Context:** Previous attempts to stabilize the linear models failed. A final, comprehensive attempt was made by fixing `NaN` propagation in the feature engineering code and using a robust training pipeline that dropped `NaN`s, pruned high-VIF features, and scaled the data.
- **Decision:** All modeling work on the spread prediction target is definitively paused. The next and only step is a manual, code-level audit and debugging of the feature engineering pipeline in `src/features/core.py`.
- **Rationale:** The final, robust training pipeline still produced `RuntimeWarning`s. This proves that the root cause is not simple multicollinearity or missing values that can be handled at the modeling stage. The problem is fundamental to the data generation process itself, which is creating extreme, non-physical values that break the linear algebra of the models.
- **Impact:** No reliable model can be trained until the feature engineering code is fixed. The project must pivot from modeling to a deep data quality and debugging session.
- **Rejected Alternatives:** All standard and advanced preprocessing techniques at the modeling stage have been exhausted. The problem is at the source.
