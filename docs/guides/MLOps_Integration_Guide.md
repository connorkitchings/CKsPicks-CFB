# MLOps Integration Guide for the CFB Model

> **Note:** This project currently uses a set of dedicated scripts for training, evaluation, and hyperparameter optimization (e.g., `train_model.py`, `optimize_hyperparameters.py`). This guide outlines how a more formalized MLOps stack using **MLFlow, Hydra, and Optuna** could be integrated as a future enhancement to our existing workflow.

---

## Overview

This document summarizes how to transform our model experimentation into a more scalable and automated MLOps system by integrating three key tools:

-   **MLFlow** → For experiment tracking and model logging.
-   **Hydra** → For configuration management.
-   **Optuna** → For advanced hyperparameter optimization.

---

## 1. MLFlow: Experiment Tracking

### Purpose

MLFlow would act as our project’s central ledger for experiments, recording parameters, metrics, and model artifacts for every training run. This would formalize the tracking we currently do via CSVs and session logs.

### Project-Specific Implementation

Our `src/cfb_model/utils/mlflow_tracking.py` already sets up a local MLFlow instance. Here is how we would use it in a training run for our `Ridge` spread model.

```python
import mlflow
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from cfb_model.models.train_model import load_and_prepare_data # Assuming a helper

mlflow.set_experiment("CFB_Spread_Predictions")

# Load data using our project's functions
X_train, X_test, y_train, y_test = load_and_prepare_data(
    train_years=[2019, 2021, 2022, 2023], 
    test_year=2024
)

with mlflow.start_run(run_name="Ridge_Alpha_0.1"):
    # Log model parameters
    alpha = 0.1
    mlflow.log_param("alpha", alpha)
    
    # Train the model
    model = Ridge(alpha=alpha, random_state=42)
    model.fit(X_train, y_train)
    
    # Evaluate and log metrics
    predictions = model.predict(X_test)
    mae = mean_absolute_error(y_test, predictions)
    mlflow.log_metric("test_mae", mae)
    
    # Log the model artifact
    mlflow.sklearn.log_model(model, "ridge_spread_model")
```

---

## 2. Hydra: Configuration Management

### Purpose

Hydra would allow us to define our training parameters (like model type, alpha values, or feature sets) in YAML files instead of hardcoding them or passing many CLI arguments.

### Example Project Config

```yaml
# conf/config.yaml
data:
  train_years: [2019, 2021, 2022, 2023]
  test_year: 2024
  # Path to our cached, point-in-time features
  feature_path: "data/processed/team_week_adj"

model:
  # Use Hydra's instantiation feature
  _target_: sklearn.linear_model.Ridge
  alpha: 0.1
  random_state: 42

training:
  experiment_name: "CFB_Spread_Predictions"
```

With this, we could instantiate our model directly from the config: `model = hydra.utils.instantiate(cfg.model)`.

---

## 3. Optuna: Hyperparameter Optimization

### Purpose

Optuna provides a more advanced alternative to the `GridSearchCV` currently used in `scripts/optimize_hyperparameters.py`. It uses Bayesian optimization to find the best hyperparameters more efficiently.

### Project-Specific Example

Here’s how we could adapt our existing optimization to use Optuna for the `Ridge` model's `alpha` parameter.

```python
import optuna
from sklearn.linear_model import Ridge
from sklearn.model_selection import cross_val_score, TimeSeriesSplit

# X, y would be loaded from our training data
# X, y = load_training_data(...)

def objective(trial):
    # Suggest a value for alpha on a log scale
    alpha = trial.suggest_float("alpha", 1e-3, 10.0, log=True)
    
    model = Ridge(alpha=alpha)
    
    # Use TimeSeriesSplit, just like in our current script
    cv = TimeSeriesSplit(n_splits=5)
    
    # Use negative MAE as the score to maximize
    score = cross_val_score(
        model, X, y, cv=cv, scoring='neg_mean_absolute_error'
    ).mean()
    
    return score

# Create and run the study
study = optuna.create_study(direction="maximize") # Maximize negative MAE (i.e., minimize MAE)
study.optimize(objective, n_trials=50)

print(f"Best alpha: {study.best_params['alpha']}")
```

---

## 4. Integrated MLOps Workflow

By combining these tools, we could create a powerful, declarative training script.

### Unified Training Script Example

```python
import hydra
from omegaconf import DictConfig
import mlflow
from sklearn.metrics import mean_absolute_error

@hydra.main(version_base=None, config_path="conf", config_name="config")
def train(cfg: DictConfig) -> float:
    # MLFlow setup
    mlflow.set_experiment(cfg.training.experiment_name)

    with mlflow.start_run():
        # Log config from Hydra
        mlflow.log_params(cfg.model)
        
        # Instantiate model from config
        model = hydra.utils.instantiate(cfg.model)

        # ... data loading and training logic ...
        model.fit(X_train, y_train)
        
        # Evaluate and log
        predictions = model.predict(X_test)
        mae = mean_absolute_error(y_test, predictions)
        mlflow.log_metric("test_mae", mae)
        mlflow.sklearn.log_model(model, "model")

    return -mae # Return negative MAE for Optuna to maximize

if __name__ == "__main__":
    train()
```

To run a hyperparameter sweep with this setup, the command would be:

```bash
# Hydra's multirun mode would use the Optuna sweeper
python train.py --multirun model.alpha=range(0.1,1.0,step=0.1)
```

---

## Conclusion

Integrating **MLFlow**, **Hydra**, and **Optuna** is a logical next step to formalize the experimentation and operational framework of this project. While our current script-based approach is effective, this stack would provide:

-   **Full Experiment Traceability**: Centralized logging to replace manual tracking.
-   **Advanced Hyperparameter Optimization**: More efficient than grid search.
-   **Declarative Configuration**: Flexible and reproducible runs without code changes.

This transforms our workflow from a series of scripts into a more robust and scalable MLOps system.
