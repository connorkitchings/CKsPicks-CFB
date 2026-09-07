# Phase 4A: Context-Free Rating Selection

- **Status:** Approved
- **Created:** 2026-09-07
- **Planner:** Sol
- **Approval source:** User-approved 2026-09-06 resequencing contract, `docs/plans/2026-09-06/06-transformation-documentation-and-phase3-plus-resequence.md`.
- **Implementation log:** Pending Phase 3
- **Commit policy:** Separate plan and implementation/evidence commits; user executes Git operations.

## Goal

Select one simple, reproducible offense/defense rating prior and within-season
updater from the frozen Phase 3 core. Auxiliary context is excluded from every
rating prior and updater.

## Current State

This phase may begin only after a signed Phase 3 retained-core manifest is
published. Historical R1/R2 and prior-tournament winners remain diagnostic
evidence and are not candidates. The Phase 2e auxiliary manifest is not a
Phase 4A input.

## Interfaces and Safeguards

- CLI input: `--phase3-retained-uri`; reject unsigned or checksum/code-SHA
  mismatches, wrong roles, 2020, non-Preview routing, and incomplete parents.
- Publish version-1 rating-selection, team-state, attribution, uncertainty,
  fold-prediction, and retained-rating artifacts beneath the data-first
  research namespace.
- States record offense/defense values, uncertainty, prior and observed
  contributions, exposure, completed games, movement, effective time, fallback,
  and exact parent identities.
- Apply requires clean tracked state, matching committed code SHA, Preview, and
  immutable identities. No V4, production, publication, or Neon activation.

## Implementation Tasks

### Task 1 — Evaluate the bounded rating grid

- Evaluate the full eight-candidate grid: neutral or fixed annual `rho=0.60`
  prior crossed with exposure weighting or recency half-lives 2, 4, and 8.
- Build one shared offense/defense rating from combined margin and total
  evidence. Translate all candidates with fixed fold-local Ridge `alpha=10`.
- Use identical chronology and complete populations. Select only if pooled MAE
  improves at least 0.5% against the `rho=0.60` exposure reference, a 90%
  paired bootstrap interval excludes zero, coverage is equal, and no target
  season regresses by more than 5%. Prefer least complexity within 0.5%; retain
  the reference when no challenger passes.

### Task 2 — Certify point-in-time state behavior

- Estimate uncertainty chronologically and retain attribution, exposure,
  completed games, movement, effective time, and fallback reasons for every
  pregame state.
- Use eligible named FCS history when available; otherwise use a preceding-
  data-only partially pooled fallback, with maximum uncertainty and explicit
  cohort reporting.
- Verify first games, byes, sparse teams, FBS–FCS games, and the 2019→2021
  transition without losing a game.

## Validation

- Test exact Phase 3 parent membership, chronology, fold-local fitting,
  deterministic state identities, uncertainty/fallback behavior, equal
  candidate populations, bootstrap units, and all rejection paths.
- Run focused rating/Phase 3 tests plus the full warning-as-error Python suite,
  coverage, Ruff, contracts validation, strict MkDocs, V4/boundary checks, and
  `git diff --check`.

## Definition of Done

- [ ] All eight candidates are evaluated on identical populations and folds.
- [ ] One shared rating or the frozen reference is sealed with reproducible
  pregame state and uncertainty behavior.
- [ ] Auxiliary context is absent from every rating input.
- [ ] Artifacts, validation, documentation, and a session log are complete.

## Amendments

New priors/updaters, altered uncertainty semantics, rating-assisted opponent
adjustment, or any auxiliary-context input requires a revised approved plan.
