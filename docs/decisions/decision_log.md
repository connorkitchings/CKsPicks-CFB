## 2025-10-29 — Sprint 4: MLOps Foundation Completion

- Category: MLOps / Architecture / Tooling
- Decision: Completed Sprint 4 implementation of MLOps foundation, establishing automated hyperparameter optimization, model versioning, and configuration management for the CFB prediction system.
- Rationale: The project required a professional MLOps setup to support scalable model development and deployment. Sprint 4 focused on building the foundational infrastructure for automated optimization and model management.
- Impact:
  - **Hydra Configuration System**: Standardized all model configurations with proper parameter definitions and sweeper parameters for automated optimization
  - **Optuna Integration**: Implemented automated hyperparameter tuning for all model types (spread, total, points-for) with configuration-driven parameter spaces
  - **Model Registry**: Created comprehensive MLflow Model Registry integration for production model versioning, staging, and deployment
  - **Prediction Pipeline Refactoring**: Developed Hydra-based prediction script replacing argparse approach for better configuration management
  - **Configuration Standardization**: All ensemble models now have consistent, tunable configurations with optimized hyperparameters
- Next Steps: Begin Sprint 5 focusing on advanced modeling and monitoring enhancements
- References: `conf/model/`, `conf/hydra/sweeper/params/`, `scripts/model_registry.py`, `scripts/generate_weekly_bets_hydra.py`, `scripts/optimize_hyperparameters.py`

## 2025-10-29 — MLflow Artifact Logging Issue

- Category: MLOps / Tooling
- Decision: A persistent issue is preventing MLflow from saving model artifacts to the `mlruns` directory. This is blocking the full end-to-end testing of the MLOps pipeline, including model registration.
- Rationale: Despite numerous debugging attempts (including dependency changes, script simplification, and configuration adjustments), the root cause of the MLflow artifact logging failure has not been identified. To move forward, a workaround will be used to test the prediction pipeline, but a dedicated task to resolve the MLflow issue is required.
- Impact:
  - The MLOps pipeline is not fully functional.
  - Model versioning and registration is blocked.
- Next Steps: Prioritize a deep investigation into the MLflow artifact logging issue in the next sprint.

## 2025-11-19 — MLflow Tracking URI Hardening

- Category: MLOps / Tooling
- Decision: Standardized all MLflow entrypoints on `src.utils.mlflow_tracking.get_tracking_uri()` so every CLI resolves the tracking URI to an absolute repo-root path (or honors `MLFLOW_TRACKING_URI`).
- Rationale: Hydra jobs occasionally ran from nested `artifacts/outputs/**` directories, causing relative URIs like `file:./artifacts/mlruns` to write runs outside the canonical store or fail when directories were missing. Centralizing the resolve logic guarantees consistent paths locally and makes it trivial to point scripts at the Dockerized tracker via an environment override.
- Impact:
  - Added `get_tracking_uri()` + `setup_mlflow()` helpers that compute `file:///.../cfb_model/artifacts/mlruns` automatically.
  - Updated all MLflow-aware CLIs (`train_model.py`, `optimize_hyperparameters.py`, `walk_forward_validation.py`, registry/test scripts, etc.) to import the helper instead of hard-coding strings.
  - Re-ran `scripts/debug_mlflow_artifact_logging.py` under Hydra to confirm artifacts now land in `artifacts/mlruns/**` with the expected experiment metadata.
- Next Steps: When running against Docker/remote MLflow, export `MLFLOW_TRACKING_URI` and the same helper will target the new endpoint (keep `docs/operations/mlflow_mcp.md` as the authoritative reference).

## 2025-11-19 — Walk-Forward Check on Staging Models

- Category: Modeling / Validation
- Decision: Ran a constrained walk-forward validation (train 2023, evaluate weeks 8–13 of 2023–2024) comparing the staging registry models (`cfb_spread_lightgbm`, `cfb_total_catboost`) to the legacy ensembles. LightGBM spreads trailed the ensemble on the 2024 holdout (RMSE 17.98 vs. 16.72), while CatBoost totals matched within 0.03 RMSE.
- Rationale: We needed evidence before promoting the newly registered models; limited-scope WFV provides a quick signal without waiting for the full 2014–2024 run.
- Impact:
  - Saved artifacts under `artifacts/validation/walk_forward/**` (including combined averages at `metrics_summary_2019_2024_avg.csv`) so future assistants can inspect per-week predictions.
  - Updated `docs/project_org/model_evaluation_criteria.md` with both the 2023–2024 table and the extended-window averages, noting that spreads require additional tuning while totals are viable once longer horizons confirm parity.
- Next Steps: Expand the WFV window (2019 onward) once CLI noise is addressed, and re-run after experimenting with exponential/half-life weighting and adjustment-depth asymmetry.

## 2025-11-19 — Points-For Spread Model Prototype

- Category: Modeling / Experimentation
- Decision: Explored a new "points-for" modeling approach for the spread prediction, where separate models are trained to predict the home and away team scores independently.
- Rationale: The existing spread models (including LightGBM and CatBoost experiments) have been underperforming the baseline ensemble. This was an attempt to tackle the problem from a different angle.
- Impact:
    - Created a prototype script `src/models/train_points_for_prototype.py`.
    - Trained two Ridge regression models (one for home points, one for away points) on 2023 data and evaluated on 2024 data.
    - The resulting spread prediction metrics were RMSE: 19.5141 and MAE: 15.2523.
    - These initial results are not competitive with the baseline ensemble's 2024 performance (RMSE: ~16.9).
- Next Steps: Further work on this specific prototype is on hold. The focus should return to other methods of improving the spread model. The prototype script is available for future reference.
