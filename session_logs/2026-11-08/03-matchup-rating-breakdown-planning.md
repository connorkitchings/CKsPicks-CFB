# Session: Matchup rating breakdown planning

## TL;DR

- **Worked On:** Planned a "How the ratings are built" section for the matchup page, driven by the V5 ratings audit finding that Georgia–Florida offense ordering is correct but not visible.
- **Outcome:** Plan approved and saved as `docs/plans/2026-11-08/02-matchup-rating-breakdown.md`.
- **Plan Contract:** `docs/plans/2026-11-08/02-matchup-rating-breakdown.md`
- **Approval / Status:** Owner approved the plan. Commit, push and PR have not been requested.
- **Blockers:** None
- **Next:** Implementation by a worker-large subagent, then validation and a read-only Preview check.

**tags:** ["web", "matchup", "ratings"]

## Context and Decisions

- Each of the four units gets a summary line plus a collapsed per-game table; the section is on the matchup page only (owner decisions).
- Data comes from `season_release_team_rating_components` (already staged each release), joined by `component_id = ${snapshotId}:${role}`. `team_possession_adjusted` is deliberately not used.
- Fail-closed guards turn any mismatch or invalid component into an "unavailable" card instead of showing wrong numbers.
- Out of scope: estimator, schema, migration, model changes; the audit branch integration.

## Work Completed

- Worktree `connorkitchings/matchup-rating-breakdown` created off `origin/dev` (`7505a4c2`).
- Contract and this log written.

## Files Modified

- `docs/plans/2026-11-08/02-matchup-rating-breakdown.md`
- `session_logs/2026-11-08/03-matchup-rating-breakdown-planning.md`

## Validation

None yet (planning only).
