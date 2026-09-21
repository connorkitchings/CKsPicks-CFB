# Session: V5-12A Conditional Historical Scorecard Implementation & Publication

## TL;DR

- **Worked On:** Contract 12A conditional historical scorecard code, unit tests, Preview R2 preflight execution, signed publication (`apply`), idempotent repeat check, independent verification, and report publication.
- **Outcome:** Contract 12A fully Implemented. Scorecard artifact and signed terminal manifest published to Preview R2 under run `conditional-v1-20260921-scorecard`. Independent verifier re-read and validated all signatures and hashes directly from storage; idempotent repeat passed. Comprehensive report rendered and saved to `docs/research/2026-09-21-v5-12a-conditional-historical-scorecard-report.md`.
- **Plan Contract:** `docs/plans/2026-09-19/12a-v5-conditional-historical-scorecard.md` (Status: Implemented)
- **Approval / Status:** User authorized execution ("Let's do sessions A and B simultaneously" and "Proceed").
- **Blockers:** None for Contract 12A. Permitted use remains `conditional_historical_results_only`. Full eligibility requires resolution of Findings 001 and 003 before full Contract 11.
- **Next:** Proceed to Foundation Corrective Rebuild Contract (addressing Finding 001 Repair verifier independence and Finding 003 Measurement score-ledger fix).

## Context and Decisions

- Contract 12A requires:
  - Exact entry record: `conditional-v1-20260919-9265314-11a` verification manifest.
  - Fail-closed re-reading of raw SHA `5a7e7d48...`, canonical SHA `7ce47863...`, and record SHA `7ee050b4...`.
  - Headline 2025 (n=934 per target), context 2022-2024, pooled 2022-2025 (n=3659 per target), and slices for completed game stages 0, 1, 2, 3, 4+.
  - Recomputed Gaussian CRPS and central 50/80/95% intervals from final target-season calibration variance.
  - Zero V4 comparison, zero readiness recommendation, permitted use `conditional_historical_results_only`.
- Verified scorecard results:
  - 2025 Headline (n=934):
    - Margin: MAE 14.382, RMSE 18.381, bias -0.842, CRPS 10.340, 50% cov 55.1%, 80% cov 79.9%, 95% cov 94.8%
    - Total: MAE 13.200, RMSE 16.388, bias +2.102, CRPS 9.307, 50% cov 52.8%, 80% cov 82.1%, 95% cov 97.0%
  - Pooled 2022-2025 (n=3659):
    - Margin: MAE 14.645, RMSE 18.496, bias -0.124, CRPS 10.432
    - Total: MAE 13.543, RMSE 16.899, bias +1.461, CRPS 9.542
  - Zero row exclusions across 7,318 prediction rows and 3,659 games.

## Work Completed

- Created `src/cks_picks_cfb/forecast/historical_scorecard.py` (entry gate validation, data loading, population validation, metric leaf calculation, report rendering).
- Created `src/cks_picks_cfb/forecast/scorecard_publication.py` (preflight, signed publication, verification).
- Created `scripts/research/run_v5_conditional_scorecard.py` (CLI with `preflight`, `apply`, and `verify`).
- Created `tests/test_historical_scorecard.py` (21 unit tests, all passing).
- Executed Preview R2 preflight; output saved to `/tmp/scorecard_preflight.json`.
- Executed Preview R2 `apply`: signed publication under `conditional-v1-20260921-scorecard`.
  - Scorecard URI: `artifacts/research/data-first-football-v1/historical-scorecards/conditional-v1/runs/conditional-v1-20260921-scorecard/historical-scorecard.json`
  - Scorecard raw SHA-256: `25fce7a214997e53a3b5bcb8a41b3ba80db3914fa6d152255ee6d47107f959e6`
  - Manifest URI: `artifacts/research/data-first-football-v1/historical-scorecards/conditional-v1/runs/conditional-v1-20260921-scorecard/scorecard-manifest.json`
  - Manifest raw SHA-256: `0f4fbf33c27d85b535fb7a6e224f2aee6433ccf76d6a182e0caf85e751a0ba23`
- Verified idempotent repeat: returned `already_applied` and `verified: true` in 0.29s.
- Verified independent re-read from storage: returned `verified: true`.
- Published Markdown report: `docs/research/2026-09-21-v5-12a-conditional-historical-scorecard-report.md`.
- Updated `docs/plans/2026-09-19/12a-v5-conditional-historical-scorecard.md` to `Implemented`.
- Updated `docs/plans/index.md`.

## Files Modified

- `src/cks_picks_cfb/forecast/historical_scorecard.py` — created
- `src/cks_picks_cfb/forecast/scorecard_publication.py` — created
- `scripts/research/run_v5_conditional_scorecard.py` — created
- `tests/test_historical_scorecard.py` — created
- `docs/research/2026-09-21-v5-12a-conditional-historical-scorecard-report.md` — created
- `docs/plans/2026-09-19/12a-v5-conditional-historical-scorecard.md` — updated to Implemented
- `docs/plans/index.md` — updated
- `session_logs/2026-09-21/01-v5-12a-conditional-historical-scorecard.md` — updated

## Validation

- [x] `uv run pytest tests/test_historical_scorecard.py` — 21 passed.
- [x] `uv run python scripts/research/run_v5_conditional_scorecard.py preflight ...` — passed.
- [x] `uv run python scripts/research/run_v5_conditional_scorecard.py apply ...` — passed.
- [x] `uv run python scripts/research/run_v5_conditional_scorecard.py apply ...` (repeat) — returned `already_applied`.
- [x] `uv run python scripts/research/run_v5_conditional_scorecard.py verify ...` — returned `verified: true`.
- [x] Ruff check and format clean.
- [x] `git diff --check` clean.

## Handoff Notes

- **Resume at:** Foundation Corrective Rebuild Contract (Plan Contract 01 under `docs/plans/2026-09-21/`).
- **Watch out for:** Keep permitted use bounded to `conditional_historical_results_only`. Full eligibility remains gated behind closing Findings 001 and 003.

**tags:** ["v5", "contract-12a", "scorecard", "publication", "verified"]
