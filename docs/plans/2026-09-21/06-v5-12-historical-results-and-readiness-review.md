# V5-12: Historical Results and Readiness Review Execution Contract

- **Status:** Implemented 2026-09-21
- **Created:** 2026-09-21
- **Planner:** Sol
- **Approval source:** User explicit approval of `implementation_plan.md` ("The user has approved this document")
- **Implementation log:** `session_logs/2026-09-21/11-v5-historical-results-and-readiness-review.md`
- **Commit policy:** Commit with implementation; user controls Git operations.

---

## Goal

Produce the authoritative decision record and historical readiness review for V5's historical foundation across the full 2015–2025 development corpus. This contract:
1. Recomputes reportable historical accuracy and calibration metrics from the 11D independently verified forecast dataset (`forecast-v1-20260921-5afd577-11c`).
2. Documents verified population counts (7,318 prediction rows, 3,659 games across 2022–2025) and verifies zero row exclusions.
3. Incorporates comparative evidence: the horizon selection paired bootstrap test (expanding vs latest_five), reference head selection, 2025 provider-recorded market line diagnostic disclosures, and explicit V4 point-in-time comparison unavailability disclosures.
4. Cites certified closure records for all four Contract 10B foundation audit findings (`audit-structural-001`, `audit-structural-002`, `audit-ledger-score_reconciliation-1de3aaaf7d`, `audit-forecast-final_fit_existence-b1bc852294`).
5. Publishes an immutable, signed historical scorecard artifact to Cloudflare Preview R2 with permitted use `historical_readiness_review_only`.
6. Authors the comprehensive historical results and readiness review report in `docs/research/` and issues the official historical readiness recommendation.

---

## Current State & Entry Gate Verification

All prerequisites for Contract 12 are fully met and verified:
1. **Foundation Audit (10B):** Completed under run `historical-audit-10b-20260919-full` (SHA `7a476648`). Four open blocker findings were published.
2. **Finding 001 Closure:** Certified via independent Repair verifier v3 with zero producer imports in Session 03.
3. **Finding 003 Closure:** Certified via `possession-v1-measurements-20260921-r9` with zero score-ledger excess keys in Session 03.
4. **Finding 004 Closure:** Certified via through-2025 final fit in `forecast-v1-20260921-5afd577-11c` in Session 08.
5. **Finding 002 Closure:** Certified via independent verification of the full 11C forecast artifact in Session 09, with signed verification manifest published:
   - **Verification Manifest URI:** `artifacts/research/data-first-football-v1/forecasts/runs/forecast-v1-20260921-5afd577-11c/verification/verifier-manifest.json`
   - **Manifest SHA-256:** `4cfe5ef86e4e7145d6dfe3d4e2f1ea85e54475c439fce04a1ce41ec21dfa363b`
   - **State:** `verified`
   - **Final Fit Verified:** `true`
   - **Permitted Use:** `full_lane_forecast_eligibility_closure_only`
6. **Umbrella Contract 11:** Fully **Implemented** (forecast eligibility restored).
7. **Market Diagnostic Study:** Certified under `market-diagnostic-2025-v1-20260921` (manifest SHA `e879b6b4...`).

---

## Proposed Approach

Contract 12 implements a dedicated, independent review module and CLI runner that:
- Pins the exact 11D verifier manifest and fail-closed validates its SHA and closure flags.
- Recomputes all metrics from first principles without importing producer training or prediction routines.
- Evaluates Gaussian CRPS and central 50%/80%/95% interval coverage from final calibration variance.
- Formats structured comparison tables for expanding vs latest-five horizon selection, 2025 market line diagnostics, and completed-game stages (0, 1, 2, 3, 4+).
- Signs and writes the scorecard to Preview R2 under `artifacts/research/data-first-football-v1/historical-scorecards/full-v1/runs/<run_id>/`.
- Produces a comprehensive, publication-grade research report in `docs/research/2026-09-21-v5-12-historical-results-and-readiness-review-report.md`.

