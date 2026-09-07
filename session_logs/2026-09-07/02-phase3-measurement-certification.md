# Session: Phase 3 Measurement Certification and Core Selection

## TL;DR

- **Worked On:** Implementing the approved Preview-only Phase 3 measurement
  certification and shared-core selection contract.
- **Outcome:** The complete Phase 3 measurement materializer, independent
  adjustment implementation, temporal tournament, bootstrap gates, immutable
  apply path, and schemas are ready for the required code-checkpoint commit.
- **Plan Contract:** `docs/plans/2026-09-07/01-phase3-measurement-certification-and-core-selection.md`
- **Approval / Status:** User explicitly authorized implementation on
  2026-09-07; contract is `In Progress`.
- **Blockers:** None identified at session start.
- **Next:** User commits this checkpoint; then run the exact-parent,
  committed-code dry run before any apply-mode R2 write.

## Context and Decisions

- The signed Phase 2d 70-ref eligibility handoff is the only Phase 3 parent.
- Phase 2e auxiliary context, markets, V4, production, Neon activation, and
  publication remain out of scope.

## Work Completed

- Began implementation after verifying the committed documentation checkpoint
  and existing Phase 2d/lake/rating primitives.
- Added fail-closed exact-70-ref eligibility validation, deterministic
  Preview-only run identity, candidate-population checks, and shared-core
  simplicity selection rules.
- Added a ten-season Phase 3 measurement configuration and a committed-code
  dry-run CLI gate. Apply mode remains intentionally unavailable until the
  materializer is implemented and committed.
- Added focused pure-contract coverage.
- Rebuilt all seven measurements from the exact Phase 2d refs and added
  mutually exclusive pass/rush EPA with explicit exclusion accounting.
- Added an independent four-iteration, league-centered opponent adjustment;
  week-open point-in-time states; fixed `rho=0.60` exposure updating; and the
  explicit two-step 2019-to-2021 carryover.
- Added the eight-candidate expanding-season Ridge tournament, training-fold
  fallback/scaling, paired season-to-week bootstrap, recency sensitivity gate,
  and deterministic simplicity selection.
- Added executable version-1 schemas and a Preview-only immutable apply path
  for observations, adjusted measurements, fold predictions,
  attribution/coverage, certification, and the retained-core manifest.
- Added a separate raw-frame numerator/denominator recomputation and a
  read-only frozen-artifact verifier for the post-apply review.

## Files Modified

- `docs/plans/2026-09-07/01-phase3-measurement-certification-and-core-selection.md` - marked implementation in progress.
- `session_logs/2026-09-07/02-phase3-measurement-certification.md` - implementation record.
- `src/cks_picks_cfb/data/data_first_phase3.py` - Phase 3 pure contracts.
- `conf/research/data_first_football_v1/phase3_measurement_core_v1.yaml` - ten-season measurement policy.
- `scripts/research/run_data_first_phase3.py` - Preview-only parent-validation CLI.
- `tests/test_data_first_phase3.py` - Phase 3 contract coverage.
- `src/cks_picks_cfb/ratings/phase3.py` - measurement certification,
  adjustment, state scaffold, tournament, bootstrap, and selection logic.
- `src/cks_picks_cfb/data/schema_contracts.py` - Phase 3 executable schemas.
- `scripts/research/verify_data_first_phase3.py` - independent checksum,
  schema, chronology, population, and retained-core verification.

## Validation

- [x] Focused Phase 2/3, schema, V4, and repository-boundary tests: 54 passed.
- [x] Full warning-as-error Python suite: 750 passed, 2 skipped; 66.67%
  branch coverage (60% required).
- [x] Repository Ruff lint and scoped Phase 3 format check.
- [x] Contracts validation and strict MkDocs build.
- [x] `git diff --check`

## Amendments and Blockers

- None.

## Handoff Notes

- **Resume at:** Commit the Phase 3 code checkpoint, then run the committed-SHA
  dry run against the exact signed 70-ref handoff.
- **Watch out for:** Apply mode requires a clean tracked worktree and exact
  committed code SHA; `.opencode/` is unrelated and must remain untouched.

**tags:** ["data-first", "phase3", "measurements", "research"]
