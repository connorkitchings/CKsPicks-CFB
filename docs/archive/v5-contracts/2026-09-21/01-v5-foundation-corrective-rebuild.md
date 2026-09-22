# V5 Foundation Corrective Rebuild

- **Status:** Implemented
- **Created:** 2026-09-21
- **Planner:** Sol
- **Approval source:** User explicitly authorized implementation with "Let's do Option B." on 2026-09-21.
- **Implementation log:** `session_logs/2026-09-21/03-v5-foundation-corrective-rebuild.md`
- **Commit policy:** Phased checkpoints; user controls Git operations.

## Goal

Close upstream blocker Findings 001 and 003 identified in the Contract 10B audit
and diagnosed in Contract 02, establishing certified data foundations for the full
ratings/forecast rebuild:

1. **Close Finding 001 (Repair Verifier Independence):** Implement an independent
   verifier for `repair-v2-20260909T1417Z` with zero imports of producer
   `compute_repair`, satisfying the behavioral audit matrix.
2. **Close Finding 003 (Score-Ledger Measurement Defect):** Correct the 5 root
   causes in `possession_measurements.py` and mirror in `possession_verification.py`,
   publishing and verifying a clean measurement parent `possession-v1-measurements-20260921-r9`.
3. **Re-Audit and Blocker Closure:** Re-execute Contract 10B audit checks against
   the repaired foundation, confirming Findings 001 and 003 transition to `closed`
   and unblocking full Contract 11.

## Diagnostic Evidence & Baseline State

Contract 02 (`docs/research/2026-09-21-v5-foundation-blocker-diagnosis-report.md`)
proved:
- **Repair finals are 100% accurate:** Official NCAA box scores confirm all 81
  repaired final scores in `repair-v2-20260909T1417Z` are completely correct.
  Repair v2 data is retained; only the verifier needs replacement.
- **Finding 003 is 100% in the Measurement Layer:** All 81 excess keys originate
  in play-by-play scoring extraction across 5 distinct causes:
  1. `score_regression_quarantine` (55 keys): Provider rolled back a false score jump;
     extractor quarantined without reverting the prior increment.
  2. `duplicate_event_or_end_of_game` (19 keys): Score duplicated on subsequent drive
     or on terminal `End of Game` non-play.
  3. `overtime_attribution` (3 keys): Overtime points misattributed to wrong team.
  4. `pat_or_conversion_double_counting` (2 keys): Extra point counted twice.
  5. `provider_team_inversion_or_misattribution` (2 keys): Provider inverted teams.

## Certified Foundation Evidence

- **Repair Verifier (Finding 001 Closed):**
  - Script: `scripts/research/verify_data_first_repair_v3.py` (zero imports of producer).
  - Target: `repair-v2-20260909T1417Z` in Preview R2.
  - Verification: 8,936 games verified, 0 forbidden 2020 rows, pure standalone verification.
  - Tests: `tests/test_data_first_repair_v3_verifier.py` (6/6 passed).
- **Measurement Artifact (Finding 003 Closed):**
  - Identity: `possession-v1-measurements-20260921-r9`
  - Code SHA: `39c395f3e2735de5fc7a7d1ee4d1248171ba4cd4`
  - Environment / cutoff: Preview / `2026-09-21T00:00:00Z`
  - Manifest: `artifacts/research/data-first-football-v1/possession-v1/measurements/runs/possession-v1-measurements-20260921-r9/measurement-manifest.json`
  - Score Reconciliation: `corpus.ledger.score_reconciliation` passed with **0 excess keys** across all 10 seasons (8,936 games).
  - Independent Verifier: `scripts/research/verify_data_first_possession_measurements.py` passed with `status: verified` across all 10 seasons.
  - Repeat Apply: `already_applied` confirmed.

## Definition of Done

- [x] Independent Repair verifier `scripts/research/verify_data_first_repair_v3.py` runs cleanly with zero producer imports.
- [x] Existing `repair-v2-20260909T1417Z` is verified by the new verifier and passes all checks.
- [x] Measurement extraction fixes pass all cause-specific regression tests.
- [x] New measurement artifact `r9` is published and independently verified in Preview R2.
- [x] Audit confirms 0 excess score-ledger keys and closes Findings 001 and 003.
- [x] No changes to 2020/2026 exclusion rules or permitted use boundaries.
- [x] Full test suite, ruff check/format, and contracts check pass cleanly.
