# Session: Phase 4 Shadow Operations Correctness Remediation

## TL;DR

- **Worked On:** Corrected the uncommitted Phase 4 shadow-operation draft.
- **Outcome:** Implemented the local safety, lineage, canonical-artifact, state
  carryover, and production-V4-read boundaries. No Preview shadow artifact was
  materialized and no production surface was written.
- **Plan Contract:** `docs/plans/2026-08-26/phase4-shadow-operations.md`
- **Approval / Status:** User authorized the corrected contract; `In Progress`.
- **Blockers:** Preview rehearsal requires a user-controlled code commit because
  the immutable research CLIs reject uncommitted implementation identities.
- **Next:** Run the full local validation battery, commit the implementation,
  then execute the two identical Preview 2025 rehearsal runs.

## Context and Decisions

- The Phase 3 v3 candidate stays frozen. The score-model loader change handles
  existing Parquet representation only; it does not retrain or alter a model.
- Production V4 verification is read-only: production Neon establishes frozen
  run state/timing and production R2 supplies checksum-verified manifest/CSV.
- Weekly shadow artifacts are canonical per season/week. Final evidence is
  emitted only when outcomes and V4 coverage are complete; incomplete scoring
  creates diagnostic-only evidence.

## Work Completed

- Added exact candidate/config/ref verification and safe serialized sequence
  parsing for frozen models.
- Replaced the single-row historical state seed with full certified historical
  snapshot/terminal chronology.
- Added canonical freeze/score artifact paths, exact coverage and interval
  validation, and row-level evidence lineage.
- Added the production prediction-run manifest/CSV adapter and read-only frozen
  run verification path.
- Reworked the rehearsal to rebuild 2025 measurements/snapshots from Phase 1
  audit parent refs before oracle comparison.
- Updated the Phase 4 contract amendment and current authority status.

## Files Modified

- `src/cks_picks_cfb/ratings/shadow.py` - shared immutable shadow contracts.
- `src/cks_picks_cfb/ratings/score_models.py` - robust frozen-model reload.
- `scripts/pipeline/build_rating_shadow_freeze.py` - canonical pregame freeze.
- `scripts/pipeline/build_rating_shadow_score.py` - canonical complete scorer.
- `scripts/pipeline/run_rating_shadow_rehearsal.py` - reconstructed 2025 oracle.
- `tests/ratings/test_shadow.py` - focused regression coverage.

## Validation

- [x] `uv run pytest -q tests/ratings/test_shadow.py tests/ratings/test_score_models.py`
- [x] `uv run pytest -q tests/ratings`
- [x] Scoped `uv run ruff check …`
- [x] Read-only Preview frozen-model load (`locked_confirmation`)
- [x] Read-only Preview locked-2025 oracle (`1,522` rows, max delta `0.0`)
- [x] Full Python suite (`528 passed, 2 skipped`), contracts validation, strict
  MkDocs, and `git diff --check`
- [ ] Committed-code Preview rehearsal and byte-identical rerun

## Amendments and Blockers

- The plan amendment records the four mechanical defects discovered by review
  and their bounded corrections. The only remaining blocker is intentional:
  immutable Preview materialization requires a committed code identity.

## Handoff Notes

- **Resume at:** Run final local validation, then make the implementation commit
  before executing `run_rating_shadow_rehearsal.py` twice.
- **Watch out for:** Do not invoke a prospective Week 0/2026 freeze; it remains
  Phase 5 work and ineligible evidence.

**tags:** ["ratings", "phase4", "shadow", "lineage"]
