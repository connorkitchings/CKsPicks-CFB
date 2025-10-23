# Repository Guidelines

This guide orients contributors and AI agents to the `cfb_model` repository. Follow these practices to stay aligned with the project's workflow and quality bar.

## Project Structure & Module Organization

- `src/cfb_model/` — production Python package; data ingestion lives in `data/`, feature pipelines in `data/aggregations/`, model code in `models/` (artifacts written to `artifacts/models/`).
- `scripts/` — CLI utilities (ingestion, caching, training).
- `tests/` — Pytest suite covering data transforms and model helpers.
- `docs/` — MkDocs site with planning (`project_org/`, `planning/`), runbooks (`operations/`), and schema references (`data/`).
- `session_logs/` — chronological handoffs; read the latest entry before starting work.

## Build, Test, and Development Commands

- `uv sync --extra dev` — install runtime plus dev tooling.
- `source .venv/bin/activate` — activate the `uv` virtual environment.
- `uv run ruff format .` / `uv run ruff check .` — auto-format and lint.
- `uv run pytest` — execute the full unit test suite.
- `uv run mkdocs serve` — preview docs locally at `http://127.0.0.1:8000`.
- `python -c 'from cfb_model.flows.preaggregations import preaggregations_flow as f; f(year=2024)'` — rebuild key data aggregates when inputs change.

## Coding Style & Naming Conventions

- Python 3.12+, 4-space indentation, Google-style docstrings, full type hints.
- Use `ruff` for formatting, linting, and import ordering (ignore E501 already configured).
- Partitioned data uses `year=YYYY/` directories; features adopt `off_*`, `def_*`, `adj_*` prefixes.
- Prefer descriptive module and function names (`ingest_games`, `persist_team_game`).

## Testing Guidelines

- Framework: `pytest` with fixtures under `tests/`.
- Add targeted tests for new aggregation logic or CLI behaviors; synthetic DataFrames are acceptable.
- Name tests `test_<functionality>` and group by module (e.g., `test_aggregations_core.py`).
- Run `uv run pytest` before submitting a PR; aim to keep existing coverage intact.

## Commit & Pull Request Guidelines

- Commit messages follow `<type>: <description>` (e.g., `feat: add weekly cache CLI`).
- Before opening a PR: run format/lint/tests, update affected docs, and capture decisions in `docs/decisions/decision_log.md` when appropriate.
- PR description should include summary, linked issues, validation results, and any screenshots/logs relevant to UI or report output.

## Agent & Contributor Onboarding

- Review the minimal context pack:
  - **Docs:** `docs/project_org/project_charter.md`, `docs/planning/roadmap.md`, `docs/decisions/decision_log.md`, `docs/project_org/modeling_baseline.md`, `docs/operations/weekly_pipeline.md`, `docs/project_org/feature_catalog.md`, `docs/project_org/betting_policy.md`, latest `session_logs/` entry.
  - **Code Anchors:** `src/config.py`, `src/utils/local_storage.py`, `src/features/pipeline.py`, `src/features/persist.py`, `src/models/train_model.py`, `src/scripts/generate_weekly_bets_clean.py`, `scripts/cli.py`, representative tests (`tests/test_aggregations_core.py`, `tests/test_betting_policy_kelly.py`).
- **Session logs:** Read the latest entry to understand recent context, but **do not create new session logs unless explicitly requested by the user**. Session logs are for handoffs between development sessions, not routine agent interactions.

### Data Access Notes

- Production data lives on an external drive; the absolute path is defined in `.env` via `CFB_DATA_ROOT`. Make sure that drive is mounted before running any ingestion, caching, or modeling commands—`src/config.get_data_root()` and `LocalStorage` both rely on that environment variable.
- Processed entities such as `team_game` are partitioned as `.../year=YYYY/week=WW/team=<Team Name>/data.csv`; don't expect a single `data.csv` directly under the week folder when probing the filesystem.

## Working with External Data Dependencies

- The project depends on `CFB_DATA_ROOT` pointing to mounted external storage. Before executing data ingestion, aggregation, or model training commands, verify the data root is accessible.
- If scripts fail with path-related errors, check that:
  1. `.env` file exists with `CFB_DATA_ROOT` defined
  2. The external drive is mounted at that path
  3. Required partition structure exists (e.g., `year=YYYY/week=WW/`)

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

## Troubleshooting

### Common Issues

- **Import errors:** Ensure you've run `uv sync --extra dev` and activated the venv
- **Data path errors:** Verify `CFB_DATA_ROOT` in `.env` and that external drive is mounted
- **Aggregation failures:** Check that input data exists for the specified year/week
- **Test failures:** Run `uv run ruff format . && uv run ruff check .` before tests
- **Missing partitions:** Partitioned data may not exist for all weeks; scripts should handle gracefully

### Getting Help

- Check existing documentation in `docs/`
- Review relevant session logs for similar issues
- Examine test cases for usage examples
- Validate environment setup matches prerequisites in README.md
