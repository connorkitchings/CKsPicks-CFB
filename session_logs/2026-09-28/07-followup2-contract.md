# Session: Draft Follow-up 2 contract (three-estimator review)

## TL;DR
- **Worked On:** Grounded and drafted the Follow-up 2 research contract comparing three rating estimators.
- **Outcome:** `docs/plans/2026-09-28/v5-estimator-three-way-review.md` created as **Draft** (approval pending). No implementation files touched.
- **Plan Contract:** The new contract itself (Draft, awaiting user approval).
- **Approval / Status:** Drafted on the user's "let's continue" after Follow-up 1 closed Implemented. CI fix + Follow-up 1 runs were pending/in-progress at draft time.
- **Blockers:** None for approval. Implementation needs no lab bucket (read-only source adapter + local manifests suffice).
- **Next:** User reviews/approves the Draft; then a fresh Terra task implements it via the implement-plan skill.

## Context and Decisions
- Grounding verified: lab individuals carry `raw_value` (not adjusted), lab cumulative builder averages raw values, no shared V5-exposure updater exists — so the contract scopes an updater, a labeled adjusted-snapshot import, and an earlier-only per-game recipe as the core work.
- Key decisions: (a) must reproduce frozen V5 states as a fidelity gate before Phase 2; per-game recipe mirrors the 4-pass additive form on earlier-only graphs; V6 Task 5 explicitly not a prerequisite; no promotion or Alabama-ordering selection under any outcome.
- Left `docs/plans/index.md` untouched until approval.

## Work Completed
- Wrote the Draft contract: goal, current state, approach, scope, affected components, four ordered tasks with acceptance criteria, testing strategy (including the `ruff format --check` + `ruff check` both-gates lesson), risks, and definition of done.

## Files Modified
- `docs/plans/2026-09-28/v5-estimator-three-way-review.md` — new Draft contract.
- `session_logs/2026-09-28/07-followup2-contract.md` — this record.

## Validation
- [ ] `git diff --check` (run below)
- [ ] `uv run mkdocs build --quiet` (run below)
- [ ] User approval of the Draft (pending)

## Amendments and Blockers
None.

## Handoff Notes
- **Resume at:** Review the Draft; approve or request changes. On approval, use the implement-plan skill with the exact plan path.
- **Watch out for:** Do not implement before approval. Phase 2 may not start until Phase 1 proofs pass (contract gate).

**tags:** ["planning", "v5", "estimator", "research", "contract"]
