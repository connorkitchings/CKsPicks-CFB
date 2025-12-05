# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🚨 CRITICAL: External Data Root Configuration 🚨

### THE MOST COMMON MISTAKE

**The data does NOT live in the project directory!**

All raw and processed data resides on an external hard drive. The path is configured via environment variable:

```bash
CFB_MODEL_DATA_ROOT='/Volumes/CK SSD/Coding Projects/cfb_model/'
```

### Before ANY Data Operation

**ALWAYS verify these three things:**

1. ✅ `CFB_MODEL_DATA_ROOT` environment variable is set
2. ✅ The external drive is mounted and accessible
3. ✅ You're reading from/writing to the external path, NOT `./data/` in project root

### Quick Validation

```python
import os
from pathlib import Path

# This should print the external drive path
data_root = os.getenv("CFB_MODEL_DATA_ROOT")
if not data_root or not Path(data_root).exists():
    raise ValueError(f"Data root not accessible: {data_root}")
print(f"✅ Data root verified: {data_root}")
```

### If You See `./data/` Being Created

**STOP IMMEDIATELY!** The script is misconfigured. Always load `CFB_MODEL_DATA_ROOT` from environment and fail loudly if not set.

---

## Session Management

### Starting a New Session

When beginning work in this repository:

1. **Read this file first** (CLAUDE.md)
2. **Verify data root configuration** as shown above
3. **Review recent session logs** (`session_logs/` last 3 days)
4. **Propose a plan** before any implementation
5. **Wait for approval** before executing

### Recommended First Prompt

```
Review CLAUDE.md first, especially the external data root configuration.
Review the last 3 session logs to understand recent work.
Then propose a clear plan for [TASK] before implementing anything.
```

### Ending a Session

When code or docs have changed:

1. ✅ Create/update session log in `session_logs/YYYY-MM-DD/NN.md`
2. ✅ Run health checks: `uv run ruff format . && uv run ruff check .`
3. ✅ Run tests if relevant: `uv run pytest -q`
4. ✅ Propose commit message for user to execute manually
5. ✅ Update relevant docs if behavior changed

**Template for session logs:**
```markdown
# TL;DR (≤5 lines)
- Attempted: [what was tried]
- Outcome: [what happened]
- Blockers/IDs: [any issues, MLflow run IDs]
- Next actions: [what's next]
- Owner/date: [your name, date]

**tags:** ["modeling", "features", "pipeline", etc.]
```

---

## Project Overview

This is a college football betting model system that predicts point spreads and over/unders using machine learning. The project uses a **points-for approach** (predicting home and away scores separately) and follows a weekly update pipeline for generating betting recommendations.

**Key Technologies:**
- Python 3.12+ with `uv` for dependency management
- Hydra for configuration management
- Optuna for hyperparameter optimization
- MLflow for experiment tracking and model registry
- CatBoost/XGBoost for modeling
- Parquet for data storage on external drive

---

## Essential Commands

### Environment Setup
```bash
# Install dependencies (from repo root)
uv sync --extra dev

# Activate virtual environment
source .venv/bin/activate
```

### Testing and Linting
```bash
# Run all tests
uv run pytest

# Run tests quietly
uv run pytest -q

# Run specific test file
uv run pytest tests/test_aggregations_core.py

# Format and lint together (recommended before commits)
uv run ruff format . && uv run ruff check .
```

### Model Training

All training commands should be run from repo root with `PYTHONPATH=.`:

```bash
# Basic training with defaults
PYTHONPATH=. uv run python src/models/train_model.py

# Run specific experiment config
PYTHONPATH=. uv run python src/models/train_model.py experiment=spread_catboost_baseline_v1

# Hyperparameter optimization
PYTHONPATH=. uv run python src/models/train_model.py mode=optimize

# Override specific configs
PYTHONPATH=. uv run python src/models/train_model.py model=catboost data.test_year=2025

# Debug configuration (see composed config without running)
PYTHONPATH=. uv run python src/models/train_model.py --cfg job --resolve
```

### Production Pipeline
```bash
# Train production points-for models
PYTHONPATH=. uv run python scripts/pipeline/train_production_points_for.py

# Generate weekly bets
PYTHONPATH=. uv run python scripts/pipeline/generate_weekly_bets.py

# Score bet performance
PYTHONPATH=. uv run python scripts/pipeline/score_weekly_bets.py
```

### MLflow Tracking
```bash
# Start MLflow UI (Docker)
MLFLOW_PORT=5050 docker compose -f docker/mlops/docker-compose.yml up mlflow

# Access at http://localhost:5050
# Backed by artifacts/mlruns/ directory
```

