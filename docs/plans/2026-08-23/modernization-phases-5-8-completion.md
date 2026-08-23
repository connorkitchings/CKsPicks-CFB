# Modernization Phases 5–8 Completion Plan

- **Status:** Implemented
- **Created:** 2026-08-23
- **Planner:** Sol
- **Approval source:** User approved `implementation_plan.md` on 2026-08-23
- **Implementation log:** `session_logs/2026-08-23/02-modernization-phases-5-8-completion.md`
- **Commit policy:** Separate plan commit recommended; implementation commits remain user-controlled.

## Goal

Complete the remaining phases of the **2026 Codebase Modernization & Full-Stack Refactoring Plan**:
- **Phase 5**: Pipeline & Production Ops Streamlining (verify & seal uncommitted refactored primitives)
- **Phase 6**: Web App & User Experience Enhancements
- **Phase 7**: Test Coverage & Quality Gates
- **Phase 8 (Proposed)**: Modernization Completion & Worktree Hygiene

## Current State

- Phases 1–4 are fully complete.
- Phase 5 structural refactoring was implemented on 2026-08-22 (`cks_picks_cfb.inference.weekly`, CLI delegation, webhook failure alerts in `StateMachine`), but remains uncommitted in the active worktree.
- The web app (`web/`) serves `market` and `predictions` modes via Drizzle ORM and Next.js 16 ISR (5-min revalidate). `WeekNav.tsx`, `GameRow.tsx`, `GamesList.tsx`, and `loading.tsx` require UX refinements and settled score/badge rendering.
- `tests/` has 56 test files (379 passing, 2 skipped requiring `TEST_DATABASE_URL`). ~216 CatBoost/scikit-learn deprecation/subnormal warnings occur during test runs. `contracts/validation.py` validates schema table names and logo maps, but doesn't yet check Python schema contracts.

## Proposed Approach

1. **Phase 5 (Verification & Sealing):** Validate existing worktree primitives in `inference/weekly.py`, `generate_weekly_bets.py`, and `state_machine.py` without modifying V4 model/data invariants.
2. **Phase 6 (Web UX Enhancements):** Enhance `WeekNav.tsx` for multi-week switching, add settled score and bet result chips (`win`, `loss`, `push`) in `GameRow.tsx` for both publication modes, and align `loading.tsx` layout to prevent cumulative layout shift.
3. **Phase 7 (Test Coverage & Quality Gates):** Suppress/filter CatBoost/scikit-learn deprecation warnings in model training routines, add CLI integration smoke test `tests/test_generate_weekly_bets_cli.py`, configure `pytest-cov` reporting in `pyproject.toml`, and expand `contracts/validation.py` to cover Python schema contracts.
4. **Phase 8 (Modernization Completion & Worktree Hygiene):** Update roadmap status in `docs/planning/2026_codebase_modernization_and_refactoring_plan.md`, create session logs, and run full cross-stack quality checks.

## Scope

### Included

- Verification of uncommitted Phase 5 pipeline/ops refactoring.
- Web UI enhancements: multi-week routing, settled scores/badges, mobile responsiveness, layout skeleton alignment.
- Test suite hardening: deprecation warning filtering, CLI smoke test, `pytest-cov` setup, cross-stack Python contract validation.
- Roadmap documentation update and worktree hygiene verification.

### Excluded

- Retuning V4 model hyperparameters or adding new ML model families (deferred research).
- Schema DDL changes to Neon Postgres or schema definition changes in `contracts/schema.sql` / `contracts/schema.ts`.
- R2 immutable storage bucket or checksum modifications.

## Affected Components and Contracts

- `scripts/pipeline/generate_weekly_bets.py`: CLI delegation verification.
- `src/cks_picks_cfb/ops/state_machine.py`: Optional webhook alert verification.
- `web/src/components/WeekNav.tsx`: Multi-week URL navigation.
- `web/src/components/GameRow.tsx`: Settled score & bet result chip display (`win`/`loss`/`push`).
- `web/src/app/loading.tsx`: Loading skeleton alignment.
- `src/cks_picks_cfb/models/regime_training.py` & `game_ordinal_training.py`: Deprecation warning filtering.
- `tests/test_generate_weekly_bets_cli.py`: New CLI smoke test suite.
- `pyproject.toml`: `pytest-cov` dependency and coverage settings.
- `contracts/validation.py`: Python schema contract validation.
- `docs/planning/2026_codebase_modernization_and_refactoring_plan.md`: Roadmap completion update.

