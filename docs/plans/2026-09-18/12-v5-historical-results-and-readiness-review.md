# V5-12: Historical Results and Readiness Review

- **Status:** Approved
- **Created:** 2026-09-18
- **Planner:** Sol
- **Approval source:** User explicit approval of `implementation_plan.md` ("The user has approved this document")
- **Implementation log:** `session_logs/2026-09-21/11-v5-historical-results-and-readiness-review.md`
- **Commit policy:** Commit with implementation; user controls Git operations.

## Goal and entry gate

Produce the decision record for V5's historical foundation through 2025. Begin
only after Contract 10 is closed and Contract 11 independently verifies eligible
historical forecasts. This review is development evidence, not prospective
evidence and not permission to apply or promote V5.

## Scope and allowed writes

Report margin and total MAE, bias, CRPS, interval coverage, sample counts,
exclusions, and season/completed-game-stage slices. Compare against the
prespecified simple reference and V4 only where equivalent chronological,
point-in-time evidence exists; disclose unavailable comparisons. Write a
versioned Preview report only. Do not refit, select, tune, modify artifacts, or
write to production, Neon, catalog, web, or V4.

## Tasks

1. Recompute reportable historical metrics from the independently verified
   forecast data and declare exact populations and exclusions.
2. Present selection evidence separately from any independent evidence and
   explain the limitation of repeatedly using the historical development years.
3. Apply existing gates without creating post-result thresholds; record every
   failed or unavailable comparison.
4. Issue a readiness recommendation, unresolved limitations, and exact next
   gate. Completion never automatically authorizes 2026 application.

## Acceptance and validation

The report enables a reviewer to judge accuracy, stability, uncertainty, and
comparability without inferring hidden populations or tuning. Validate metric
calculations with focused tests, source/identity checks, strict MkDocs, and
`git diff --check`.

## Definition of done and amendments

- [ ] Historical report has all required target, slice, coverage, and exclusion data.
- [ ] Comparisons are either point-in-time comparable or explicitly unavailable.
- [ ] Recommendation separates historical readiness from 2026 authority.
- [ ] Explicit user acceptance is recorded before any re-review of 07-09.

Changes to metrics, gates, design, or later application scope require an
approved amendment or a separate contract.

## Amendment 1 — Conditional historical-results lane (2026-09-19)

This Draft contract remains the sole historical-readiness review. It cannot
begin until 10B is complete, implemented 11A and approved 12A have successfully
completed, and every foundation blocker required for readiness is resolved.
Approved [12A](../2026-09-19/12a-v5-conditional-historical-scorecard.md) publishes only
`conditional_historical_results_only` development evidence: it issues no
readiness recommendation and cannot authorize 2026 application. Only explicit
user acceptance of this final Contract 12 review may trigger re-review of 06–09.

## Amendment 2 — Full-lane readiness review execution (2026-09-21)

Following the completion of 10B, diagnosis and resolution of Findings 001/003 on
the `r9` measurement line, and completion of the full Contract 11 decomposition
(11B ratings rebuild, 11C forecast bridge + final fit, and 11D signed verification
closing Findings 002/004), full forecast eligibility is restored.

Detailed execution for Contract 12 is Approved under
[`docs/plans/2026-09-21/06-v5-12-historical-results-and-readiness-review.md`](../2026-09-21/06-v5-12-historical-results-and-readiness-review.md).
It recomputes metrics from the 11D independently verified dataset
(`forecast-v1-20260921-5afd577-11c`), evaluates horizon and head selection,
incorporates market diagnostic evidence, discloses V4 point-in-time
unavailability, publishes signed scorecard artifacts to Preview R2, and issues
the formal readiness recommendation.
