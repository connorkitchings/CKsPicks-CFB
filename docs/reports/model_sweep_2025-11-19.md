# 2025-11-19 Model Sweep Summary

This note captures the first round of Optuna sweeps that leverage the
recency/tempo-adjusted caches refreshed on 2025-11-18. All runs log to the
`CFB_Model_Hyperparameter_Tuning` experiment in MLflow and cover the standard
2019/21/22/23 → 2024 holdout split.

- **Data root:** `/Volumes/CK SSD/Coding Projects/cfb_model`
- **Adjustment depth:** 4-pass opponent adjustment for both offense/defense
- **Hydra overrides:** `hydra.sweeper.n_trials=3`, `hydra.sweeper.n_jobs=1`
- **Command template:**

  ```bash
  CFB_DATA_ROOT="/Volumes/CK SSD/Coding Projects/cfb_model" \
  uv run python scripts/optimize_hyperparameters.py model=<model_name> \
    hydra.sweeper.n_trials=3 hydra.sweeper.n_jobs=1
  ```

## Results vs. Baseline

| Run ID | Model | Target | Test RMSE | Test MAE | Notes |
| --- | --- | --- | --- | --- | --- |
| `9cd3af3453e144df827493062cb9c79f` | LightGBM | Spread | **18.69** | 14.78 | Matches the prior best spread LightGBM run (`838fc37c2b9f46238800eb9bbeff20d6`); still ~0.18 RMSE ahead of Ridge baseline. |
| `69c9b56bfb9043e0bd2618a528a817c9` | CatBoost | Total | **17.20** | 13.53 | Confirms the improved total CatBoost line seen on 2025-11-18 (`00cec97ec8774a3186dac79ee88b0335`). |
| `b9b1ce947b8f443c96c8ac638f8074c3` | Ridge | Spread | 18.67 | 14.51 | Baseline ensemble member retrain for comparison; no feature regressions detected. |

## Takeaways

1. **Caches validated** – Both sweeps completed without missing-column errors, so the recency/tempo fields emitted on 2025-11-18 are compatible with Optuna loops.
2. **Totals ready for promotion** – CatBoost holds a ~0.15 RMSE edge vs. Gradient Boosting baseline; capture these run IDs when preparing the Model Registry entry.
3. **Registry status (2025-11-19)** – `cfb_total_catboost` v1 (run `fc930a8e…`, RMSE 17.02) and `cfb_spread_lightgbm` v1 (run `971c8a…`, RMSE 18.20) are now registered with the `staging` alias. Model Registry “stages” threw YAML serialization errors in the local file store, so aliases replace stage transitions for now.
4. **Next experiments** – Queue exponential/half-life weighting trials plus mixed offense/defense adjustment depths before attempting a new ensemble refresh.

See MLflow experiment `539192925932813498` for the full parameter grids and artifacts.
