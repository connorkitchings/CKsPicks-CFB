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
│   ├── linear.yaml          # Ridge/linear (default family)
│   ├── elastic_net.yaml
│   ├── catboost_v1.yaml
│   ├── xgboost_v1.yaml
│   ├── champion.yaml        # Legacy V2 champion reference
│   ├── ensemble_v1.yaml
│   ├── stacking_v1.yaml
│   └── catboost_classifier.yaml
├── features/                # Feature set definitions
│   ├── matchup_v1.yaml      # (default) 16-feature matchup set
│   ├── matchup_v2.yaml / matchup_v2_pruned.yaml
│   ├── opponent_adjusted_v1.yaml
│   ├── recency_weighted_v1.yaml
│   ├── extended_v1.yaml
│   ├── interaction_v1.yaml
│   ├── internal_advanced_v1.yaml / internal_power_rating_v1.yaml
│   ├── cover_classifier_v1.yaml
│   └── ablation_baseline.yaml
├── experiment/              # Pre-packaged experiments
│   ├── week0_regimes.yaml   # 2026 regime tournament
│   ├── preseason_regimes.yaml
│   └── v2_*.yaml            # V2-era history (+ legacy/)
├── training/                # Chronology contracts
│   ├── default.yaml
│   └── week0_2026.yaml      # Frozen 2026 temporal windows
├── weekly_bets/             # Weekly publish configs
│   ├── v4_2026.yaml         # LAUNCH (V4 bundle)
│   ├── v3_preview_games_ordinal_2026.yaml
│   ├── v2_preview_2026.yaml
│   └── v2_champion.yaml
├── policy/                  # canonical_week_2026_v1.yaml
├── preprocessing/ paths/ hydra/ sweeper/ research/ legacy/ validation.yaml
```

---

## Config Composition

### Main Config (`conf/config.yaml`)

```yaml
defaults:
  - _self_                    # Load this file first
  - paths: default            # Load conf/paths/default.yaml
  - model: linear             # Load conf/model/linear.yaml
  - features: matchup_v1      # Load conf/features/matchup_v1.yaml
  - training: default         # Load conf/training/default.yaml
  - preprocessing: none
  - hydra: default
  - experiment: null          # Optional experiment override

random_seed: 42
```

### Model Config (example: `conf/model/catboost_v1.yaml`)

```yaml
name: catboost_v1
params:
  iterations: 1000
  depth: 6
  learning_rate: 0.1
  l2_leaf_reg: 3
  random_seed: 42

early_stopping_rounds: 50
verbose: False
```

### Feature Config (example shape: `conf/features/matchup_v1.yaml`)

```yaml
feature_set_id: matchup_v1

allow_list:
  - home_off_yards_per_play_adj2
  - home_def_yards_per_play_adj2
  - away_off_yards_per_play_adj2
  - away_def_yards_per_play_adj2
  # ... more features

feature_groups:
  - efficiency
  - situational
```

### Experiment Config (example: `conf/experiment/week0_regimes.yaml`)

```yaml
# @package _global_

defaults:
  - override /model: catboost_v1
  - override /features: matchup_v1

data:
  adjustment_iteration: 2
  test_year: 2024

model:
  params:
    iterations: 500
    depth: 4

experiment_name: week0_regimes
```

---

## Command Line Overrides

### Basic Syntax

```bash
# General pattern
PYTHONPATH=src uv run python -m cks_picks_cfb.train key=value

# Nested keys
PYTHONPATH=src uv run python -m cks_picks_cfb.train model.params.depth=8

# Multiple overrides
PYTHONPATH=src uv run python -m cks_picks_cfb.train \
    model=xgboost_v1 \
    data.test_year=2025 \
    mode=optimize
```

### Config Group Selection

```bash
# Use different model config
model=xgboost_v1            # Uses conf/model/xgboost_v1.yaml

# Use different feature set
features=recency_weighted_v1  # Uses conf/features/recency_weighted_v1.yaml

# Load experiment (overrides all)
experiment=week0_regimes
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

# Train on different years (never include 2020)
data.train_years=[2021,2022,2023]
```

### Model Selection

```bash
# Use CatBoost
model=catboost_v1

# Use XGBoost
model=xgboost_v1

# Use linear/Ridge (baseline family)
model=linear
```

### Feature Sets

```bash
# Matchup features (default)
features=matchup_v1

# Pruned matchup set
features=matchup_v2_pruned

# With recency weighting
features=recency_weighted_v1
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
experiment=week0_regimes

# Load experiment and override
experiment=week0_regimes \
data.test_year=2025
```

---

## Debugging Configs

### View Composed Config

```bash
# See final composed config
PYTHONPATH=src uv run python -m cks_picks_cfb.train --cfg job

# See with interpolations resolved
PYTHONPATH=src uv run python -m cks_picks_cfb.train --cfg job --resolve

# Pretty print
PYTHONPATH=src uv run python -m cks_picks_cfb.train --cfg job | less
```

### Validate Config

```bash
# Show help (lists all options)
PYTHONPATH=src uv run python -m cks_picks_cfb.train --help

# Show config options
PYTHONPATH=src uv run python -m cks_picks_cfb.train --cfg hydra

# List available config groups
PYTHONPATH=src uv run python -m cks_picks_cfb.train --help | grep -A 10 "Config groups"
```

---

## Optuna Integration

Legacy Optuna search spaces live under `conf/legacy/tuning/`. Optimization is
driven through `mode=optimize` (see `.codex/QUICKSTART.md`); sweep behavior is
configured in `conf/sweeper/`.

### Running Optimization

```bash
# Run Optuna sweep
PYTHONPATH=src uv run python -m cks_picks_cfb.train \
    mode=optimize \
    model=catboost_v1

# Custom trials
PYTHONPATH=src uv run python -m cks_picks_cfb.train \
    mode=optimize \
    optuna.n_trials=50

# Different metric
PYTHONPATH=src uv run python -m cks_picks_cfb.train \
    mode=optimize \
    optuna.direction=maximize
```

---

## Config Interpolation

### Variable Interpolation

```yaml
# conf/config.yaml (illustrative)
raw_data_path: ${paths.data_root}/raw
processed_data_path: ${paths.data_root}/processed

# ${paths.data_root} will be replaced with the actual value
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
  - override /model: catboost_v1
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
- **Fix:** Ensure `conf/config.yaml` has `defaults: - model: linear`

**Error:** `ConfigCompositionException: Could not find 'model/xgboost'`
- **Fix:** Check that the config exists — the current name is `model=xgboost_v1`

**Error:** `InterpolationResolutionError: Could not resolve ${data_root}`
- **Fix:** Ensure variable is defined or use `oc.env:VAR_NAME`

**Error:** `OverrideParseException: Error parsing override 'key=value'`
- **Fix:** Check syntax - no spaces around `=`, use quotes for strings with spaces

### Debug Checklist

1. **View composed config:** `--cfg job --resolve`
2. **Check file exists:** `ls conf/model/catboost_v1.yaml`
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

_Last Updated: 2026-08-19_
_Hydra configuration system reference_
