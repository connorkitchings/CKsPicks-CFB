# Phase 5: Final Spread and Total Selection

- **Status:** Approved
- **Created:** 2026-09-07
- **Planner:** Sol
- **Approval source:** User-approved 2026-09-06 resequencing contract, `docs/plans/2026-09-06/06-transformation-documentation-and-phase3-plus-resequence.md`.
- **Implementation log:** Pending Phase 4B
- **Commit policy:** Separate plan and implementation/evidence commits; user executes Git operations.

## Goal

Select one immutable spread formulation and one immutable total formulation, or
retain the corresponding frozen Phase 4B simple baseline. Historical NB2
results make no performance claim and do not enter selection without rebuild.

## Current State

This phase requires the signed Phase 4A retained rating and exact Phase 4B
target-baseline manifest. The Phase 4B context choice is frozen: context-free
ablations are diagnostic only and cannot reopen context selection. All historical
results through 2025 remain development evidence.

## Interfaces and Safeguards

- CLI inputs: `--phase4-rating-uri` and `--phase4b-context-uri`; reject
  unsigned/wrong-role/checksum-mismatched parents, 2020, future information,
  markets as features, duplicate games, nonfinite predictions, and silent row
  loss.
- Publish version-1 candidate registry, fold predictions, uncertainty and
  calibration diagnostics, selection report, retained spread/total manifests,
  and a separately identified market diagnostic in the Preview research namespace.
- Outputs use home-minus-away margin convention and record target, mean,
  uncertainty, coverage/fallback, cutoff, and exact parents.
- Apply requires Preview, clean tracked state, matching committed code SHA, and
  immutable identity. V4, Neon, publication, betting, and promotion are excluded.

## Implementation Tasks

### Task 1 — Evaluate the bounded candidate registry

- Compare rating-based Ridge margin/total, Ridge team scores, direct
  football-core Ridge, and a newly rebuilt NB2 score candidate.
- Fit Ridge alphas `{0.1, 1, 10, 100}` with training-fold-only
  standardization. NB2 must pass current-lineage, finite-mean, uncertainty,
  and complete-population gates before its performance is evaluated.
- Supply every candidate with the frozen target context. Evaluate identical
  chronological folds and game populations; select spread and total separately.

### Task 2 — Select and freeze final forecasts

- A challenger is eligible only when MAE and CRPS are within 1% of its simple
  reference and no season regresses by more than 5%. Claim a gain only at 0.5%
  or more with a 90% paired hierarchical bootstrap interval excluding zero.
- Prefer the simplest candidate within 0.5% of the best passing result. Retain
  the Phase 4B baseline when no challenger passes; do not broaden the registry
  after inspection.
- Freeze one spread and one total candidate/reference with complete lineage,
  uncertainty/calibration diagnostics, and prospective-freeze readiness.

### Task 3 — Publish post-selection market diagnostics

- After selection only, use reconstructed market references to report sign
  verification, quote coverage, forecast-versus-line error, and disagreement.
- This report cannot affect fitting, selection, promotion, CLV claims, or a
  prospective-evidence count.

## Validation

- Test parent membership, chronological/fold-local fitting, target/sign
  convention, population equality, NB2 gates, finite outputs, calibration,
  bootstrap units, thresholds, deterministic identities, and market separation.
- Run focused forecast/rating tests plus full warning-as-error Python, coverage,
  Ruff, contracts validation, strict MkDocs, V4/boundary checks, and
  `git diff --check`.

## Definition of Done

- [ ] Every candidate uses identical folds and admitted populations.
- [ ] One immutable spread and one immutable total candidate/reference is frozen.
- [ ] Market diagnostics are separate, reconstructed-only, and selection-neutral.
- [ ] Artifacts, validation, documentation, and a session log are complete.

## Amendments

New candidate families, grids, metrics, uncertainty behavior, context changes,
market-informed modeling, or promotion requires a revised approved plan.