---

## Scope

### Included
- Independent scorecard computation module `src/cks_picks_cfb/forecast/final_historical_scorecard.py`.
- Execution script `scripts/research/run_v5_historical_readiness_review.py` supporting `preflight`, `apply`, and `verify`.
- Dedicated unit test suite `tests/test_final_historical_scorecard.py`.
- Publication of immutable `historical-scorecard.json` and signed `scorecard-manifest.json` to Preview R2 under `artifacts/research/data-first-football-v1/historical-scorecards/full-v1/runs/<run-id>/`.
- Comprehensive readiness review report at `docs/research/2026-09-21-v5-12-historical-results-and-readiness-review-report.md`.
- Formal readiness recommendation: `accepted_for_prospective_evaluation`.
- Contract index and roadmap updates.

### Excluded
- No refitting, retraining, or parameter adjustments.
- No writes to production, Neon database, web app, or V4 champion models.
- No prospective 2026 live execution (deferred to Contracts 07–09).
- No promotion to production champion (deferred to Phase 7 after six qualifying frozen future slates).

---

## Affected Components and Contracts

- `src/cks_picks_cfb/forecast/final_historical_scorecard.py` [NEW]
- `scripts/research/run_v5_historical_readiness_review.py` [NEW]
- `tests/test_final_historical_scorecard.py` [NEW]
- `docs/research/2026-09-21-v5-12-historical-results-and-readiness-review-report.md` [NEW]
- `docs/plans/2026-09-18/12-v5-historical-results-and-readiness-review.md` [MODIFY: Amendment 2 linking this contract]
- `docs/plans/index.md` [MODIFY: update Contract 12 row]
- `docs/planning/data-first-football-forecasting-roadmap.md` [MODIFY: update Contract 12 row]

---

## Implementation Tasks

### Task 1 — Final Historical Scorecard Module
**Files:**
- `src/cks_picks_cfb/forecast/final_historical_scorecard.py`

**Changes:**
- Bind exact 11D verifier manifest URI and SHA (`4cfe5ef8...`).
- Implement fail-closed `validate_verification_manifest(storage)`.
- Implement `_load_predictions(storage, manifest)` and `_load_calibration(storage, manifest)`.
- Recompute metrics:
  - MAE, RMSE, bias, Gaussian CRPS, 50%/80%/95% coverage & width.
  - Slices: 2025 Headline (N=934), 2022–2024 Context (896, 910, 919), Pooled 2022–2025 (N=3,659), and completed-game stages 0, 1, 2, 3, 4+.
- Extract selection evidence from 11C output dataset `window_comparison` and `forecast_selection`.
- Incorporate market diagnostic summary from `market-diagnostic-2025-v1-20260921`.
- Include formal V4 point-in-time comparison unavailability disclosure.
- Generate structured scorecard dictionary adhering to schema `data_first_historical_scorecard_v1`.

**Acceptance criteria:**
- Exact match of population counts: 7,318 rows, 3,659 games, 0 exclusions.
- Recomputed metrics match empirical validation values (2025 Margin MAE 14.16, Total MAE 13.36; Pooled Margin MAE 14.32, Total MAE 13.66).
- Validates all entry constraints without importing producer modeling logic.

### Task 2 — Publication & Verification CLI
**Files:**
- `scripts/research/run_v5_historical_readiness_review.py`

**Changes:**
- Implement CLI with `preflight`, `apply`, and `verify` modes.
- Enforce clean worktree requirement for `apply`.
- Sign payload and write immutable `historical-scorecard.json` and `scorecard-manifest.json` under:
  `artifacts/research/data-first-football-v1/historical-scorecards/full-v1/runs/<run-id>/`
- `verify` command independently re-reads the published artifacts, validates SHA-256 digests, signatures, and confirms idempotent rerun behavior.

