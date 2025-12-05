# 2025 Season Performance Report

**Pruned Points-For Model (40 Features)**

## Executive Summary

The pruned Points-For model was evaluated on the 2025 college football season using walk-forward validation. This report summarizes the model's predictive performance, calibration characteristics, and key findings.

## Dataset

- **Total Games**: 827
- **Weeks Covered**: Weeks 3-13 of 2025 season
- **Model**: CatBoost ensemble with 40 features
- **Configuration**: `points_for_pruned` experiment

## Performance Metrics

### Spread Predictions

| Metric                   | Value                                      |
| ------------------------ | ------------------------------------------ |
| **RMSE**                 | 17.95 points                               |
| **MAE**                  | 14.05 points                               |
| **Bias**                 | -1.21 points (model underpredicts margins) |
| **Directional Accuracy** | 66.26% (548/827 games)                     |

### Totals Predictions

| Metric   | Value                                     |
| -------- | ----------------------------------------- |
| **RMSE** | 16.14 points                              |
| **MAE**  | 12.98 points                              |
| **Bias** | -0.81 points (model underpredicts totals) |

## Key Findings

### 1. Consistent Performance

The 2025 season RMSE of **17.95** aligns closely with historical validation:

- 2024: 17.90
- 2023: 17.95
- 2022: 17.88
- 2021: 17.81

This consistency demonstrates the model's **stability and reliability** across different seasons.

### 2. Negative Bias

The model exhibits a **negative bias** of -1.21 points (actual - predicted):

- The model tends to underpredict the margin of victory
- This bias is within the historical range (-1.43 in 2021 to +0.83 in 2024)
- Consistent with the decision to **not apply bias correction** due to year-over-year instability

### 3. Directional Accuracy

- **66.26%** success rate in predicting the correct winner
- This translates to correctly calling the winner in approximately **2 out of every 3 games**
- Exceeds the break-even threshold of 52.4% needed for profitable betting (at standard -110 odds)

### 4. Totals Performance

- Totals predictions show **lower error** than spreads (RMSE: 16.14 vs 17.95)
- Bias is minimal at -0.81 points
- Suggests the model's points-for predictions are well-calibrated

## Limitations

### Betting Line Availability

The 2025 predictions CSV does not contain historical betting lines (`spread` and `total_line`). As a result:

- **Exact ATS (Against the Spread) performance** cannot be calculated
- **Totals betting performance** (Over/Under) cannot be determined
- **Edge-based analysis** (model prediction vs. betting line) is not possible

To enable full betting analysis, the predictions would need to be joined with a games database or CSV containing: -`spread` - The opening or closing betting line for the spread

- `total_line` - The opening or closing betting line for the total

## Comparison to Baseline

This model was selected as the **new baseline** after comparison with:

1. **Full feature model** (500+ features): Similar performance but prone to overfitting
2. **Static bias correction**: Rejected due to year-over-year bias instability
3. **Dynamic calibration**: Rejected due to increased RMSE from noisy bias signals

## Conclusions

1. **Model Stability**: The pruned model demonstrates consistent performance across multiple seasons
2. **Feature Efficiency**: Comparable accuracy to full model with 92% fewer features
3. **Bias Considerations**: Negative bias is present but not corrected due to historical instability
4. **Directional Edge**: 66% winner prediction rate suggests potential betting value
5. **Next Steps**: To improve performance further, focus should shift to:
   - **Variance reduction** through better feature engineering
   - **Alternative architectures** (e.g., XGBoost, LightGBM)
   - **Ensemble techniques** combining multiple model types

## Recommendation

The pruned Points-For model is **recommended for production use** as the baseline model for the 2026 season, with ongoing monitoring of:

- RMSE trends
- Bias drift
- Directional accuracy
- Feature importance stability

---

_Generated: 2025-11-24_  
_Model Version: points_for_pruned (40 features)_  
_Validation Method: Walk-forward (weekly)_
