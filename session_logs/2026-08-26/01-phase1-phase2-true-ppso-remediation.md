# Session: Phase 1/2 True-PPSO Remediation and Phase 3 v3

## TL;DR

- **Worked On:** Implemented the local, isolated Phase 1 true-PPSO v3 code and
  contract.
- **Outcome:** Ready for the required user-controlled commit before Preview
  materialization; no R2 research artifact, production path, V4 input, Neon
  resource, market input, or Phase 4 operation was touched.
- **Plan Contract:** `docs/plans/2026-08-26/phase1-phase2-true-ppso-remediation-and-phase3-v3.md`
- **Approval / Status:** User explicitly authorized implementation on
  2026-08-26; contract remains `In Progress`.
- **Blockers:** None. The next gate is intentional commit identity pinning.
- **Next:** Commit the listed Phase 1 v3 code/configuration, then materialize
  the immutable Preview Phase 1 artifacts and require a same-stamp rerun.

## Context and Decisions

- The correction is contained in `cks_picks_cfb.ratings`; shared drive
  aggregation and all V4/production paths remain unchanged.
- v3 reconstructs PPSO from ordered canonical `offense_score` and
  `defense_score` streams. Outcome points validate final scores only and never
  form or replace a drive numerator.
- A malformed, regressing, out-of-range, or final-score-mismatched team stream
  quarantines that offense PPSO row and the paired opponent-defense row with
  `score_stream_mismatch`.
- v2 behavior remains versioned and reproducible. v3 alone emits the new
  observation/snapshot/terminal schema identities.

## Work Completed

- Added `measurement_baseline_v3` with a dedicated Preview research prefix and
  explicit true-score PPSO policy.
- Added deterministic score-stream reconstruction, per-season reconciliation
  evidence, no-clipping `[0, 8]` validation, symmetric quarantine, and terminal
  PPSO mean gate.
- Added dynamic schema selection and commit-identity checking for the exact
  supplied measurement configuration.
- Added unit and local immutable-storage integration coverage for true drive
  points, Boolean-score exclusion, malformed/out-of-range values, quarantine,
  unchanged non-PPSO measures, new schemas, and byte-identical reruns.

## Files Modified

- `conf/ratings/measurement_baseline_v3.yaml` — v3 Phase 1 contract.
- `src/cks_picks_cfb/ratings/{observations,contracts,audit,snapshots}.py` —
  isolated score reconstruction, versioned schemas, and gates.
- `scripts/pipeline/build_rating_measurements.py` — version-aware code identity
  and season-scoped reconciliation gate.
- `tests/ratings/{helpers,test_observations,test_contracts,test_cli}.py` —
  regression and deterministic Preview integration coverage.
- `docs/plans/2026-08-26/...`, `docs/plans/index.md` — approved execution
  contract and authority entry.

## Validation

- [x] Focused Phase 1 tests and local immutable-storage v3 integration:
  `59 passed`.
- [x] Complete ratings suite: `100 passed`.
- [x] Scoped Ruff format/check.
- [x] `make contracts-check`.
- [x] `uv run mkdocs build --strict`.
- [x] `git diff --check`.
- [ ] Full Python suite after the code/configuration commit and staged
  materialization.

## Amendments and Blockers

The user-specified per-season 94% reconciliation gate is enforced by the
season-scoped materializer rather than a single-season unit builder, allowing
tests to verify individual mismatch quarantines while production execution
still fails closed across the full historical set.

The first committed v3 Preview attempt at
`2026-08-26T1225Z-phase1-ppso-v3` failed before any successful refs were
published: 2021 reconciliation was below 94%. The failure identified a
mechanical final-score audit defect (trailing score marker rather than
cumulative maximum). The local correction now reproduces the expected 2021
rate of `0.9494535519125683`; it will be committed and retried under a fresh
run ID without changing parents, thresholds, or model design.

## Handoff Notes

- **Resume at:** Commit the staged Phase 1 v3 code/configuration, obtain the
  commit SHA, then invoke the Preview-only measurement materializer with that
  SHA and its new immutable v3 research prefix.
- **Watch out for:** Do not materialize before the commit. Do not alter
  `features/aggregations/drives.py`, V4, production R2, Neon, the catalog,
  public APIs, or market feature paths.

**tags:** ["ratings", "phase1", "phase2", "ppso", "preview"]