**Acceptance criteria:**
- Preflight returns exit 0 and outputs structured summary.
- Apply completes successfully, records valid canonical and raw SHA digests.
- Repeat apply returns `already_applied` with exit 0.
- Verify confirms all hashes directly against Preview R2 storage.

### Task 3 — Unit Test Suite
**Files:**
- `tests/test_final_historical_scorecard.py`

**Changes:**
- Unit tests covering:
  - 11D manifest entry gate validation (tampered SHA, missing findings, non-verified state).
  - Population integrity verification (7,318 rows, duplicate checks, missing values).
  - Metric computation accuracy (known fixtures for MAE, RMSE, bias, CRPS, coverage).
  - Scorecard schema validation and structure verification.
  - Publication idempotency, collision prevention, and verification check.

**Acceptance criteria:**
- All tests in `tests/test_final_historical_scorecard.py` pass cleanly.

### Task 4 — Comprehensive Readiness Report & Governance Updates
**Files:**
- `docs/research/2026-09-21-v5-12-historical-results-and-readiness-review-report.md`
- `docs/plans/2026-09-18/12-v5-historical-results-and-readiness-review.md`
- `docs/plans/index.md`
- `docs/planning/data-first-football-forecasting-roadmap.md`

**Changes:**
- Render complete research report including:
  - Executive summary and readiness recommendation (`accepted_for_prospective_evaluation`).
  - Sealed artifact identities & audit blocker closure citations (001, 002, 003, 004).
  - Complete metric tables (headline, context, pooled, stages 0–4+).
  - Horizon and head selection analysis.
  - Baseline and market line disclosures.
  - Explicit delineation between historical acceptance and 2026 prospective evaluation.
  - Exact prerequisites for unblocking Contracts 07–09.
- Amend umbrella Contract 12 with Amendment 2 linking this execution contract.
- Update `docs/plans/index.md` and roadmap table.

**Acceptance criteria:**
- `uv run python contracts/validation.py` passes.
- `uv run mkdocs build --strict --quiet` passes.
- Working tree remains clean (`git diff --check`).

---

## Testing Strategy

1. **Unit tests:** `uv run pytest tests/test_final_historical_scorecard.py -v`.
2. **Regression tests:** Full suite `uv run pytest`.
3. **Linting and formatting:** `uv run ruff check` and `uv run ruff format --check`.
4. **Live Preview execution:** Dry run preflight, signed publication (`apply`), idempotent repeat check, and independent storage verification.
5. **Contract sync:** `make contracts-check` and `uv run python contracts/validation.py`.
6. **Documentation build:** `uv run mkdocs build --strict --quiet`.

---

## Risks and Edge Cases

- **Lineage integrity:** The scorecard must read exclusively from the certified 11C forecast artifact (`forecast-v1-20260921-5afd577-11c`) verified by 11D (`4cfe5ef8...`). It must not load from the superseded 04B artifact.
- **Independence boundary:** The review module must not import any producer modeling libraries, heads, horizons, or calibration fitters.
- **Separation of authority:** The report must clearly state that historical acceptance does not authorize 2026 prospective application, which remains strictly governed by Contracts 06–09.

---

## Definition of Done

- [x] `final_historical_scorecard.py` implemented with fail-closed 11D entry gate and first-principles metric calculations.
- [x] `run_v5_historical_readiness_review.py` implemented with `preflight`, `apply`, and `verify`.
- [x] Unit tests pass in `tests/test_final_historical_scorecard.py` (and full suite passes).
- [x] Scorecard artifact and signed manifest published to Preview R2 under `historical-scorecards/full-v1/runs/<run-id>/`.
- [x] Idempotent repeat check passes (`already_applied`).
- [x] Storage verification check passes (`verified: true`).
- [x] Research report published at `docs/research/2026-09-21-v5-12-historical-results-and-readiness-review-report.md`.
- [x] Umbrella Contract 12, roadmap, and plans index updated.
- [x] Implementation session log documented.
