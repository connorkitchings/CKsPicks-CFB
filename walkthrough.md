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

## 3. Feature Pipeline Fix (2025-11-25)

**Issue:** The initial control experiment failed to load `pace_stats` (e.g., `plays_per_game`) and `luck_stats`, defaulting to a subset of features.
**Root Cause:**

1.  `avg_luck_factor` was requested but not implemented (placeholder was `luck_factor`).
2.  `drive_time` (seconds per play) was requested but deemed untrustworthy.
3.  **Critical:** The `team_week_adj` cache for `adjustment_iteration=2` (used by the experiment) was outdated and missing `plays_per_game`, while `adjustment_iteration=4` (default) had it. This caused a silent failure where features appeared present in debug checks (using default iteration) but were missing during experiment execution.

**Fixes:**

1.  Removed `avg_luck_factor` and `drive_time` from `selector.py` and `core.py`.
2.  Updated `persist.py` to ensure pace stats are preserved in `team_season_adj`.
3.  **Regenerated Feature Cache:** Re-ran `cache_weekly_stats.py` for all training years (2019, 2021-2023) and test year (2024) with `--adjustment-iterations "2,4"`.

**Re-Evaluation (Control Baseline):**

- **Command:** `uv run python scripts/run_experiment.py model=spread_catboost features=standard_v1 +test_years="[2024]"`
- **Status:** Success (No missing feature warnings).
- **Metrics (2024):**
  - **RMSE:** 18.83 (vs 18.61)
  - **MAE:** 14.59 (vs 14.37)
  - **Hit Rate:** 47.2% (210-235-6) -> **+1.5% improvement** over broken baseline (45.7%).

**Conclusion:**
The feature pipeline is now fully functional. The inclusion of pace and luck features improved the model's ability to pick winners (Hit Rate), though it slightly increased error magnitude (RMSE). The baseline is now trustworthy for further experimentation.

## 4. Final Outcome

- **Model**: The **Pruned Points-For Model** (CatBoost, 40 features) is accepted as the new baseline.
- **Configuration**: No post-processing bias correction will be applied.
- **Next Steps**: Future profitability improvements must come from **Variance Reduction** (better features, different model architectures like XGBoost) rather than bias tuning.

## 5. Artifacts Created

- [Validation Report](file:///Users/connorkitchings/Desktop/Repositories/cfb_model/artifacts/reports/pruned_model_validation.md)
- [Calibration Research Report](file:///Users/connorkitchings/Desktop/Repositories/cfb_model/artifacts/reports/dynamic_calibration_research.md)
- [Calibration Simulation Script](file:///Users/connorkitchings/Desktop/Repositories/cfb_model/scripts/research/simulate_dynamic_calibration.py)
