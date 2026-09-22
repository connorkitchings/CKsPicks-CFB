# V5 Documentation Authority Reset and Completion Sequence

- **Status:** In Progress
- **Created:** 2026-09-22
- **Planner:** Sol
- **Approval source:** User explicitly authorized implementation of this exact plan on 2026-09-22.
- **Implementation log:** `session_logs/2026-09-22/07-v5-documentation-authority-reset-and-08-rating-replay.md`
- **Commit policy:** Separate documentation and certified-evidence checkpoints; user executes Git.

## Goal

Make the September 22 V5 state unambiguous across active documentation, then
coordinate the remaining live-research sequence without replacing its approved
implementation contracts. Success means active entry points name the canonical
roadmap, show Contract 08 as next, and preserve the exact historical evidence
record; subsequent work advances only through 08, 09, 06, and a conditional
Phase 7 review.

## Current State

V4 is the public 2026 production champion. V5 historical development is complete
and accepted: Repair v2, r9 measurements, 11B ratings, the 11C through-2025
forecast fit, and 11D independent verification closed all four 10B findings.
Contract 07 is Implemented with 157 certified 2026 games through Week 3.
Contract 08 is approved, re-reviewed, and has its verified entry parent.

Contracts 08, 09, and 06 remain the sole implementation authorities for their
respective stages. V5 stays Preview-only; no step changes V4, Neon serving
state, public publication, or betting policy.

## Proposed Approach

Use the data-first roadmap as the detailed authority and make every active entry
point carry the same short September 22 checkpoint linked to it. Preserve dated
audit/conditional records as historical evidence. Then execute existing contracts
in dependency order, with immutable artifacts and independent verification at
every stage.

## Scope

### Included

- Documentation authority reset and regression coverage.
- Contract 08 rating-state replay.
- Contract 09 forecasts and live readiness after the required Week 4 refresh.
- Contract 06 prospective evidence collection and recommendation.
- Conditional Phase 7 promotion-review planning after a qualifying recommendation.

### Excluded

- V4 model, bundle, publication, Neon serving, or web changes.
- Tuning, re-selection, or fitting on 2026 outcomes.
- Automatic V5 activation, betting, staking, or market-driven model changes.
- Reorganization or archival of the documentation tree.

## Affected Interfaces and Contracts

- Documentation changes only alter authority wording and lifecycle status; no
  public API, schema, or serving interface changes.
- Contract 08 emits versioned `priors`, `rating_states`, `team_states`, and a
  verified replay manifest.
- Contract 09 emits forecast predictions, a verified forecast manifest, and a
  live-readiness report.
- Contract 06 emits an evidence ledger, slate reports, a market appendix, and
  a final recommendation.
- [Contract 08](../2026-09-18/08-v5-2026-rating-state-replay.md),
  [Contract 09](../2026-09-18/09-v5-2026-forecast-and-readiness.md), and
  [Contract 06](../2026-09-13/06-v5-prospective-evidence-and-recommendation.md)
  remain authoritative.

## Implementation Tasks

### Task 1 — Reset active documentation authority

Update README, documentation home, assistant/context guides, quickstart,
operations roadmap, data-first roadmap, rating/evaluation references, and the
plans index to state: historical V5 is complete and accepted; all four audit
findings are closed; 07 is Implemented with 157 certified Weeks 0–3 games; 08
is next; V4 remains champion. Link every concise checkpoint to the data-first
roadmap. Keep dated 10B, 11A, and 12A findings intact and label their timing.

**Acceptance criteria:** no active checkpoint claims that 12A is next, findings
remain open, 11 is pending, the scorecard is unauthoritative, or all 2026
application remains deferred. Documentation tests distinguish current authority
from historical evidence and require the sequence `07 → 08 → 09 → 06 → Phase 7`.

**Validation:** `uv run pytest tests/test_data_first_documentation_authority.py`,
`uv run python contracts/validation.py`, `uv run mkdocs build --strict --quiet`,
and `git diff --check`.

### Task 2 — Execute Contract 08

Follow Contract 08 exactly: build 2026 priors with no 2026-outcome fitting,
replay Weeks 0–3 from `possession-v1-measurements-20260922-2026c`, then
independently verify and idempotently repeat the Preview-only run. The frozen
11B identity is `ppp__rho_0_60__exposure`; no selection may change. Its verified
terminal replay manifest becomes Contract 09's only live rating parent.

After Week 4 finals stabilize, rerun 07 and 08 under new immutable identities
through Week 4. Do not alter Weeks 0–3 artifacts.

### Task 3 — Execute Contract 09

After the through-Week-4 refresh, apply the frozen 11C expanding alpha-10
through-2025 final-fit bridge and final calibration to live team states without
fitting on 2026 outcomes. Independently verify forecasts and re-run readiness
for Week 5. Only an independently verified `ready` result opens Contract 06;
record a `blocked` result with its exact missing dependency and correct it under
a new identity.

### Task 4 — Execute Contract 06

Collect six qualifying paired V4/V5 slates, targeting Weeks 5–10. Freeze at the
T-2h target and never later than T-1h with at least 40 paired games; score at
least 24 hours after the last included result; then refresh the chain for the
next slate. Keep all exclusions and corrections in the immutable ledger. Evaluate
football performance and calibration before separate authentic-quote diagnostics.
Publish one recommendation: retain V4, continue shadowing, or prepare Phase 7.

### Task 5 — Conditional Phase 7 review

Create a separate Phase 7 plan only if Contract 06 recommends preparing it.
That plan must specify operational rehearsal, rollback proof, serving interfaces,
acceptance criteria, and an explicit activation decision. Retain-V4 or
continue-shadowing results complete the review without an activation plan.
Production activation requires separate user approval.

## Testing Strategy

Documentation changes use the Task 1 checks. Each existing contract supplies
the binding unit, preflight, apply, independent-verification, idempotent-repeat,
and evidence checks for its stage. Verify exact immutable parent manifests before
starting each stage instead of relying on narrative status.

## Risks and Edge Cases

- CFBD finals lag can delay the Week 4 refresh. It cannot be bypassed; any
  temporary Week-3-state diagnostic must be recorded as a limitation.
- Week 4 is not a prospective candidate slate. Week 5 is only a target, subject
  to readiness and timing gates.
- Six qualifying slates permit a promotion review; they never activate V5.
- Any new V5 identity, changed timing, refit, or parent mismatch requires the
  existing contract amendment process or a new Sol plan.

## Definition of Done

- [x] Active documentation and authority tests reflect the September 22 state.
- [ ] Contract 08 has a certified and independently verified 2026 replay.
- [ ] Contract 09 has a certified forecast and verified Week 5 readiness.
- [ ] Contract 06 has published its verified six-slate recommendation.
- [ ] A Phase 7 contract exists only when the recommendation supports one, or
  the retained/continued-shadowing review condition is recorded.
- [ ] Every completed stage has its session log and required validation.

## Amendments

None.
