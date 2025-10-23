# Gemini CLI Guidelines for `cfb_model`

This guide orients Gemini when working with code in this repository through the CLI. Follow these practices to stay aligned with the project's workflow and quality bar.

## Project Structure & Module Organization

- `src/cfb_model/` — production Python package; data ingestion lives in `data/`, feature pipelines in `data/aggregations/`, model code in `models/` (artifacts written to `artifacts/models/`).
- `scripts/` — CLI utilities (ingestion, caching, training).
- `tests/` — Pytest suite covering data transforms and model helpers.
- `docs/` — MkDocs site with planning (`project_org/`, `planning/`), runbooks (`operations/`), and schema references (`data/`).
- `session_logs/` — chronological handoffs; read the latest entry before starting work.
- `conf/` — Hydra configuration files for model hyperparameters and pipeline settings.
- `artifacts/` — generated outputs including MLflow runs, trained models, reports, and validation results (never committed to git).
- `notebooks/` — Jupyter notebooks for exploratory data analysis and one-off investigations.

## Build, Test, and Development Commands

### Environment Setup

```bash
# Install dependencies (include dev tools)
uv sync --extra dev

# Activate virtual environment
source .venv/bin/activate
```

### Code Quality & Testing

```bash
# Format and lint (run before commits)
uv run ruff format .
uv run ruff check .

# Run tests
uv run pytest

# Security scanning
uv run bandit -r src/
uv run safety check
```

### Data Pipeline Operations

```bash
# Complete ingestion pipeline for a full year
python scripts/run_ingestion_year.py --year 2024 --data-root /path/to/external/drive

# Individual entity ingestion (for testing or updates)
python scripts/ingest_cli.py teams --year 2024
python scripts/ingest_cli.py games --year 2024 --season-type regular

# Run aggregations pipeline (requires CFB_DATA_ROOT in .env)
python scripts/cli.py aggregate preagg --year 2024

# Rebuild key data aggregates
python -c 'from cfb_model.flows.preaggregations import preaggregations_flow as f; f(year=2024)'

# Train models
PYTHONPATH=src uv run python -m models.train_model --train-years 2019,2021,2022,2023 --test-year 2024
```

### Documentation & Monitoring

```bash
# Preview docs locally at http://127.0.0.1:8000
uv run mkdocs serve

# Launch MLflow UI at http://127.0.0.1:5000
mlflow ui --backend-store-uri file:///$(pwd)/artifacts/mlruns

# Data validation and quality checks
python scripts/check_links.py
PYTHONPATH=src uv run python -m utils.validation --year 2024 --data-type processed --deep
```

## Coding Style & Naming Conventions

- Python 3.12+, 4-space indentation, Google-style docstrings, full type hints.
- Use `ruff` for formatting, linting, and import ordering (ignore E501 already configured).
- Partitioned data uses `year=YYYY/` directories; features adopt `off_*`, `def_*`, `adj_*` prefixes.
- Prefer descriptive module and function names (`ingest_games`, `persist_team_game`).
- Use `logging` module instead of `print()` for application code.

## Testing Guidelines

- Framework: `pytest` with fixtures under `tests/`.
- Add targeted tests for new aggregation logic or CLI behaviors; synthetic DataFrames are acceptable.
- Name tests `test_<functionality>` and group by module (e.g., `test_aggregations_core.py`).
- Run `uv run pytest` before submitting a PR; aim to keep existing coverage intact.

## Commit & Pull Request Guidelines

- Commit messages follow `<type>: <description>` (e.g., `feat: add weekly cache CLI`).
- Before opening a PR: run format/lint/tests, update affected docs, and capture decisions in `docs/decisions/decision_log.md` when appropriate.
- PR description should include summary, linked issues, validation results, and any screenshots/logs relevant to UI or report output.

## Session Context & Onboarding

### Minimal Context Pack

Before starting work, review these resources in order:

**Documentation**

