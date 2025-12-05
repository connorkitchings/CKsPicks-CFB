# Experimentation Workflow

This document defines the Standard Operating Procedure (SOP) for running model experiments in the `cfb_model` repository.

## 1. Define Features

Create a new feature configuration file in `conf/features/`.
**Example**: `conf/features/my_new_features.yaml`

```yaml
name: my_new_features
features:
  - off_epa_pp
  - def_epa_pp
target: spread_target
```

## 2. Configure Model

Create or reuse a model configuration in `conf/model/`.
**Example**: `conf/model/ridge_v1.yaml`

```yaml
name: ridge_v1
type: linear_regression
params:
  alpha: 1.0
target: spread_target
```

## 3. Run Experiment

Use the universal training script `src/train.py` with Hydra overrides.

**Basic Run**:

```bash
uv run python src/train.py model=ridge_v1 features=my_new_features
```

**Override Parameters**:

```bash
uv run python src/train.py model=ridge_v1 features=my_new_features model.params.alpha=0.5
```

## 4. Track Results

All runs are automatically tracked in MLflow.

- **Metrics**: RMSE, MAE logged automatically.
- **Artifacts**: Models saved to `artifacts/mlruns/...`
- **Logs**: Hydra logs saved to `artifacts/hydra_outputs/...`

## 5. View Results

Start the MLflow UI to compare runs:

```bash
uv run mlflow ui
```
