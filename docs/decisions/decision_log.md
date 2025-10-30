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