1. `docs/project_org/project_charter.md` — Project scope, guardrails, and success criteria
2. `docs/planning/roadmap.md` — Sprint focus and active tasks
3. `docs/decisions/decision_log.md` — Recent architecture and policy decisions
4. `docs/project_org/modeling_baseline.md` — Current ensemble configuration and training plan
5. `docs/operations/weekly_pipeline.md` — Manual weekly runbook and dependencies
6. `docs/project_org/feature_catalog.md` — Canonical feature definitions and validation patterns
7. `docs/project_org/betting_policy.md` — Risk controls, sizing rules, and thresholds
8. Latest `session_logs/<date>/<nn>.md` — Most recent session summary

**Code Anchors**

- `src/config.py` — Repository/data path resolution and shared constants
- `src/utils/local_storage.py` — Storage contract, partition naming, manifest schema
- `src/features/pipeline.py` & `src/features/persist.py` — End-to-end feature pipeline
- `src/models/train_model.py` — Ensemble training loop and MLflow integration
- `src/scripts/generate_weekly_bets_clean.py` — Weekly prediction and report writing
- `scripts/cli.py` — Typer CLI for ingestion/aggregation/season automation
- Representative tests in `tests/` (e.g., `test_aggregations_core.py`, `test_betting_policy_kelly.py`)

### Session Logs

- **Read the latest entry** to understand recent context
- **Do not create new session logs unless explicitly requested by the user**
- Session logs are for handoffs between development sessions, not routine interactions

### Session Initialization Prompt

When starting a new session, use this prompt:

```
Please review @README.md, @mkdocs.yml, @pyproject.toml, the Minimal Context Pack (docs + code anchors) listed in gemini.md, and @session_logs/** before inspecting broader @src/**, @scripts/**, and @tests/**.
```

## Data Access & Storage

### External Data Dependencies

- Production data lives on an external drive; the absolute path is defined in `.env` via `CFB_DATA_ROOT`
- Make sure that drive is mounted before running any ingestion, caching, or modeling commands
- `src/config.get_data_root()` and `LocalStorage` both rely on that environment variable
- Processed entities such as `team_game` are partitioned as `.../year=YYYY/week=WW/team=<Team Name>/data.csv`

### Data Flow Architecture

1. **Ingestion**: Raw data from CFBD API → local partitioned CSVs in `/data/raw/`
2. **Feature Engineering**: Multi-stage pipeline with opponent adjustment → `/data/processed/`
3. **Modeling**: Ridge regression and ensemble models on engineered features
4. **Betting Logic**: Edge calculation with thresholds
5. **Output**: Weekly CSV reports in `artifacts/reports/`

### Data & Modeling Rules

- **No Data Leakage**: Training data must strictly precede prediction data
- **Betting Lines**: Never use as model features, only for edge calculation
- **Minimum Games**: Teams need ≥4 games played before betting eligibility
- **Training Window**: 2014–2023 (excluding 2020). Holdout test year is 2024
- **Column Naming**: `off_*` (offense), `def_*` (defense), `adj_*` (opponent-adjusted)
- **Traceability**: Always include `season`, `week`, and `game_id` in time-based data

## MLflow Experiment Tracking

### Experiment Organization

- **Naming convention**: Use descriptive names following the pattern `model-type-target-version` (e.g., `xgboost-spread-v1`, `random-forest-total-v2`)
- **Creating experiments**:
  - Create new experiments for different model architectures or prediction targets (spread vs. total)
  - Create new runs within existing experiments for hyperparameter tuning or incremental improvements
- **Primary metric**: While various model metrics should be logged, the **primary metric to optimize is betting prediction hit rate** (percentage of correct ATS predictions)
- **Required logging**: Always log hyperparameters, evaluation metrics (RMSE, MAE, hit rate), model artifacts, and relevant tags (e.g., `train_years`, `test_year`)
- **Viewing results**: Launch the MLflow UI with `mlflow ui --backend-store-uri file:///$(pwd)/artifacts/mlruns` and navigate to `http://127.0.0.1:5000`

### Comparing Experiments

