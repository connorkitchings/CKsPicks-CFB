# Gemini Rules for `cfb_model`

This file provides guidance to Gemini when working with code in this repository. It is based on the best practices outlined in `WARP.md`.

---

## 1. Essential Development Commands

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
python scripts/check_links.py
python -m src.cfb_model.data.validation --year 2024 --data-type processed --deep
```

### Data Pipeline Operations

```bash
# Complete ingestion pipeline for a full year
python scripts/run_ingestion_year.py --year 2024 --data-root /path/to/external/drive

# Individual entity ingestion (for testing or updates)
python scripts/ingest_cli.py teams --year 2024
python scripts/ingest_cli.py games --year 2024 --season-type regular

# Run aggregations pipeline (requires CFB_MODEL_DATA_ROOT in .env)
python scripts/cli.py aggregate preagg --year 2024

# Train Ridge baseline models
python src/cfb_model/models/ridge_baseline/train.py --train-years 2019,2021,2022,2023 --test-year 2024
```

### Documentation

```bash
# Serve documentation locally
uv run mkdocs serve
# Access at http://127.0.0.1:8000
```

---

## 2. Project Architecture

- **`src/cfb_model/data/`**: Data ingestion, storage abstraction, and feature engineering pipeline.
  - `ingestion/`: API clients for CollegeFootballData.com.
  - `storage/`: Local CSV storage backend.
  - `aggregations/`: Plays → drives → games → season aggregates.
- **`src/cfb_model/models/`**: ML modeling components, including the Ridge baseline.
- **`scripts/`**: CLI entry points for data operations.

**Data Flow:**
1.  **Ingestion**: Raw data from CFBD API → local partitioned CSVs.
2.  **Feature Engineering**: Multi-stage pipeline with opponent adjustment.
3.  **Modeling**: Ridge regression on engineered features.
4.  **Betting Logic**: Edge calculation with thresholds.
5.  **Output**: Weekly CSV reports.

---

## 3. Development Standards

### Data & Modeling Rules
- **No Data Leakage**: Training data must strictly precede prediction data.
- **Betting Lines**: Never use as model features, only for edge calculation.
- **Minimum Games**: Teams need ≥4 games played before betting eligibility.
- **Training Window**: 2014–2023 (excluding 2020). Holdout test year is 2024.
- **Storage**: Raw data in `/data/raw/` (immutable), processed in `/data/processed/`. `CFB_MODEL_DATA_ROOT` env var defines the root.
- **Column Naming**: `off_*` (offense), `def_*` (defense), `adj_*` (opponent-adjusted).
- **Traceability**: Always include `season`, `week`, and `game_id` in time-based data.

### Code Style & Quality
- **Version**: Python 3.12+
- **Tooling**: Use `uv` for environment/package management and `ruff` for formatting/linting.
- **Standards**: All new functions must include Google-style docstrings and type hints.
- **Logging**: Use the `logging` module; avoid `print()` in application code.

---

## 4. Session Context Requirements

To get up to speed, review this minimal context pack:
1.  `docs/project_org/project_charter.md` - Project scope and goals.
2.  `docs/project_org/feature_catalog.md` - Feature definitions.
3.  `docs/operations/weekly_pipeline.md` - Production runbook.
4.  `docs/project_org/modeling_baseline.md` - MVP model specs.
5.  `docs/decisions/decision_log.md` - Architectural decisions.

---

## 5. AI Development Guidelines

- **Be Explicit**: Reference specific files and functions in your requests.
- **Verify Output**: Always review and validate AI-generated code. You are responsible for its quality.
- **Update Documentation**: All changes to code, data, or workflow must be reflected in the documentation.
- **Track Decisions**: Record material changes in `docs/decisions/decision_log.md`.

---
## Gemini Added Memories
- When a new session starts in the `/Users/connorkitchings/Desktop/Repositories/cfb_model` directory, please read the following files to get context: `README.md`, `mkdocs.yml`, `pyproject.toml`, `docs/**`, `src/**`, `scripts/**`, and `tests/**`.