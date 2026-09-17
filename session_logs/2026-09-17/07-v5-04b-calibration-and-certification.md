# Session: V5-04B Calibration and Certification Implementation (Terra)

## TL;DR
- **Worked On:** Implementing V5-04B forecast calibration, apply path, and verification
- **Outcome:** Code implementation complete. All quality gates pass. Certification execution requires user to commit and run in proper environment with R2 access.
- **Plan Contract:** `docs/plans/2026-09-17/02-v5-forecast-calibration-and-certification.md` (Implemented)
- **Approval / Status:** Approved plan; Terra executed.
- **Blockers:** None. Certification execution requires R2 storage access.
- **Next:** User commits code, then runs certification sequence in proper environment.

## Context and Decisions
- Implemented 04B as a single Terra execution per user decision during planning.
- Calibration computed in preflight (changes evidence shape from 04A).
- All 8 tasks completed except Task 8 (certification execution) which requires R2 access.

## Work Completed

### Task 1 — Calibration module
- Created `src/cks_picks_cfb/forecast/calibration.py` (~150 lines)
- Implements nested rolling-origin residual calibration
- Per-target, per-season variance estimation with floor enforcement
- 7 focused tests in `tests/test_forecast_calibration.py`

### Task 2 — Integrate calibration into runner preflight
- Modified `scripts/research/run_data_first_forecasts.py`
- Added calibration computation after horizon selection
- Updated evidence JSON to include calibration plans and summary
- Added `calibration_started` and `calibration_complete` progress events
- 3 new runner integration tests

### Task 3 — Apply path, evidence replay, and manifest-last publication
- Added `ForecastPreflightEvidence` and `DatasetPlan` classes
- Implemented `_load_forecast_preflight_evidence()` for evidence replay
- Implemented `_existing_forecast_manifest()` for idempotency
- Implemented `_writers()` for partitioned dataset writers
- Implemented `apply()` function with full immutable write lifecycle
- Updated `main()` to handle `--apply` and `--preflight-evidence` flags
- Removed the `--apply is blocked` error

### Task 4 — Forecast manifest builder
- Added `FORECAST_MANIFEST_SCHEMA` and `FORECAST_MANIFEST_NAME` constants
- Implemented `forecast_manifest()` function in `data_first_forecast_v1.py`
- Uses `signed_payload` for manifest signing

### Task 5 — Independent verifier module and CLI
- Created `src/cks_picks_cfb/forecast/forecast_verification.py` (~600 lines)
- Independent reconstruction of offsets, features, bridges, calibration
- No imports from producer modules (offsets, heads, horizons, calibration)
- Created `scripts/research/verify_data_first_forecasts.py` CLI
- 6 focused tests in `tests/test_forecast_verification.py`

### Task 6 — Focused test suite expansion
- 7 tests in `test_forecast_calibration.py`
- 6 tests in `test_forecast_verification.py`
- 3 new runner integration tests in `test_data_first_forecasts.py`
- Total: 16 new tests, all passing

### Task 7 — Quality gates
- Full test suite: 966 passed, 2 skipped
- Ruff format and check: all clean
- Contracts validation: passed
- MkDocs build: passed
- `git diff --check`: clean

### Task 8 — Certification execution sequence (pending)
- Requires user to commit code
- Requires R2 storage access for Preview environment
- Steps: preflight → evidence review → apply → verify → idempotent repeat

## Files Modified

### New files
- `src/cks_picks_cfb/forecast/calibration.py` — calibration module
- `src/cks_picks_cfb/forecast/forecast_verification.py` — verifier module
- `scripts/research/verify_data_first_forecasts.py` — verifier CLI
- `tests/test_forecast_calibration.py` — calibration tests
- `tests/test_forecast_verification.py` — verifier tests

### Modified files
- `src/cks_picks_cfb/data/data_first_forecast_v1.py` — manifest builder
- `scripts/research/run_data_first_forecasts.py` — apply path, calibration integration
- `tests/test_data_first_forecasts.py` — updated test for apply path
- `docs/plans/2026-09-17/02-v5-forecast-calibration-and-certification.md` — status update
- `docs/plans/index.md` — status update

## Validation
- [x] Focused calibration tests — 7 passed
- [x] Focused verifier tests — 6 passed
- [x] Full forecast test suite — 32 passed
- [x] Full warning-as-error suite — 966 passed, 2 skipped
- [x] Ruff format and check — clean
- [x] Contracts validation — passed
- [x] MkDocs build — passed
- [x] `git diff --check` — clean

## Amendments and Blockers
- None.

## Handoff Notes
- **Resume at:** User commits code, then runs certification sequence:
  1. `git add -A && git commit -m "feat(research): implement V5-04B calibration, apply, and verification"`
  2. Capture committed SHA: `git rev-parse HEAD`
  3. Set UTC cutoff: `date -u +"%Y-%m-%dT%H:%M:%SZ"`
  4. Run preflight: `PYTHONPATH=.:src uv run python scripts/research/run_data_first_forecasts.py --run-id forecast-v1-YYYYMMDD-<shortsha>-04b --expected-code-sha <full-sha> --environment preview --as-of <cutoff> --rating-manifest-uri <uri> --measurement-manifest-uri <uri> --repair-manifest-uri <uri> > preflight.json`
  5. Review preflight.json for zero warnings, all 6 dataset plans, calibration variances
  6. Run apply: `PYTHONPATH=.:src uv run python scripts/research/run_data_first_forecasts.py --run-id <same> --expected-code-sha <same> --environment preview --as-of <same> --rating-manifest-uri <uri> --measurement-manifest-uri <uri> --repair-manifest-uri <uri> --apply --preflight-evidence preflight.json`
  7. Run verifier: `PYTHONPATH=.:src uv run python scripts/research/verify_data_first_forecasts.py --manifest-uri <manifest-uri> --expected-code-sha <same> --environment preview --rating-manifest-uri <uri> --measurement-manifest-uri <uri> --repair-manifest-uri <uri>`
  8. Run idempotent repeat: same apply command, expect `already_applied`
- **Watch out for:** Certification requires Preview R2 credentials and access to the certified 03 rating parent. The worktree must be clean for apply.

**tags:** ["v5", "forecasting", "calibration", "verification", "terra"]
