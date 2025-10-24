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

## 3. Configuration: Hydra + Typer

- **Role:** Hydra composes configuration across models, data slices, and sweep search spaces. Typer/argparse remain in place for legacy CLIs (`scripts/cli.py`, `scripts/training_cli.py`), but Hydra is the source of truth for optimization and validation jobs.
- **Implementation:** Defaults live in `conf/config.yaml`. Per-model overrides sit in `conf/model/*.yaml`, and Optuna parameter bundles live in `conf/hydra/sweeper/params/*.yaml`. Sweeps write to `artifacts/outputs/<YYYY-MM-DD>/<job_name_timestamp_trial>/`.
- **Future Work:** Continue migrating legacy CLIs to Hydra once downstream consumers are ready.

## 4. Hyperparameter Optimization: Optuna Sweeps

- **Role:** `scripts/optimize_hyperparameters.py` runs Hydra-powered Optuna sweeps, logging MLflow metrics per trial and persisting composed configs for reproducibility.
- **Implementation:** The Optuna sweeper is selected in the Defaults List (`override hydra/sweeper: optuna`). Study metadata lives in the run directory unless pointed to a persistent SQLite URI.
- **Next Steps:** Calibrate trial budgets by model, add multi-objective sweeps (hit rate + RMSE), and promote best-parameter snapshots into `conf/model/` as defaults.
