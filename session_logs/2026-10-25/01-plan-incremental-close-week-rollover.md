# Session: Plan and approve the incremental close-week rollover (Week 8→9)

## TL;DR

- **Worked On:** Start-session review, read-only investigation of the weekly builder's full-history defect, and persistence of the owner-approved narrow-amendment contract for the incremental close/open path.
- **Outcome:** Contract `docs/plans/2026-10-25/01-incremental-close-week-rollover.md` saved as Approved; amendment recorded in the 2026-10-20 incremental-ingestion draft; plans index updated.
- **Plan Contract:** [`docs/plans/2026-10-25/01-incremental-close-week-rollover.md`](../../docs/plans/2026-10-25/01-incremental-close-week-rollover.md)
- **Approval / Status:** Owner approved the narrow-amendment path in session on 2026-10-25 (Odds API Week 9 capture authorized at ~2 credits; Preview-only, no Production activation, no `dev`→`main` merge).
- **Blockers:** None.
- **Next:** Implement tasks 2–7 (controller `advance-week`, incremental builder mode, stop gate, Make targets, docs, tests), then run the Week 8→9 rollover.

**tags:** ["planning", "data", "pipeline", "weekly-operations"]

## Context and Decisions

- Week state at session start: Weeks 0–7 scored; Week 8 slate complete; active releases `production-season-2026-125158328e025fb89c96ce0d` / `preview-season-2026-125158328e025fb89c96ce0d`. Branch `dev` clean at `5a370d5e`; work isolated in worktree branch `connorkitchings/incremental-close-week`.
- The runbook pauses the full-history builder (`make season-revision`) for routine rollovers. Read-only R2 checks (no provider calls) verified the carry-forward material: the certified `plays` (`90dd40851581cf0fc74707ae`) and `team_game_stats` (`17c47043c9efc7f787b55f05`) versions each carry exactly 8 Week 0–7 source-capture IDs, and the certified `byplay` manifest lists its four parents as bare version IDs resolvable by reading each candidate dataset's manifest.
- Source inspection confirmed `_silver_from_ingestion_step` already selects captures explicitly (`--capture-id` per capture), so the incremental path needs a union parameter, not new machinery. The legacy `close-week` controller command name is taken, so the new command is `advance-week`.
- Owner decisions: narrow amendment (implement the normal close/open path only; repair mode and promotion harness deferred), Odds API Week 9 capture approved, scope confirmed as Preview-only.

## Work Completed

- Persisted the approved contract with goal, verified baseline, ordered tasks, validation and handoff.
- Recorded the 2026-10-25 amendment (reason, previous approach, revised approach, impact) in `docs/plans/2026-10-20/02-incremental-weekly-ingestion.md`.
- Registered the contract in `docs/plans/index.md` under Current Execution and updated the draft's row.

## Files Modified

- `docs/plans/2026-10-25/01-incremental-close-week-rollover.md` — new approved contract.
- `docs/plans/2026-10-20/02-incremental-weekly-ingestion.md` — amendment entry.
- `docs/plans/index.md` — new contract row; draft row updated.
- `session_logs/2026-10-25/01-plan-incremental-close-week-rollover.md` — this log.

## Validation

- [x] `git diff --check`
- [ ] `uv run mkdocs build --quiet` (to run with the implementation commit)
- [x] Read-only storage checks only; no provider, R2 write, or database requests.

## Amendments and Blockers

- The contract itself is the owner-approved narrowing of the 2026-10-20 draft; recorded in both files.

## Handoff Notes

- **Resume at:** Implementation tasks 2–7 in the same session's branch, then the operational rollover (task 8).
- **Watch out for:** Production activation and `dev`→`main` are explicitly out of scope; the stop gate must halt on any historical schedule drift rather than rewrite certified history.
