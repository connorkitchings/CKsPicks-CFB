# Dynamic Calibration Research Plan

## 1. Objective

Determine if a **Dynamic Calibration** strategy (correcting predictions based on recent historical bias) would have yielded a profitable Hit Rate (>52.4%) across the 2019-2024 validation period.

## 2. Context

- **Problem**: The Pruned Points-For model has good accuracy (RMSE ~17.9) but unstable bias (drifting from -1.4 to +0.8).
- **Hypothesis**: The bias changes slowly enough that a "Trailing Average" of recent errors can predict the current week's bias.
- **Opportunity**: We already have the raw predictions and actuals for every game in 2019-2024 (from the previous task). We can _simulate_ this strategy without retraining any models.

## 3. Proposed Experiment

Create a script `scripts/research/simulate_dynamic_calibration.py` that:

1.  Loads all `artifacts/validation/walk_forward/{year}_predictions.csv` files.
2.  Sorts all games chronologically.
3.  Iterates through weeks, maintaining a "Rolling Bias" buffer (e.g., last 4 weeks, last 8 weeks, or Season-to-Date).
4.  For each game, applies the correction: `Calibrated_Pred = Raw_Pred + Rolling_Bias`.
5.  Calculates the hypothetical Betting Performance (Hit Rate, ROI) using this calibrated line.
6.  Optimizes the "Window Size" (e.g., is a 4-week window better than an 8-week window?).

## 4. Success Criteria

- **Primary**: Finding a window size that achieves >52.4% Hit Rate on the spread.
- **Secondary**: Confirming that the "Calibrated RMSE" is lower than the "Raw RMSE".

## 5. Execution Steps

1.  [ ] Create `scripts/research/simulate_dynamic_calibration.py`.
2.  [ ] Run simulation for window sizes [2, 4, 6, 8, Season-to-Date].
3.  [ ] Analyze results to see if any strategy is consistently profitable.
4.  [ ] Report findings.
