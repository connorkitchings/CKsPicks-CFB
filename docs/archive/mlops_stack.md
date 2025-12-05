# MLOps Stack

This document outlines the MLOps stack currently in use for the `cfb_model` project and highlights planned upgrades captured on the roadmap.

## Core Components

The present-day stack is intentionally lightweight but now fully integrates Hydra and Optuna:

- **Core ML:** Scikit-learn (plus XGBoost for points-for experiments) as described in the modeling baseline.
- **Experiment Tracking:** MLflow for experiment management and model versioning.
- **Configuration:** Hydra drives all sweep/validation jobs with defaults defined under `conf/`.
- **Hyperparameter Optimization:** Optuna sweeps launched through Hydra (`scripts/optimize_hyperparameters.py`) with search spaces stored in `conf/hydra/sweeper/params/`.
- **Workflow Orchestration:** Prefect flows remain available for pre-aggregations, though weekly operations run via CLI scripts.

## 1. Core ML: Scikit-learn

- **Role:** Scikit-learn powers the ensemble models for spread and total predictions; XGBoost supplements the points-for experiments.
- **Implementation:** Training lives in `src/models/train_model.py`, which emits metrics and artifacts per season.

## 2. Experiment Tracking: MLflow

- **Role:** MLflow is used to log experiments, including parameters, metrics, and model artifacts. This provides a centralized and organized way to track model performance and compare different experiments.
- **Implementation:** MLflow is integrated into the training script (`src/models/train_model.py`), the Hydra-based optimization workflow (`scripts/optimize_hyperparameters.py`), and walk-forward validation (`scripts/walk_forward_validation.py`). Results write to the local tracking URI under `artifacts/mlruns/`.
- **Dashboards via Docker:** All MLflow reviews (and future monitoring dashboards) must run via Docker. From the repo root, launch the tracker with `MLFLOW_PORT=5050 docker compose -f docker/mlops/docker-compose.yml up mlflow`. Override `MLFLOW_PORT` if `5000` is unavailable; the UI binds to `http://localhost:${MLFLOW_PORT:-5000}` and reads the shared `artifacts/mlruns/` volume.

## 3. Configuration: Hydra + Typer

- **Role:** Hydra composes configuration across models, data slices, and sweep search spaces. Typer/argparse remain in place for legacy CLIs (`scripts/cli.py`, `scripts/training_cli.py`), but Hydra is the source of truth for optimization and validation jobs.
- **Implementation:** Defaults live in `conf/config.yaml`. Per-model overrides sit in `conf/model/*.yaml`, and Optuna parameter bundles live in `conf/hydra/sweeper/params/*.yaml`. Sweeps write to `artifacts/outputs/<YYYY-MM-DD>/<job_name_timestamp_trial>/`.
- **Future Work:** Continue migrating legacy CLIs to Hydra once downstream consumers are ready.

## 4. Hyperparameter Optimization: Optuna Sweeps

- **Role:** `scripts/optimize_hyperparameters.py` runs Hydra-powered Optuna sweeps, logging MLflow metrics per trial and persisting composed configs for reproducibility. Spread/total sweeps now search expanded spaces (Ridge α from 1e‑4–1e2, ElasticNet l1_ratio 0.1–0.95, RF/GBM depth + sampling tweaks) and include the new HistGradientBoosting, LightGBM, and CatBoost model families.
- **Implementation:** The Optuna sweeper is selected in the Defaults List (`override hydra/sweeper: optuna`). Study metadata lives in the run directory unless pointed to a persistent SQLite URI. Style/tempo contrasts arrive automatically through `load_point_in_time_data`, so no extra overrides are required.
- **Workflow:** To reproduce the sanctioned train/test split (train: 2019, 2021-2023 weeks 3-12; test: 2024 weeks 13-15), run e.g.

  ```bash
  uv run python scripts/optimize_hyperparameters.py \
    model=spread_hist_gradient_boosting \
    data.train_years='[2019,2021,2022,2023]' \
    data.test_year=2024 \
    data.adjustment_iteration=4 \
    +hydra.sweeper.params=model.params.learning_rate:tag(log,interval(0.01,0.3))
  ```

  Override `model=` with `total_random_forest`, `spread_elastic_net`, etc., to sweep other ensembles; results log under `artifacts/mlruns/<experiment_id>/<run_id>/` for comparison against the current ensemble baseline.
- **Next Steps:** Calibrate trial budgets by model, add multi-objective sweeps (hit rate + RMSE), and promote best-parameter snapshots into `conf/model/` as defaults.
