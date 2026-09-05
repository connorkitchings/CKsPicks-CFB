# R4 Structured Predictor and Candidate-v2 Freeze

- **Status:** Superseded 2026-09-05 by `docs/plans/2026-09-05/00-repository-architecture-and-documentation-alignment.md`
- **Created:** 2026-08-27
- **Planner:** Sol
- **Approval source:** User explicitly authorized implementation of the exact
  full-corpus successor-v2 plan in Codex on 2026-08-27.
- **Implementation log:** Pending fresh Terra task after R3 selection.
- **Commit policy:** Separate plan commit required after R3 and before implementation.

## Goal

> Historical planning evidence only. Do not implement this contract. Forecast
> development now follows the data-first audit, measurement, and simple-rating
> sequence; 2025 is development evidence in that new namespace.

Select a structured football predictor on data through 2024, freeze the entire
successor-v2 design, evaluate 2025 exactly once, and either publish a complete
candidate-v2 identity or a terminal failed report. V4 remains the unchanged
production champion and candidate v1 remains diagnostic-only.

## Current State

Existing rating code provides linear/NB2 score models and v1 selection helpers,
while the successor report CLI trusts caller-supplied metrics and pass booleans.
It does not implement direct bivariate or structured residual candidates, bind
an end-to-end design before 2025, enforce a one-time locked confirmation, or
materialize a candidate-v2 refit/manifest.

## Proposed Approach

Consume only the frozen R2 and R3 winners, generate cross-fitted selection
evidence through 2024, and freeze one end-to-end design manifest. A separate
locked-confirmation command derives every 2025 gate from exact refs and is
immutable for that design SHA. Passing designs refit unchanged on the full
permitted corpus and publish candidate v2; failures stop permanently.

## Scope

### Included

- Predictor/residual implementations, cross-fitted selection, candidate-v1/V4 comparisons, design freeze, one locked-2025 confirmation, refit, manifest, and prospective-lane identity.

### Excluded

- Production/Neon activation, public publication, market-feature selection, retrospective 2026 freezes, evidence transfer, and promotion.

## Affected Components and Contracts

- The v2 roster seals NB2 team scores, Gaussian linear team scores, direct bivariate Gaussian margin/total, Ridge residual over fixed NB2, and shallow CatBoost residual over fixed NB2.
- Replace trusted flags such as `--locked-2025-passed` with exact immutable refs and recomputed gates.
- Add immutable end-to-end design, locked-confirmation, prediction-bundle, refit-model, and candidate-manifest schemas that bind R1–R4 lineage.
- Split the authoritative interface into `select` and `locked-confirmation`; only the latter may read 2025.

## Implementation Tasks

### Task 1 — Implement the structured predictor roster

**Changes:**

- Reuse hardened NB2 and Gaussian team-score implementations behind the successor interface.
- Add direct bivariate Gaussian margin/total with shared residual covariance and positive-semidefinite uncertainty.
- Add cross-fitted Ridge and shallow CatBoost residuals over the fixed NB2 base. Use the existing V4 CatBoost grid but only state, uncertainty, pace, venue, weather, completed-game counts, and admitted football context.
- Reject team categorical memorization, markets, future observations, unadmitted context, and non-cross-fitted residual training.

**Acceptance criteria:** Every family emits paired margin/total/team-score predictions, covariance/intervals, provenance, and finite uncertainty under one schema.

### Task 2 — Generate and select through 2024

**Changes:**

- Generate expanding-fold predictions only from permitted seasons through 2024.
- Compute MAE, RMSE, bias, residual standardization, covariance/interval validity, calibration, season slices, Games 1–3 slices, and paired candidate-v1/V4 evidence where available.
- Apply seed 42 and exactly 2,000 paired bootstrap samples for combined Games 1–3 MAE versus candidate v1.
- Require existing quality gates, full-season non-regression, and a bootstrap upper 95% bound below zero; use the sealed 0.5% simplicity tie.

**Acceptance criteria:** One selected predictor or an immutable failed report exists, with no 2025 read.

### Task 3 — Freeze the end-to-end design

**Changes:**

- Publish an immutable design manifest binding R1 ref/coverage/cross-lineage reports, context decisions, R2/R3 winners, R4 family and features, all config/code SHAs, fold evidence, and the locked-test policy.
- Make the design SHA the sole namespace for locked confirmation. Reject changed parents, configs, code, features, or previously conflicting confirmation artifacts.

**Acceptance criteria:** The complete design is frozen before any 2025 partition is opened.

### Task 4 — Run one locked-2025 confirmation

**Changes:**

- A separate command reads the frozen design and exact 2025 refs, evaluates the unchanged pipeline once, and derives every pass/fail result from artifacts.
- Require finite/bias/calibration/interval gates, individual margin/total full-season non-regression within 1%, Games 1–3 paired evidence, complete game coverage, and production-isolation checks.
- Treat identical reruns as verification; any conflicting rerun or alternate candidate under the same design fails closed.

**Acceptance criteria:** Locked confirmation is immutable and one-time. Failure publishes terminal diagnostics and cannot return to R2–R4 selection.

### Task 5 — Refit and freeze candidate v2

**Changes:**

- After a passing locked test, refit the unchanged design on 2015–2019 and 2021–2025.
- Publish checksummed model/state/prediction bundles and a candidate-v2 manifest containing every R1–R4 parent, locked report, code/config SHA, and prospective-policy SHA.
- Set the first eligible prospective slate to the first normal-coverage slate frozen after the committed candidate implementation. Forbid candidate-v1 evidence transfer and retrospective freezes.

**Acceptance criteria:** A complete reproducible candidate-v2 identity exists only after all gates pass; it has no path to production activation.

## Testing Strategy

- Unit-test all families, covariance/interval behavior, residual cross-fitting, feature boundaries, bootstrap determinism, selection ties, and gate computation.
- Integration-test exact R1/R2/R3 pins, no-2025 selection, design freeze, one-time locked confirmation, immutable retries, failed-manifest prohibition, full refit, and candidate identity.
- Re-run ratings/data/ops/V4/production-write boundaries, full pytest/coverage, scoped Ruff, contracts, strict MkDocs, CLI smoke tests, web regressions, and `git diff --check`.

## Risks and Edge Cases

- 2025 is the single locked end-to-end confirmation; it must not be used to revise any upstream stage.
- Candidate-v1 and V4 comparisons are evidence only and never parents of candidate-v2 state estimation.
- Passing historical results do not authorize publication or promotion; O3 remains Preview-only until a separate promotion contract.

## Definition of Done

- [ ] R2 and R3 winners are pinned and verified.
- [ ] Selection through 2024 freezes one complete design or a failed report.
- [ ] 2025 is evaluated exactly once under that design and immutable evidence is published.
- [ ] Passing designs publish an unchanged full-corpus refit and complete candidate-v2 manifest; failures publish no candidate.
- [ ] Prospective policy forbids transfer/backdating and production remains unchanged.
- [ ] Required validation and implementation log are complete; status is `Implemented`.

## Amendments

Any post-selection change to candidate families, features, folds, gates,
locked-test semantics, refit behavior, or prospective identity requires a new
Sol contract and a new design generation.
