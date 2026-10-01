# Session: Modular Historical Import Pipeline & 2026 Prep Finalization

## TL;DR
- **Worked On:** Fixed historical bootstrap pipeline (`import-history`), modularized execution with `--skip-imports` and `make import-history-silver`, resolved database routing for preview environments, and built CFBD Model Pick'em exporter.
- **Completed:** 
  1. Built CFBD Pick'em exporter (`scripts/pipeline/export_cfbd_pickem.py`), unit tests (`tests/test_export_cfbd_pickem.py`), and Makefile target `make export-pickem`.
  2. Fixed CLI parameters and `--environment preview` routing across all downstream pipeline scripts (`build_schedule_week_policy.py`, `build_history_silver.py`, `build_team_game_dataset.py`, `combine_history_versions.py`, `build_temporal_matchups.py`, `build_regime_features.py`, `generate_baseline_predictions.py`, `assemble_model_ready_features.py`).
  3. Added `--skip-imports` flag to `import-history` and added `make import-history-silver` to execute downstream Silver/Gold steps in under 30 seconds without re-probing 3,900 raw captures.
  4. Fixed lake manifest re-evaluation when re-running failed dataset manifests (`src/cks_picks_cfb/data/lake.py`).
- **Blockers:** None.
- **Next:** Execute Week 0 readiness check (`make readiness YEAR=2026 WEEK=0 AS_OF=2026-08-20 ENV=preview`) and submit CFBD Pick'em picks for Week 0 (`make export-pickem YEAR=2026 WEEK=0 SUBMIT=1`).

## Changes Made
- **`scripts/pipeline/export_cfbd_pickem.py`**: [NEW] CFBD Model Pick'em exporter and API submission client.
- **`tests/test_export_cfbd_pickem.py`**: [NEW] Unit tests for CFBD Pick'em exporter (5 tests passing).
- **`Makefile`**: Added `export-pickem` and `import-history-silver` targets.
- **`.codex/QUICKSTART.md`**: Updated documentation for Pick'em exporter and `import-history-silver`.
- **`src/cks_picks_cfb/ops/__main__.py`**: Added `--skip-imports` CLI flag to `import-history`, fixed `--environment` and parameter passing across all Silver/Gold sub-commands.
- **`src/cks_picks_cfb/data/lake.py`**: Fixed manifest caching to allow re-evaluating failed dataset manifests.
- **`scripts/pipeline/*.py`**: Added `--environment preview` support, `PREVIEW_DATABASE_URL` selection, short-circuit checks, and missing CLI parameter fixes across all pipeline scripts.

## Testing
- [x] `uv run ruff format .` passed (3 files reformatted)
- [x] `uv run ruff check .` passed (all clean)
- [x] `PYTHONPATH=src:. uv run pytest -q` passed (295/295 tests passed in 4.98s)
- [x] `make contracts-check` passed
- [x] `make web-typecheck` and `make web-build` passed cleanly

## Technical Details
- Added `--skip-imports` flag to `import-history` to skip probing ~3,900 raw captures once imported into Neon preview catalog/lake.
- Resolved preview database routing issue by checking `PREVIEW_DATABASE_URL` when `environment == "preview"`.
- Resolved failed manifest immutability error by overwriting `manifest.json` when `existing.get("state") == "failed"`.

## Notes for Next Session
- **Resume at:** Week 0 readiness check and Week 0 CFBD Pick'em submission.
- **Commands:**
  - `make readiness YEAR=2026 WEEK=0 AS_OF=2026-08-20 ENV=preview`
  - `make export-pickem YEAR=2026 WEEK=0 SUBMIT=1`
- **Remember:** All commands must run via `uv run` per execution constraints.

**tags:** ["pipeline", "import-history", "pickem", "ops", "2026-season"]
