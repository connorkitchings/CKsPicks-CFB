# MLOps and Experimentation Guide

This guide explains how to run experiments, tune hyperparameters, and manage models using the Hydra/Optuna/MLflow stack.

## Quick Start

### Basic Training

Train a model with default configuration:

```bash
PYTHONPATH=. uv run python src/models/train_model.py
```

### Run a Pre-Configured Experiment

Use an experiment config from `conf/experiment/`:

```bash
PYTHONPATH=. uv run python src/models/train_model.py experiment=debug_dry_run
```

### Hyperparameter Optimization

Run an Optuna study to find the best parameters:

```bash
PYTHONPATH=. uv run python src/models/train_model.py mode=optimize
```

## Configuration System (Hydra)

The project uses [Hydra](https://hydra.cc/) for hierarchical configuration management.

### Configuration Structure

```
conf/
├── config.yaml              # Main config (defaults)
├── model/                   # Model-specific configs
│   ├── catboost.yaml
│   └── ridge.yaml
├── features/                # Feature set configs
│   └── standard_v1.yaml
├── tuning/                  # Optuna search spaces
│   └── catboost_optuna.yaml
├── experiment/              # Pre-configured experiments
│   ├── debug_dry_run.yaml
│   ├── spread_catboost_baseline_v1.yaml
│   └── totals_pace_interaction_v1.yaml
└── paths/
    └── default.yaml         # Path overrides
```

### Overriding Config Values

Override specific values via command line:

```bash
# Override model type
PYTHONPATH=. uv run python src/models/train_model.py model=ridge

# Override data year
PYTHONPATH=. uv run python src/models/train_model.py data.test_year=2025

# Override multiple values
PYTHONPATH=. uv run python src/models/train_model.py \
  model=catboost \
  data.test_year=2025 \
  model.params.depth=8
```

## Hyperparameter Tuning (Optuna)

### Define Search Space

Edit `conf/tuning/catboost_optuna.yaml`:

```yaml
metric: RMSE
direction: minimize
n_trials: 50

params:
  learning_rate:
    type: float
    low: 0.001
    high: 0.1
    log: true
  depth:
    type: int
    low: 4
    high: 10
```

### Run Optimization

```bash
PYTHONPATH=. uv run python src/models/train_model.py mode=optimize
```

Best parameters are automatically saved to `conf/model/params/catboost_best.yaml`.

### Use Optimized Parameters

```bash
# Manually edit conf/model/catboost.yaml to include the best params
# OR use Hydra to merge them at runtime
PYTHONPATH=. uv run python src/models/train_model.py \
  +model.params=@params/catboost_best.yaml
```

## Model Registry (MLflow)

All trained models are automatically registered to MLflow with standardized IDs.

### Model ID Schema

Format: `{model_type}-{feature_set}-{tuning}-{data_version}-{timestamp}-{hash}`

Example: `catboost-standard_v1-baseline-train_2019_2023-20251127_095712-a1b2c3`

### View Registered Models

Start MLflow UI:

```bash
mlflow ui --backend-store-uri artifacts/mlruns
```

Navigate to http://localhost:5000/

### Promote to Production

Via MLflow UI:

1. Navigate to "Models" → Your model
2. Select a version
3. Click "Stage" → "Transition to Production"

Via Python:

```python
from mlflow.tracking import MlflowClient

client = MlflowClient()
client.transition_model_version_stage(
    name="PointsFor_Home",
    version=1,
    stage="Production"
)
```

## Creating New Experiments

### 1. Create Experiment Config

Create `conf/experiment/my_experiment.yaml`:

```yaml
# @package _global_
defaults:
  - override /model: catboost
  - override /features: standard_v1

experiment:
  name: my_experiment

model:
  params:
    depth: 8
    learning_rate: 0.05
```

### 2. Run The Experiment

```bash
PYTHONPATH=. uv run python src/models/train_model.py experiment=my_experiment
```

### 3. Compare Results

View in MLflow UI or export metrics:

```python
import mlflow

runs = mlflow.search_runs(experiment_names=["CFB_Model_Training"])
print(runs[["metrics.home_rmse", "metrics.away_rmse", "params.model.type"]])
```

## Best Practices

1. **Use Experiments for Major Changes**: Create experiment configs for significant feature/model changes.
2. **Tag Your Runs**: Add custom tags via MLflow to track experiment conditions.
3. **Version Your Data**: Include data version in the Model ID for full reproducibility.
4. **Save Predictions**: Always save test predictions for post-hoc analysis.
5. **Document Decisions**: Update `session_logs/` with experiment findings.

## Troubleshooting

### Import Errors

Ensure `PYTHONPATH=.` is set:

```bash
export PYTHONPATH=.
uv run python src/models/train_model.py
```

### Hydra Output Directory

Hydra creates `artifacts/hydra_outputs/` by default. This is configured in `conf/config.yaml`:

```yaml
hydra:
  run:
    dir: artifacts/hydra_outputs/${now:%Y-%m-%d}/${now:%H-%M-%S}
```

### Missing MLflow Data

If MLflow tracking is not working, check:

1. `artifacts/mlruns/` exists
2. `src/utils/mlflow_tracking.py` points to the correct URI
