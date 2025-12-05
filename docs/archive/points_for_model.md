# Points-For Modeling Initiative

## Overview

The current system maintains separate ensembles for spread and total predictions. This initiative explores consolidating both into a unified points-for framework that estimates home and away scoring, then derives spreads and totals downstream. The goal is to reduce maintenance overhead while improving consistency between markets.

## Objectives

- Train models that output expected points for both teams with calibrated uncertainty.
- Derive spread and total predictions (and confidence bands) from the same scoring view.
- Preserve or improve hit rate, bet volume, and calibration relative to existing ensembles.
- Avoid leakage and maintain deterministic weekly generation.

## Scope Assumptions

- Applies to FBS regular-season games (consistent with existing pipelines).
- Reuses cached weekly features where possible, with extensions for per-team scoring targets.
- Continues to exclude in-season data beyond the prediction week.
- Keeps betting policy thresholds configurable and comparable to legacy outputs.

## Data and Pipeline Implications

1. **Targets**
   - Define per-team historical targets: `home_points_for`, `away_points_for`.
   - Confirm raw partitions capture final scores for every game; backfill gaps if needed.
2. **Feature Caching**
   - Ensure `team_week_adj` (now partitioned by `iteration=<n>`) contains offense/defense splits sufficient for per-team scoring estimates and capture which adjustment depth (0–4 passes) yields the most stable targets.
   - Evaluate if additional pace or drive-level metrics are required for accurate totals.
   - Determine whether caches need extra columns (e.g., variance indicators) or if modeling handles this internally.
   - `scripts/build_points_for_slice.py` can generate filtered training slices (enforces minimum prior games) for rapid experimentation.
3. **Weekly Generation**
   - Update `generate_weekly_bets_clean.py` to request points-for predictions, compute derived spread/total, and propagate uncertainty.
   - Maintain compatibility with existing reporting schema while introducing new diagnostic fields (e.g., predicted points, point variance).

## Candidate Modeling Approaches

1. **Dual Single-Target Models (Shared Pipeline)**
   - Train mirrored regressors for home and away points.
   - Advantages: simpler tooling; reuse of current Optuna/Hydra setup.
   - Considerations: need to maintain correlation between paired outputs.
2. **Multi-Output Regression**
   - Use a single estimator with two outputs (e.g., multi-task elastic net, gradient boosting with multi-target support, neural network).
   - Advantages: captures covariance structure directly.
   - Considerations: limited scikit-learn support for some multi-output estimators; Optuna search space grows.
3. **Generative / Simulation-Based**
   - Model expected possessions and efficiency separately, then simulate scoring.
   - Advantages: rich interpretability.
   - Considerations: higher complexity; likely a later phase.

Initial recommendation: prototype dual single-target models that share the existing offensive/defensive feature pipeline (home vs. away context included), while instrumenting prediction covariance. Evaluate whether a tighter multi-output model is necessary after we benchmark against current ensembles.

## Evaluation Strategy

- **Backtest Window:** Train on 2019–2023 (skip 2020), test on 2024 (and a 2025-to-date smoke check).
- **Metrics:** RMSE/MAE for points, derived spread/total accuracy, hit rate vs. closing lines, calibration of prediction intervals.
- **Baseline Comparison:** Compare against current ensembles to ensure no regression in hit rate or bet volume.
- **Uncertainty Validation:** Confirm that combined variance (home + away) matches observed total variance; adjust calibration if mismatched.

## Productionization Outcomes (November 2024)

### Implementation Summary

The Points-For modeling initiative has been successfully productionized. The architecture predicts home and away scores independently using CatBoost ensembles, then derives spread and total predictions downstream.

**Architecture:**

- **5-seed CatBoost ensembles** for both `home_points` and `away_points`
- **Adjustment Iteration 2** selected as optimal (4 passes of opponent adjustment showed overfitting)
- **Derived predictions:** Spread = Home - Away, Total = Home + Away
- **MLflow Registry:** All models registered and promoted to Production stage

### Performance Results

**Walk-Forward Validation (2019-2024):**

| Model                 | Spread RMSE | Total RMSE | Spread MAE | Total MAE |
| :-------------------- | :---------- | :--------- | :--------- | :-------- |
| Points-For (CatBoost) | **18.37**   | **17.12**  | **14.52**  | **13.65** |
| Points-For (Ensemble) | 18.42       | 17.14      | 14.55      | 13.68     |
| Direct Spread/Total   | 18.57       | 17.25      | 14.65      | 13.80     |

**Betting Performance (2024 Season):**

