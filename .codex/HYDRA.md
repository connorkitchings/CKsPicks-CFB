# Hydra Configuration Guide

> **Quick reference for Hydra configuration system in CFB Model**
>
> Hydra is used for experiment management and configuration composition.

---

## Overview

Hydra allows us to:
- **Compose** configs from multiple files
- **Override** parameters via command line
- **Version** experiments with automatic logging
- **Sweep** hyperparameters with Optuna integration

**Documentation:** https://hydra.cc/docs/intro/

---

## Directory Structure

```
conf/
├── config.yaml              # Main entry point
├── model/                   # Model configurations
│   ├── catboost.yaml
│   ├── xgboost.yaml
│   ├── ridge.yaml
│   └── lgbm.yaml
├── features/                # Feature set definitions
│   ├── standard_v1.yaml
│   ├── recency_v1.yaml
│   ├── pace_v1.yaml
│   └── spread_shap_pruned.yaml
├── experiment/              # Pre-packaged experiments
│   ├── spread_catboost_baseline_v1.yaml
│   └── total_xgboost_v1.yaml
├── tuning/                  # Optuna search spaces
│   ├── catboost_optuna.yaml
│   └── xgboost_optuna.yaml
├── paths/                   # Data path overrides
│   └── default.yaml
└── weekly_bets/            # Betting policy configs
    └── default.yaml
```

---

## Config Composition

### Main Config (`conf/config.yaml`)

```yaml
defaults:
  - _self_                    # Load this file first
  - paths: default            # Load conf/paths/default.yaml
  - model: catboost           # Load conf/model/catboost.yaml
  - features: standard_v1     # Load conf/features/standard_v1.yaml
  - experiment: null          # Optional experiment override

data:
  adjustment_iteration: 2
  train_years: [2019, 2021, 2022, 2023]
  test_year: 2024

mode: train                   # train | optimize
```

### Model Config (`conf/model/catboost.yaml`)

```yaml
name: catboost
params:
  iterations: 1000
  depth: 6
  learning_rate: 0.1
  l2_leaf_reg: 3
  random_seed: 42

early_stopping_rounds: 50
verbose: False
```

### Feature Config (`conf/features/standard_v1.yaml`)

```yaml
feature_set_id: standard_v1

allow_list:
  - home_off_yards_per_play_adj2
  - home_def_yards_per_play_adj2
  - away_off_yards_per_play_adj2
  - away_def_yards_per_play_adj2
  # ... more features

feature_groups:
  - efficiency
  - situational
  - pace
```

### Experiment Config (`conf/experiment/spread_catboost_baseline_v1.yaml`)

```yaml
# @package _global_

defaults:
  - override /model: catboost
  - override /features: standard_v1

data:
  adjustment_iteration: 2
  test_year: 2024

model:
  params:
    iterations: 500
    depth: 4

experiment_name: spread_catboost_baseline_v1
```

---

## Command Line Overrides

### Basic Syntax

```bash
# General pattern
PYTHONPATH=. uv run python src/models/train_model.py key=value

# Nested keys
PYTHONPATH=. uv run python src/models/train_model.py model.params.depth=8

# Multiple overrides
PYTHONPATH=. uv run python src/models/train_model.py \
    model=xgboost \
    data.test_year=2025 \
    mode=optimize
```

### Config Group Selection

```bash
# Use different model config
model=xgboost              # Uses conf/model/xgboost.yaml

# Use different feature set
features=recency_v1        # Uses conf/features/recency_v1.yaml

# Load experiment (overrides all)
experiment=spread_catboost_baseline_v1
```

### Parameter Overrides

```bash
# Override top-level parameter
data.test_year=2025

# Override nested parameter
model.params.iterations=2000

# Override list
data.train_years=[2021,2022,2023]
```

### Add/Delete Parameters

```bash
# Add new parameter
+new_param=value

# Delete parameter
~unwanted_param

# Add nested parameter
+model.params.new_param=123
```

---

## Common Override Patterns

### Training Different Years

```bash
# Train on 2023, test on 2024
data.test_year=2024

# Train on different years
data.train_years=[2020,2021,2022]
```

### Model Selection

```bash
# Use CatBoost
model=catboost

# Use XGBoost
model=xgboost

# Use Ridge (baseline)
model=ridge
```

### Feature Sets

```bash
# Standard features
features=standard_v1

# With recency weighting
features=recency_v1

# SHAP-pruned features
features=spread_shap_pruned
```

### Hyperparameter Tuning

```bash
# Change learning rate
model.params.learning_rate=0.05

# Change tree depth
model.params.depth=8

# Change regularization
model.params.l2_leaf_reg=5
```

### Experiment Selection

```bash
# Load full experiment config
experiment=spread_catboost_baseline_v1

# Load experiment and override
experiment=spread_catboost_baseline_v1 \
data.test_year=2025
```

---

## Debugging Configs

### View Composed Config

```bash
# See final composed config
PYTHONPATH=. uv run python src/models/train_model.py --cfg job

# See with interpolations resolved
PYTHONPATH=. uv run python src/models/train_model.py --cfg job --resolve

# Pretty print
PYTHONPATH=. uv run python src/models/train_model.py --cfg job | less
```

### Validate Config

```bash
# Show help (lists all options)
PYTHONPATH=. uv run python src/models/train_model.py --help

# Show config options
PYTHONPATH=. uv run python src/models/train_model.py --cfg hydra

# List available config groups
PYTHONPATH=. uv run python src/models/train_model.py --help | grep -A 10 "Config groups"
```

