# Session: Yards per play display and diagnostic planning

## TL;DR

- **Worked On:** Wrote two plan contracts for yards per play (YPP): a display contract and a predictive diagnostic.
- **Outcome:** The display contract is Approved (owner decision 2026-11-19); the diagnostic is Draft and waits for the 2026-12-13 final close. Both are indexed; the backlog and `CHANGELOG.md` are updated.
- **Plan Contract:** [`docs/plans/2026-11-19/yards-per-play-display.md`](../../docs/plans/2026-11-19/yards-per-play-display.md), [`docs/plans/2026-11-19/adjusted-ypp-predictive-diagnostic.md`](../../docs/plans/2026-11-19/adjusted-ypp-predictive-diagnostic.md)
- **Approval / Status:** Display Approved 2026-11-19; diagnostic Draft.
- **Blockers:** None.
- **Next:** Implement the display contract; target merge to `main` before the 2026-11-22 close.

**tags:** ["planning", "ypp", "display", "research"]

## Context and Decisions

- Indiana is #5 in adjusted YPP and #39 in the V5 offense rating; the owner decided to do both display and diagnostic, display first, context only.
- V5 stays frozen for the 2026 record; YPP does not enter ratings or forecasts.

## Work Completed

- Wrote both contracts, indexed them, linked them from backlog section B, added the `CHANGELOG.md` entry.

## Files Modified

- `docs/plans/2026-11-19/yards-per-play-display.md` — new
- `docs/plans/2026-11-19/adjusted-ypp-predictive-diagnostic.md` — new
- `docs/plans/index.md` — two Current Execution rows
- `docs/planning/offseason-2027-backlog.md` — section B bullet
- `CHANGELOG.md` — Added entry
- `session_logs/2026-11-19/02-ypp-display-planning.md` — this log

## Validation

- [x] Links checked by path
- [x] `git diff --check`

## Amendments and Blockers

- None

## Handoff Notes

- **Resume at:** Display implementation
- **Watch out for:** Code must not reach `main` between a close and its Monday market refresh.
