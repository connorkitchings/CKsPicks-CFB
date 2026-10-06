# Session: Stage 7B Exact Release and Cutover Planning

## TL;DR
- **Worked On:** Prepared the Stage 7B exact release and cutover contract after Stage 7A close-out.
- **Outcome:** User-approved contract persisted at `docs/plans/2026-10-06/02-stage7b-exact-release-and-cutover.md`; implementation is a fresh-task handoff.
- **Plan Contract:** `docs/plans/2026-10-06/02-stage7b-exact-release-and-cutover.md`
- **Approval / Status:** User approved persistence in this task; contract status is Approved.
- **Blockers:** Original Week 5 prospective freeze provenance and a valid historical registration route must be verified before any release authorization or serving selection.
- **Next:** User commits the plan. A fresh implementation task uses `.agent/skills/implement-plan/` with the exact contract path.

## Context and Decisions
- Stage 7A is committed and marked Implemented. The user's Preview read-only report found `current_week=(2026, 6)`, six active selections, and zero rows in `public.prospective_week_records`.
- The live `N` is deliberately not selected in this planning session. Contract 04 Appendix B fixes `N` only when a release packet is built from fresh certified state.
- The original Week 5 prospective designation requires authentic original run, signed freeze receipt, timestamp, kickoff and selection/freeze evidence. A replay, current selection, or grade cannot establish prospective status.
- Preview rehearsal, authorization insertion, freeze, Production activation, and rollback remain separately authorized operator operations. Planning approval did not authorize these writes.
- Stage 8 2025 matchup backfill remains out of scope and separately gated.

## Work Completed
- Reviewed the Stage 7A contract and implementation close-out, Contract 04 Amendment 2, and normative Window 2 Appendices A and B.
- Persisted the decision-complete Stage 7B contract and this planning log only. Did not change implementation code, live data, or `docs/status.md`.

## Files Modified
- `docs/plans/2026-10-06/02-stage7b-exact-release-and-cutover.md` - Approved Stage 7B execution contract.
- `session_logs/2026-10-06/07-stage7b-exact-release-planning.md` - Planning findings and handoff.

## Validation
- [x] `git diff --check`
- [x] `.venv/bin/python contracts/validation.py`
- [x] `.venv/bin/python -m mkdocs build --quiet`

## Amendments and Blockers
- No contract amendment. Authentic Week 5 prospective provenance is an implementation preflight gate; stop before packet authorization or selection if it cannot be verified.

## Handoff Notes
- **Resume at:** User-run plan commit, then a fresh implementation task invoking `.agent/skills/implement-plan/` with `docs/plans/2026-10-06/02-stage7b-exact-release-and-cutover.md`.
- **Watch out for:** Recompute `N` and all packet inputs from live state; never assume Week 6 from the dated Stage 7A report. Preview and Production have separate exact packets, identities, authorizations and apply decisions.

**tags:** ["release", "data-integrity", "planning"]
