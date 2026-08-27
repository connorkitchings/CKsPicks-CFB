# R2 Redesigned Offseason-Prior Tournament

- **Status:** Approved
- **Created:** 2026-08-27
- **Planner:** Sol
- **Approval source:** User explicitly authorized implementation of the exact
  full-corpus successor-v2 plan in Codex on 2026-08-27.
- **Implementation log:** Pending fresh Terra task after R1 certification.
- **Commit policy:** Separate plan commit required after R1 and before implementation.

## Goal

Select and freeze an uncertainty-bearing offseason prior from the certified
full historical corpus without reading 2025. The selected prior must improve
Games 1–3 state/downstream prediction while preserving full-season quality and
remaining interpretable, point-in-time, and football-only.

## Current State

The repository validates a v1 sealed roster from caller-supplied fold metrics,
but does not generate candidate priors, states, predictions, models, or
attribution. The old roster is superseded by the approved mixed-method redesign.
R2 must remain blocked until the exact R1 report says
`tournaments_permitted: true`.

## Proposed Approach

Implement a versioned `successor_v2_tournaments_v2` prior roster and an
end-to-end selection runner. Each candidate is evaluated through the same fixed
Gaussian team-score head on expanding folds. Selection ends at 2024; 2025 is
reserved for the single end-to-end R4 locked confirmation.

## Scope

### Included

- Prior estimators, fold materialization, fixed evaluation head, metrics, uncertainty, diagnostics, immutable selection report, and frozen R2 winner.

### Excluded

- Within-season updater selection, final predictor selection, 2025 reads, 2026 outcomes, markets, and production activation.

## Affected Components and Contracts

- Replace the v1 tournament roster with a new immutable v2 contract while retaining v1 readability.
- R2 selection accepts exact R1 ref-set, coverage-report, and context-admission refs; it does not accept caller-supplied admission flags or metrics.
- Outputs include candidate prior states, fold predictions, fold metrics, model records, attribution/ranking diagnostics, and a checksummed selection manifest.

## Implementation Tasks

### Task 1 — Freeze the redesigned prior roster

**Changes:**

- Seal candidates: neutral population, fixed `rho=0.60`, partially pooled component/role transition, terminal EWMA half-lives 1/2/3, multi-output Ridge alphas 0.1/1/10/100, and context Ridge variants only when an immutable admission report passes.
- Define the fixed-rho baseline, 0.5% simplicity tie, 1% full-season non-regression, exact selection folds, allowed fields, and output schemas in configuration.
- Reject team categorical fields, markets, future observations, manual candidate additions, and 2025 partitions.

**Acceptance criteria:** The config SHA seals the complete roster and rules before any selection outcome is read.

### Task 2 — Implement transition estimators and uncertainty

**Changes:**

- Fit normal-transition parameters only on policy-approved one-year transitions.
- Apply the selected annual operator twice for 2019→2021 and never include that gap in normal-transition fitting.
- Partially pool component/role slopes toward a shared transition; carry parameter/residual uncertainty into prior variance.
- Compute EWMA weights as `0.5 ** (age / half_life)` over available preceding terminal states.
- Fit Ridge candidates within each training fold only; context columns are available only through the passing context report.
- Emit standardized component and team priors with positive uncertainty, population centering, provenance, and missing-team neutral fallback.

**Acceptance criteria:** Synthetic transitions recover direction, gap compounding, finite uncertainty, and deterministic missing-team behavior.

### Task 3 — Generate expanding-fold downstream evidence

**Changes:**

- Train only on seasons preceding each target in 2018, 2019, 2022, 2023, and 2024.
- Feed each candidate prior through the same fixed Gaussian team-score evaluation head; generate Games 1–3 and full-season margin/total predictions and state-forecast diagnostics.
- Record fold samples, MAE, bias, interval/calibration evidence, uncertainty, component attribution, top/bottom states, and movement diagnostics.
- Treat ranking plausibility as diagnostic only; finite states, positive uncertainty, valid centering, and lineage are structural gates.

**Acceptance criteria:** Every eligible candidate has exact complete fold coverage and no 2025 read.

### Task 4 — Select and freeze R2

**Changes:**

- Rank by combined Games 1–3 margin/total MAE.
- Require each full-season margin and total MAE to be no worse than 1.01 times fixed rho; choose lower complexity within 0.5% of the best eligible result.
- Publish immutable selected or failed reports binding R1/context/config/code identities and all candidate evidence.

**Acceptance criteria:** R3 can resolve exactly one passing R2 winner; failure produces diagnostics and no R3 authorization.

## Testing Strategy

- Unit-test estimators, pooled shrinkage, EWMA, Ridge isolation, uncertainty, gap compounding, context exclusion, ties, and non-regression.
- Integration-test fold chronology, exact R1 parents, generated metrics, manifest collisions, and hard rejection of 2025/2020/markets/team IDs.
- Run ratings/data/V4 boundary regressions, full pytest/coverage, scoped Ruff, contracts, strict MkDocs, CLI smoke, and `git diff --check`.

## Risks and Edge Cases

- Context remains diagnostic-only unless all admission evidence passes.
- Sparse/new teams fall back to population priors and must not be silently dropped.
- No R2 result may be revised after selection outcomes are inspected; material defects require a new versioned tournament contract.

## Definition of Done

- [ ] R1 is certified and pinned.
- [ ] The redesigned roster and estimator implementations are frozen and tested.
- [ ] Complete selection-fold artifacts and an immutable selected/failed report exist.
- [ ] No 2025, 2026 outcome, market, production, or V4 path was read or changed.
- [ ] Required validation and implementation log are complete; status is `Implemented`.

## Amendments

Candidate, fold, metric, gate, or estimator changes after outcome inspection
require a new plan and tournament version.
