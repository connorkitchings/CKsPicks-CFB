# Opponent Adjustment Iteration Validation

## Current Setting

- **Iteration**: 2
- **Logic**: 2 passes of opponent adjustment (League Mean -> Opponent Adjust -> Opponent's Opponent Adjust).

## Evidence for Iteration=2

1.  **Overfitting Risk**: Higher iterations (3, 4) tend to overfit to the schedule graph, propagating noise from distant opponents.
2.  **Stability**: Iteration 2 provides a balance between raw stats (Iter 0) and fully connected graph adjustments (Iter 4).
3.  **Performance**: Current Points-For models (CatBoost) were tuned with Iteration 2 and show stable performance (Totals hit rate ~54%).
4.  **Previous Findings**: Earlier experiments (referenced in `docs/planning/points_for_model.md`) indicated Iteration 2 was optimal for the Points-For architecture.

## Recommendation

- **Retain Iteration 2** as the default for now.
- **Future Work**: If model architecture changes significantly (e.g., to XGBoost), re-sweep iterations 0-4 to confirm optimality.
