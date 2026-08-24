# Rating-Centric Architecture Transition Documentation

- **Status:** Superseded
- **Created:** 2026-08-23
- **Planner:** Sol
- **Approval source:** User explicitly authorized this exact plan and its implementation on 2026-08-23.
- **Implementation log:** `session_logs/2026-08-23/06-rating-centric-transition-documentation.md`
- **Commit policy:** Separate plan commit recommended; git operations remain user-controlled.

> **Superseded on 2026-08-23 by:**
> [`repository-documentation-and-2026-ratings-realignment.md`](repository-documentation-and-2026-ratings-realignment.md).
> This record remains accurate for its completed, narrower documentation tranche;
> the replacement changes the target from 2027 to evidence-gated 2026 work and
> expands the scope to the full project-owned Markdown inventory.

## Goal

Create a documentation-only foundation for moving CKsPicks-CFB from the V4
ten-route, prediction-centric architecture toward an approved rating-centric
hybrid architecture for 2027. The documents must accurately describe the
current system, establish the target responsibility boundaries, and provide an
incremental migration roadmap while leaving V4 production unchanged.

Observable success means the repository's authority documents agree that V4 is
the 2026 production champion and benchmark, ratings-first is the approved future
direction, and 2026 outcomes are protected prospective evidence for frozen
candidate designs.

## Current State

The as-built modeling flow is:

`immutable canonical data → team-game measurements → recency aggregation → iterative opponent adjustment → point-in-time matchup features → empirical-Bayes shrinkage → V4 regime routing → spread/total prediction → market edge and publication`

The existing measurement, adjustment, point-in-time, shrinkage, evaluation,
bundle, and operational foundations are reusable. Team strength is nevertheless
implicit across features and route-specific models; the canonical intermediate
product is a matchup row rather than a persistent team state. Predictive
uncertainty is not modeled, and weekly inference currently emits null spread and
total standard-deviation fields.

V4 is live in predictions publication mode, remains the production-safe model,
and must not be altered by this tranche.

## Proposed Approach

Distribute the architecture direction across existing authority documents
rather than introducing a new blueprint. Define the target flow as:

`source data → canonical Bronze/Silver/Gold → football measurements → measurement-level opponent adjustment → team ratings/state → structured game prediction → optional ML residual → probabilistic output → market decision`

Preserve V4 throughout 2026, complete a 10–14 day architecture and measurement
foundation, then use separately approved contracts for measurement interfaces,
a minimum rating baseline, candidate research, protected shadow evaluation, and
a possible 2027 promotion.

## Scope

### Included

- Current-state, target-state, migration, and evaluation documentation.
- The approved responsibility boundaries between measurement, adjustment,
  rating, prediction, residual ML, probabilistic output, and market decisions.
- Scoped corrections to stale module paths, validation posture, and publication
  state in documents touched by the transition.
- An architectural decision-log entry and contributor/assistant orientation.

### Excluded

- Python, TypeScript, SQL, schemas, datasets, configurations, bundles, models,
  production operations, or deployment changes.
- Selecting a rating estimator, scale, prior model, uncertainty method,
  special-teams component, residual architecture, or artifact schema.
- A repository-wide documentation audit.

## Affected Components and Contracts

- Strategic authority: `docs/planning/roadmap.md` and
  `docs/decisions/decision_log.md`.
- Modeling authority: `docs/modeling/features.md`,
  `docs/modeling/early_season_regimes.md`, and
  `docs/modeling/evaluation.md`.
- Contributor and assistant orientation: `AGENTS.md`, `.agent/CONTEXT.md`, and
  `README.md`.
- No public API, schema, dataset, configuration, model-bundle, or operational
  contract changes in this tranche.

## Implementation Tasks

### Task 1 — Document current and target modeling responsibilities

**Changes:**

- Record the as-built flow, reusable foundations, implicit team-state problem,
  absent uncertainty output, and V4 benchmark status.
- Define the target responsibility boundaries and prohibit schedule-strength
  double-counting across adjustment and rating layers.

**Acceptance criteria:**

- Modeling documents use consistent terminology and preserve point-in-time,
  market-separation, immutable-lineage, temporal-validation, 2020-exclusion,
  sealed-selection, and fail-closed rules.

### Task 2 — Publish the phased transition roadmap

**Changes:**

- Add Phase 0 production preservation, the two-week foundation, measurement and
  adjustment contracts, minimum rating baseline, candidate research, and
  protected 2026 evaluation leading to a possible 2027 promotion.

**Acceptance criteria:**

- Every future code or research phase requires a separate contract; the roadmap
  does not prematurely select an estimator or invent concrete interfaces.

### Task 3 — Align authority documents and scoped facts

**Changes:**

- Record the approved decision, orient contributors and assistants, correct
  touched stale paths/status, and link the distributed authority documents.

**Acceptance criteria:**

- No document implies that the rating system is already implemented or that V4
  is no longer authoritative for 2026.

### Task 4 — Validate and hand off

**Validation:**

- `uv run mkdocs build --quiet`
- `git diff --check`
- Internal-link and terminology review
- Changed-path audit proving no source, configuration, schema, model, artifact,
  or production file changed

## Testing Strategy

This is documentation-only work. MkDocs compilation, diff hygiene, link review,
cross-document terminology checks, and changed-path inspection are the required
validation. Runtime and model tests are unnecessary because implementation
behavior is unchanged.

## Risks and Edge Cases

- Future-state language could be mistaken for implemented behavior; every target
  section must distinguish `as built` from `approved direction`.
- 2026 may cease to be protected if outcomes are reused iteratively; later
  contracts must freeze candidate design and eligible outcome cutoffs first.
- Opponent strength could be counted twice; the initial architecture keeps
  adjustment at the measurement layer and requires explicit attribution before
  any rating-assisted adjustment challenger.
- Distributed documentation can drift; the roadmap, modeling documents, decision
  log, and contributor orientation must cross-link and use the same terms.

## Definition of Done

- [x] All implementation tasks and acceptance criteria are complete.
- [x] Required validation passes.
- [x] Documentation and session log are updated.
- [x] Plan status is updated to `Implemented`.

## Amendments

None.
