# Phase 4A: Context-Free Rating Selection

- **Status:** Implemented
- **Created:** 2026-09-07
- **Planner:** Sol
- **Approval source:** User-approved 2026-09-06 resequencing contract, `docs/plans/2026-09-06/06-transformation-documentation-and-phase3-plus-resequence.md`.
- **Implementation log:** `session_logs/2026-09-08/01-phase3-closure-and-phase4a-rating-selection.md`, `session_logs/2026-09-08/02-phase4a-rating-selection-completion.md`
- **Commit policy:** Separate plan and implementation/evidence commits; user executes Git operations.
- **Completed:** 2026-09-08. Selected candidate: `rho_0_60__exposure` (frozen reference). Manifest: `artifacts/research/data-first-football-v1/phase4a/runs/phase4a-v1-20260908T1500Z/retained-rating-manifest.json`, SHA `af9e66af67f26155ab74d1acd1947f72add7307203ae09bf1853856696e27612`.

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

- [x] All eight candidates are evaluated on identical populations and folds.
- [x] One shared rating or the frozen reference is sealed with reproducible
  pregame state and uncertainty behavior.
- [x] Auxiliary context is absent from every rating input.
- [x] Artifacts, validation, documentation, and a session log are complete.

## Amendments

New priors/updaters, altered uncertainty semantics, rating-assisted opponent
adjustment, or any auxiliary-context input requires a revised approved plan.

### 2026-09-08 implementation amendment — bounded numerical execution

The diagnostic-only Preview dry runs established that the approved rating
values remain approximately within -3 to +3. The observed Ridge overflow came
from pandas nullable `Float64` feature and target columns becoming NumPy
`object` matrices at the fold translator boundary, not from rating semantics.
Phase 4A now explicitly converts standardized training features, validation
features, and targets to contiguous native `float64` arrays before fitting or
prediction. The established `0.05` scale floor and range guard remain in
place.

Every `RuntimeWarning` or floating-point exception raised during Ridge fitting
or prediction is now a contextual `Phase4AError`; matrices, coefficients,
intercepts, predictions, absolute errors, and attribution evidence must all be
finite before artifact creation. The independent verifier repeats the evidence
and coefficient checks. This is an execution-boundary correction only: it does
not alter candidates, rating values, chronology, alpha, selection gates,
schemas, clipping policy, or activation boundary. Only a warning-free run of
the corrected committed code may determine the retained candidate.

### 2026-09-08 implementation amendment — user-authorized analytic posterior

The user's 2026-09-08 instruction to implement this contract authorizes this
bounded amendment. It resolves the remaining implementation choices without
changing the phase boundary:

- Evaluate exactly these eight IDs: `neutral__exposure`,
  `neutral__half_life_2`, `neutral__half_life_4`,
  `neutral__half_life_8`, `rho_0_60__exposure`,
  `rho_0_60__half_life_2`, `rho_0_60__half_life_4`, and
  `rho_0_60__half_life_8`. The `rho_0_60__exposure` row is the frozen
  selection reference.
- Use the Phase 3 EPA-only adjusted measurement only. Each candidate applies
  its history weighting, then the same four-iteration opponent adjustment;
  there is no rating-assisted second adjustment. Standardize each season from
  terminal states of strictly preceding permitted seasons, with fallback
  center `0`, scale `0.15`, and scale floor `0.05`.
- Use an analytic posterior: neutral annual priors reset to mean `0`, variance
  `1`; fixed-`rho` priors carry terminal state with `rho=0.60`, including
  two-year 2019-to-2021 decay. An evidence contribution of `e` has precision
  `e / 100`; posterior variance is `1 / (1/prior_variance + e/100)`. No
  residual floor or volatility model is introduced. Overall rating is the mean
  of offense and sign-reversed defense, with propagated analytic uncertainty.
- Named FCS teams use their own eligible history. An unseen FCS team uses a
  preceding-data-only role cohort partially pooled against the same neutral
  prior and carries maximum available training-fold uncertainty; an empty
  cohort uses neutral state. States must expose the cohort and fallback reason.
- Translate pregame states with separate fold-local, standardized Ridge
  (`alpha=10`) heads for margin and total. Validation seasons are 2018, 2019,
  2021–2025, with all fitting restricted to preceding seasons. Rank pooled
  mean absolute error with equal target weight. Challengers require at least
  0.5% pooled improvement, equal coverage, no target-season regression above
  5%, and a positive 90% paired season-then-week bootstrap lower bound (2,000
  draws, deterministic 20260908 seed). Within 0.5% of the best passer, choose
  fewer mechanisms; otherwise retain the reference.
- Use the same `0.05` lower scale bound for fold-local rating-feature
  standardization. This prevents an all-neutral or near-constant early fold
  from manufacturing numerically explosive Ridge inputs; it does not clip or
  otherwise transform rating values.
- Apply artifacts are Preview-only under
  `artifacts/research/data-first-football-v1/phase4a/runs/<run-id>/` and bind
  the signed Phase 3 manifest plus its exact Phase 2d parent chain. Required
  artifacts are versioned long rating states, wide team states, fold
  predictions, attribution/coverage diagnostics, and a signed retained-rating
  manifest. They explicitly deny production activation, Neon activation, and
  publication.
