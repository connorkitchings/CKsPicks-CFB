# Quick Start Commands

> **Essential commands for CFB Model development**
>
> Quick reference for common operations. Copy-paste ready.

---

## Environment Setup

### Install Dependencies

```bash
# Install all dependencies (from repo root)
uv sync --extra dev

# Activate virtual environment
source .venv/bin/activate

# Verify installation
uv pip list | grep cfb-model
```

### Environment Variables

```bash
# Required: Data root location
export CFB_MODEL_DATA_ROOT='/Volumes/CK SSD/Coding Projects/cfb_model/'

# Optional: API keys
export CFBD_API_KEY='your_api_key_here'

# Optional: MLflow tracking
export MLFLOW_TRACKING_URI='file:///path/to/mlruns'
```

**Best practice:** Add to `.env` file in repo root:

```bash
# .env file
CFB_MODEL_DATA_ROOT=/Volumes/CK SSD/Coding Projects/cfb_model/
CFBD_API_KEY=your_api_key
```

---

## Testing & Code Quality

### Run Tests

```bash
# Run all tests
uv run pytest

# Run tests quietly (summary only)
uv run pytest -q

# Run tests with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_aggregations_core.py

# Run tests matching pattern
uv run pytest -k "test_aggregate"

# Stop on first failure
uv run pytest -x
```

### Format and Lint

```bash
# Format code (automatic fixes)
uv run ruff format .

# Check linting issues
uv run ruff check .

# Fix auto-fixable linting issues
uv run ruff check . --fix

# Format + Lint together (recommended before commits)
uv run ruff format . && uv run ruff check .
```

### Pre-commit Hooks

```bash
# Install pre-commit hooks
pre-commit install

# Run hooks on all files
pre-commit run --all-files

# Update hooks to latest versions
pre-commit autoupdate
```

---

## Model Training

### Basic Training

```bash
# Train with default config
PYTHONPATH=. uv run python src/models/train_model.py

# Train with specific model
PYTHONPATH=. uv run python src/models/train_model.py model=catboost

# Train with specific feature set
PYTHONPATH=. uv run python src/models/train_model.py features=recency_v1

# Train on different test year
PYTHONPATH=. uv run python src/models/train_model.py data.test_year=2025
```

### Experiment Configs

```bash
# Run pre-configured experiment
PYTHONPATH=. uv run python src/models/train_model.py experiment=spread_catboost_baseline_v1

# Override experiment parameters
PYTHONPATH=. uv run python src/models/train_model.py \
    experiment=spread_catboost_baseline_v1 \
    data.test_year=2025
```

### Hyperparameter Optimization

```bash
# Run Optuna optimization
PYTHONPATH=. uv run python src/models/train_model.py mode=optimize

# Optimize specific model
PYTHONPATH=. uv run python src/models/train_model.py \
    mode=optimize \
    model=catboost \
    tuning=catboost_optuna

# Optimize with custom trials
PYTHONPATH=. uv run python src/models/train_model.py \
    mode=optimize \
    optuna.n_trials=100
```

### Debug Configuration

```bash
# See composed config (before running)
PYTHONPATH=. uv run python src/models/train_model.py --cfg job

# See config with interpolations resolved
PYTHONPATH=. uv run python src/models/train_model.py --cfg job --resolve

# Validate config only (no training)
PYTHONPATH=. uv run python src/models/train_model.py --help
```

---

## Production Pipeline

### Training Pipeline

```bash
# Train production points-for models
PYTHONPATH=. uv run python scripts/pipeline/train_production_points_for.py

# Train with specific config
PYTHONPATH=. uv run python scripts/pipeline/train_production_points_for.py \
    --config conf/production/points_for_v1.yaml
```

### Weekly Predictions