| Market    | Threshold | W-L         | Hit Rate  | Units      | Volume  |
| :-------- | :-------- | :---------- | :-------- | :--------- | :------ |
| Spread    | > 0.0     | 384-349     | 52.4%     | +0.06u     | 737     |
| Spread    | > 2.5     | 283-257     | 52.4%     | +0.25u     | 543     |
| **Total** | **> 5.0** | **186-165** | **53.0%** | **+4.07u** | **352** |

> [!IMPORTANT]
> The Points-For model achieves profitability on both spreads and totals, with particularly strong performance on high-confidence total bets (>5.0 edge).

### Feature Pruning

SHAP analysis was performed to identify the most important features for each model:

**Pruned Model Performance (2024):**

| Metric           | Baseline (116 features) | Pruned (40 features) | Difference |
| :--------------- | :---------------------- | :------------------- | :--------- |
| Home Points RMSE | 13.39                   | 13.49                | +0.10      |
| Away Points RMSE | 11.95                   | 11.83                | -0.12      |
| Spread RMSE      | 18.69                   | 18.54                | **-0.15**  |
| Total RMSE       | 17.18                   | 17.33                | +0.15      |

**Top Features Identified:**

- **Home Points:** `home_adj_off_epa_pp`, `home_adj_off_sr`, `home_def_expl_rate_overall_10_last_3`
- **Away Points:** `away_adj_off_sr`, `away_adj_off_epa_pp`, `away_off_eckel_rate_last_3`

**Recommendation:** The pruned models offer a **65.5% feature reduction** with minimal performance impact (~0.15 RMSE difference). They are suitable for faster training and experimentation while the baseline models remain in production for maximum accuracy.

### Integration Status

- ✅ **Weekly Generation:** `scripts/generate_weekly_bets_hydra.py` updated with `points_for_registry` mode
- ✅ **Walk-Forward Validation:** `scripts/walk_forward_validation.py` supports Points-For evaluation
- ✅ **MLflow Registry:** All 10 models (baseline + pruned) registered and promoted
- ✅ **Documentation:** `docs/operations/weekly_pipeline.md` and `docs/decisions/decision_log.md` updated

### Next Steps

1. **Monitor Production Performance:** Track weekly calibration and betting performance
2. **Calibration Monitoring:** Implement automated weekly bias checks
3. **Probabilistic Ratings:** Begin research on probabilistic power ratings (future sprint)

## Evaluation Plan

To systematically evaluate and improve the points-for model, the following steps will be taken, with a primary focus on the "totals" prediction task:

1.  **Adapt Walk-Forward Validation:** The existing script (`scripts/walk_forward_validation.py`) will be modified to train and evaluate the points-for models. This will involve:

    - Adding a training loop for the `points_for_models` (home and away points).
    - Calculating the derived `predicted_total` from the points-for model's output.
    - Logging the performance (RMSE, MAE, and betting hit rate) of the points-for totals prediction.
    - Adding `points_for` as a configurable strategy in `conf/config.yaml` to allow for direct comparison against the legacy ensemble.

2.  **Experiment with XGBoost:** A more powerful `XGBoost` model will be introduced to predict home and away scores.

    - This aligns with the project roadmap and aims to capture more complex patterns in the data.
    - The existing Hydra/Optuna pipeline will be used to perform hyperparameter tuning for the new XGBoost models.

3.  **Benchmark Performance:** The new XGBoost-based points-for model will be benchmarked against the legacy totals ensemble and the baseline points-for model using the adapted walk-forward validation framework.

4.  **Analyze and Document:** The results will be analyzed, and a recommendation will be made. If the new model proves superior, a decision will be recorded in the `decision_log.md` and project documentation will be updated.

## Open Questions

1. Confirm that paired single-target models (home points, away points) using shared offense/defense features remain acceptable for the first iteration.
2. Define expectations for running legacy spread/total ensembles in parallel for validation and potential fallback.
3. Decide how Optuna sweeps should score trials (e.g., single-objective total points RMSE with additional logging).
4. Choose a strategy for modeling correlation between home and away outputs when using independent models.
5. Capture any reporting requirements (e.g., displaying expected scores) that would affect schema changes.

> 📌 **Future considerations:**
>
> - Once residual analysis stabilizes, derive per-game predictive variance (analytic or conformal) so spread/total bets can be filtered or sized via probability thresholds rather than fixed edge cutoffs.
> - Evaluate whether fewer opponent-adjustment iterations (e.g., 1–3 rounds instead of 4) yield more stable or predictive weekly stats before generating points-for features.
> - Audit feature selection: the current models rely on very dense feature sets. Plan a research slice to compare a curated/regularized subset (e.g., via permutation importance, SHAP, or iterative pruning) against the full bundle to confirm we’re not masking signal with noise.

## Risks and Mitigations