- Use the MLflow UI to compare runs across experiments
- Filter by tags and metrics to identify top-performing configurations
- Download artifacts and parameters for reproducibility

## Hydra Configuration Management

### Configuration Structure

The project uses Hydra for managing model hyperparameters and pipeline settings. Base configuration lives in `conf/config.yaml` with model-specific configs in `conf/model/`.

### Key Configuration Groups

- **model**: Model-specific hyperparameters (e.g., `spread_elastic_net`, `total_random_forest`)
- **data**: Training/test year splits, adjustment iterations, data paths
- **mlflow**: Experiment tracking settings
- **hydra/sweeper**: Hyperparameter search configuration (uses Optuna)

### Using Configurations

- **Override from command line**: `python script.py model=spread_xgboost data.test_year=2024`
- **Multirun for sweeps**: `python script.py -m model.alpha=0.1,0.5,1.0` (requires Optuna sweeper configured)
- **Access in code**: Hydra decorator `@hydra.main` automatically loads config; access via `cfg.data.train_years`

### Best Practices

- Use existing model configs as templates when adding new architectures
- Don't modify base `config.yaml` for experiments; use overrides or new model configs
- Hydra automatically logs all configs to MLflow for reproducibility

## Artifact Management

### Artifact Types and Locations

- **Models**: `artifacts/models/` — trained model binaries and metadata
- **MLflow runs**: `artifacts/mlruns/` — experiment tracking data
- **Reports**: `artifacts/reports/` — weekly predictions and scored results
- **Validation**: `artifacts/validation/` — walk-forward and other evaluation outputs
- **Hydra outputs**: `artifacts/outputs/` — run logs and sweep results

### Naming Conventions

- **Models**: `model_YYYY-MM-DD_HH-MM-SS_{model_type}_{target}.pkl`
  - Example: `model_2024-10-23_14-30-00_xgboost_spread.pkl`
- **Reports**: `weekly_predictions_YYYY_week_WW.csv`, `scored_results_YYYY_week_WW.csv`
- **Use ISO 8601 timestamps** for versioning: `YYYY-MM-DD_HH-MM-SS`

### Retention Policy

- **No formal retention policy currently established.** Artifacts accumulate over time.
- Consider periodic cleanup of old Hydra outputs and intermediate validation files.
- Keep all trained models and final reports for historical reference.

### Git Policy

- **All artifacts are gitignored.** Never commit contents of `artifacts/` directory.
- Artifact paths should be referenced via environment variables or config files.

## Notebook Guidelines

### Purpose and Scope

- **Primary use**: Exploratory data analysis (EDA) and one-off investigations
- **Not for production**: Notebook code should remain experimental; production logic belongs in `src/cfb_model/`

### Workflow

1. Create notebooks freely for exploration and analysis
2. Use notebooks to prototype new features or validate data quality
3. Extract stable, reusable logic into modules when ready for production
4. Keep notebooks as documentation of analysis decisions

### Notebook Hygiene

- **Clear outputs before committing**: Run "Restart & Clear Output" before staging changes
- **No naming convention required**: Use descriptive names that indicate purpose
- **Organize as needed**: Can group by topic/phase if collection grows large

### Transitioning to Production

- Currently no formal process for promoting notebook code to main codebase
- Extract functions and logic manually when needed
- This process may be formalized in future as the project matures

## Environment Variables

### Required Variables

The project requires several environment variables defined in a `.env` file at the repository root. **Never commit `.env` to version control.**

### Environment Variable Reference

```properties
# CFBD API access (required for data ingestion)
CFBD_API_KEY=your_api_key_here

# Data storage location (required for all operations)
CFB_DATA_ROOT=/path/to/external/drive/cfb_data

# Email notification settings (required for automated reporting)
PUBLISHER_SMTP_SERVER=smtp.example.com
PUBLISHER_SMTP_PORT=587
PUBLISHER_EMAIL_SENDER=sender@example.com
PUBLISHER_EMAIL_PASSWORD=your_email_password

# Email recipients (required for report distribution)
TEST_EMAIL_RECIPIENT=test@example.com
PROD_EMAIL_RECIPIENTS=recipient1@example.com,recipient2@example.com
```