## Implementation Tasks

### Task 1 — Verify and Seal Phase 5 Ops & Pipeline Refactoring

**Files:**
- `scripts/pipeline/generate_weekly_bets.py`
- `src/cks_picks_cfb/inference/weekly.py`
- `src/cks_picks_cfb/ops/state_machine.py`

**Changes:**
- Confirm `generate_weekly_bets.py` CLI delegates inference execution to `cks_picks_cfb.inference.weekly` while keeping all CLI parameters intact.
- Verify `CFB_OPS_ALERT_WEBHOOK_URL` failure alert delivery in `StateMachine` fails safely without masking exceptions.

**Acceptance criteria:**
- `uv run pytest tests/test_weekly_inference.py tests/test_ops_state_machine.py` passes cleanly.

### Task 2 — Web App UX Enhancements (Phase 6)

**Files:**
- `web/src/components/WeekNav.tsx`
- `web/src/components/GameRow.tsx`
- `web/src/app/loading.tsx`

**Changes:**
- In `WeekNav.tsx`, verify dropdown and arrow navigation correctly handle multi-week switching via `?season=2026&week=N`.
- In `GameRow.tsx`, render settled scores (`homePoints` / `awayPoints`) and bet result badges (`Spread win/loss/push`, `Total win/loss/push`) when `gameResults` exist, operating identically across both `predictions` and `market` modes.
- Audit mobile layout on `GameRow.tsx` for viewports 375px–420px to prevent horizontal text truncation or chip wrapping issues.
- In `loading.tsx`, match skeleton dimensions and layout exactly to `Header` + `RecordBanner` + `WeekNav` + `GameRow` list.

**Acceptance criteria:**
- `cd web && npm run typecheck && npm run build` compiles with zero errors.

### Task 3 — Test Hardening & Quality Gates (Phase 7)

**Files:**
- `src/cks_picks_cfb/models/regime_training.py`
- `src/cks_picks_cfb/models/game_ordinal_training.py`
- `tests/test_generate_weekly_bets_cli.py` [NEW]
- `pyproject.toml`
- `contracts/validation.py`

**Changes:**
- Filter/suppress CatBoost and scikit-learn pipeline parameter deprecation warnings emitted during training fold iterations.
- Add `tests/test_generate_weekly_bets_cli.py` with mock storage and synthetic golden datasets to test CLI flags, options, and error handling.
- Add `pytest-cov>=5.0` to `pyproject.toml` dev dependencies with `[tool.coverage.run]` and `[tool.coverage.report]` configured for `src/cks_picks_cfb`.
- Expand `contracts/validation.py` to check Python schema contracts (`src/cks_picks_cfb/data/schema_contracts.py` and `src/cks_picks_cfb/model_bundle.py`) against canonical definitions.

**Acceptance criteria:**
- `uv run pytest` runs cleanly with 0 deprecation warning spam and includes CLI smoke test.
- `python contracts/validation.py` passes cleanly.

### Task 4 — Modernization Documentation Sync & Worktree Audit (Phase 8)

**Files:**
- `docs/planning/2026_codebase_modernization_and_refactoring_plan.md`

**Changes:**
- Update `2026_codebase_modernization_and_refactoring_plan.md` status table and phase headings to reflect completion of all 8 phases.

**Acceptance criteria:**
- `uv run mkdocs build --quiet` passes.
- `git diff --check` reports zero formatting issues.

## Testing Strategy

- `uv run pytest` (full suite including new CLI smoke tests)
- `uv run ruff check .` and `uv run ruff format --check .`
- `python contracts/validation.py`
- `uv run mkdocs build --quiet`
- `cd web && npm run typecheck && npm run build`

## Risks and Edge Cases

- **Web ISR Caching:** Ensure `WeekNav.tsx` query-param navigation works seamlessly with Next.js ISR page revalidation.
- **Fail-Closed Operations:** Verify webhook delivery failures in ops `StateMachine` strictly log diagnostic alerts without replacing original exceptions.
- **Contract Parity:** Ensure `contracts/validation.py` additions don't break on local-only dev environments missing Postgres.

## Definition of Done

- [x] All implementation tasks and acceptance criteria are complete.
- [x] Required validation passes across Python and Web.
- [x] Documentation and session logs are updated.
- [x] Plan status is updated to `Implemented`.

## Amendments

- None at present.
