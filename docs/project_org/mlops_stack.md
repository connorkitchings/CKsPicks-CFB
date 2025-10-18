# MLOps Stack

This document outlines the MLOps stack currently in use for the `cfb_model` project and highlights planned upgrades captured on the roadmap.

## Core Components

The present-day stack is intentionally lightweight:

- **Core ML:** Scikit-learn for the ensemble models described in the modeling baseline.
- **Experiment Tracking:** MLflow for experiment management and model versioning.
- **Configuration:** Standard Python argparse/CLI flags (Hydra is targeted as a future enhancement per the roadmap).
- **Hyperparameter Optimization:** Manual grid search utilities in `scripts/optimize_hyperparameters.py` (Optuna adoption is deferred).

## 1. Core ML: Scikit-learn

- **Role:** Scikit-learn is used for implementing the core machine learning models, including the ensemble models for spread and total predictions.
- **Implementation:** The models are defined and trained in `src/cfb_model/models/train_model.py`.

## 2. Experiment Tracking: MLflow

- **Role:** MLflow is used to log experiments, including parameters, metrics, and model artifacts. This provides a centralized and organized way to track model performance and compare different experiments.
- **Implementation:** MLflow is integrated into the training script (`src/cfb_model/models/train_model.py`) and the hyperparameter optimization script (`scripts/optimize_hyperparameters.py`).

## 3. Configuration: CLI Flags

- **Role:** Command-line arguments (via `argparse`/Typer) manage runtime parameters for scripts such as `src/models/train_model.py` and `scripts/cli.py`.
- **Future Work:** The roadmap tracks an upgrade to Hydra for richer configuration composition once the underlying flows stabilize.

## 4. Hyperparameter Optimization: Manual Grid Search

- **Role:** Simple, reproducible grid searches (see `scripts/optimize_hyperparameters.py`) are used to tune model parameters.
- **Future Work:** Optuna remains on the roadmap; once revisited, this section will expand to cover sweeper configuration and experiment management.