### Dashboard
```bash
# Run monitoring dashboard
cd dashboard
docker compose up
```

---

## Architecture Overview

### Data Pipeline Flow

The system follows a hierarchical aggregation pipeline:

1. **Raw Ingestion** (`src/data/`): Fetch data from CollegeFootballData.com API
   - `ingest_api.py`: Core API client
   - `plays.py`, `games.py`, `teams.py`, etc.: Domain-specific loaders
   - Data stored as Parquet files under `CFB_MODEL_DATA_ROOT` (external drive)

2. **Aggregation** (`src/features/pipeline.py`):
   - Plays → `byplay` (play-level features)
   - Byplay → `drives` (drive-level aggregations)
   - Drives → `team_game` (game-level team stats)
   - Team-game → `team_season` (season-level metrics)

3. **Feature Engineering** (`src/features/`):
   - `core.py`: Core aggregation functions
   - `byplay.py`: Play-level transformations
   - `weather.py`: Weather feature integration
   - `selector.py`: Feature selection by configuration
   - `persist.py`: Caching and persistence layer

4. **Modeling** (`src/models/`):
   - `train_model.py`: Main training script (Hydra-integrated)
   - `features.py`: Feature loading and point-in-time data slicing
   - `betting.py`: Bet generation and sizing logic
   - `calibration.py`: Model calibration utilities
   - `ensemble.py`: Ensemble model management

### Points-For Modeling Approach

Unlike traditional spread models, this system predicts:
1. **Home team points**
2. **Away team points**

Then derives spreads and totals from those predictions:
- `predicted_spread = home_points - away_points`
- `predicted_total = home_points + away_points`

This approach provides more flexibility and better captures asymmetric team matchups.

**Current Production Models (as of Nov 2024):**
- Spreads: CatBoost with recency features
- Totals: XGBoost optimized via Optuna

### Feature Engineering Principles

**Opponent Adjustment:**
The system uses iterative opponent adjustment to normalize raw stats. The `adjustment_iteration` parameter controls how many rounds of adjustment are applied (typically 2-4).

**Feature Categories:**
- Offensive efficiency (yards/play, success rate, explosiveness)
- Defensive efficiency (same metrics, from defense perspective)
- Situational performance (red zone, third down, etc.)
- Pace metrics (plays per game, seconds per play)
- Recency-weighted stats (last 3-4 games weighted higher)
- Weather features (temperature, wind, precipitation for outdoor games)
- Mismatch features (offense vs defense interactions)

**Feature Naming Convention:**
- `home_off_*`: Home team offensive stats
- `home_def_*`: Home team defensive stats
- `away_off_*`: Away team offensive stats
- `away_def_*`: Away team defensive stats

Features are selected via `conf/features/` configs, which define feature groups and allow-lists.

---

## Configuration System (Hydra)

Configs live in `conf/` with a hierarchical structure:

```
conf/
├── config.yaml              # Top-level defaults
├── model/                   # Model-specific configs
├── features/                # Feature set definitions
├── experiment/              # Pre-packaged experiments
├── tuning/                  # Optuna search spaces
├── paths/                   # Data path overrides
└── weekly_bets/            # Betting policy configs
```

### Key Config Patterns

```yaml
# conf/config.yaml - Main entry point
defaults:
  - _self_
  - paths: default
  - model: catboost
  - features: standard_v1
  - experiment: null

data:
  adjustment_iteration: 2  # Opponent adjustment depth
  train_years: [2019, 2021, 2022, 2023]
  test_year: 2024
```

### Override Patterns

- `model=xgboost`: Switch model type
- `data.test_year=2025`: Change test year
- `experiment=spread_catboost_baseline_v1`: Load full experiment config
- `+new_param=value`: Add new parameter
- `~old_param`: Delete parameter
- `model.params.depth=8`: Override nested parameter

### Debugging Configs

```bash
# See composed config before running
PYTHONPATH=. uv run python src/models/train_model.py --cfg job

# See with interpolations resolved
PYTHONPATH=. uv run python src/models/train_model.py --cfg job --resolve
```

---

## Data Storage

### Environment Variable Required

Set `CFB_MODEL_DATA_ROOT` in `.env` to point to your external data directory. All data is stored as Parquet files under this root.

### Directory Structure

```
$CFB_MODEL_DATA_ROOT/  (external drive)
├── raw/                    # Raw API responses
│   ├── plays/
│   ├── games/
│   └── teams/
├── aggregated/             # Aggregated data products
│   ├── byplay/
│   ├── drives/
│   ├── team_game/
│   └── team_season/
├── features/               # Feature caches (by adjustment iteration)
│   ├── adj_iter_2/
│   ├── adj_iter_4/
│   └── weekly_features/
└── betting_lines/          # Market lines and results
```