---

## Optuna Integration

### Tuning Config (`conf/tuning/catboost_optuna.yaml`)

```yaml
search_space:
  iterations:
    type: int
    low: 100
    high: 2000

  depth:
    type: int
    low: 3
    high: 10

  learning_rate:
    type: float
    low: 0.01
    high: 0.3
    log: true

optuna:
  n_trials: 100
  direction: minimize
  study_name: catboost_spread
```

### Running Optimization

```bash
# Run Optuna sweep
PYTHONPATH=. uv run python src/models/train_model.py \
    mode=optimize \
    model=catboost \
    tuning=catboost_optuna

# Custom trials
PYTHONPATH=. uv run python src/models/train_model.py \
    mode=optimize \
    optuna.n_trials=50

# Different metric
PYTHONPATH=. uv run python src/models/train_model.py \
    mode=optimize \
    optuna.direction=maximize
```

---

## Config Interpolation

### Variable Interpolation

```yaml
# conf/config.yaml
data_root: /Volumes/CK SSD/Coding Projects/cfb_model/
raw_data_path: ${data_root}/raw
processed_data_path: ${data_root}/processed

# ${data_root} will be replaced with the actual value
```

### Resolver Functions

```yaml
# Reference another config group
model_name: ${model.name}

# Environment variables
data_root: ${oc.env:CFB_MODEL_DATA_ROOT}

# Conditional values
learning_rate: ${oc.select:model.params.learning_rate,0.1}
```

---

## Experiment Tracking

### Hydra Outputs

Hydra creates an output directory for each run:

```
artifacts/hydra_outputs/
└── YYYY-MM-DD/
    └── HH-MM-SS/
        ├── .hydra/
        │   ├── config.yaml       # Composed config
        │   ├── hydra.yaml        # Hydra settings
        │   └── overrides.yaml    # CLI overrides
        └── main.log              # Execution log
```

### Config Versioning

Every training run logs:
- **Composed config** (`.hydra/config.yaml`)
- **CLI overrides** (`.hydra/overrides.yaml`)
- **Timestamp** (directory name)

This allows **perfect reproducibility** of any experiment.

---

## Best Practices

### DO

✅ **Use experiment configs** for significant experiments
✅ **Version feature sets** with IDs (e.g., `standard_v1`, `standard_v2`)
✅ **Document configs** with comments
✅ **Test configs** with `--cfg job` before training
✅ **Use interpolation** to reduce duplication

### DON'T

❌ **Don't hardcode paths** - use `paths/default.yaml` and env vars
❌ **Don't duplicate configs** - use composition and inheritance
❌ **Don't modify configs during execution** - override via CLI
❌ **Don't delete `.hydra/` folders** - they're for reproducibility
❌ **Don't use mutable defaults** (lists, dicts) without `_target_`

---

## Config Templates

### New Model Config

```yaml
# conf/model/my_model.yaml
name: my_model

params:
  param1: value1
  param2: value2
  random_seed: 42

early_stopping_rounds: 50
verbose: False
```

### New Feature Set

```yaml
# conf/features/my_features_v1.yaml
feature_set_id: my_features_v1

allow_list:
  - feature1
  - feature2
  - feature3

feature_groups:
  - group1
  - group2
```

### New Experiment

```yaml
# conf/experiment/my_experiment.yaml
# @package _global_

defaults:
  - override /model: catboost
  - override /features: my_features_v1

data:
  adjustment_iteration: 2
  test_year: 2024

model:
  params:
    iterations: 1000

experiment_name: my_experiment
```

---

## Troubleshooting

### Common Errors

**Error:** `MissingMandatoryValue: Missing mandatory value: model`
- **Fix:** Ensure `conf/config.yaml` has `defaults: - model: catboost`

**Error:** `ConfigCompositionException: Could not find 'model/xgboost'`
- **Fix:** Check that `conf/model/xgboost.yaml` exists

**Error:** `InterpolationResolutionError: Could not resolve ${data_root}`
- **Fix:** Ensure variable is defined or use `oc.env:VAR_NAME`

**Error:** `OverrideParseException: Error parsing override 'key=value'`
- **Fix:** Check syntax - no spaces around `=`, use quotes for strings with spaces

### Debug Checklist

1. **View composed config:** `--cfg job --resolve`
2. **Check file exists:** `ls conf/model/catboost.yaml`
3. **Validate syntax:** YAML indentation (2 spaces, no tabs)
4. **Check interpolation:** Ensure referenced variables exist
5. **Test overrides:** Try with minimal overrides first

---

## Quick Reference

### CLI Flags

| Flag | Purpose |
|------|---------|
| `--cfg job` | Show composed config |
| `--cfg hydra` | Show Hydra config |
| `--resolve` | Resolve interpolations |
| `--help` | Show all options |
| `--info` | Show debug info |

### Override Syntax

| Syntax | Example | Purpose |
|--------|---------|---------|
| `key=value` | `data.test_year=2025` | Set value |
| `+key=value` | `+new_param=123` | Add new key |
| `~key` | `~unwanted_param` | Delete key |
| `key=[a,b]` | `train_years=[2021,2022]` | Set list |
| `key=null` | `experiment=null` | Set to null |

### Composition Order

1. `defaults` in `config.yaml`
2. Experiment config (if specified)
3. CLI overrides

**Later overrides win** - CLI overrides have highest priority.

---

_Last Updated: 2026-02-13_
_Hydra configuration system reference_
