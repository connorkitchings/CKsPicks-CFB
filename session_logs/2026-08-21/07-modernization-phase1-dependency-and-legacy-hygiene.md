# Session: Modernization Phase 1 — Dependency & Legacy Hygiene

## TL;DR
- **Worked On:** Executed Milestone 1 of [`docs/planning/2026_codebase_modernization_and_refactoring_plan.md`](../../docs/planning/2026_codebase_modernization_and_refactoring_plan.md): dependency pruning and dead script archival.
- **Outcome:** Cleaned `pyproject.toml` (moved unused packages `streamlit`, `plotly`, `pymc`, `shap`, `fastapi`, `uvicorn` to `[project.optional-dependencies.research]`, removed duplicates, tightened `boto3`), archived 7 legacy scripts to `scripts/archive/`, removed dead `run_season` command from `scripts/cli.py`, cleaned up validation & documentation references.
- **Plan Contract:** `docs/planning/2026_codebase_modernization_and_refactoring_plan.md` (Milestone 1)
- **Approval / Status:** User approved implementation plan; Milestone 1 complete.
- **Blockers:** None.
- **Next:** Proceed to Milestone 2 (Data Layer Decomposition: modularizing `src/cks_picks_cfb/data/storage.py` and `silver.py`).

## Context and Decisions
- **`jinja2` retained:** Kept in production dependencies because `scripts/pipeline/publish_review.py` still relies on it.
- **`run_season` CLI command removed:** Removed from `scripts/cli.py` and removed `src/cks_picks_cfb/inference/` after moving `predict.py` and `report.py` to `scripts/archive/inference/`.
- **Contracts validation updated:** Removed archived `publish_picks.py` from `contracts/validation.py` logo map sync verification list.

## Work Completed
- **`pyproject.toml`:**
  - Added `research` optional dependency group with `streamlit`, `plotly`, `pymc`, `shap`, `fastapi`, and `uvicorn`.
  - Removed duplicate `pytest`, `ruff`, and unnecessary transitive dependencies (`iniconfig`, `pluggy`) from production dependencies.
  - Constrained `boto3>=1.35.0,<2.0.0`.
- **Archival:**
  - `src/cks_picks_cfb/inference/predict.py` -> `scripts/archive/inference/predict.py`
  - `src/cks_picks_cfb/inference/report.py` -> `scripts/archive/inference/report.py`
  - `src/cks_picks_cfb/data/ingest_api.py` -> `scripts/archive/ingest_api.py`
  - `scripts/pipeline/publish_picks.py` -> `scripts/archive/publish_picks.py`
  - `scripts/pipeline/run_pipeline_generic.py` -> `scripts/archive/run_pipeline_generic.py`
  - `scripts/pipeline/train_preseason_model.py` -> `scripts/archive/train_preseason_model.py`
  - `scripts/pipeline/training_cli.py` -> `scripts/archive/training_cli.py`
  - Removed empty `src/cks_picks_cfb/inference/` folder.
- **Reference Updates:**
  - `scripts/cli.py`: Removed `run_season` command and unused imports (`os`, `REPORTS_DIR`).
  - `contracts/validation.py`: Removed `publish_picks.py` from `TEAM_LOGO_MAP` checks.
  - `scripts/pipeline/publish_to_db.py`: Updated comment.
  - `README.md`: Updated directory tree.

## Files Modified
- `pyproject.toml` [MODIFY]
- `uv.lock` [MODIFY]
- `scripts/cli.py` [MODIFY]
- `contracts/validation.py` [MODIFY]
- `scripts/pipeline/publish_to_db.py` [MODIFY]
- `README.md` [MODIFY]
- `scripts/archive/inference/predict.py` [MOVE]
- `scripts/archive/inference/report.py` [MOVE]
- `scripts/archive/ingest_api.py` [MOVE]
- `scripts/archive/publish_picks.py` [MOVE]
- `scripts/archive/run_pipeline_generic.py` [MOVE]
- `scripts/archive/train_preseason_model.py` [MOVE]
- `scripts/archive/training_cli.py` [MOVE]

## Validation
- [x] `uv run ruff check .` — All checks passed
- [x] `uv run ruff format --check .` — 189 files formatted
- [x] `uv run pytest -q` — 367 passed, 2 skipped
- [x] `uv run python contracts/validation.py` — Contracts validation passed
- [x] `uv run mkdocs build --quiet` — Docs build succeeded
- [x] `git diff --check` — Clean whitespace check

## Handoff Notes
- **Resume at:** Phase 2 (Data Ingestion & Storage Modularization) of the modernization plan: decompose `src/cks_picks_cfb/data/storage.py` (1,370 lines) into submodules under `src/cks_picks_cfb/data/storage/` (`base.py`, `local.py`, `r2.py`, `factory.py`) and split `silver.py`.

**tags:** ["modernization", "refactoring", "dependencies", "archival", "cleanup"]