### Common Data Paths

Based on `CFB_MODEL_DATA_ROOT='/Volumes/CK SSD/Coding Projects/cfb_model/'`:

- Raw plays: `/Volumes/CK SSD/Coding Projects/cfb_model/raw/plays/year=YYYY/week=WW/`
- Processed features: `/Volumes/CK SSD/Coding Projects/cfb_model/processed/team_week_adj/iteration=N/year=YYYY/week=WW/`
- Games: `/Volumes/CK SSD/Coding Projects/cfb_model/raw/games/year=YYYY/`

### Correct Data Path Usage Example

```python
import os
from pathlib import Path
import pandas as pd

# ✅ CORRECT: Load from environment
data_root = Path(os.getenv("CFB_MODEL_DATA_ROOT"))
if not data_root.exists():
    raise ValueError(f"Data root not found: {data_root}")

# ✅ CORRECT: Build paths from root
plays_path = data_root / "raw/plays/year=2024/week=12/data.parquet"
features_path = data_root / "processed/team_week_adj/iteration=4/year=2024/week=12/data.parquet"

# ❌ WRONG: Hardcoded or relative paths
plays_path = "./data/raw/plays/2024/12/data.parquet"  # NO!
plays_path = "/Volumes/CK SSD/..."  # NO! (hardcoded)
```

### Other Environment Variables

- `CFBD_API_KEY`: CollegeFootballData.com API key (required for ingestion)
- `MLFLOW_TRACKING_URI`: Override MLflow tracking location (optional)

---

## Development Guidelines

### Testing Requirements
- All new aggregation functions must have unit tests
- Use minimal fixtures (see `tests/test_aggregate_drives_minimal.py`)
- Test edge cases: empty DataFrames, missing columns, single-row inputs

### Code Style
- Format with `ruff format .` before committing
- Fix linting issues with `ruff check .`
- Line length: 88 characters (Black-compatible)
- Type hints encouraged but not required

### Data & Modeling Guardrails

**Storage Location:**
- All raw and processed data resides on external drive at `CFB_MODEL_DATA_ROOT`
- Validate this path exists before any I/O operation
- Never create `./data/` in project root

**Data Leakage Prevention:**
- Training strictly precedes prediction
- No target-aware transforms on full dataset
- Use `load_point_in_time_data()` to avoid future data leakage

**Training Windows:**
- Train: 2019, 2021-2023 (skip 2020 COVID year)
- Holdout: 2024
- Minimum games: 4 games required for adjusted stats & betting eligibility

**Column Conventions:**
- Maintain: `season`, `week`, `game_id`, `team` keys
- Prefix: `off_*`, `def_*`, `adj_*` consistently
- No bookmaker-derived features in model inputs (only in post-model edge calc)

### Feature Engineering
- Always provide opponent-adjusted versions of raw stats
- Use explicit feature allow-lists in `conf/features/` configs
- Document new feature groups in feature configs
- Avoid accidental feature creep by using selector safety checks
- Update `docs/modeling/features.md` when adding features

### Model Development
- Use Hydra configs for all experiments (no hardcoded parameters)
- Log all runs to MLflow with tags: `git_sha`, `model_type`, `feature_set`
- Generate unique model IDs: `{model_type}_{feature_set}_{tuning}_{data_version}`
- Register production models to MLflow Model Registry
- Test on walk-forward validation before production deployment
- Always report baseline comparisons

### Betting Policy
- Policy is defined in `docs/modeling/betting_policy.md`
- **Never modify** policy programmatically
- Only apply existing rules, return reason codes for violations
- Use Kelly Criterion for bet sizing
- Respect minimum edge thresholds
- Track actual vs predicted performance

### Documentation Discipline
- Update session logs under `session_logs/YYYY-MM-DD/NN.md` for any code changes
- Decision logs go in `docs/decisions/decision_log.md`
- Keep README.md in sync with major changes
- Update docs with minimal, targeted diffs (no aspirational content)

---

## Scripts Organization

Scripts are organized by purpose under `scripts/`:

### Pipeline (`scripts/pipeline/`)
Production pipeline scripts:
- `train_production_points_for.py`: Main production training
- `generate_weekly_bets.py`: Generate bet recommendations
- `score_weekly_bets.py`: Evaluate bet performance
- `cache_weekly_stats.py`: Cache feature computations

