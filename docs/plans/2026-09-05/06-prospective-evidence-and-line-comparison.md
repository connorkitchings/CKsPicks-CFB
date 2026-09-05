# Phase 6: Prospective Evidence and Line Comparison

- **Status:** Approved
- **Created:** 2026-09-05
- **Planner:** Sol
- **Approval source:** User approved the full data-first plan on 2026-09-05.
- **Implementation log:** Pending Phase 5
- **Commit policy:** Separate plan commit required

## Goal

Measure frozen future forecast quality and compare it with authentic timestamped
market lines without implementing betting decisions.

## Dependencies and Scope

Consume the frozen Phase 5 candidate and validated Phase 2 capture. Include
pregame freeze, paired V4 evaluation, forecast scoring, and line comparison.
Exclude production activation, public changes, feature selection from markets,
staking, bet selection, bankroll results, and optimized betting thresholds.

## Interfaces

Each freeze binds code/config, training cutoff, inputs, model/state identity,
game population, predictions, and cutoff. Line comparisons bind authentic quote
identity and time, distinguishing prediction-time from closing lines.

## Implementation Tasks

1. Target T-2h and require at least T-1h before the slate's first kickoff.
   Require six normal-coverage slates with >=40 games; Week 0 is ineligible.
2. Compare candidate and V4 on identical games/cutoffs; report broader candidate
   coverage separately. Allow only predefined updates using earlier completed games.
3. Score after >=24 hours and finalized outcomes. A changed candidate starts a
   new prospective window with no inherited/backdated evidence.
4. After football evaluation, compare candidate and market-implied margin/total
   error, prediction-time disagreement, and closing lines separately. Exclude
   unverifiable quotes and report coverage.
5. Publish a recommendation to retain V4, continue shadow evidence, or prepare a
   separate promotion contract.

## Acceptance and Validation

Six slates permits review but does not guarantee sufficiency. Verify authentic
timing, immutable identity, paired population, finalized outcomes, quote lineage,
and deterministic scoring. Markets never enter rating/model fitting or selection.

## Failure Behavior and Done

Late, incomplete, changed, or unverifiable freezes are ineligible and never
backdated. Continue the same candidate when evidence is inconclusive. Complete
the evidence report, line comparison, operational validation, session log, and
status update without activation.

## Amendments

Promotion, publication, betting decisions, thresholds, evidence-window changes,
or market-informed modeling require a separate approved contract.