- **Error Propagation:** Summing two noisy predictions amplifies total variance. Mitigation: track covariance and consider shrinkage or calibration layers.
- **Data Quality:** Missing or inconsistent final scores could silently skew targets. Mitigation: add validation checks before training.
- **Tooling Complexity:** Multi-output Optuna sweeps may increase runtime. Mitigation: start with constrained parameter spaces and caching intermediate datasets.
- **Operational Change:** Weekly scripts, tests, and documentation need synchronized updates. Mitigation: stage changes behind feature flags or configuration toggles.

## Documentation Touchpoints

- `docs/project_org/modeling_baseline.md` — describe new modeling architecture and outputs.
- `docs/operations/weekly_pipeline.md` — update generation workflow and diagnostics.
- `docs/project_org/feature_catalog.md` — include any new features or targets.
- `docs/project_org/betting_policy.md` — note any policy tweaks tied to updated uncertainty handling.
- Tests and runbooks should reference the points-for outputs once stabilized.

## Proposed Next Steps

1. Answer open questions and finalize modeling approach.
2. Prototype points-for training locally using existing caches; document findings.
3. Extend Hydra/Optuna configuration for the chosen approach and add regression tests.
4. Implement weekly generator updates with feature flag for dual operation (legacy vs. points-for).
5. Roll out documentation and pipeline updates, then retire legacy models if performance holds.
6. Current status (2025-10-22): keep points-for outputs in comparison-only mode. Focus next on simplifying the model—calibrate residual variance and revisit feature selection/regularization before considering production rollout.

### Hydra/Optuna Integration Plan (Documentation-Only Draft)

- Add a new Hydra config group `model: points_for` representing the paired single-target models (home/away) with shared preprocessing.
- Introduce sweep parameters for the primary estimator while keeping the objective scalar (total points RMSE); log derived spread/total RMSEs as supplemental metrics.
- Update `conf/config.yaml` defaults to keep legacy ensembles active by default; enable points-for runs via explicit override once experiments begin.
- Capture evaluation scripts/commands (e.g., regenerated slice via `scripts/build_points_for_slice.py`) so sweeps can be reproduced without colliding with existing experiments.
- Defer implementation until active Hydra experiments complete.

#### Example Command Sequence (when ready to run)

```bash
# Build or refresh the filtered slice (enforces 2+ prior FBS games)
python scripts/build_points_for_slice.py --season 2023 --min-games 2 \
  --output outputs/prototypes/points_for_training_slice_2023_filtered.csv

# Train and persist points-for models (saves joblib files under artifacts/models/<year>/)
python scripts/train_points_for_models.py \
  --slice-path outputs/prototypes/points_for_training_slice_2023_filtered.csv \
  --model ridge \
  --model-year 2024 \
  --model-dir ./artifacts/models \
  --spread-threshold 8.0 \
  --total-threshold 8.0

# Summarize scored results across modes (e.g., legacy vs points_for)
python scripts/report_model_comparison.py \
  --season 2024 \
  --mode legacy=artifacts/reports/2024/scored \
  --mode points_for=artifacts/reports/points_for/2024/scored \
  --output-dir artifacts/reports/metrics \
  --print

# Run a points-for sweep with elastic net (defaults to alpha/l1 sweeps)
uv run python scripts/optimize_hyperparameters.py \
  model=points_for_elastic_net \
  data.slice_path=outputs/prototypes/points_for_training_slice_2023_filtered.csv \
  data.train_weeks="[3,4,5,6,7,8,9,10]" \
  data.test_weeks="[11,12,13,14,15]"

# Alternate: ridge variant (override sweeper params as needed)
uv run python scripts/optimize_hyperparameters.py \
  model=points_for_ridge \
  hydra.sweeper.params."model.params.alpha"=range(0.01,10.0) \
  data.slice_path=outputs/prototypes/points_for_training_slice_2023_filtered.csv \
  data.train_weeks="[3,4,5,6,7,8,9,10]" \
  data.test_weeks="[11,12,13,14,15]"
```

#### Recent Sweep Snapshot (2025-10-20)

| Model                            | Total RMSE | Total MAE  | Spread RMSE | Spread MAE |
| -------------------------------- | ---------- | ---------- | ----------- | ---------- |
| ElasticNet (default sweep)       | 17.203     | 13.869     | 18.656      | 14.931     |
| Ridge (alpha sweep)              | **17.076** | **13.565** | 18.164      | 14.486     |
| Gradient Boosting (choice sweep) | 18.088     | 14.826     | **18.116**  | **14.365** |

## Tracking

- Owner: TBD
- Target Decision Date: 2025-11-01 (before next sprint planning)
- Dependencies: Hydra/Optuna stability (`session_logs/2025-10-20/01.md`), data cache completeness.