### Analysis (`scripts/analysis/`)
Analysis and validation tools:
- `compare_models.py`: Model comparison reports
- `run_shap_analysis.py`: Feature importance analysis
- `analyze_calibration.py`: Calibration diagnostics
- `simulate_bankroll_2024.py`: Bankroll simulation

### Experiments (`scripts/experiments/`)
Research and optimization:
- `optimize_hyperparameters.py`: Optuna sweeps
- `run_points_for_experiment.py`: Points-for experiments
- `run_feature_selection.py`: Feature selection studies

### Debug (`scripts/debug/`)
Debugging utilities:
- `debug_features.py`: Feature pipeline debugging
- `inspect_model.py`: Model inspection
- `list_models.py`: List registered models
- `check_data_columns.py`: Verify data schema

### Utils (`scripts/utils/`)
Helper utilities:
- `model_registry.py`: Model registration helpers
- `init_session.py`: Session initialization

### Ratings (`scripts/ratings/`)
Probabilistic power ratings (research phase):
- `train_ppr.py`: Train power ratings
- `backtest_ppr.py`: Backtest ratings

---

## Common Workflows

### Adding a New Model Type

1. Create model config in `conf/model/new_model.yaml`
2. Create Optuna search space in `conf/tuning/new_model_optuna.yaml`
3. Add model instantiation logic if needed
4. Run experiment:
   ```bash
   PYTHONPATH=. uv run python src/models/train_model.py model=new_model mode=optimize
   ```
5. Document findings in decision log

### Adding New Features

1. Add feature computation to `src/features/core.py` or `byplay.py`
2. Create feature config in `conf/features/new_feature_v1.yaml`
3. Add unit tests for feature generation
4. Run ablation study to validate feature impact
5. Update feature catalog documentation

### Weekly Production Pipeline

1. Ingest latest week data: `scripts/pipeline/cache_running_season_stats.py`
2. Generate predictions: `scripts/pipeline/generate_weekly_bets.py`
3. Publish picks: `scripts/pipeline/publish_picks.py`
4. After games: Score bets with `scripts/pipeline/score_weekly_bets.py`
5. Review performance in dashboard

### Debugging Data Issues

1. Verify external drive mounted and accessible
2. Check `CFB_MODEL_DATA_ROOT` environment variable is set
3. Check column presence: `scripts/debug/check_data_columns.py`
4. Verify aggregations: `scripts/debug/verify_stats.py`
5. Debug feature pipeline: `scripts/debug/debug_feature_pipeline.py`
6. Profile feature cache: `scripts/debug/profile_feature_cache.py`

---

## Common Pitfalls & Solutions

### 1. Creating Local Data Directory

**Problem**: Script creates `./data/` folder in project root
**Solution**: Load `CFB_MODEL_DATA_ROOT` from env; fail loudly if not set
**Check**: Add validation at script start

### 2. Forgetting Cached Features

**Problem**: Regenerating features that are already cached
**Solution**: Use `processed/team_week_adj/iteration=4/` cache first
**Check**: Profile script to see if unnecessary recomputation

### 3. Hardcoded Paths

**Problem**: Using `/Users/...` or `./data/` hardcoded paths
**Solution**: Always use `os.getenv("CFB_MODEL_DATA_ROOT")` or `src.config`
**Check**: Search codebase for hardcoded paths before committing

### 4. Skipping Environment Check

**Problem**: Script fails silently when drive isn't mounted
**Solution**: Add explicit validation at script start
**Pattern**: See "Quick Validation" section above

### 5. Training on 2020 Data

**Problem**: Including COVID-disrupted 2020 season
**Solution**: Use `train_years: [2019, 2021, 2022, 2023]` pattern
**Check**: Verify year lists in configs

### 6. Future Data Leakage

**Problem**: Using future data in historical analysis
**Solution**: Use `load_point_in_time_data()` for strict temporal splits
**Check**: Validate training data doesn't include test period

### 7. Modifying Betting Policy in Code

**Problem**: Changing unit sizing or exposure rules programmatically
**Solution**: Only read and apply policy, never modify
**Check**: Betting logic should only implement, not define policy

---

## MLflow Integration

All training runs are automatically tracked in MLflow:

- **Tracking**: `artifacts/mlruns/` (file-based backend)
- **Artifacts**: Models, feature lists, and predictions
- **Metrics**: RMSE, MAE, calibration metrics, betting performance
- **Parameters**: All Hydra config values logged automatically
- **Tags**: `git_sha`, `model_type`, `feature_set`, experiment info

### Model Registry Stages

Models can be promoted through stages:
1. None → Development
2. Development → Staging
3. Staging → Production

Use `src/utils/model_registry.py` utilities for model registration.

### Model ID Convention

