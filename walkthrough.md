# Session Walkthrough: Pruned Model Validation & Calibration Research

## 1. Objective

Validate the "Pruned Points-For" model (40 features) across multiple years (2019, 2021-2024) and determine if bias correction (static or dynamic) could stabilize its performance to achieve profitable hit rates (>52.4%).

## 2. Key Actions & Findings

### A. Multi-Year Walk-Forward Validation

- **Action**: Ran walk-forward validation for 5 seasons.
- **Finding 1 (Performance)**: The model achieves a consistent RMSE of **~17.9** in recent years (2022-2024), which is a solid baseline.
- **Finding 2 (Bias Instability)**: The calibration bias is highly unstable, drifting from **-1.43** (2021) to **+0.83** (2024).
- **Decision**: **Rejected Static Bias Correction** (e.g., fixed +1.4) because the bias sign flips between seasons.

### B. Dynamic Calibration Research

- **Action**: Simulated "Rolling Bias Correction" (correcting this week's bet based on the last 4 weeks' errors) on the validation data.
- **Finding**: While dynamic calibration centered the long-term bias to zero, it **increased RMSE** (worsened precision) in almost every year.
- **Root Cause**: The week-to-week bias is dominated by noise. Chasing it leads to "whipsawing" (overcorrecting).
- **Decision**: **Rejected Dynamic Calibration**.

## 3. Final Outcome

- **Model**: The **Pruned Points-For Model** (CatBoost, 40 features) is accepted as the new baseline.
- **Configuration**: No post-processing bias correction will be applied.
- **Next Steps**: Future profitability improvements must come from **Variance Reduction** (better features, different model architectures like XGBoost) rather than bias tuning.

## 4. Artifacts Created

- [Validation Report](file:///Users/connorkitchings/Desktop/Repositories/cfb_model/artifacts/reports/pruned_model_validation.md)
- [Calibration Research Report](file:///Users/connorkitchings/Desktop/Repositories/cfb_model/artifacts/reports/dynamic_calibration_research.md)
- [Calibration Simulation Script](file:///Users/connorkitchings/Desktop/Repositories/cfb_model/scripts/research/simulate_dynamic_calibration.py)