```bash
# Generate predictions for upcoming week
PYTHONPATH=. uv run python scripts/pipeline/generate_weekly_bets.py

# Generate for specific week
PYTHONPATH=. uv run python scripts/pipeline/generate_weekly_bets.py \
    --season 2024 \
    --week 12

# Generate with custom threshold
PYTHONPATH=. uv run python scripts/pipeline/generate_weekly_bets.py \
    --min-edge 0.03
```

### Performance Scoring

```bash
# Score all bets for a week
PYTHONPATH=. uv run python scripts/pipeline/score_weekly_bets.py \
    --season 2024 \
    --week 12

# Generate performance report
PYTHONPATH=. uv run python scripts/analysis/generate_performance_report.py \
    --season 2024
```

---

## Data Management

### Ingestion

```bash
# Ingest plays for specific week
PYTHONPATH=. uv run python scripts/data/ingest_plays.py \
    --year 2024 \
    --week 12

# Ingest all data for a season
PYTHONPATH=. uv run python scripts/data/ingest_season.py \
    --year 2024

# Cache running season stats
PYTHONPATH=. uv run python scripts/pipeline/cache_running_season_stats.py
```

### Feature Generation

```bash
# Generate features for specific week
PYTHONPATH=. uv run python scripts/features/generate_weekly_features.py \
    --year 2024 \
    --week 12

# Regenerate all features with new adjustment
PYTHONPATH=. uv run python scripts/features/regenerate_features.py \
    --adjustment-iteration 4
```

---

## MLflow

### Start MLflow UI

```bash
# Start MLflow server (Docker)
MLFLOW_PORT=5050 docker compose -f docker/mlops/docker-compose.yml up mlflow

# Access at http://localhost:5050

# Start MLflow UI (local, no Docker)
mlflow ui --backend-store-uri file:///path/to/mlruns --port 5050
```

### Model Registry

```bash
# List registered models
mlflow models list

# Get model details
mlflow models get-model-versions --name "home_points_catboost"

# Promote model to staging
mlflow models update-model-version \
    --name "home_points_catboost" \
    --version 1 \
    --stage Staging

# Promote to production
mlflow models update-model-version \
    --name "home_points_catboost" \
    --version 1 \
    --stage Production
```

---

## Dashboard

### Local Development

```bash
# Run dashboard (Docker)
cd dashboard
docker compose up

# Access at http://localhost:8501

# Run dashboard (local Streamlit)
cd dashboard
streamlit run app.py
```

---

## Git Workflows

### Branch Management

```bash
# Create feature branch
git checkout -b feature/your-feature-name

# Create fix branch
git checkout -b fix/issue-description

# Create experiment branch
git checkout -b experiment/model-name

# Switch back to main
git checkout main

# Delete merged branch
git branch -d feature/your-feature-name
```

### Commits

```bash
# Stage specific files
git add src/models/train_model.py tests/test_models.py

# Stage all changes
git add -A

# Commit with message
git commit -m "feat: Add new feature X

- Implemented feature computation
- Added unit tests
- Updated documentation

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

# Amend last commit (if needed)
git commit --amend
```

### Syncing

```bash
# Pull latest changes
git pull origin main

# Push feature branch
git push -u origin feature/your-feature-name

# Force push (use carefully!)
git push --force-with-lease origin feature/your-feature-name
```

---

## Debugging

### Python Debugging

```bash
# Run script with debugger
python -m pdb src/models/train_model.py

# Run pytest with debugger (drops into pdb on failure)
uv run pytest --pdb

# Run pytest with print statements visible
uv run pytest -s
```

### Data Inspection

```bash
# Check data root
ls -lh "$CFB_MODEL_DATA_ROOT"

# Check specific year/week data
ls -lh "$CFB_MODEL_DATA_ROOT/raw/plays/year=2024/week=12/"

# View parquet file schema
python -c "import pandas as pd; print(pd.read_parquet('$CFB_MODEL_DATA_ROOT/raw/plays/year=2024/week=12/data.parquet').dtypes)"

# Quick row count
python -c "import pandas as pd; print(len(pd.read_parquet('$CFB_MODEL_DATA_ROOT/raw/plays/year=2024/week=12/data.parquet')))"
```

