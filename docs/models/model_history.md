# Model Development History

This document chronicles the modeling approaches, experiments, and key learnings from the CFB prediction model project.

## Current Champion: Points-For Ensemble (2024-2025)

### Architecture

**Separate Home/Away Models → Derived Spread/Total**

- Two independent regression models predict home and away scores
- Spread = Home Points - Away Points
- Total = Home Points + Away Points

### Model Stack

- **CatBoost**: Primary model with tuned hyperparameters
- **XGBoost**: Secondary model for ensemble diversity
- **Ensemble**: Weighted average (weights can be tuned)

### Key Parameters

- **Opponent Adjustment Depth**: 2 iterations (optimal balance)
- **Feature Set**: `standard_v1` (off/def stats, pace, recency, luck)
- **Training Data**: 2019, 2021-2023 (skip 2020 COVID season)
- **Target Year**: 2024-2025

### Performance (2024 Holdout)

- **Spread RMSE**: ~13-14 points
- **Total RMSE**: ~12-13 points
- **Betting Performance**: Positive ROI with calibrated thresholds

---

## Experiments & Evolution

### 1. Direct Spread/Total Models (2023)

**Approach**: Train models to predict spread and total directly.

**Results**:

- More noise than derived approach
- Less interpretable
- Harder to debug team-level performance

**Decision**: Abandoned in favor of Points-For approach.

### 2. Spread Classifier (2023)

**Approach**: Binary classification (Cover/No Cover).

**Results**:

- Lost granularity of point predictions
- Couldn't derive betting edge as effectively

**Decision**: Regression provides more actionable information.

### 3. Opponent Adjustment Depth Experiments (2024)

**Approach**: Test adjustment iterations from 0 (raw stats) to 4 (deep recursion).

**Results**:
| Depth | Spread RMSE | Total RMSE | Notes |
|-------|-------------|------------|-------|
| 0 | 15.2 | 14.8 | No opponent adjustment |
| 1 | 14.1 | 13.5 | First-order adjustment |
| **2** | **13.7** | **12.9** | **Sweet spot** |
| 3 | 13.8 | 13.0 | Diminishing returns |
| 4 | 13.9 | 13.2 | Overfitting risk |

**Decision**: Depth 2 provides optimal complexity/performance tradeoff (see [Decision Log](../decisions/decision_log.md)).

### 4. CatBoost vs XGBoost (2024)

**Approach**: Compare gradient boosting implementations.

**Results**:

- **CatBoost**: Slightly better RMSE (~0.3 points), handles categoricals well
- **XGBoost**: Competitive, faster training
- **Ensemble**: Best of both worlds

**Decision**: Use CatBoost as primary, XGBoost for diversity.

### 5. Feature Selection via RFE (2024)

**Approach**: Recursive Feature Elimination to prune low-importance features.

**Results**:

- Reduced feature count from ~80 to ~50
- Minimal performance degradation (~0.1 RMSE)
- Faster inference

**Decision**: Pruned models deployed for 2024 season.

### 6. Quantile Regression for Prediction Intervals (2024)

**Approach**: Use quantile regression to estimate uncertainty.

**Results**:

- Coverage rates were reasonable but needed calibration
- Intervals were overconfident initially
- Recalibration improved betting decisions

**Decision**: Integrated into betting policy (see [Betting Policy](../project_org/betting_policy.md)).

---

## Key Learnings

### Architecture

1. **Derived targets work better**: Predicting home/away independently and deriving spread/total is more robust than direct prediction
2. **Opponent adjustment is critical**: Raw stats are insufficient; accounting for opponent strength is essential
3. **Depth 2 is optimal**: Deeper recursion shows diminishing returns and risks overfitting

### Modeling

1. **CatBoost excels**: Handles mixed data types and categorical features naturally
2. **Ensemble diversity helps**: Combining CatBoost + XGBoost improves robustness
3. **Feature engineering > hyperparameter tuning**: Time spent on feature quality yields better returns than exhaustive grid searches

### Calibration & Betting

1. **Calibration is essential**: Raw model predictions need bias correction (e.g., -1.4 point spread adjustment)
2. **Edge thresholds matter**: Spread threshold = 5.0 points, Total threshold = 3.5 points (empirically derived)
3. **Uncertainty quantification**: Prediction intervals inform bet sizing and risk management

### Infrastructure

1. **Point-in-time features**: Avoid lookahead bias by caching weekly snapshots
2. **MLflow tracking**: Essential for experiment reproducibility
3. **Modular pipeline**: Separation of ingestion → features → training → inference enables rapid iteration

---

## Future Exploration

### Potential Improvements

- **Deep learning**: Explore neural network architectures (RNNs for sequential data, attention mechanisms)
- **Weather integration**: Currently included but impact not fully quantified
- **Injury data**: API availability unclear but could be valuable
- **Player-level features**: Roster turnover, QB rating, etc.

### Avoid Retreading

- Direct spread/total models (already tested)
- Classification approaches (less granular)
- Adjustment depths > 2 (diminishing returns)

---

## References

- [Decision Log](../decisions/decision_log.md): Planning-level decisions
- [Betting Policy](../project_org/betting_policy.md): Risk controls and thresholds
- [Feature Catalog](../project_org/feature_catalog.md): Canonical feature definitions
- [Modeling Baseline](../project_org/modeling_baseline.md): MVP approach
