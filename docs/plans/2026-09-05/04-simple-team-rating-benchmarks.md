# Phase 4: Simple Team-Rating Benchmarks

- **Status:** Approved
- **Created:** 2026-09-05
- **Planner:** Sol
- **Approval source:** User approved the full data-first plan on 2026-09-05.
- **Implementation log:** Pending Phase 3
- **Commit policy:** Separate plan commit required

## Goal

Select one reproducible, interpretable preseason and within-season rating
benchmark with offense, defense, uncertainty, and explicit fallback behavior.

## Dependencies and Candidates

Consume Phase 3 measurements. Preseason candidates are neutral, fixed annual
carryover 0.60, the R2 winner if Phase 1/2 preserve its evidence, and context
Ridge with alpha `{0.1,1,10,100}`. Within-season candidates are the existing
exposure update and recency half-lives `{2,4,8}`. Kalman, Glicko, and nonlinear
transition models are deferred.

## Interfaces

Team states contain component means, uncertainty, prior/observed contributions,
team-specific completed games/exposures, effective time, quality/fallback flags,
and exact parent identity. Rating meaning stays continuous across a season.

## Implementation Tasks

1. Generate chronological preseason states; treat 2019->2021 as a two-year gap.
2. Select the prior before updater comparison and record staged-selection risk.
3. Generate identical pregame evidence for each updater and evaluate Game 1,
   Games 2-4, and established periods separately.
4. Estimate uncertainty from prior variability and chronological residuals with
   an empirical floor; evidence may increase uncertainty when instability rises.
5. Use eligible named FCS history when available. Otherwise learn a partially
   pooled FCS state only from preceding FBS-FCS games, with explicit fallback
   status and uncertainty.
6. Publish movement, attribution, prior reliance, uncertainty, coverage, and
   error reports; rankings remain diagnostics.

## Acceptance and Validation

Select a simple benchmark or retain the valid reference. Test first games,
byes, missing observations, abrupt changes, unequal experience, sparse teams,
and the two-year gap. If no evaluable FCS fallback exists, label those games
unsupported and block claims of all-FBS readiness.

## Failure Behavior and Done

Failed challengers do not expand the roster automatically. Freeze the valid
reference with its inputs and diagnostics, validation, session log, and status.

## Amendments

Adding updater families, changing the candidate grid, uncertainty semantics,
or FCS fallback requires a revised plan.

