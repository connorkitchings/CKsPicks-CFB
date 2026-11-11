# Session: Regular-season end-state contract and offseason backlog

## TL;DR

- **Worked On:** Planning for the end of the 2026 regular season (owner chose postseason option B) and a consolidated 2027 offseason backlog.
- **Outcome:** Draft contract `docs/plans/2026-11-11/regular-season-end-state.md` and the new `docs/planning/offseason-2027-backlog.md`; `docs/status.md` Open items updated. No product code changed.
- **Plan Contract:** [`docs/plans/2026-11-11/regular-season-end-state.md`](../../docs/plans/2026-11-11/regular-season-end-state.md)
- **Approval / Status:** Option B chosen by the owner 2026-11-11; the contract itself is Draft pending owner approval.
- **Blockers:** None for planning. Implementation is gated on verifying the last regular-season week in the 2026 schedule (Army–Navy may be week 16).
- **Next:** Owner approves the contract; verify the final week; implement and release to `main` before early December.

**tags:** ["plan", "postseason", "offseason"]

## Context and Decisions

- Verified in code: at the final week `decide_close_week` returns `skip`, so the last week would never be graded without this work; `--next-week` is already optional in `run_season.py`, so a no-next-week release is plausible, to be proven by a feasibility check in the contract.
- The offseason backlog is a list only; nothing in it starts before January, and each model, data or Production item needs its own contract.

## Files Modified

- `docs/plans/2026-11-11/regular-season-end-state.md`, `docs/plans/index.md`, `docs/planning/offseason-2027-backlog.md`, `mkdocs.yml`, `docs/status.md`

## Validation

- [x] `mkdocs build --strict`, `git diff --check`, documentation tests
