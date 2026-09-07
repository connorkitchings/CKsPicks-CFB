# Phase 4B: Target-Context Selection

- **Status:** Approved
- **Created:** 2026-09-07
- **Planner:** Sol
- **Approval source:** User-approved 2026-09-06 resequencing contract, `docs/plans/2026-09-06/06-transformation-documentation-and-phase3-plus-resequence.md`.
- **Implementation log:** Pending Phase 4A
- **Commit policy:** Separate plan and implementation/evidence commits; user executes Git operations.

## Goal

Starting from the frozen Phase 4A rating, select at most one context family for
margin and at most one for total. Context remains outside the rating and is
evaluated through a frozen simple forecast bridge.

## Current State

This phase requires the signed Phase 4A rating, the signed Phase 3 retained
core, and the Phase 2e reconstructed-only manifest:

`artifacts/research/data-first-football-v1/phase2/auxiliary/2026-09-07T0016Z-phase2e-auxiliary-v1/eligibility-manifest.json`

Its SHA-256 is
`d06ed3968a7bb6ec7ba97212aa2063068c253f26202e810c921b044006ab13ad`. It is
research-only and activation-ineligible. Reconstructed market references are
excluded entirely.

## Interfaces and Safeguards

- CLI inputs: `--phase4-rating-uri` and `--auxiliary-eligibility-uri`; reject
  unsigned, wrong-role, checksum/code-SHA-mismatched, or activation-eligible
  claims.
- Freeze the Phase 4A Ridge `alpha=10` translation head as the canonical bridge.
- Publish version-1 target-context selection, prediction, attribution,
  coverage/fallback, and retained-baseline manifests in Preview only.
- Fit every transform, imputation, and replacement from the training fold only.
  Require `poll_week < game_week`, structural recruiting/roster fallbacks,
  explicit missing indicators, and complete population retention.

## Implementation Tasks

### Task 1 — Evaluate one family at a time

- Test field position, pace, turnovers, recruiting, returning production,
  coaching, roster continuity, and strictly lagged AP/Coaches polls independently
  for margin and total.
- Retain a family only if its target pooled MAE improves at least 0.5%, its 90%
  paired bootstrap interval excludes zero, coverage does not decline, and no
  validation season regresses by more than 5%.
- Select the fewest-feature family within 0.5% of the best passing result; do
  not stack families, re-open rating selection, or conduct post-result searches.

### Task 2 — Freeze simple target baselines

- Seal margin and total baselines with the Phase 4A rating, selected context or
  explicit no-context outcome, exact inputs, folds, metrics, fallbacks,
  exclusions, bootstrap seed, and activation authorization set false.
- Report all candidates and complete cohorts, including missing/poll/roster
  fallbacks. Do not pass context into the rating state.

## Validation

- Test parent identity, fold-local transforms, ranking lag, missing indicators,
  structural fallbacks, equal populations, thresholds, deterministic manifests,
  immutable collisions, and market exclusion.
- Run focused Phase 2e/Phase 3/rating tests plus full warning-as-error Python,
  coverage, Ruff, contracts validation, strict MkDocs, V4/boundary checks, and
  `git diff --check`.

## Definition of Done

- [ ] Each target retains no more than one context family.
- [ ] Rating states remain context-free and every game remains represented.
- [ ] Frozen simple target baselines are reproducible and research-only.
- [ ] Artifacts, validation, documentation, and a session log are complete.

## Amendments

Context stacking, additional families, altered bridge/folds/thresholds, market
inputs, or rating-context interaction requires a revised approved plan.
