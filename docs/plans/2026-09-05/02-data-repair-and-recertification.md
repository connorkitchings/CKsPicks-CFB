# Phase 2: Data Repair and Recertification

- **Status:** Approved
- **Created:** 2026-09-05
- **Planner:** Sol
- **Approval source:** User approved the full data-first plan on 2026-09-05.
- **Implementation log:** Pending Phase 1
- **Commit policy:** Separate plan commit required

## Goal

Repair reproduced defects, recertify trustworthy research inputs, and begin
validated automated pregame capture without changing production behavior.

## Dependencies and Scope

Consume the Phase 1 inventory and issue register. Include deterministic repairs,
bounded recapture, rebuilt research descendants, eligibility, and capture.
Exclude speculative fixes, production changes, model selection, purchases, and
rewriting immutable source/history.

## Interfaces

Publish corrected dataset refs under the new research namespace, repair
dispositions, before/after impact reports, and an eligibility manifest naming
seasons, populations, timing class, null/fallback policy, parents, and checksums.

## Implementation Tasks

1. Reproduce and repair admitted identifier, join, duplicate, finite-value,
   count, or transformation defects. Give definition changes new versions.
2. Rebuild only affected research descendants under new identities; preserve
   original captures, reports, and historical timestamps.
3. Perform budgeted recapture from existing providers where recoverable, with
   call estimates and distinct retrieval observations. Quarantine unresolved
   conflicts; preserve unavailable values as null with reasons.
4. Recompute affected metrics and document conclusion changes. Keep invalidated
   artifacts readable as historical evidence but ineligible for selection.
5. Validate and establish automated capture of already available pregame
   information. Capture outputs cannot become eligible without timing/coverage
   checks and must stay isolated from production.
6. Publish the eligibility manifest and explicit Phase 3 input refs.

## Acceptance and Validation

No unresolved correctness or leakage defect remains in admitted inputs.
Applicable coverage and reconciliation gates pass without post-result weakening.
Every repair has a regression test, lineage verification, deterministic rerun,
before/after reconciliation, and proof that V4 outputs and production interfaces
remain unchanged. Missing FCS detail remains explicit.

## Failure Behavior and Done

Unresolved conflicts are quarantined and excluded; affected descendants do not
advance. Shared fixes that could alter V4 are isolated under research versions.
A production defect receives a separate contract. Complete reports, capture
runbook, eligibility manifest, validation, session log, and status update.

## Amendments

Production fixes, new paid sources, fabricated timing, gate changes, or new
measurement definitions require separate authorization or a revised plan.

