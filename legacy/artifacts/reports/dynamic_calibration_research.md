# Dynamic Calibration Research Report

## 1. Objective

Investigate if a **Dynamic Calibration** strategy (correcting predictions based on recent historical bias) could improve the performance of the Pruned Points-For model, which showed unstable bias in validation (-1.43 to +0.83).

## 2. Methodology

- **Data**: Walk-forward validation predictions for 2019, 2021-2024 (approx. 3,500 games).
- **Simulation**: Replayed predictions week-by-week, applying a bias correction term calculated from previous weeks.
- **Strategies Tested**:
  - **Baseline**: Raw model output.
  - **Rolling 4 Weeks**: Average error of the last 4 weeks.
  - **Season-to-Date (STD)**: Expanding average error of the current season (resetting annually).

## 3. Results

### Overall Performance (2019-2024)

| Strategy        | RMSE      | Bias      | Avg Correction |
| :-------------- | :-------- | :-------- | :------------- |
| **Baseline**    | **18.37** | -0.33     | 0.00           |
| Rolling 4 Weeks | 18.44     | -0.06     | 1.11           |
| Season-to-Date  | 18.42     | **-0.03** | 0.82           |

- **Finding**: Calibration successfully reduced the long-term bias to near zero, but **increased RMSE** by ~0.05-0.07 points. This indicates that the bias correction added more "noise" (variance) than it removed in "signal" (bias).

### Year-by-Year Breakdown

| Year     | Baseline Bias | STD Bias  | Baseline RMSE | STD RMSE | Result                    |
| :------- | :------------ | :-------- | :------------ | :------- | :------------------------ |
| **2019** | -0.99         | -0.12     | 19.49         | 19.53    | RMSE Worsened (+0.04)     |
| **2021** | **-1.43**     | **-0.07** | 18.72         | 18.80    | RMSE Worsened (+0.08)     |
| **2022** | -0.29         | -0.67     | 17.97         | 17.90    | **RMSE Improved (-0.07)** |
| **2023** | +0.50         | +0.21     | 17.76         | 17.80    | RMSE Worsened (+0.04)     |
| **2024** | +0.83         | -0.32     | 17.89         | 17.98    | RMSE Worsened (+0.09)     |

- **2021 (High Negative Bias)**: STD correction eliminated the bias (-1.43 -> -0.07) but still hurt RMSE. This suggests the bias was not perfectly stable week-to-week.
- **2024 (High Positive Bias)**: STD correction overshot and flipped the bias (-0.32), hurting RMSE.
- **2022 (Low Bias)**: Surprisingly, this was the only year RMSE improved, despite the baseline bias being low.

## 4. Conclusion

Dynamic Calibration is **NOT recommended**.

- While it effectively centers the mean error (bias) to zero, it consistently degrades the precision (RMSE) of individual predictions.
- The "Bias" signal appears to be dominated by week-to-week noise rather than a persistent, predictable trend.
- Attempting to chase this bias results in "whipsawing" the predictions.

## 5. Recommendation

1.  **Reject Dynamic Calibration**: Do not implement this in the production pipeline.
2.  **Accept Baseline**: The Pruned Points-For model (RMSE ~17.9 in recent years) is likely performing at the limit of its architecture.
3.  **Focus on Variance**: The high RMSE (18+) suggests that the "Spread" variance is high. Future efforts should focus on reducing variance (e.g., better features, different model class like XGBoost) rather than bias correction.