Production models follow naming convention:
```
{target}_{model_type}_{feature_set}_{tuning_method}_{data_version}
```

Example: `home_points_catboost_standard_v1_optuna_2024_adj2`

---

## Project-Specific Details

### Year 2020 is Excluded
COVID-affected 2020 season is typically excluded from training sets due to schedule disruptions.

### Adjustment Iterations
The system supports different adjustment depths for offense and defense:
- `adjustment_iteration`: Default for both
- `adjustment_iteration_offense`: Override for offense
- `adjustment_iteration_defense`: Override for defense

Typical value is 2-4 iterations.

### Hydra Output Directories
Hydra outputs go to `artifacts/hydra_outputs/` by default. Each run gets a timestamped subdirectory. The `.hydra/` subfolder contains composed configs for reproducibility.

### Feature Set IDs
Feature sets have semantic IDs like `standard_v1`, `recency_v1`, `pace_v1`. These are composed via Hydra defaults. Pruned variants (e.g., `spread_shap_pruned`) exist for performance-optimized models.

### Dashboard and Monitoring
A Flask-based dashboard (`dashboard/app.py`) provides monitoring and visualization. It's containerized and can be run via `docker compose` in the dashboard directory.

---

## Troubleshooting

**Import Errors:**
Ensure you run scripts with `PYTHONPATH=.` from repo root, or activate the venv with `source .venv/bin/activate`.

**Missing Data / Path Errors:**
1. Check `CFB_MODEL_DATA_ROOT` environment variable is set
2. Verify external drive is mounted
3. Confirm path exists: `ls "$CFB_MODEL_DATA_ROOT"`
4. Check script uses environment variable, not hardcoded paths

**Hydra Config Errors:**
Use `--cfg job --resolve` flag to debug composed configuration:
```bash
PYTHONPATH=. uv run python src/models/train_model.py --cfg job --resolve
```

**MLflow Tracking Issues:**
1. Ensure `artifacts/mlruns/` directory exists and is writable
2. Start MLflow UI with Docker compose
3. Check `MLFLOW_TRACKING_URI` if using custom location

**Test Failures:**
Run `uv run pytest -v` for verbose output. Check that test data fixtures are valid and match expected schemas.

**Ruff Formatting Issues:**
If ruff fails, ensure you're using the version specified in `pyproject.toml`. Run `uv sync` to update dependencies.

**External Drive Not Accessible:**
1. Verify drive is mounted: `ls /Volumes/`
2. Check drive name matches `CFB_MODEL_DATA_ROOT`
3. Remount if necessary
4. Update `.env` if drive path changed

---

## Quick Reference: Key Files

### Must Read First
- `CLAUDE.md` (this file) - Start here for every session
- `README.md` - Project overview and setup
- `.env` - Environment configuration (set `CFB_MODEL_DATA_ROOT` here)

### Configuration
- `conf/config.yaml` - Main Hydra config
- `conf/model/` - Model configurations
- `conf/features/` - Feature set definitions
- `conf/experiment/` - Pre-configured experiments

### Core Code Anchors
- `src/config.py` - Path configuration and constants
- `src/features/pipeline.py` - Feature engineering pipeline
- `src/models/train_model.py` - Main training script
- `scripts/pipeline/generate_weekly_bets.py` - Prediction generation

### Documentation (Read on Demand)
- `docs/guide.md` - Documentation hub (start here!)
- `docs/modeling/features.md` - Feature definitions
- `docs/modeling/betting_policy.md` - Unit sizing rules
- `docs/decisions/decision_log.md` - Decision history
- `docs/ops/weekly_pipeline.md` - Production workflow

### Testing
- `tests/test_*.py` - Test suite with usage examples
- `pyproject.toml` - Dependencies and tool config

---

## Context Management (for AI Assistants)

When working on tasks in this repository:

### Context Budget
- Per-task context budget: ≤ 50k tokens overall, prefer ≤ 10k
- Default read order: CLAUDE.md → README.md → pyproject.toml → last 3 days session logs → code anchors on demand

### What NOT to Read Automatically
- `artifacts/**`, `.venv/**`, `.git/**`, `**__pycache__/`
- `notebooks/**` (only when debugging exploration outcomes)
- `session_logs/` older than 3 days
- Files > 200 KB
- Files unchanged in last 30 days (use `git diff --name-only --since=30.days`)

### Load Code on Demand
Only open source files when actively working on them. Use section gating for docs (read headers/summaries, skip large tables unless needed).

---

_Last Updated: 2025-12-02_
_This file consolidates guidance from gemini.md and AGENTS.md for universal AI assistant use_
