# Pruned Points-For Model Validation Report

**Date:** 2025-11-24
**Model:** Points-For (CatBoost, Pruned Feature Set)
**Validation Strategy:** Multi-Year Walk-Forward (2019, 2021-2024)

## 1. Executive Summary

The pruned (40-feature) Points-For model was validated across 5 seasons. Key findings:

1.  **Bias Instability:** The calibration bias is **highly unstable**, drifting from **-1.43** (2021) to **+0.83** (2024). A static bias correction is **NOT viable**.
2.  **Performance Trend:** RMSE has steadily improved from 19.49 (2019) to 17.89 (2024), indicating the model is learning better representations over time or the game is becoming more predictable.
3.  **Recommendation:** Do **NOT** deploy a static bias correction. Investigate **dynamic calibration** (e.g., trailing 4-week average bias) or **regime-based correction**.

## 2. Year-over-Year Performance

| Year | Count | RMSE  | MAE   | Bias (Actual - Pred) | Interpretation                                 |
| ---- | ----- | ----- | ----- | -------------------- | ---------------------------------------------- |
| 2019 | 667   | 19.49 | 14.65 | **-1.17**            | Over-predicted spread (favored Home too much)  |
| 2021 | 701   | 18.83 | 14.28 | **-1.43**            | Over-predicted spread                          |
| 2022 | 704   | 17.89 | 13.91 | **-0.49**            | Slight over-prediction                         |
| 2023 | 720   | 17.76 | 14.09 | **+0.50**            | Under-predicted spread (favored Away too much) |
| 2024 | 737   | 17.89 | 13.98 | **+0.83**            | Under-predicted spread                         |

## 3. Analysis of Bias Drift

The shift from negative bias (2019-2022) to positive bias (2023-2024) suggests a fundamental shift in either:

- **Game Dynamics:** Home field advantage changes or scoring environments.
- **Feature Distributions:** Key features (like EPA/Success Rate) might have drifted.
- **Model Calibration:** The model might be over-correcting for past errors as it retrains.

## 4. Next Steps

1.  **Dynamic Calibration:** Implement a post-processing step that corrects bias based on the _previous season_ or _trailing N weeks_.
2.  **Feature Drift Analysis:** Check if top features (e.g., `home_adj_off_epa_pp`) have shifted distributions.
3.  **Production Decision:** The Pruned model is safer than the full model due to lower complexity, but requires dynamic calibration to be profitable.
