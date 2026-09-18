# Session: V5 Contract 10A Reclosure Planning (Amendment 2)

## TL;DR
- **Worked On:** Planned the 10A reclosure (Amendment 2) and 10B readiness updates from the user's six-gap review with four corrections.
- **Outcome:** 10a reopened to In Progress with Amendment 2; 10b and umbrella updated for validity/gate separation, `closure_state`, local verification record, and `rejected_seasons`; index updated.
- **Plan Contract:** `docs/plans/2026-09-18/10a-v5-audit-harness-and-lineage.md` (Amendment 2)
- **Approval / Status:** User approved the plan with four corrections; persisted in Build mode. Terra task 1 (10A) is authorized next; task 2 (10B) waits for 10A Implemented + commit.
- **Blockers:** None for planning.
- **Next:** Terra task 1 executes Amendment 2 with zero R2 writes.

## Context and Decisions
- Post-close review (user) found 10A's Implemented label premature: duplicated header fields, depth-limited traversal, static-only assurance, non-final publishable manifest, run-only idempotence, no digest reconstruction/parent reread, disposition/closure conflation. Implementation direction confirmed correct.
- Four user corrections applied: (1) 16 behavioral cases must execute + classify accurately, failures become findings, harness closes regardless; (2) publication validity separate from Contract 11 gate; (3) explicit `rejected_seasons: [2020, 2026]` interface; (4) verification record stays local/session-log evidence — exactly four published outputs.
- Verified in code before planning: `max_depth=3`, `finalized: false`, run-only idempotence, no evidence-digest reconstruction, disposition-proxy gate.
- Packaging: two sequential Terra tasks; corrections recorded as Amendment 2 in place.
- Earlier completion claim (`bdf3ba7`, three preflights, digest `29235642…`) preserved as history in 10a/Amendment 2 and session log 06.

## Work Completed
- 10a: header deduplicated, Status In Progress, Task 4 behavioral matrix specified, DoD rewritten to reclosure terms, Amendment 2 appended.
- 10b: Task 4 rewritten (closure_state, final-publication rules, verifier requirements, rejected seasons, local verification record), DoD updated (finalized manifest, exact idempotence, validity/gate split).
- Umbrella: rejected-seasons declaration, closure_state + validity/gate separation in Findings section, DoD updated.
- Index: 10a row In Progress.

## Files Modified
- `docs/plans/2026-09-18/10a-v5-audit-harness-and-lineage.md` — reopen + Amendment 2.
- `docs/plans/2026-09-18/10b-v5-full-corpus-audit-execution.md` — corrections 2–4.
- `docs/plans/2026-09-18/10-v5-historical-foundation-audit.md` — gate/season wording.
- `docs/plans/index.md` — 10a lifecycle row.
- `session_logs/2026-09-18/07-v5-10a-reclosure-planning.md` — this log.

## Validation
- [x] Focused tests: 135 passed (55 + 44 + 36)
- [x] `uv run mkdocs build --strict`
- [x] `git diff --check`

## Amendments and Blockers
- None beyond Amendment 2 itself.

## Handoff Notes
- **Resume at:** Terra task 1 on `docs/plans/2026-09-18/10a-v5-audit-harness-and-lineage.md` (Amendment 2). Zero R2 writes; new committed SHA; three new preflights.
- **Watch out for:** 10b apply binds to the post-Amendment-2 SHA. Contract 11 stays Draft. Corrective contracts (if blockers) are separate.

**tags:** ["v5", "contract-10a", "planning", "amendment-2"]
