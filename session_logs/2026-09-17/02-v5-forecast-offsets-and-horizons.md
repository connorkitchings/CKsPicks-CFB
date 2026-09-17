# Session: V5-04A Forecast Offsets, Bridge, and Horizons

## TL;DR

- **Worked On:** Implemented the approved V5-04A no-write forecast boundary.
- **Outcome:** Added Preview-only forecast contracts/config, regulation non-offense offsets, bounded Ridge heads, shared horizon selection, schema registrations, dry-run runner, and focused tests. `--apply` fails closed before storage access.
- **Plan Contract:** `docs/plans/2026-09-17/01-v5-forecast-offsets-bridge-and-horizons.md`.
- **Approval / Status:** User explicitly authorized implementation; contract is **In Progress** until the user commits the code checkpoint and reviewed deterministic preflight evidence exists.
- **Blockers:** No Preview identity may be selected until the user commits this checkpoint. 04B calibration, artifact writes, verifier, and freeze remain blocked.
- **Next:** User reviews and commits the code checkpoint; a fresh task may then select a Preview preflight identity and execute the dry run.

## Context and Decisions

- The signed frozen rating parent `possession-v1-ratings-20260917-d029526-cert` and its pinned R6/Repair v2 checksums were read and accepted before implementation.
- Per the approved 04A clarification, calibration and candidate-manifest schemas are registered now but have no preflight plan or output until 04B.
- Offsets consume only regulation `regulation_non_offense` events and use preceding-season paired league evidence with a four-game prior; they translate final targets without changing rating state.

## Work Completed

- Added `forecast_v1.yaml`, `data_first_forecast_v1.py`, and executable schemas for all seven forecast records.
- Added pure `forecast` producer modules for offsets, earlier-only head fitting/alpha selection, and common horizon selection.
- Added `run_data_first_forecasts.py`, a Preview-only dry-run CLI that loads and validates exact parents, reports ordered no-write evidence, and unconditionally rejects `--apply`.
- Added focused regression coverage for offsets, horizon policy, bounded heads, schema registration, and the blocked apply boundary.

## Files Modified

- `conf/research/data_first_football_v1/forecast_v1.yaml` — sealed 04A config.
- `src/cks_picks_cfb/forecast/` and `src/cks_picks_cfb/data/data_first_forecast_v1.py` — forecast producer/contracts.
- `src/cks_picks_cfb/data/schema_contracts.py` — forecast dataset schemas.
- `scripts/research/run_data_first_forecasts.py` and `tests/test_data_first_forecasts.py` — CLI boundary and focused coverage.

## Validation

- [x] Focused warning-as-error forecast plus adjacent ratings tests — 37 passed; forecast-only regression suite — 7 passed.
- [x] Scoped Ruff and Python compile checks.
- [x] Forecast runner `--help` and blocked `--apply` test.
- [x] Full warning-as-error suite — 941 passed, 2 skipped.
- [x] `contracts/validation.py`, `make contracts-check`, strict MkDocs, and `git diff --check`.

## Amendments and Blockers

- No semantic amendments. 04A records plans only for outputs it actually computes; calibration evidence is deferred to 04B exactly as approved.

## Handoff Notes

- **Resume at:** Complete final repository validation, then let the user execute the separate code checkpoint commit before choosing a new Preview run identity.
- **Watch out for:** Never add `--apply`, calibration, immutable output, independent verification, V4, catalog, Neon, production, or serving behavior in 04A.

**tags:** ["v5", "forecasting", "offsets", "bridge", "horizons", "research"]
