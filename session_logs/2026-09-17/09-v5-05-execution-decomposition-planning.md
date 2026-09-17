# Session: V5-05 Execution Decomposition Planning (Sol)

## TL;DR
- **Worked On:** Planned Contract 05 (prospective readiness and shadow tooling) as three dependency-ordered execution phases
- **Outcome:** Three Draft phase contracts persisted; umbrella 05 and plan index updated; no implementation code touched
- **Plan Contracts:** `docs/plans/2026-09-17/04-v5-05a-readiness-and-replay.md`, `05-v5-05b-freeze-score-ledger.md`, `06-v5-05c-rehearsal-verification-runbook.md` (all Draft)
- **Approval / Status:** Decomposition approved by user 2026-09-17; 05A authorized on contract approval, 05B/05C gated on prior certification
- **Blockers:** None for planning. Live 2026 readiness expected `blocked` (no 2026 measurement/rating pipeline, Preview lag) — documented, not resolved here
- **Next:** Fresh Terra task implements approved 05A contract

## Context and Decisions

- Start-session established the baseline: Contract 04 Implemented with certified `forecast-v1-20260917-4600ddd-04b`; Contract 05 Approved with entry gate met; same-day readiness assessment found live 2026 `blocked`.
- User decisions (recorded): (1) three phases by dependency — 05A readiness+replay, 05B freeze+score+ledger, 05C rehearsal+verify+runbook; (2) producer code in `src/cks_picks_cfb/forecast/shadow.py`; (3) keep and refresh the readiness assessment doc in Phase 05C.
- Confirmed in plan review: (1) keep explicit `blocked` expectation — Terra's verified assessment decides, expectation does not substitute; (2) Phase 05A requires its own Preview preflight/apply/verify cycle; (3) config filename `shadow_v1.yaml` confirmed.
- Existing candidate-v1 shadow system is pattern reference only; its counter and identity must not be reused. No V5 shadow code/config/schemas exist yet.

## Work Completed

1. Loaded start-session and plan-session skills; reviewed AGENTS.md, roadmap, common contract, umbrella 05, Contract 06 handoff requirements.
2. Ran exploration subagent over shadow/prediction infrastructure, DB schema, forecast runner/verifier, V4 pipeline, configs, and recent session logs.
3. Verified worktree state (`main`, HEAD `4600ddd`, planning-doc modifications + untracked readiness assessment preserved).
4. Wrote three Draft phase contracts with exact schemas, CLIs, pinned parents, acceptance criteria, and certification cycles.
5. Updated umbrella 05 with execution decomposition section; updated plan index (05 row + new 05A/05B/05C section).

## Files Modified

- `docs/plans/2026-09-17/04-v5-05a-readiness-and-replay.md` — new Draft phase contract
- `docs/plans/2026-09-17/05-v5-05b-freeze-score-ledger.md` — new Draft phase contract
- `docs/plans/2026-09-17/06-v5-05c-rehearsal-verification-runbook.md` — new Draft phase contract
- `docs/plans/2026-09-13/05-v5-prospective-readiness-and-shadow-tooling.md` — execution decomposition section
- `docs/plans/index.md` — 05 row update + 05A/05B/05C section
- `session_logs/2026-09-17/09-v5-05-execution-decomposition-planning.md` — this log

## Validation

- [ ] `git diff --check` (pending)
- [ ] `uv run mkdocs build --quiet` (pending)

## Amendments and Blockers

- None. The `blocked` readiness expectation is planning context from the same-day assessment, not a scope reduction — Terra must still run the full verified assessment.

## Handoff Notes

- **Resume at:** Fresh Terra task implements the approved 05A contract (approval required first — all three phases are Draft).
- **Watch out for:** 05B/05C must not execute before prior-phase certification. The readiness assessment doc is uncommitted planning evidence — Terra preserves and refreshes it in 05C, never deletes it. No implementation files were touched in this session.

**tags:** ["v5", "planning", "contract-05", "shadow-operations"]
