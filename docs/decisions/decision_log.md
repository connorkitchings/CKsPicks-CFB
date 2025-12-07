# Decision Log

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
