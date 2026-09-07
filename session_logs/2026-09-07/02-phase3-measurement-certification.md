# Session: Phase 3 Measurement Certification and Core Selection

## TL;DR

- **Worked On:** Implementing the approved Preview-only Phase 3 measurement
  certification and shared-core selection contract.
- **Outcome:** Phase 3 parent-validation, identity, candidate-decision, and
  ten-season configuration foundation are ready for a code checkpoint.
- **Plan Contract:** `docs/plans/2026-09-07/01-phase3-measurement-certification-and-core-selection.md`
- **Approval / Status:** User explicitly authorized implementation on
  2026-09-07; contract is `In Progress`.
- **Blockers:** None identified at session start.
- **Next:** User commits this checkpoint; then run the committed-code dry run
  before extending the materializer and attempting any apply-mode R2 write.

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

## Files Modified

- `docs/plans/2026-09-07/01-phase3-measurement-certification-and-core-selection.md` - marked implementation in progress.
- `session_logs/2026-09-07/02-phase3-measurement-certification.md` - implementation record.
- `src/cks_picks_cfb/data/data_first_phase3.py` - Phase 3 pure contracts.
- `conf/research/data_first_football_v1/phase3_measurement_core_v1.yaml` - ten-season measurement policy.
- `scripts/research/run_data_first_phase3.py` - Preview-only parent-validation CLI.
- `tests/test_data_first_phase3.py` - Phase 3 contract coverage.

## Validation

- [x] Focused Phase 2/3 and schema tests: 21 passed.
- [ ] Full warning-as-error Python suite with coverage
- [x] Ruff for changed Phase 3 code.
- [ ] Contracts validation, strict MkDocs, V4/boundary checks
- [x] `git diff --check`

## Amendments and Blockers

- None.

## Handoff Notes

- **Resume at:** Implement Phase 3 pure contracts and Preview-only runner.
- **Watch out for:** Apply mode requires a clean tracked worktree and exact
  committed code SHA; `.opencode/` is unrelated and must remain untouched.

**tags:** ["data-first", "phase3", "measurements", "research"]
