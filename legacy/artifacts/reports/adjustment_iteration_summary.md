# Adjustment Iteration Experiments Summary (Redo)

**Date:** 2025-11-23
**Parameters:** Train: 2019, 2021-2023 (Skip 2020) | Test: 2024
**Objective:** Evaluate the impact of opponent-adjustment iteration depth (0-4) on model performance with the new training/test split.

## Key Findings

- **Spread Model:**

  - **Best RMSE:** **Iteration 2** (17.97)
  - **Best Hit Rate:** **Iteration 1 & 2** (48.2%)
  - **Conclusion:** **Iteration 2** is the clear winner, delivering the lowest error and the highest hit rate. This is a shift from the previous run (where Iter 1/3 split the honors).

- **Total Model:**
  - **Best RMSE:** Iteration 4 (17.17)
  - **Best Hit Rate:** **Iteration 2** (54.1%)
  - **Conclusion:** **Iteration 2** offers the best Hit Rate, slightly edging out Iteration 0 (54.0%) and Iteration 1 (53.9%). Iteration 4 remains the best for minimizing raw error but lags in betting performance (53.3%).

## Detailed Results

### Spread Model (CatBoost)

| Iteration | RMSE      | MAE       | Hit Rate  |
| :-------- | :-------- | :-------- | :-------- |
| 0         | 18.47     | 14.43     | 47.6%     |
| 1         | 18.25     | 14.25     | **48.2%** |
| **2**     | **17.97** | **14.10** | **48.2%** |
| 3         | 18.17     | 14.28     | 46.7%     |
| 4         | 18.13     | 14.15     | 46.2%     |

### Total Model (CatBoost)

| Iteration | RMSE      | MAE       | Hit Rate  |
| :-------- | :-------- | :-------- | :-------- |
| 0         | 17.27     | 13.72     | 54.0%     |
| 1         | 17.34     | 13.74     | 53.9%     |
| **2**     | 17.28     | 13.67     | **54.1%** |
| 3         | 17.30     | 13.72     | 53.4%     |
| 4         | **17.17** | **13.61** | 53.3%     |

## Recommendations

1. **Unified Approach:** **Iteration 2** appears to be the "sweet spot" for this specific training/test split, performing best (or tied for best) in Hit Rate for both Spread and Total models.
2. **Spread:** Switch to **Iteration 2**.
3. **Total:** Switch to **Iteration 2** to maximize Hit Rate (+0.8% over default), or stick with 4 if RMSE is prioritized.
