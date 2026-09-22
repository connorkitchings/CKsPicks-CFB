# V5-11D: Forecast Verification and Findings Closure

- **Status:** Implemented
- **Created:** 2026-09-21
- **Planner:** Sol
- **Approval source:** User authorized the full Contract 11 decomposition on 2026-09-21 ("Let's do it all"); targeted-closure vehicle (no renewed full audit) confirmed by structured decision the same day.
- **Implementation log:** `session_logs/2026-09-21/09-v5-11d-forecast-verification-and-finding-closure.md`
- **Commit policy:** Separate commits — verifier checkpoint, then evidence checkpoints per phase. User controls Git operations.

## Goal

Independently verify every computation of the 11C forecast artifact —
including the new through-2025 final-fit rows — and close Findings 002/004
with signed Preview evidence plus targeted audit-check re-runs (the 001/003
precedent). Success restores full-lane forecast eligibility and closes
umbrella Contract 11.

## Current State

- The 11A-era verifier (`src/cks_picks_cfb/forecast/forecast_verification.py`,
  1,531 lines) performs full reconstruction of the frozen artifact (proven:
  all six digests matched) but is pinned to the R6-derived parents and has no
  final-fit reconstruction.
- Verifier/producer separation is AST-enforced
  (`tests/test_forecast_verification.py:311-330` forbids producer imports);
  shared imports are limited to constants, signing, lake readers, and schema
  contracts.
- Finding 002's closure criterion: "Contract 11 records signed verification of
  reconstructed outputs" (`corpus_ratings.py:730`, `blocking_dependencies:
  ["contract-11"]`). Finding 004's criterion: the disjunctive closure
  ("check passes on renewed evidence, or a corrective contract closes the
  finding with a recorded disposition").
- Umbrella Contract 11 Task 3 requires negative tests (missing datasets,
  corrupted outputs, wrong parents, chronological leakage, producer
  perturbations) plus a positive bit-exact fixture.

## Proposed Approach

Re-point the proven reconstruction verifier at the r9-derived parents,
extend reconstruction to the final-fit rows with independently reviewed
copy-free math, run the verification sequence under a signed Preview record,
execute the negative/positive test battery, then close both findings with
targeted evidence (no harness edits, no full re-audit, no catalog writes).

## Scope

### Included

- Verifier re-pointing: rating run-id, r9 measurement run-id, repair run-id
  (unchanged), population 8,936/8,935, 11C run identity.
- Final-fit reconstruction: independent re-derivation of the `final` model
  and calibration rows from raw parents (recipe, window, alpha, variance
  source all recomputed, none trusted).
- Signed Preview verification manifest + independent re-read + idempotent
  repeat.
- Umbrella Task 3 test battery (negative cases + positive bit-exact fixture
  using real output shapes).
- Closure records for 002/004; lifecycle updates (umbrella 11 → Implemented,
  04/04B rows resolved via the decomposition, index updated).

### Excluded

- Producer changes (11C owns them); methodology or gate changes.
- Renewed full-corpus audit publication (deferred to Contract 12 planning).
- Any edit to 11A/12A/10B/04B evidence, frozen pins, or the 04B artifact.

## Affected Components and Contracts

- `src/cks_picks_cfb/forecast/forecast_verification.py` (re-point + final-fit
  reconstruction; still zero producer imports).
- `tests/test_forecast_verification.py` (extended boundary + battery).
- New Preview verification record under the 11C run prefix (`verification/`).
- Closes umbrella 11; unblocks final Contract 12.

## Implementation Tasks

### Task 1 — Verifier re-pointing and final-fit reconstruction

**Files:**

- `src/cks_picks_cfb/forecast/forecast_verification.py`
- `tests/test_forecast_verification.py`

**Changes:**

- Resolve the 11C run's exact parent identities (rating manifest, r9
  measurement manifest, repair manifest) and pin them; extend
  `_reconstruct_outputs` to the final-fit rows: re-derive the final model
  coefficients from the full development window under the recorded recipe,
  re-derive the carried 2025 calibration variance from the design's
  calibration outputs (never from the stored final row), and verify
  `training_max = 2025`. Every producer-math mirror stays hand-written and
  independently reviewed.

**Acceptance criteria:**

- Verifier accepts the 11C artifact and rejects the 04B artifact (stale
  parents), any r6 lineage, and any tampered final row.

**Validation:**

- AST boundary test extended and passing; unit tests for final-fit
  reconstruction against hand-computed fixtures.

### Task 2 — Umbrella Task 3 test battery

**Files:**

- `tests/test_forecast_verification.py`

**Changes:**

- Negative: missing datasets, corrupted outputs, wrong parents, chronological
  leakage (future season in a training window), producer perturbation
  (byte-changed forecast output). Positive: bit-exact fixture with real output
  shapes that passes end to end.

**Acceptance criteria:**

- Every negative case fails closed with a named error; the positive fixture
  verifies cleanly.

**Validation:**

- Full verification test suite green.

### Task 3 — Signed verification and findings closure

**Files:**

- Verification record (Preview R2, under the 11C run prefix)
- `src/cks_picks_cfb/audit/corpus_ratings.py` (read-only check reuse)

**Changes:**

- Execute verifier preflight → signed Preview verification manifest →
  independent re-read → idempotent repeat.
- Close Finding 002 with the signed verification record (reconstructed all
  outputs, exact digests, per-partition equality).
- Close Finding 004 with the targeted `final_fit_existence` pass on the 11C
  artifact (recorded output; the 11C contract produces the artifact, this
  contract records the closure disposition).
- Update umbrella 11 to Implemented; resolve the 04/04B rows via the
  decomposition record; update the index.

**Acceptance criteria:**

- `verified: true` from independent re-read; repeat returns
  `already_applied`; closure dispositions recorded for 002/004 referencing
  exact evidence SHAs.

**Validation:**

- Verifier output reviewed byte-for-byte against stored artifacts;
  `git diff --check`.

## Testing Strategy

- Unit: reconstruction steps against hand fixtures; final-fit math.
- Negative battery per umbrella Task 3; positive bit-exact fixture.
- Integration: end-to-end Preview verification cycle.
- Boundary: AST import test extended to any new verifier helper.

## Risks and Edge Cases

- **Verifier/producer drift:** every 11C math detail needs a mirrored,
  independently reviewed verifier change — diff the two implementations
  line-by-line during review, never copy.
- **Selection-flip propagation:** if 11C retained a different horizon/head,
  the verifier must reconstruct the retained design, not the 04B one.
- **Closure overreach:** the verification record closes 002/004 only; it does
  not restore 04/04B artifacts, create 2026 eligibility, or replace Contract 12.

## Definition of Done

- [x] 11C is Implemented and its artifact is the only accepted target.
- [x] All outputs including final-fit rows independently reconstructed.
- [x] Negative and positive reconstruction tests pass.
- [x] Signed verification evidence records the exact result and artifact use.
- [x] Findings 002/004 closed with recorded dispositions; umbrella 11 Implemented.
- [x] Tests, ruff, contracts validation, strict MkDocs, `git diff --check` pass.

## Amendments

None. A verifier disagreement with stored outputs preserves the artifact and
requires a corrective contract — never a silent recomputation.
