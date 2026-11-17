# Session: Direction decision (model first, site in the summer)

## TL;DR

- **Worked On:** Read-only review of project state, then a planning discussion on whether to work on the site or the model next.
- **Outcome:** Owner decided: the model is the focus from 2026-12-14, the site gets no new feature or performance work until summer 2027, and the rest of the 2026 season goes to time-critical close-out. Recorded in `docs/planning/direction-2026-11-14.md`.
- **Plan Contract:** N/A (direction document, documentation only)
- **Approval / Status:** Owner approved the direction plan on 2026-11-14 and asked for it to be recorded.
- **Blockers:** None.
- **Next:** Sunday 2026-11-15 close runs unattended; Monday 2026-11-16 push `dev` and rehearse the kickoff-time refresh on Preview.

**tags:** ["planning", "direction", "offseason", "model-research"]

## Context and Decisions

- Starting state: `dev` clean, 4 local commits ahead of `origin/dev`, 46 commits ahead of `main`; `CFB_WEEKLY_AUTOMATION_ENABLED` is `true`; Week 11 active on Production.
- Owner answers: audience is mostly the owner and friends; model research starts after the 2026-12-13 final close (replaces 2027-01-01); the 2027 ambition level is decided after the first measured candidate results.
- Reasoning: the 2026 record is below break-even on both targets, and the 2021 to 2025 diagnostics show structural gaps (predicted totals with a 1.43 point standard deviation, no neutral-site handling, early-season margin bias). V5 is frozen in-season, so the remaining weeks are for data and evidence that cannot be recovered later.
- Unverified hypothesis recorded as such: the flat totals may come from nothing about pace or possessions per game reaching the bridge.

## Work Completed

- Wrote the direction document with the three phases and their completion criteria.
- Updated the offseason backlog's start date and linked the direction document.
- Added the document to the documentation navigation.

## Files Modified

- `docs/planning/direction-2026-11-14.md` — new direction document
- `docs/planning/offseason-2027-backlog.md` — research start date and pointer
- `mkdocs.yml` — navigation entry

## Validation

- [x] `uv run mkdocs build --strict`
- [x] `git diff --check`

## Amendments and Blockers

- None.

## Handoff Notes

- **Resume at:** Phase 1, item 2 of the direction document (Monday 2026-11-16).
- **Watch out for:** no code pushes to `dev` during the Sunday and Monday weekly runs; the `dev` to `main` release should land by Thursday 2026-11-19 so near-kickoff capture is live for Saturday 2026-11-21.
