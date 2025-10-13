# MLOps Stack

This document outlines the MLOps stack used in the `cfb_model` project to ensure reproducibility, scalability, and efficient experimentation.

## Core Components

The project is built around a modern MLOps stack that includes:

- **Core ML:** Scikit-learn for traditional ML models.
- **Experiment Tracking:** MLflow for experiment management and model versioning.
- **Configuration:** Hydra for managing different model configurations and feature sets.
- **Hyperparameter Optimization:** Optuna for finding optimal model parameters.

## 1. Core ML: Scikit-learn

- **Role:** Scikit-learn is used for implementing the core machine learning models, including the ensemble models for spread and total predictions.
- **Implementation:** The models are defined and trained in `src/cfb_model/models/train_model.py`.

## 2. Experiment Tracking: MLflow

- **Role:** MLflow is used to log experiments, including parameters, metrics, and model artifacts. This provides a centralized and organized way to track model performance and compare different experiments.
- **Implementation:** MLflow is integrated into the training script (`src/cfb_model/models/train_model.py`) and the hyperparameter optimization script (`scripts/optimize_hyperparameters.py`).

## 3. Configuration: Hydra

- **Role:** Hydra is used for managing configurations for training and hyperparameter optimization. This allows for easy switching between different models, feature sets, and other parameters without changing the code.
- **Implementation:** Hydra configurations are stored in the `conf/` directory. The training and optimization scripts are decorated with `@hydra.main()` to load the configurations.

## 4. Hyperparameter Optimization: Optuna

- **Role:** Optuna is used for efficient hyperparameter optimization. It is integrated with Hydra through the `hydra-optuna-sweeper` plugin.
- **Implementation:** The hyperparameter optimization script (`scripts/optimize_hyperparameters.py`) uses Optuna to find the best hyperparameters for the models. The search space is defined in the Hydra configuration files.