### Environment Debugging

```bash
# Check Python version
python --version

# Check uv version
uv --version

# Verify packages installed
uv pip list

# Check environment variables
env | grep CFB

# Verify PYTHONPATH
echo $PYTHONPATH
```

---

## Documentation

### Build Docs

```bash
# Build MkDocs documentation
mkdocs build

# Build with strict mode (fail on warnings)
mkdocs build --strict

# Serve docs locally
mkdocs serve

# Access at http://localhost:8000
```

### Generate API Docs

```bash
# Generate API documentation
mkdocs build --strict

# Deploy docs to GitHub Pages
mkdocs gh-deploy
```

---

## Analysis & Experiments

### Feature Importance

```bash
# Run SHAP analysis
PYTHONPATH=. uv run python scripts/analysis/run_shap_analysis.py \
    --model-path artifacts/models/home_points_catboost.joblib

# Generate feature importance plot
PYTHONPATH=. uv run python scripts/analysis/plot_feature_importance.py \
    --run-id abc123
```

### Model Comparison

```bash
# Compare multiple models
PYTHONPATH=. uv run python scripts/analysis/compare_models.py \
    --run-ids abc123,def456,ghi789

# Generate comparison report
PYTHONPATH=. uv run python scripts/analysis/generate_comparison_report.py \
    --season 2024
```

### Calibration Analysis

```bash
# Analyze model calibration
PYTHONPATH=. uv run python scripts/analysis/analyze_calibration.py \
    --model-path artifacts/models/home_points_catboost.joblib

# Plot calibration curves
PYTHONPATH=. uv run python scripts/analysis/plot_calibration.py \
    --run-id abc123
```

---

## Utilities

### Clean Up

```bash
# Remove Python cache files
find . -type d -name "__pycache__" -exec rm -r {} +

# Remove pytest cache
rm -rf .pytest_cache

# Remove Hydra outputs
rm -rf artifacts/hydra_outputs/

# Clean all build artifacts
rm -rf build/ dist/ *.egg-info/
```

### Dependency Management

```bash
# Update all dependencies
uv sync --upgrade

# Add new dependency
uv add package-name

# Add dev dependency
uv add --dev package-name

# Remove dependency
uv remove package-name

# Export requirements
uv pip freeze > requirements.txt
```

---

## Common Command Chains

### Full Quality Check

```bash
# Format, lint, test (run before every commit)
uv run ruff format . && \
uv run ruff check . && \
uv run pytest -q
```

### Training + Evaluation

```bash
# Train model and generate predictions
PYTHONPATH=. uv run python src/models/train_model.py \
    experiment=spread_catboost_baseline_v1 && \
PYTHONPATH=. uv run python scripts/pipeline/generate_weekly_bets.py
```

### Weekly Production Pipeline

```bash
# Complete weekly workflow
PYTHONPATH=. uv run python scripts/pipeline/cache_running_season_stats.py && \
PYTHONPATH=. uv run python scripts/pipeline/generate_weekly_bets.py && \
PYTHONPATH=. uv run python scripts/pipeline/publish_picks.py
```

---

## Keyboard Shortcuts (IDE)

### VSCode

- `Cmd+Shift+P` - Command palette
- `Cmd+P` - Quick open file
- `Cmd+Shift+F` - Search in files
- `Cmd+B` - Toggle sidebar
- `Cmd+J` - Toggle terminal
- `F5` - Start debugging
- `Shift+F5` - Stop debugging

### Cursor / Claude Code

- `Cmd+K` - Ask Claude
- `Cmd+L` - Continue conversation
- `Cmd+Shift+E` - Open files

---

_Last Updated: 2026-02-13_
_Quick command reference for CFB Model_
