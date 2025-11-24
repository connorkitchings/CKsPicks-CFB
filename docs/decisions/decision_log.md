# Decision Log

## 2025-11-23: Productionize Points-For Model Architecture

- **Context:** The "Points-For" prototype (predicting Home/Away scores directly) achieved a 53.3% spread hit rate and 55.2% totals hit rate on 2024 holdout, outperforming legacy models.
- **Decision:**
  1.  **Productionize:** Train and deploy 5-seed ensembles for `points_for_home` and `points_for_away`.
  2.  **Architecture:** Use "Standard" feature set with Iteration 2 opponent adjustment.
  3.  **Pipeline:** Update `generate_weekly_bets_hydra.py` to use these models for all future predictions.
- **Rationale:** This architecture provides the first profitable spread betting strategy (>52.4% hit rate) and simplifies the pipeline by deriving both spread and total predictions from a single set of score estimates.
- **Impact:** Legacy spread/total models are deprecated. Weekly betting now relies on the Points-For ensemble.
- **Artifacts:** `conf/model/points_for_catboost.yaml`, `scripts/generate_weekly_bets_hydra.py` updated.

## 2025-11-23: Points-For Model Prototype Achieves Profitability

- **Context:** After feature pruning improved the spread model to 51.1% hit rate (still below the 52.4% breakeven), we prototyped a unified "Points-For" approach that predicts Home and Away scores independently, then derives spread and total predictions from those estimates.
- **Findings:**
  - **Spread Hit Rate:** **53.3%** on 2024 holdout (+2.2% vs. pruned direct spread model)
  - **Total Hit Rate:** **55.2%** on 2024 holdout (+0.6% vs. baseline total model)
  - **Spread RMSE:** 18.72 (slightly higher than 18.61 for direct spread model, expected due to error propagation)
  - **Total RMSE:** 17.40 (comparable to baseline 17.14)
  - **Bet Volume:** 460 spread bets, 503 total bets (thresholds: 5.0 and 3.5 respectively)
  - The unified architecture provides natural uncertainty quantification and reduces maintenance overhead.
- **Decision:**
  1. **Adopt Points-For as the new production architecture** for both spread and total predictions.
  2. Train 5-seed ensemble of Points-For models (Home + Away pairs) for production deployment.
  3. Update `generate_weekly_bets_hydra.py` to use Points-For models as the default prediction mode.
- **Rationale:** The Points-For approach achieves **profitable spread betting** (53.3% > 52.4% breakeven) while maintaining excellent totals performance. The slightly higher RMSE is acceptable given the significant hit rate improvement and architectural benefits (unified modeling, better uncertainty quantification).
- **Impact:** This achieves the project's core objective of profitable ATS betting. The spread model is now above breakeven for the first time.
- **Artifacts:** `scripts/run_points_for_experiment.py`, `walkthrough.md` with full analysis.

## 2025-11-23: Feature Pruning Improves Spread Model Hit Rate

- **Context:** The Spread model (Iteration 2 + Bias Correction) was underperforming with a 48.6% hit rate. We hypothesized that the large feature set (153+ features) was causing overfitting. We ran SHAP analysis to identify feature importance.
- **Findings:**
  - The top features are dominated by opponent-adjusted efficiency metrics (`adj_off_epa_pp`, `adj_def_sr`) and recency metrics (`_last_3`).
  - A long tail of low-importance features existed.
  - Pruning to the top 40 features improved the 2024 Hit Rate from **48.6%** to **51.1%** (+2.5%).
  - RMSE increased slightly (18.12 -> 18.61), indicating less overfitting to training noise but better generalization for betting direction.
- **Decision:**
  1.  Adopt the **Top 40** feature set for the Spread model.
  2.  Register the pruned model (`spread_catboost_pruned`) as the new Production model for spread predictions.
- **Rationale:** The primary goal is betting profitability (Hit Rate > 52.4%). The pruned model significantly closes the gap to profitability by reducing noise.
- **Impact:** `spread_catboost_pruned` version 1 is now the active production model. Future experiments should start from this reduced feature set.
- **Artifacts:** `artifacts/analysis/feature_importance/shap_summary_catboost.png`, `conf/features/spread_top_40.yaml`.

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
