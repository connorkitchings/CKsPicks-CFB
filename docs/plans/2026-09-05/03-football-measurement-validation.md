# Phase 3: Football Measurement Validation

- **Status:** Approved
- **Created:** 2026-09-05
- **Planner:** Sol
- **Approval source:** User approved the full data-first plan on 2026-09-05.
- **Implementation log:** Pending Phase 2
- **Commit policy:** Separate plan commit required

## Goal

Determine which football measurements contain useful, distinct, and reliable
information before expanding rating or model complexity.

## Dependencies and Scope

Consume the Phase 2 eligibility manifest. Reproduce the seven-measurement
foundation, then compare the equal-weight composite, EPA-only, leave-one-out
composites, audited passing/rushing components, and one-family context additions
for recruiting, returning production, coaching, pace, field position, and
turnovers. Do not alter V4 or introduce a second schedule adjustment.

## Interfaces

Each candidate declares numerator, denominator, eligible events, direction,
exposure, missingness, adjustment, timing, lineage, and population. Comparison
outputs identify retained, redundant, inconclusive, unavailable, and capture-only
information on common populations.

## Implementation Tasks

1. Reproduce current measurements and four-iteration opponent adjustment from
   certified inputs; retain unadjusted values as diagnostics only.
2. Implement the bounded ablations/components under new research versions.
3. Hold one simple updater and regularized linear forecast head fixed across
   comparisons; fit all transforms within chronological folds.
4. Test measurement redundancy, correlated uncertainty, sparse events, and
   missing-feature fallback. Investigate possession volume and scoring
   efficiency separately for totals.
5. Admit shorter-window families only on a contiguous window with >=90% FBS
   team coverage per season and at least three chronological validation seasons.
6. Publish attribution, coverage, fallback, and common-population reports.

## Acceptance and Validation

The phase may retain the current set; adding a feature is not required. Verify
independent calculations, symmetry, zero exposure, overtime, garbage time,
fold-local fitting, and population parity. Missing-feature fallback predictions
must appear in aggregate results rather than disappearing.

## Failure Behavior and Done

Inconclusive or unavailable families remain capture-only and cannot feed Phase
4. A measurement-definition correction returns through Phase 2 versioning.
Complete artifacts, attribution report, exact retained set, validation, session
log, and status update.

## Amendments

Adding candidate families, changing adjustment policy, admission gates, or the
fixed comparison head requires a revised plan.

