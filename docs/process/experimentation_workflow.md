# Experimentation Workflow (v2)

**Status**: Proposed | **Version**: 2.0 | **Date**: 2025-12-05

This document outlines the standardized workflow for all feature engineering, modeling, and experimentation. It is designed to enforce rigor, prevent performance regressions, and ensure that complexity is only added when justified by a significant and measurable improvement in performance.

This workflow supersedes all previous modeling processes.

---

## Guiding Principles

1.  **Baseline First**: All experiments are measured against a simple, fast, and stable baseline model. No change is adopted unless it outperforms this benchmark.
2.  **Incremental Complexity**: Start simple. Add new features or more complex models in isolated, measurable steps.
3.  **Rigor over Speed**: Follow the process. Do not skip steps. Every champion model must pass every gate.
4.  **Configuration as Code**: All experiments are defined declaratively using Hydra configuration files. No magic numbers or hardcoded paths in scripts.
5.  **Immutability**: Never overwrite experiment results. MLflow is the source of truth for all metrics and artifacts.

---

## The 4-Phase Workflow

The workflow is divided into four distinct phases. A component (feature set or model) must be formally "promoted" from one phase to the next.

### Phase 1: Baseline Establishment

The foundation of all experimentation is a stable baseline.

1.  **Model**: A simple, interpretable model. **Initial choice: Ridge Regression.**
2.  **Features**: A minimal, robust set of core features. **Initial choice: Unadjusted, season-to-date team-game statistics.**
3.  **Benchmark**: This model is trained on the standard training set (e.g., 2019, 2021-2023) and evaluated on the holdout set (e.g., 2024). Its performance metrics (RMSE, Hit Rate, ROI) become the **official benchmark**.
4.  **Process**:
    - The baseline model is defined in `conf/model/baseline.yaml`.
    - It is trained and evaluated using the main training script (`src/train.py`).
    - The results are tracked in MLflow under a dedicated `baseline` experiment tag.

### Phase 2: Feature Engineering & Selection

The goal of this phase is to find and validate new feature sets that improve performance.

1.  **Proposal**: A new feature set (e.g., "Opponent-Adjusted Stats," "PPR Ratings") is defined in a new Hydra config file under `conf/features/`.
2.  **Experiment**: An experiment is run **using the baseline model** but with the new feature set.
    - The experiment config (`conf/experiment/`) will compose the baseline model with the new feature set (e.g., `model: baseline`, `features: opponent_adjusted_v1`).
3.  **Evaluation**: The performance of the baseline model with the new features is compared _directly_ against the official benchmark performance from Phase 1.
4.  **Promotion**:
    - If the new feature set provides a statistically significant improvement over the benchmark, it is promoted.
    - **Promotion criteria**: Must improve holdout set ROI by an absolute 1.0% or more.
    - Promoted feature sets are added to a "registry" of approved features (`docs/project_org/feature_registry.md`). The benchmark is then updated to include this new feature set.
    - **Documentation**: After a new feature set is promoted, the feature dictionary must be updated. Run the generation script: `uv run python scripts/analysis/generate_feature_dictionary.py --input <path_to_aggregated_data>.parquet --output docs/modeling/feature_dictionary.md`

### Phase 3: Model Selection

This phase aims to find more powerful models that can leverage the validated feature sets.

1.  **Proposal**: A new model architecture (e.g., CatBoost, XGBoost, NN) is defined in a new Hydra config file under `conf/model/`.
2.  **Experiment**: The new model is trained on the **currently accepted best feature set** (as defined by the latest benchmark).
    - The experiment config will compose the new model with the benchmark features (e.g., `model: catboost_v1`, `features: benchmark_features`).
3.  **Evaluation**: The new model's performance is compared directly against the benchmark (i.e., the baseline model trained on the same features).
4.  **Promotion**:
    - If the new model demonstrates a significant improvement over the baseline on the same feature set, it is promoted to become the new "Champion Model".
    - **Promotion criteria**: Must improve holdout set ROI by an absolute 1.5% or more over the Ridge baseline.

If a candidate model passes all gates, it becomes the new "Champion Model." This model is tagged for production deployment and registered in the MLflow model registry (tag: `production`).

### Phase 4: Deployment & Monitoring

Once a Champion Model is selected, it moves to production with ongoing monitoring.

1. **Deployment**:

   - Champion Model registered in MLflow with `production` tag
   - Model artifact saved and ready for weekly predictions
   - Configuration documented in `conf/model/champion.yaml`
   - Decision log entry created

2. **Monitoring**:

   - Weekly performance tracked via **Streamlit dashboard**
   - Key metrics: ROI (rolling 4-week), Hit Rate, Volume
   - Alert levels: 🟢 Green / 🟡 Yellow / 🟠 Orange / 🔴 Red
   - **Manual workflow**: User checks dashboard when convenient

3. **Rollback Criteria**:

   - **Recommended** if 🔴 RED for 2+ weeks:
     - ROI drops >5% below test
     - Hit rate <48% (hard floor)
   - **Manual decision** after reviewing dashboard
   - Follow **[Rollback SOP](../ops/rollback_sop.md)** procedure

4. **Process**:
   - Generate weekly predictions: `uv run python scripts/prediction/generate_weekly_bets.py`
   - Review picks manually
   - Place bets
   - After games, score results: `uv run python scripts/scoring/score_weekly_bets.py`
   - Check dashboard: `streamlit run dashboard/monitoring.py`
   - If needed, rollback to previous Champion via MLflow

**Documentation**:

- [Monitoring Dashboard](../ops/monitoring.md) — Dashboard design and usage
- [Rollback SOP](../ops/rollback_sop.md) — Model rollback procedure
- [Weekly Pipeline](../ops/weekly_pipeline.md) — Production workflow

---

## Configuration Structure

This workflow is supported by a well-organized `conf/` directory that uses Hydra's composition model:

- **`conf/model/`**: Model definitions (e.g., `baseline.yaml`, `catboost_v1.yaml`, `champion.yaml`)
- **`conf/features/`**: Feature set definitions (e.g., `minimal_unadjusted_v1.yaml`, `opponent_adjusted_v1.yaml`)
- **`conf/experiment/`**: Experiment configurations that compose a model and feature set (e.g., `01_baseline.yaml`, `02_test_opponent_adjustment.yaml`)
- **`conf/training/`**: Training-specific configs (train years, test year, hyperparameters)

**Example Experiment**:

```yaml
# conf/experiment/02_test_opponent_adjustment.yaml
defaults:
  - override /model: baseline
  - override /features: opponent_adjusted_v1

experiment:
  name: v2_phase2_opponent_adjustment
  phase: 2
  description: "Testing opponent adjustment impact on Ridge baseline"
```

---

## Related Documentation

- **[12-Week Implementation Plan](./12_week_implementation_plan.md)** — Week-by-week V2 roadmap
- **[Promotion Framework](./promotion_framework.md)** — Detailed 5-gate criteria and testing
- **[V2 Baseline](../modeling/baseline.md)** — Ridge regression philosophy
- **[Feature Registry](../project_org/feature_registry.md)** — Active feature sets
- **[Experiments Index](../experiments/index.md)** — Experiment tracking
- **[Decision Log](../decisions/decision_log.md)** — All V2 decisions
- **[Monitoring](../ops/monitoring.md)** — Dashboard and performance tracking
- **[Rollback SOP](../ops/rollback_sop.md)** — Model rollback procedure
- **[Data Quality](../ops/data_quality.md)** — 3-layer validation system

---

**Last Updated**: 2025-12-05  
**Status**: Active (V2 Implementation)
