# R3 Mixed State-Update Tournament

- **Status:** Approved
- **Created:** 2026-08-27
- **Planner:** Sol
- **Approval source:** User explicitly authorized implementation of the exact
  full-corpus successor-v2 plan in Codex on 2026-08-27.
- **Implementation log:** Pending fresh Terra task after R2 selection.
- **Commit policy:** Separate plan commit required after R2 and before implementation.

## Goal

Select and freeze a continuous within-season updater across Bayesian,
recency-weighted, score-driven, and constrained ML families while preserving
the R2 offseason prior, uncertainty, point-in-time chronology, and interpretable
offense/defense/overall state outputs.

## Current State

The existing Phase baseline implements one fixed-precision update. The current
successor selector only validates caller-produced metrics; Kalman, robust,
recency, Glicko-style, and ML transition engines do not exist. R3 is blocked
unless R2 publishes one passing immutable winner.

## Proposed Approach

Run every updater sequentially over identical pregame measurement evidence and
evaluate it through the same fixed Gaussian team-score head. Selection uses
2017–2019 and 2021–2024 only. R3 locks one updater without reading 2025.

## Scope

### Included

- Comparable state-updater implementations, uncertainty/provenance schemas, expanding-fold predictions, metrics, diagnostics, selection, and frozen R3 manifest.

### Excluded

- Predictor-family selection, 2025 locked confirmation, 2026 outcomes, markets, V4 changes, and production activation.

## Affected Components and Contracts

- The v2 tournament config seals fixed precision; Kalman process SD 0.025/0.05/0.10/0.20; robust Kalman SD 0.10 caps 2/3; recency half-lives 2/4/8; Glicko-style RD inflation 0.05/0.10; and one shallow CatBoost transition candidate.
- Each candidate emits the same component/team-state contract, including mean, SD, prior/observed weights, exposures, timestamps, quality flags, and exact parent identity.
- R3 consumes the immutable R2 winner and generated R1 evidence; no caller-supplied fold metrics are authoritative.

## Implementation Tasks

### Task 1 — Implement common sequential state interfaces

**Changes:**

- Define a point-in-time updater interface that consumes one frozen prior and ordered pregame measurement innovations and emits component plus offense/defense/overall states before each game.
- Enforce identical missingness, neutral fallback, opponent-adjusted inputs, state aggregation, uncertainty, and lineage fields across families.
- Reject future evidence, team-ID features, markets, and non-admitted context.

**Acceptance criteria:** All candidates produce schema-compatible, kickoff-ordered states with positive uncertainty.

### Task 2 — Implement the mixed updater roster

**Changes:**

- Preserve the current fixed-precision exposure updater as baseline.
- Add Kalman process variance before each update; add robust variants that cap standardized innovations at 2 or 3.
- Add exponential game-recency weighting with the sealed half-lives.
- Add score-driven offense/defense Glicko-style updates with rating-deviation inflation and contraction based on standardized own/opponent score innovations.
- Add one shallow CatBoost next-state transition model trained fold-locally from prior state, measurement innovations, exposure, uncertainty, and admitted football context. Derive uncertainty from cross-fitted residual dispersion; never use team identity.

**Acceptance criteria:** Synthetic sequential tests prove contraction, responsiveness, robust-outlier behavior, bye handling, and deterministic missing-team fallback.

### Task 3 — Generate temporal evaluation evidence

**Changes:**

- Evaluate target seasons 2017, 2018, 2019, 2021, 2022, 2023, and 2024 using training seasons that strictly precede each target.
- Use the fixed Gaussian team-score head for every updater.
- Emit early/full margin and total metrics, calibration/interval evidence, state stability/responsiveness, movement, rankings, attribution, and exact fold lineage.
- Ranking plausibility is diagnostic; finite values, positive uncertainty, contraction, chronology, and calibration are hard gates.

**Acceptance criteria:** Complete paired fold coverage exists for every candidate without 2025 access.

### Task 4 — Select and freeze R3

**Changes:**

- Rank by combined full-season margin/total MAE.
- Require Games 1–3 margin and total MAE within 1% of the fixed updater; choose lower complexity within 0.5% of the best eligible result.
- Publish an immutable selected or failed report binding R1, R2, config, code, context, states, predictions, and metrics.

**Acceptance criteria:** R4 resolves exactly one passing updater; a failed tournament cannot authorize prediction work.

## Testing Strategy

- Unit-test each updater, uncertainty, innovation caps, RD behavior, recency, CatBoost feature boundary, byes, cancellations, missing teams, and deterministic ordering.
- Integration-test chronological folds, exact R2 pinning, common output schemas, generated metrics, collision behavior, and 2025/2020/market rejection.
- Run ratings/data/V4 boundary regressions, full pytest/coverage, scoped Ruff, contracts, strict MkDocs, CLI smoke, and `git diff --check`.

## Risks and Edge Cases

- Glicko-style and ML candidates remain challengers, not alternate production paths.
- Sparse evidence must increase uncertainty or retain prior weight rather than fabricate observations.
- Any post-result roster or gate change requires a new tournament version.

## Definition of Done

- [ ] R2 winner is pinned and verified.
- [ ] Every updater is implemented behind the common contract and passes focused tests.
- [ ] Complete selection artifacts and an immutable selected/failed report exist without 2025 access.
- [ ] Required regression/quality gates and implementation log are complete; status is `Implemented`.

## Amendments

Changes to updater families, hyperparameters, folds, gates, common schemas, or
selection metrics after outcome inspection require a new Sol contract.
