# V5 Foundation Corrective Rebuild

- **Status:** In Progress
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
   causes in `possession_measurements.py` that produced 81 excess team-game keys,
   publishing a clean measurement parent `possession-v1-measurements-...-r7`.
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

## Proposed Changes

### Phase 1: Independent Repair Verifier (Finding 001)

- Create `scripts/research/verify_data_first_repair_v3.py`:
  - **Zero producer imports:** Does not import `compute_repair`, `run_data_first_repair_v2`,
    or any builder module.
  - Implements pure verification of `repair-v2-20260909T1417Z`:
    - SHA-256 checksum reconciliation of all raw and canonical parquet datasets.
    - Strict 2020 exclusion check (asserts 0 games from season 2020).
    - Schema validation and null/non-finite checks.
    - Outcome integrity against official NCAA reference score checksums.
  - Generates a signed verification manifest under Preview R2.

### Phase 2: Measurement Score-Ledger Corrections (Finding 003)

- Update `src/cks_picks_cfb/ratings/possession_measurements.py`:
  - **Score-regression rollback:** When provider score regresses, detect and roll back
    the preceding false scoring event rather than allowing phantom points to remain.
  - **Terminal event filtering:** Skip non-play scoring duplicates such as `End of Game`.
  - **PAT deduplication:** Prevent double-counting PAT/2PT when already included in TD event.
  - **Ledger final reconciliation:** Validate cumulative extracted points against
    the verified repaired final score; fail closed on discrepancy.
- Add unit tests in `tests/test_possession_measurements_ledger.py` covering all 5 diagnosed causes.
- Execute dry run / preflight and signed publish to Preview R2 under new identity:
  `possession-v1-measurements-20260921-...-r7`.
- Run independent verification on the published `r7` artifact.

### Phase 3: Contract 10B Re-Audit and Blocker Closure

- Execute Contract 10B audit checks with target measurement set to `r7` and repair verifier set to `v3`.
- Verify that:
  - Finding 001 status transitions from `prohibited_until_closed` to `closed`.
  - Finding 003 status transitions from `prohibited_until_closed` to `closed`.
  - 0 excess keys remain in the score ledger across all 2015–2019 and 2021–2025 seasons.
  - Audit output certifies `findings_001_003_closed: true`.

## Definition of Done

- [ ] Independent Repair verifier `scripts/research/verify_data_first_repair_v3.py` runs cleanly with zero producer imports.
- [ ] Existing `repair-v2-20260909T1417Z` is verified by the new verifier and passes all checks.
- [ ] Measurement extraction fixes pass all 5 cause-specific regression tests.
- [ ] New measurement artifact `r7` is published and independently verified in Preview R2.
- [ ] Contract 10B re-audit confirms 0 excess score-ledger keys and closes Findings 001 and 003.
- [ ] No changes to 2020/2026 exclusion rules or permitted use boundaries.
- [ ] Full test suite, ruff check/format, and contracts check pass cleanly.
