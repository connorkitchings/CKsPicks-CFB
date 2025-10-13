# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Essential Development Commands

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

# Data validation and quality checks
python scripts/check_links.py  # Verify documentation links
# TODO: Add data validation scripts for pipeline testing
```

### Data Pipeline Operations

```bash
# Complete ingestion pipeline for a full year (placeholder; wire your ingestion CLI here)
# python scripts/run_ingestion_year.py --year 2024 --data-root /path/to/external/drive

# Individual entity ingestion (for testing or updates)
# python scripts/ingest_cli.py teams --year 2024
# python scripts/ingest_cli.py games --year 2024 --season-type regular
# python scripts/ingest_cli.py plays --year 2024 --limit-games 5
# python scripts/ingest_cli.py betting_lines --year 2024 --limit-games 10

# Run aggregations pipeline (requires CFB_MODEL_DATA_ROOT in .env)
python -c 'from cfb_model.flows.preaggregations import preaggregations_flow as f; f(year=2024)'
# Byplay-only utility
python -c 'from cfb_model.data.aggregations.persist import persist_byplay_only as f; f(year=2024)'

# Train models (baseline and ensemble)
python src/cfb_model/models/train_model.py --train-years 2019,2021,2022,2023 --test-year 2024

```

### Documentation

```bash
# Serve documentation locally
uv run mkdocs serve
# Access at http://127.0.0.1:8000
```

## Project Architecture

### Core Structure

The project follows a clear separation between data ingestion, processing, modeling, and deployment:

- **`src/cfb_model/data/`**: Data ingestion and storage abstraction layer
  - `ingestion/`: API clients for CollegeFootballData.com (teams, games, plays, betting lines, etc.)
  - `storage/`: Local CSV storage backend with partitioned datasets
  - `aggregations/`: Feature engineering pipeline (plays → drives → games → season aggregates)

- **`src/cfb_model/models/`**: ML modeling components
  - `ridge_baseline/`: MVP Ridge regression model for spread/total prediction
  - `train_model.py`: Model training orchestration

- **`src/cfb_model/flows/`**: Prefect workflow orchestration
- **`src/cfb_model/utils/`**: Shared utilities (logging, MLflow tracking, lineage)
- **`scripts/`**: CLI entry points for data operations

### Data Flow Architecture

1. **Ingestion**: Raw data from CollegeFootballData.com API → local CSV storage (partitioned by year/week/game_id)
2. **Feature Engineering**: Multi-stage pipeline with opponent adjustment via iterative averaging
3. **Modeling**: Ridge regression on engineered features with season-silo training
- **Betting Logic**: Edge calculation (|model - line|) with thresholds (spreads ≥6.0, totals ≥6.0)
5. **Output**: Weekly CSV reports with betting recommendations

### Key Data Transformations

- **Play-level canonicalization**: Success rate calculation, explosive play detection, garbage time filtering
- **Drive segmentation**: Possession-aware aggregation with Eckel drive metrics
- **Opponent adjustment**: 4-iteration algorithm with recency weighting (last 3 games: 3x, 2x, 1x weights)
- **Season-to-date features**: Weighted aggregation excluding current game to prevent data leakage

## Development Standards

### Data Handling Rules

- **No Data Leakage**: Training data must strictly precede prediction data
- **Betting Lines**: Never use as model features, only for edge calculation
- **Minimum Games**: Teams need ≥4 games played before betting eligibility
- **Data Storage**: Raw data in `/data/raw/` (immutable), processed in `/data/processed/`
- **Environment Variable**: `CFB_MODEL_DATA_ROOT` defines data storage location
- **Partitioning Strategy**: Plays partitioned by `year/week/game_id`, other entities by `year`
- **Storage Format**: CSV with JSON manifests for metadata and validation
- **Idempotent Operations**: All ingestion supports overwrite mode for reproducibility

### Feature Engineering Conventions

- **Naming**: `off_*` (offensive), `def_*` (defensive), `adj_*` (opponent-adjusted)
- **Required Fields**: Always include `season`, `week`, `game_id` for traceability
- **Aggregation Validation**: Include counts of underlying data for validation

### Code Quality Requirements

- **Python 3.12+** with type hints and Google-style docstrings
- **Ruff** for formatting and linting
- **Logging**: Use `logging` module, avoid `print()` in application code
- **Testing**: Pytest for all new functionality
- **Documentation**: Keep data dictionary and decision log current

### Model Training & Validation

- **Training Window**: 2019–2023 (excluding 2020 COVID season)
- **Test Year**: 2024 holdout
- **Baseline Comparison**: All models compared against Ridge regression baseline
- **Artifacts**: Models saved to `models/<model_name>/<test_year>/`
- **Metrics**: Evaluation reports in `reports/metrics/`

## Session Context Requirements

### Minimal Context Pack (start each session)

### AI Session Kickoff

To begin a development session, please provide the following prompt to ensure the AI has full project context:

```
Please review @README.md , @mkdocs.yml , @pyproject.toml , @docs/** , and @session_logs/** to get up to speed on the project. Then review the codebase in @src/** , @scripts/** , and @tests/**
```


Essential documents to review before making changes:

1. `docs/project_org/project_charter.md` - Project scope and technical goals
2. `docs/project_org/feature_catalog.md` - Complete feature definitions and validation rules
3. `docs/operations/weekly_pipeline.md` - Production pipeline runbook
4. `docs/project_org/modeling_baseline.md` - MVP model specifications
5. `docs/decisions/decision_log.md` - Architectural decisions to date

### Full Context Pack

For a comprehensive understanding of the project, review the following:

* `README.md`
* `mkdocs.yml`
* `pyproject.toml`
* `docs/**`
* `src/**`
* `scripts/**`
* `tests/**`

### Current Status Check

- Review latest session log in `session_logs/` for recent work
- Check `docs/planning/roadmap.md` for active sprint goals
- Reference `docs/project_org/checklists.md` for quality gates

## Key File Locations

### Configuration

- `.env`: API keys and environment variables
- `pyproject.toml`: Dependencies and project metadata
- `prefect.yaml`: Workflow orchestration configuration

### Data Schemas

- `docs/data/raw_api/`: CFBD API response schemas
- `docs/data/transformed/`: Processed data schemas
- Feature definitions comprehensively documented in `docs/project_org/feature_catalog.md`

### Quality Assurance

- Pre-commit checklist in `docs/project_org/checklists.md`
- Code review standards in `docs/project_org/development_standards.md`
- Security review requirements for authentication and data handling

## Betting Policy & Risk Management

### Core Betting Rules

- **Edge Thresholds**: Spreads ≥6.0 points, totals ≥6.0 points (configurable via CLI)
- **Team Requirements**: Both teams must have ≥4 games played
- **Unit Sizing**: 2% base unit with edge-based scaling (MVP approach)
- **Portfolio Limits**: Maximum 15% bankroll exposure, 12 bets per week
- **Circuit Breakers**: Stop betting at -50% drawdown, pause at 40% win rate

### Risk Controls

- **Model Validation**: RMSE tracking, calibration monitoring
- **Performance Monitoring**: Weekly hit rate, ROI, Sharpe ratio analysis
- **Bankroll Management**: Dynamic sizing based on performance (-20% = reduce sizing)
- **Quality Gates**: Data validation, feature stability, prediction range checks

### Advanced Features (Future)

- **Kelly Criterion Sizing**: 25% fractional Kelly for optimal growth
- **Confidence-Based Betting**: Scale bets by model uncertainty
- **Multi-Model Ensemble**: Risk distribution across different approaches

## AI Development Guidelines

- **Explicit Requests**: Reference specific files, functions, and line numbers
- **Validation Required**: Always review and test AI-generated code
- **Context Discipline**: Only load relevant documents to maintain focus
- **Documentation**: Update relevant docs for all code/data/workflow changes
- **Decision Tracking**: Record material changes in decision log with rationale