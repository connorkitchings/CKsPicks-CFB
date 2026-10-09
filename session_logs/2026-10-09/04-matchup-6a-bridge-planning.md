# Session: 6A matchup bridge planning (Sol)

## TL;DR
- **Worked On:** Sol investigation + decision-complete plan for the corrected-lineage matchup-data bridge blocking contract `02`.
- **Outcome:** Contract `docs/plans/2026-10-09/03-matchup-6a-bridge.md` (Approved): 6A-aware loader, signed gate-receipt verifier, Week-6 write scoping, tests, Preview proof, resume handoff. No implementation, no writes.
- **Plan Contract:** `docs/plans/2026-10-09/03-matchup-6a-bridge.md`
- **Approval / Status:** User approved in session (bridge design + gate-receipt verifier level). Contract `Approved`.
- **Blockers:** None for planning.
- **Next:** Fresh Terra task with `implement-plan` on the contract path, Tasks 1–4.

## Context and Decisions
- plan-session skill followed; baseline from today's three prior sessions (all context current).
- Investigation (read-only): full `matchup_publish.py` (loader, build, static + DB gates, writer, registry), `build_matchup_candidate.py`, `publish_matchup_data.py`, `verify_matchup_data.py`, `publish_v5_intended_update_ratings.py` (proves w6live frames feed snapshots row-for-row), w6live `output_refs` (all children consumable), web `matchup-lineage.ts` (exact ready/updating/unavailable rules), `selected_rating_source` (latest selected week → matchup publish must follow selection), existing matchup tests.
- Key findings: only the measurement side is broken (rating side passes as-is; `CANDIDATE_ID` matches); 6A run exposes all needed states via the trusted `open_published_run` path; write scoping for the game log is required to avoid overwriting served W0–5 provenance (stats/adjusted/components are new keys under `--weeks 6`); contract `02` Task 5 needs a select-before-matchup ordering fix on resume.
- User decision: signed gate-receipt verifier (not second implementation).

## Work Completed
- Read-only investigation across publisher, candidate tool, CLIs, verifier, tests, web lineage, manifests (R2 reads only).
- Wrote the contract (above) and this log. No other files touched.

## Files Modified
- `docs/plans/2026-10-09/03-matchup-6a-bridge.md` - new contract (Approved)
- `session_logs/2026-10-09/04-matchup-6a-bridge-planning.md` - this log

## Validation
- [ ] `git diff --check` (run before handoff)
- [ ] `mkdocs build --quiet` (run before handoff)
- [x] No implementation files edited; no database/artifact/cloud writes

## Amendments and Blockers
- None.

## Handoff Notes
- **Resume at:** fresh Terra task → `implement-plan` on `docs/plans/2026-10-09/03-matchup-6a-bridge.md`, Task 1.
- **Watch out for:** Preview T4 `--apply` needs explicit user authorization; no Production writes in the bridge contract; release resume belongs to contract `02` after T4.

**tags:** ["planning", "matchup", "v5", "bridge", "corrected-lineage"]
