# Session: Phase 4 Shadow Operations Correctness Remediation

## TL;DR

- **Worked On:** Corrected the uncommitted Phase 4 shadow-operation draft.
- **Outcome:** Implemented and rehearsed the local safety, lineage,
  canonical-artifact, state carryover, and production-V4-read boundaries. The
  full-2025 Preview rehearsal and byte-identical rerun passed; no production
  surface was written.
- **Plan Contract:** `docs/plans/2026-08-26/phase4-shadow-operations.md`
- **Approval / Status:** User authorized the corrected contract; `Implemented`.
- **Blockers:** None.
- **Next:** Draft and approve the separate Phase 5 Week 1 operations contract;
  do not create an actual 2026 freeze before then.

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
- `src/cks_picks_cfb/data/lake.py` - idempotent immutable partition comparison.
- `tests/ratings/test_shadow.py` - focused regression coverage.
- `tests/test_data_lake.py` - NumPy-partition retry regression coverage.

## Validation

- [x] `uv run pytest -q tests/ratings/test_shadow.py tests/ratings/test_score_models.py`
- [x] `uv run pytest -q tests/ratings`
- [x] Scoped `uv run ruff check …`
- [x] Read-only Preview frozen-model load (`locked_confirmation`)
- [x] Read-only Preview locked-2025 oracle (`1,522` rows, max delta `0.0`)
- [x] Full Python suite (`529 passed, 2 skipped`), contracts validation, strict
  MkDocs, and `git diff --check`
- [x] Committed-code Preview rehearsal and byte-identical rerun: 15/15 weeks,
  `1,522` oracle rows, max delta `9.947598300641403e-14`, summary SHA-256
  `b755b585914d2f36b6ff93edba8eb520c500cd0e6ea416a58f47ee4fbdc33e31`

## Amendments and Blockers

- The plan amendment records the four mechanical defects discovered by review
  and their bounded corrections. The only remaining blocker is intentional:
  immutable Preview materialization requires a committed code identity.
- First Preview rehearsal `2026-08-26T2107Z-phase4-rehearsal` failed closed on
  the historical V4 `spread`/shadow `margin` label mismatch. It published no
  successful evidence or summary. The follow-up normalizes the historical
  replay boundary and writes diagnostics for incomplete rehearsal scores.
- A read-only all-week preflight then rebuilt 19,786 observations and 19,812
  snapshots. All 15 2025 weeks had complete outcomes/V4 coverage and matched
  their frozen oracle rows within `9.95e-14`.
- Added prospective V4 identity pins, cancellation waivers, Preview catalog
  preflight, canonical partial-artifact rejection, and explicit Week 1
  eligibility declaration before the next materialization attempt.
- A fully cancelled slate is now diagnostic-only rather than producing an
  empty evidence dataset. This retains cancellation traceability without
  recording zero-row scored evidence.
- The committed rehearsal exposed a generic immutable-lake retry defect: a
  pandas/NumPy partition scalar serializes as a string in the manifest but was
  compared to its in-memory scalar on rerun. Canonical JSON comparison now
  makes matching retries idempotent; the interrupted run published no summary
  and therefore no successful rehearsal evidence.
- The rehearsal code-identity guard now explicitly includes the shared lake
  writer used for its immutable prediction and evidence artifacts.
- Successful run `2026-08-26T2140Z-phase4-rehearsal-v3` used committed code
  `b8103350899080994eeca6e39a9731790a61c0b9`, the frozen model ref
  `071f4de17b4b351e74e0a670` (SHA-256 `b941a173…f86d3b`), and summary URI
  `artifacts/research/rating-successor/shadow-v1/584f3f5cd43653745b4f3e4eed4f5437444fb5997366e574f22f3bf05ec4172e/rehearsal/runs/2026-08-26T2140Z-phase4-rehearsal-v3/summary.json`.
  Both invocations produced the same SHA; the summary contains every weekly
  prediction/evidence ref and checksum.

## Handoff Notes

- **Resume at:** Create the separate Phase 5 Week 1 operations contract.
- **Watch out for:** Do not invoke a prospective Week 0/2026 freeze; actual
  Week 1 evidence remains Phase 5 work.

**tags:** ["ratings", "phase4", "shadow", "lineage"]
