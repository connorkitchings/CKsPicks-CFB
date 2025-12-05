# PPR Model Validation Summary

**Date:** 2025-12-03
**Model Version:** Dynamic PPR v1 (Gaussian Random Walk)
**Scope:** Backtest across 2019, 2021-2025

## Executive Summary

The initial "Dynamic Probabilistic Power Ratings" (PPR) model was backtested across 6 seasons. **The current performance is significantly below the production baseline.**

- **RMSE:** Ranges from **21.19** to **23.30** (Production Baseline: ~18.4).
- **Win Accuracy (Straight Up):** Ranges from **60.4%** to **63.8%** (Expectation: >70%).

**Conclusion:** The current PPR model is not yet ready for production or even as a primary feature. It requires significant tuning of the random walk parameters, priors, and potentially the inclusion of margin-of-victory scaling (currently it treats all point differentials linearly).

## Detailed Results

| Year     | RMSE      | MAE       | Win Accuracy | ATS Accuracy | Games |
| :------- | :-------- | :-------- | :----------- | :----------- | :---- |
| **2019** | 23.40     | 18.44     | 62.5%        | 47.7%        | 740   |
| **2021** | 22.55     | 17.65     | 60.8%        | 48.1%        | 750   |
| **2022** | 21.37     | 16.63     | 60.7%        | **52.2%**    | 744   |
| **2023** | **20.94** | 16.45     | 60.3%        | 49.6%        | 752   |
| **2024** | 21.18     | **16.65** | 61.5%        | 51.7%        | 750   |
| **2025** | 22.22     | 17.53     | **64.6%**    | 50.5%        | 1038  |

## Comparison to Baseline (2024)

| Metric                 | PPR Model (Tuned) | Hybrid Strategy (Production) | Delta          |
| :--------------------- | :---------------- | :--------------------------- | :------------- |
| **Spread RMSE**        | 21.18             | 19.13 (Verified)             | +2.05 (Worse)  |
| **Win Accuracy (SU)**  | 61.5%             | 70.3% (Verified)             | -8.8% (Worse)  |
| **Win Accuracy (ATS)** | 51.7%             | 51.1% (Verified)             | +0.6% (Better) |

## Recommendations

1.  **Tune Hyperparameters:** The random walk variance (`sigma_drift`) and initial priors need optimization. The model may be "drifting" too much or too little.
2.  **Score Modeling:** The current model assumes a normal distribution for score difference. CFB scores are heavy-tailed. Consider a Student-T likelihood.
3.  **Feature Integration:** Despite poor standalone performance, the _ratings themselves_ might still be useful features for the XGBoost/CatBoost models if they capture a different signal than the current feature set.
