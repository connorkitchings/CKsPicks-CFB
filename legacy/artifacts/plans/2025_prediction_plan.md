# 2025 Season Prediction & Scoring Plan

## 1. Objective

Generate predictions for all available weeks in the 2025 College Football season using the "Pruned Points-For" baseline model and evaluate its performance (RMSE, Bias, Betting Hit Rate/ROI).

## 2. Context

- **Current Date**: Nov 24, 2025.
- **Model**: Pruned Points-For (CatBoost, 40 features).
- **Status**: Validated on 2019-2024. 2025 is the current "live" (or recently completed) season data.

## 3. Execution Steps

1.  **Run Predictions**: Execute `scripts/walk_forward_validation.py` targeting the year 2025.
    - Command: `uv run python scripts/walk_forward_validation.py experiment=points_for_pruned walk_forward.years=[2025]`
2.  **Analyze Calibration**: Run `scripts/analyze_calibration.py` on the generated `2025_predictions.csv`.
3.  **Calculate Betting Metrics**: Create/Update a script to calculate ATS (Against The Spread) and Totals performance.
    - Need to ensure we have the betting lines (Spread/Total) in the output or join them from the source data.
    - _Note_: The `walk_forward_validation.py` output `_predictions.csv` contains `spread_actual` (Margin) and `total_actual` (Score Sum), but we need to verify if it has the _Closing Line_ to calculate ATS hits.
    - If `spread_actual` is (Home - Away), and `spread_pred` is predicted (Home - Away), we can calculate the "Edge". But to know if we _won_ the bet, we need the Line.
    - _Self-Correction_: `spread_actual` in the CSV is likely the _result_ relative to the spread? No, usually it's the margin. I need to check this.
    - If the CSV doesn't have the line, I'll write a script to join the predictions with the `games` table (or `partitioned_data`) to get the lines.

## 4. Deliverables

- `artifacts/validation/walk_forward/2025_predictions.csv`
- `artifacts/reports/2025_performance_report.md` (RMSE, Bias, Hit Rate, ROI)

## 5. Verification

- Check if `2025_predictions.csv` is generated and non-empty.
- Verify betting metrics are calculated correctly (e.g., checking a few games manually).
