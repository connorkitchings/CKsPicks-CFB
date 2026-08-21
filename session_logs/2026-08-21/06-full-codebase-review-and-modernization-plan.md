# Session: Full Codebase Review & Modernization Plan

## TL;DR
- **Worked On:** Conducted a comprehensive end-to-end audit across data ingestion, data architecture, feature engineering, modeling lifecycle, pipeline operations, and web app. Documented a full-scale refactoring and modernization master plan.
- **Outcome:** Authored [`docs/planning/2026_codebase_modernization_and_refactoring_plan.md`](../../docs/planning/2026_codebase_modernization_and_refactoring_plan.md), updated [`docs/planning/roadmap.md`](../../docs/planning/roadmap.md), and wired documentation navigation in `mkdocs.yml`.
- **Plan Contract:** `docs/planning/2026_codebase_modernization_and_refactoring_plan.md`
- **Approval / Status:** Documented and verified with `mkdocs build`. Implementation staged across 5 discrete milestones.
- **Blockers:** None.
- **Next:** Execute Milestone 1 (Dependency pruning in `pyproject.toml` and legacy dead-code removal).

## Context and Decisions
- **Dependencies:** Unused production dependencies (`streamlit`, `plotly`, `pymc`, `fastapi`, `uvicorn`, `shap`) will be pruned or moved to optional groups (`research`/`dev`), and duplicate `pytest`/`ruff` entries removed from the production group.
- **Storage & Silver Decomposition:** `storage.py` (1,370 lines) and `silver.py` (812 lines) will be modularized into focused submodules with isolated responsibility.
- **Modeling Cadence:** Confirmed strictly: 2021–2024 training/temporal validation (OOF) → 2025 locked test for candidate selection → 2021–2025 refit → 2026 deployment (2020 COVID year quarantined).
- **Inference Pipeline:** `generate_weekly_bets.py` (885 lines) will be decoupled into pure functional pipeline steps with mock-storage unit testing.

## Work Completed
- Completed full multi-layer codebase review.
- Created master planning document `docs/planning/2026_codebase_modernization_and_refactoring_plan.md`.
- Updated `mkdocs.yml` navigation and `docs/planning/roadmap.md` references.
- Verified documentation build with `uv run mkdocs build`.

## Files Modified
- `docs/planning/2026_codebase_modernization_and_refactoring_plan.md` [NEW] — Complete architectural modernization & refactoring plan.
- `docs/planning/roadmap.md` [MODIFY] — Linked modernization plan in header.
- `mkdocs.yml` [MODIFY] — Added plan to "2026 Season" navigation.

## Validation
- [x] `uv run mkdocs build` — Documentation build succeeded.
- [x] `git status --short` — Clean status with only intended planning additions.

## Handoff Notes
- **Resume at:** Begin Milestone 1 by cleaning up `pyproject.toml` and safely removing or archiving dead scripts (`src/cks_picks_cfb/inference/predict.py`, `src/cks_picks_cfb/data/ingest_api.py`, `scripts/pipeline/publish_picks.py`).

**tags:** ["review", "planning", "refactoring", "modernization", "architecture", "dependencies"]
