# Session: Week 6 display-only Production release planning (Sol)

## TL;DR
- **Worked On:** Start-session load + read-only review of the Week 6 display run, then Sol planning for opening it on the Production site.
- **Outcome:** Decision-complete contract `docs/plans/2026-10-09/02-week6-display-production-release.md` (Approved). No implementation, ingest, write, or serving change.
- **Plan Contract:** `docs/plans/2026-10-09/02-week6-display-production-release.md`
- **Approval / Status:** User approved in session (d2 run, full scope, Preview rollback rehearsal kept, local-site verification loop). Contract `Approved`.
- **Blockers:** None for planning. Execution blockers for Terra: the two admin payloads and every Production apply are user-run.
- **Next:** User opens a fresh Terra task with `implement-plan` on the contract path, starting at Task 1 (Preview gap publishes).

## Context and Decisions
- Start-session per `.agent/skills/start-session/`: read AGENTS.md, `docs/status.md`, QUICKSTART, CONTEXT (via reminder), last-3-days logs, branch/worktree state, env keys (no secrets).
- The session goal reverses the 2026-10-08 hold decision for Week 6 only (Amendment 9 already permits a labeled display-only release; Production publication was a reserved separate go-ahead — this contract is it).
- User decisions: (1) publish the existing d2 run, not a fresh d3; (2) full scope (picks + ratings + stats + matchup), not picks-only; (3) keep the Preview rollback rehearsal, not direct-to-Production; (4) verify every stage via `run_web_local.sh` against the respective database.
- New finding for the contract: the corrected rating manifest `c83b1423…` has no `v5_rating_snapshots` rows anywhere, so selecting d2 without the Phase 0 publishes would empty the Ratings page and degrade W6 matchup pages. Production approvals cover only bundle `30c4f1eb…`; d2 needs a B2 (`a507d0c7…`) approval row + production authorization row. The existing staging dry run covers only c2 Weeks 0–5, not d2.

## Work Completed
- Reviewed (read-only): d2 Preview run row + selection, full 55-game prediction slate, corrected post-W5 ratings top 25 (R2 `current_teams.parquet`), served-vs-corrected lineage, Production prerequisites (current_week, games, venues, approvals, authorizations, policy), packet/staging/rating/venue/seed/select/publisher CLI interfaces.
- Wrote the contract (above) and this log. No other files touched.

## Files Modified
- `docs/plans/2026-10-09/02-week6-display-production-release.md` - new contract (Approved)
- `session_logs/2026-10-09/02-week6-display-production-planning.md` - this log

## Validation
- [ ] `git diff --check` (run before handoff)
- [x] No implementation files edited; no database/artifact/cloud writes (all queries SELECT-only under pipeline roles)

## Amendments and Blockers
- None. One correction during review: `select_public_run` needs no freeze; web accepts `published`+`pending`.

## Handoff Notes
- **Resume at:** fresh Terra task → `implement-plan` on `docs/plans/2026-10-09/02-week6-display-production-release.md`, Task 1.
- **Watch out for:** every Production apply + both admin inserts are user-run; Phase 2 gated on user review of the rollback script + Preview rehearsal; never freeze/close Week 6.

**tags:** ["planning", "week6", "production", "v5", "display-only"]
