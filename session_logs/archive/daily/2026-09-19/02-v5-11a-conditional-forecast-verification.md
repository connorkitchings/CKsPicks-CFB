# Session: V5-11A Conditional Forecast Verification

## TL;DR

- **Worked On:** Implemented the authorized Contract 11A independent forecast reconstruction and conditional-only publication boundary.
- **Outcome:** Contract 11A is **Implemented**. Committed clean-SHA preflight, signed Preview publication, independent re-read, and idempotent repeat all passed for `conditional-v1-20260919-9265314-11a`.
- **Plan Contract:** `docs/plans/2026-09-19/11a-v5-conditional-forecast-verification.md`.
- **Approval / Status:** User authorized 11A with “Let's go to 11A” and later authorized Preview publication with “apply 11a” on 2026-09-19. All definition-of-done items are complete.
- **Blockers:** None for 11A. Findings 001/003, full Contract 11, and final readiness remain separate gates.
- **Next:** Contract 12A may calculate the bounded V5-only conditional historical scorecard from the exact 11A verification record.

## Context and Decisions

- The exact four frozen identities and raw hashes are sealed in the 11A boundary: Repair v2, R6 measurements, retained possession ratings, and `forecast-v1-20260917-4600ddd-04b`.
- The independent verifier does not import forecast offsets, heads, horizons, calibration, or the producer runner. It reconstructs those computations locally from generic storage readers, schemas, signing utilities, NumPy/Pandas/SciPy, and Ridge.
- The verifier recursively checks parent signatures/hashes and core eligibility, rejects 2020 and 2026, reads and validates every stored output, reconstructs offsets/features/heads/calibration/horizon selection, and compares logical/partition digests.
- Successful publication is restricted to `conditional_historical_results_only`; the record and terminal manifest explicitly deny prospective evidence, forecast-eligibility restoration, and production activation.
- A failed apply writes terminal failure evidence only and grants no scorecard permission.
- Full Contract 11, Contract 12 readiness, V4, production, Neon, web, markets, and 2026 work remain unchanged.

## Work Completed

1. Expanded `forecast_verification.py` from envelope-only checking to complete independent reconstruction and exact six-output comparison.
2. Added `conditional_verification.py` with exact frozen hashes, open findings, no-write evidence, signed record/manifest publication, independent re-read, immutable idempotency, and bounded failure evidence.
3. Added the Contract 11A research CLI with dry-run, evidence-bound apply, verification-only mode, clean-worktree enforcement, and bounded progress heartbeats.
4. Reworked focused tests for wrong parents, missing/invalid envelopes, rejected seasons, producer perturbations, import independence, conditional permissions, signed re-read, and idempotency.
5. Updated Contract 11A and authority documentation without changing full-11/readiness gates.
6. Ran the independent verifier against the real frozen Preview artifact with no writes. Exact matches:
   - `forecast_prediction`: 7,318 rows / 62 partitions
   - `forecast_model`: 16 rows / 4 partitions
   - `forecast_calibration`: 8 rows
   - `forecast_registry`: 4 rows
   - `window_comparison`: 4 rows
   - `forecast_selection`: 2 rows
   - selected horizon: `expanding`
   - horizon SHA-256: `9c1adef04afd39c239ed18e7161232a1a65f590a52f5496c675d67c69f0d1510`
7. Clean-SHA preflight at `2026-09-19T20:31:28Z` produced evidence SHA-256 `3b24ff0ddfbe82ab68fbaea227d9457a4ad19e73f2a03f26f62087f05245a90a`.
8. Published and independently re-read signed Preview record `7ee050b45ea8df9e00f44bdde3159f4d6a2ffe16878a93835e69ad068302cda2` and terminal manifest `7ce47863e1e34874357f3f503ef1d8f1f232e48c9b199c5aff99dfb5606b93ad`.
9. Idempotent repeat returned `already_applied` with the identical terminal-manifest SHA.

## Files Modified

- `src/cks_picks_cfb/forecast/forecast_verification.py` — full independent reconstruction and output comparison.
- `src/cks_picks_cfb/forecast/conditional_verification.py` — 11A evidence and publication boundary.
- `scripts/research/run_v5_conditional_forecast_verification.py` — 11A dry-run/apply/re-read CLI.
- `scripts/research/verify_data_first_forecasts.py` — corrected CLI description for full reconstruction.
- `tests/test_forecast_verification.py` — focused reconstruction and conditional-publication coverage.
- `tests/test_data_first_documentation_authority.py` — current Contract 10/11A lifecycle assertions.
- `docs/plans/2026-09-19/11a-v5-conditional-forecast-verification.md` — authorization, status, checkpoint, and DoD progress.
- `docs/plans/index.md`, `docs/planning/data-first-football-forecasting-roadmap.md`, `AGENTS.md` — current 11A lifecycle alignment.

## Validation

- [x] Real frozen-artifact no-write reconstruction: all six output digests and selection/calibration metadata matched.
- [x] Focused forecast/audit suites: 96 passed with warnings as errors.
- [x] Documentation-authority suite: 37 passed with warnings as errors.
- [x] Full suite: 1,151 passed, 2 skipped with warnings as errors.
- [x] Full Ruff check.
- [x] Strict MkDocs build.
- [x] Direct contracts validation and `make contracts-check`.
- [x] New CLI `--help` and Python compilation.
- [x] `git diff --check`.
- [x] Clean-SHA Preview preflight, evidence-bound apply, independent CLI re-read, and idempotent repeat.

## Amendments and Blockers

- No material contract amendment was required. Missing `partition_keys` in the historical forecast manifest's top-level partitioned refs was handled mechanically by enforcing the sealed dataset-specific partition keys and then validating them against each child partition manifest.
- The signed evidence permits `conditional_historical_results_only` only. It does not clear the Repair verifier-dependence or score-ledger findings, restore full forecast eligibility, or authorize readiness/2026 work.

## Handoff Notes

- **Resume at:** Plan and authorize Contract 12A only if a V5-only conditional historical scorecard is desired.
- **Watch out for:** 11A does not clear Findings 001/003, full Contract 11, readiness, or any 2026 gate. Contract 12A cannot publish a V4 comparison or readiness recommendation.

**tags:** ["v5", "contract-11a", "forecast-verification", "historical-validation"]
