# Rating-Centric Successor: High-Level Implementation Roadmap

- **Status:** Approved
- **Created:** 2026-08-24
- **Planner:** Sol
- **Approval source:** User approved the proposed roadmap and explicitly requested its formalization on 2026-08-24.
- **Implementation log:** Each phase receives its own implementation log; this roadmap is sequencing authority, not a single Terra execution contract.
- **Commit policy:** Separate plan commit recommended because the roadmap governs multiple sessions and protected prospective evidence.

## Goal

Build a simple end-to-end rating-based challenger while V4 remains unchanged in
production. Preserve a credible 2026 promotion option, target the first eligible
Week 1 shadow slate only if safety gates pass, and evaluate direct margin and
total predictions.

Observable success means:

- V4 production behavior and rollback authority remain unchanged.
- A versioned measurement layer, uncertainty-bearing team state, structured
  predictor, and isolated shadow workflow are delivered through separate gates.
- One frozen candidate accumulates paired prospective evidence against V4
  without being tuned on outcomes it claims as protected.
- No production promotion occurs without six eligible full slates and a
  separate approved promotion contract.

## Current State

The repository has immutable Bronze/Silver/Gold lineage, broad team-game
aggregations, iterative measurement-level opponent adjustment, point-in-time
matchup assembly, reproducible V4 bundles, and fail-closed weekly operations.
It does not yet have a durable team-state interface, non-null predictive
uncertainty, or a research-only candidate freeze and scoring lifecycle.

V4 remains the 2026 production champion. Historical 2021–2025 outcomes are
development evidence for the successor, not an untouched test. Week 0 does not
count toward the six-slate prospective gate.

## Proposed Approach

Deliver a gated vertical slice before exploring sophisticated challengers:
measurement contract, simple team state, direct margin/total prediction,
isolated shadow operations, protected evidence, then attributable research and
promotion review. Each phase requires a dedicated decision-complete contract
and a fresh Terra task.

## Phase Sequence and Exit Gates

### Phase 0 — Preserve production and evidence integrity

- Keep V4 weights, routes, bundles, publication, weekly operations, Neon
  activation, and rollback selection unchanged.
- Isolate successor code, configuration, artifacts, and evaluation.
- Require candidate identity and pre-kickoff freeze controls in every later
  phase.

**Exit gate:** V4 regression and publication-boundary checks pass, and the
successor has no production activation path.

### Phase 1 — Measurement and opponent-adjustment foundation

- Audit 2021–2026 Gold coverage, effective times, exposures, missingness, and
  redundancy.
- Introduce a small versioned team-game measurement interface with explicit
  provenance and quality state.
- Apply opponent adjustment once at the measurement layer.

**Exit gate:** Reproducible adjusted measurements pass coverage, lineage,
redundancy, point-in-time, and no-double-counting checks. No estimator exists in
this phase.

### Phase 2 — Minimum viable team-state baseline

- Select the simplest viable estimator in the Phase 2 contract.
- Produce pregame offense, defense, overall-quality, and uncertainty-bearing
  state with continuous prior-to-evidence credibility.
- Emit immutable historical state snapshots with exact lineage.

**Exit gate:** Every historical matchup reproduces both pregame states without
future data, and uncertainty contracts plausibly with credible exposure.

### Phase 3 — Structured margin and total prediction

- Map two frozen states plus legitimate venue and game context directly to
  expected margin and total.
- Emit non-null uncertainty for both targets; exclude residual ML and markets.
- Compare against V4 on the same temporal game set and pre-register prospective
  gates.

**Exit gate:** Candidate v1 has a frozen identity, design/configuration hash,
historical report, reproducible predictions, and declared eligibility window.

### Phase 4 — Isolated shadow operations

- Build a research-only pregame state/prediction/freeze workflow and paired
  postgame scoring.
- Keep artifacts outside V4 bundles, Neon activation, publication, and rollback
  authority.
- Fail closed on coverage, timing, duplication, and integrity failures.

**Exit gate:** Pregame freeze and postgame scoring rehearsals pass. Week 1 is
eligible only if Phases 1–4 finish without weakened gates.

### Phase 5 — Protected prospective evidence

- Run the frozen baseline unchanged across normal-coverage full slates.
- Evaluate rating behavior, prediction quality, calibration, then authentic
  timestamped market value.
- Preserve paired V4 coverage and record every exclusion or operational issue.

**Exit gate:** Candidate v1 accumulates six eligible completed full slates.

### Phase 6 — Attributable challenger research

- After baseline freeze, evaluate estimator families, priors, special teams,
  uncertainty alternatives, rating-assisted adjustment, and optional residual
  ML as separate changes.
- Assign every revision a new identity and later untouched window.

**Exit gate:** A challenger can replace the baseline only through predeclared
historical gates and a fresh prospective-evidence contract.

### Phase 7 — Promotion review and operationalization

- Require six eligible slates for one unchanged candidate.
- Review paired V4 evidence, calibration, reproducibility, operational rehearsal,
  fail-closed behavior, and rollback proof.
- Put every production interface or activation change in a separate contract.

**Exit gate:** Explicit user approval of a promotion contract; V4 remains the
fallback and promotion is never automatic.

## Scope Boundaries

### Included

- Internal research contracts for adjusted measurements, team-state snapshots,
  direct margin/total predictions, candidate identity, shadow manifests, and
  paired scoring.
- Historical expanding temporal development and protected 2026 shadow evidence.

### Excluded

- Changes to V4, public web APIs, production database schemas, publication,
  weekly rollback authority, or model activation before Phase 7 approval.
- Residual ML, rating-assisted adjustment, and special-teams rating components
  in the first baseline.

## Validation Strategy

- Point-in-time and leakage tests at measurement, state, and prediction
  boundaries.
- Schema, checksum, provenance, missingness, and schedule-coverage tests.
- Expanding temporal evaluation for 2021–2025, excluding 2020 and limiting 2019
  to approved prior lineage.
- Stability, responsiveness, uncertainty contraction, calibration, bias,
  MAE/RMSE, and paired V4 comparisons.
- Shadow integration tests for immutable freeze, reproducible scoring,
  isolation, and fail-closed behavior.
- Existing V4, publication, contracts, Python quality, and documentation gates.

## Assumptions and Defaults

- The objective is to earn a 2026 promotion option, not promise promotion.
- Week 1 is conditional; Week 0 production and evidence integrity take priority.
- The first predictor models margin and total directly.
- Separate gated contracts govern every phase.
- Phase 1 is the next detailed planning and implementation target.

## Amendments

Any change to phase order, evidence eligibility, production isolation, or the
six-slate gate requires a new Sol review and explicit user approval. Phase-level
implementation details may be amended only inside their own contracts.
