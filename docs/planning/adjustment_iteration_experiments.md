# Adjustment Iteration Experiments

## Overview

Recent refactors partition the weekly opponent-adjusted cache at
`processed/team_week_adj/iteration=<n>/year=/week=` for iteration depths
`n ∈ {0,1,2,3,4}`. This study evaluates how many opponent-adjustment passes yield the
best modeling signal, including asymmetric configurations where offense and defense
features use different iteration depths.

## Objectives

1. Quantify model performance (RMSE/MAE, calibration, hit rate) for uniform iteration
   depths (same `n` for both offense and defense) across spread and total targets.
2. Explore mixed configurations where offensive features use iteration `n_off` and
   defensive features use iteration `n_def`, identifying any gains from lighter or
   heavier smoothing on one side of the ball.
3. Surface a short list of candidate configurations for production, along with
   documentation and updated defaults if a change is warranted.

## Prerequisites

- Weekly caches rebuilt for each year of interest at depths 0–4
  (`scripts/cache_weekly_stats.py --adjustment-iterations 0,1,2,3,4 ...`).
- Hydra/Optuna configuration already parameterised with
  `data.adjustment_iteration` (default = 4).
- Ability to merge offense and defense features from different iteration partitions
  (prototype helper or notebook TBD).

## Experiment Matrix

### A. Uniform Iteration Depths (5 runs)

| Depth `n` | Description                               | Command Template                        |
| --------- | ----------------------------------------- | --------------------------------------- |
| 0         | No opponent adjustment (running averages) | `hydra.run data.adjustment_iteration=0` |
| 1         | Single-pass adjustment                    | `...=1`                                 |
| 2         | Two passes                                | `...=2`                                 |
| 3         | Three passes                              | `...=3`                                 |
| 4         | Current production default                | `...=4`                                 |

Run both:

```bash
source .venv/bin/activate
python scripts/optimize_hyperparameters.py model=spread_elastic_net data.adjustment_iteration=<n>
python scripts/optimize_hyperparameters.py model=total_random_forest data.adjustment_iteration=<n>
```

Capture metrics in MLflow (`test_rmse`, `test_mae`) and walk-forward summaries:

```bash
python scripts/walk_forward_validation.py data.adjustment_iteration=<n>
```

### B. Mixed Offense/Defense Depths (5×5 grid)

| `n_off` (offense) | `n_def` (defense) | Notes                                                                   |
| ----------------- | ----------------- | ----------------------------------------------------------------------- |
| 0–4               | 0–4               | 25 combinations; start with {0,2,4}×{0,2,4} for a cheaper initial pass. |

Implementation notes:

- The weekly feature loader already supports separate offense/defense depths via
  `load_point_in_time_data(..., adjustment_iteration_offense=…, adjustment_iteration_defense=…)`.
  Surface the overrides with CLI flags (`--offense-adjustment-iteration`,
  `--defense-adjustment-iteration`) or Hydra keys
  (`data.adjustment_iteration_offense`, `data.adjustment_iteration_defense`).

Metrics: same as uniform experiment, plus residual standard deviation and bet-level
hit rate (use `scripts/walk_forward_validation.py` and weekly generator).

## Evaluation & Reporting

- Aggregate results in `artifacts/reports/metrics/adjustment_iteration_summary.csv`
  (spread, total, ensemble metrics).
- Current findings (2024 walk-forward, train=2019,2021–2023):
  - Uniform depths remain close; the production 4/4 ensemble is still acceptable,
    though offense=1 / defense=1 trimmed ~0.01 RMSE off totals.
  - Asymmetric offense=1 / defense=3 produced the best totals RMSE (≈16.75) with no
    meaningful spread change; we’re keeping 4/4 as default pending more analysis.
- Plot RMSE/MAE versus iteration depth for offense and defense separately.
- Highlight any statistically significant improvements (paired t-tests or bootstrap
  across weeks).
- Summarise findings in `docs/decisions/decision_log.md` if a new default is adopted.

## Next Steps

1. Execute uniform-depth sweeps (A) to establish baseline sensitivities.
2. Sample mixed-depth combinations (B), focusing on edge cases informed by (A).
3. Document outcomes and recommend production defaults or further analysis.