### Setup Instructions

1. Copy the template above to a new file named `.env` in the repository root
2. Fill in actual values for all variables (no defaults provided)
3. Verify `.env` is listed in `.gitignore`
4. Ensure `CFB_DATA_ROOT` points to mounted external drive before running data operations

### Sensitive Data

- **Never commit `.env` file** or expose API keys, passwords, or email credentials
- Use environment variables for all sensitive configuration
- Consider using a password manager or secrets vault for production deployments

## Common Workflows

### Weekly Pipeline

The standard weekly workflow (detailed in `docs/operations/weekly_pipeline.md`):

1. Ingest latest games and plays data
2. Run preaggregations flow for the current year
3. Train/update model with latest features
4. Generate weekly betting recommendations
5. Validate and publish reports

### Feature Development

When adding new features:

1. Define feature logic in `src/cfb_model/data/aggregations/`
2. Update `src/cfb_model/features/pipeline.py` to include new features
3. Add tests in `tests/` covering edge cases
4. Document feature in `docs/project_org/feature_catalog.md`
5. Re-run preaggregations flow to materialize
6. Validate feature distribution and correlation with existing features

### Model Experiments

For model development and experimentation:

1. MLflow tracks all experiments in `artifacts/mlruns/`
2. Use descriptive experiment names (e.g., `xgboost-spread-v2`)
3. Log hyperparameters, metrics, and model artifacts
4. Validate on walk-forward splits before production deployment
5. Document significant model changes in `docs/decisions/decision_log.md`

### Hyperparameter Tuning

For systematic hyperparameter optimization:

1. Define parameter ranges in `conf/hydra/sweeper/params/{model_name}.yaml`
2. Run multirun sweep: `python train.py -m hydra/sweeper=optuna`
3. Monitor progress in MLflow UI
4. Select best configuration based on betting hit rate
5. Update model config with optimal parameters

## AI Development Guidelines

### Working with Gemini

- **Be Explicit**: Reference specific files and functions in requests
- **Verify Output**: Always review and validate AI-generated code. You are responsible for its quality
- **Update Documentation**: All changes to code, data, or workflow must be reflected in documentation
- **Track Decisions**: Record material changes in `docs/decisions/decision_log.md`
- **Session Logs**: Do not create new session logs unless explicitly requested

### Code Generation Standards

- All generated code must include Google-style docstrings and type hints
- Follow existing patterns and conventions in the codebase
- Run format/lint/tests before finalizing changes
- Ensure generated code respects data leakage rules and betting policies

## Troubleshooting

### Common Issues

- **Import errors**: Ensure you've run `uv sync --extra dev` and activated the venv
- **Data path errors**: Verify `CFB_DATA_ROOT` in `.env` and that external drive is mounted
- **Aggregation failures**: Check that input data exists for the specified year/week
- **Test failures**: Run `uv run ruff format . && uv run ruff check .` before tests
- **Missing partitions**: Partitioned data may not exist for all weeks; scripts should handle gracefully
- **MLflow tracking errors**: Verify `artifacts/mlruns/` directory exists and is writable
- **Hydra config errors**: Check for typos in override syntax; use `--cfg job` to print resolved config

### Getting Help

- Check existing documentation in `docs/`
- Review relevant session logs for similar issues
- Examine test cases for usage examples
- Validate environment setup matches prerequisites in README.md
- Use MLflow UI to investigate experiment failures and compare configurations

## Gemini Memory Integration

When a new session starts in the `/Users/connorkitchings/Desktop/Repositories/cfb_model` directory:

1. Load `README.md`, `mkdocs.yml`, `pyproject.toml`
2. Review the Minimal Context Pack (docs plus code anchors) listed above
3. Read the latest `session_logs/` handoff
4. Only then drill into broader `src/**`, `scripts/**`, or `tests/**`

To run Python scripts, always use: `uv run python <script_name>.py`
