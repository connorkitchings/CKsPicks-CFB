# Session: V5 Rating Materializer and Tournament

## TL;DR

- **Worked On:** Continued the approved V5-03A materializer and no-write
  tournament checkpoint from its existing working-tree implementation.
- **Outcome:** The full 60-candidate fixture now completes deterministically,
  with chronology-safe priors, canonical partition plans, and warning-clean
  outputs. The contract remains **In Progress** pending the complete
  repository validation set and a user-controlled code commit before any
  Preview preflight.
- **Plan Contract:** `docs/plans/2026-09-16/01-v5-rating-materializer-and-tournament.md`
- **Approval / Status:** User explicitly authorized implementation on
  2026-09-16; Contract 03A is In Progress.
- **Blockers:** The retry dry run exposed a Pandas all-null concatenation
  warning while reading R6 snapshots. The warning-safe stream repair requires
  a new committed SHA and fresh no-write identity.
- **Next:** Have the user commit the warning-safe stream repair, regression
  test, and this log; then rerun the deterministic Preview dry run under the
  new SHA.

## Context and Decisions

- The only permissible runtime parents remain R6 possession measurements
  `possession-v1-measurements-20260915-18fb0aa-r6` and Repair v2.
- Contract 03B remains out of scope: no R2 apply, retained-rating manifest,
  independent verifier, idempotency run, catalog/Neon, production, V4, or
  serving change occurred.
- The full tournament test exposed a seasonless prior lookup that allowed a
  later season's prior to overwrite an earlier one. State lookup keys now bind
  `season`, `unit_role`, and `team`, preserving chronological isolation and
  first-season FCS fallback behavior.

## Work Completed

- Normalized single-key output partitions to tuple keys, preserving ordered
  deterministic plans for priors and Kalman noise fits.
- Filtered learned-prior context to the target season's admitted prefix, so
  future-only rows cannot alter earlier fallbacks.
- Replaced warning-prone all-null candidate concatenation with stable canonical
  partition construction and aligned optional output-column dtypes before
  retained-frame concatenation.
- Vectorized the unchanged 2,000-replicate hierarchical bootstrap at the
  season/week/game levels; it remains deterministic while allowing the 60-grid
  fixture to finish promptly.
- Removed unused state construction and fixed scoped Ruff findings.

## Validation

- [x] Materializer and pure-rating suite with warnings as errors — 31 passed.
- [x] Possession measurement and verifier regressions with warnings as errors — 16 passed.
- [x] Documentation-authority regression with warnings as errors — 32 passed.
- [x] Scoped Ruff, Python compile, and runner `--help` checks.
- [x] `contracts/validation.py`, `make contracts-check`, and strict MkDocs build.
- [x] Full warning-as-error suite — 920 passed, 2 skipped (rerun after the
  warning-safe stream repair).
- [ ] `git diff --check` after this failure/repair log update.

## Amendments and Blockers

- The bootstrap and concatenation changes are mechanical performance and
  warning-safety repairs: they preserve the sealed parents, registry, folds,
  gates, schemas, and no-write boundary.
- No material contract amendment is required.
- The first read-only Preview attempt used
  `possession-v1-ratings-20260916-7f3b3f5-03a` at
  `2026-09-16T17:13:53Z`. It failed during adjusted-history audit setup with a
  positional argument passed to the keyword-only `storage` parameter; it did
  not reach tournament output or apply/write code. The call now uses
  `storage=storage`. This failure is not preflight evidence and that identity
  must never be reused.
- The retry used `possession-v1-ratings-20260916-4903017-03a` at
  `2026-09-16T18:04:39Z`. It passed parent loading and began the bounded
  adjusted-history audit, but emitted a Pandas FutureWarning while combining
  the R6 snapshot partitions. It was stopped before tournament output and
  cannot serve as reviewed preflight evidence. `_concat_frames` now normalizes
  optional mixed-null columns before concat; focused coverage asserts that the
  path is warning-safe. This identity must never be reused.

## Handoff Notes

- **Resume at:** Run final validation, inspect the complete diff, and request a
  user-controlled code/documentation commit. Then choose a new SHA-bound
  Preview dry-run identity and inspect its deterministic evidence.
- **Watch out for:** Do not invoke `--apply` or proceed to 03B before the clean
  committed checkpoint and reviewed preflight evidence exist.

**tags:** ["v5", "ratings", "possession", "research", "preview"]
