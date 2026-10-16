# Session: Charts module planning

## TL;DR

- **Worked On:** Planning the weekly team Charts module (net-success bars, efficiency scatter, opponent-adjusted EPA/play scatter).
- **Outcome:** Revision 3 of the plan, incorporating two owner code reviews, approved and persisted as an execution contract. No implementation.
- **Plan Contract:** [`docs/plans/2026-10-16/01-charts-module.md`](../../docs/plans/2026-10-16/01-charts-module.md)
- **Approval / Status:** Owner approved in chat on 2026-10-16; contract Status: Approved.
- **Blockers:** None. Week 8 delivery is optional, not a deadline.
- **Next:** Implement Ordered tasks 1–7 from the contract; task 8 (Preview rehearsal) is owner-gated.

**tags:** ["charts", "planning", "release-pipeline", "web"]

## Context and Decisions

- Baseline `dev` at `a08bf6f3`; active release `production-season-2026-d0272a48d3a0252fd4196db3`.
- New atomic projection tables (`team_season_roster`, `team_game_stats`, `team_adjusted_epa`) in versioned set `charts_v1`; retained releases read back by their recorded set; staging requires `charts_v1`.
- Adjusted EPA/play uses the unchanged V5 adjuster on a venue-neutralized baseline; venue coefficient from weighted least squares with row-wise √w scaling (`X_weighted = X * sqrt(w)[:, None]`, `y_weighted = y * sqrt(w)`), one `RCOND` policy, rank-condition identification.
- Charts are descriptive reconstructions and never feed ratings, forecasts or grading.

## Work Completed

- Created worktree and branch `connorkitchings/charts-module`.
- Persisted the plan and this log.

## Files Modified

- `docs/plans/2026-10-16/01-charts-module.md` — new execution contract.
- `session_logs/2026-10-16/01-charts-module-planning.md` — this log.

## Validation

- [x] `git diff --check`

## Amendments and Blockers

- None. The plan index (`docs/plans/index.md`) is not yet updated; add the row when implementation starts.

## Handoff Notes

- **Resume at:** Ordered task 1.
- **Watch out for:** No edits to the shared adjuster, V5 measurements, ratings, forecasts or existing projection builders; once merged, staging requires `charts_v1`, so migration 0026 must reach Preview and Production first.
