# Decision Log

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
