# Session: Draft Follow-up 1 contract (ratings serving selection binding)

## TL;DR
- **Worked On:** Follow-up planning for the 2026-09-28 V5 audit's serving findings; drafted one Sol implementation contract.
- **Outcome:** `docs/plans/2026-09-28/v5-default-view-selection-binding.md` created as **Draft** (approval pending). No implementation files touched.
- **Plan Contract:** The new contract itself (Draft, awaiting user approval).
- **Approval / Status:** User chose "V5 audit follow-ups" and said go; Follow-up 1 drafted first per the recommended sequence. Follow-up 2 (estimator review) not yet drafted.
- **Blockers:** None.
- **Next:** User reviews/approves the Draft; then a fresh Terra task implements it via the implement-plan skill. Optionally draft Follow-up 2 in parallel.

## Context and Decisions
- Audit findings verified against code before drafting: default-branch desync at `web/src/lib/v5.ts:218-223`, selection-dependent backfill at `:151` reused at `:197-201`, implicit newest-row dedup at `:187-192`.
- Key contract decisions (so Terra rediscovers nothing): derive default label from served rows via an exported pure helper; pin frozen backfill to the cutoff-owning source with explicit-SHA priors param; codify newest-row-wins; pure-helper tests without DB; no migration; expected rendered output unchanged.
- Left `docs/plans/index.md` untouched until approval (Drafts are not active contracts).
- Web suite entry confirmed: `npm run test:publication` covers `ratings.test.ts`.

## Work Completed
- Wrote the Draft contract with goal, current state, approach, scope, affected components, three ordered tasks with acceptance criteria, testing strategy, risks, and definition of done.

## Files Modified
- `docs/plans/2026-09-28/v5-default-view-selection-binding.md` — new Draft contract.
- `session_logs/2026-09-28/04-followup1-contract.md` — this record.

## Validation
- [ ] `git diff --check` (run below)
- [ ] `uv run mkdocs build --quiet` (run below)
- [ ] User approval of the Draft (pending)

## Amendments and Blockers
None.

## Handoff Notes
- **Resume at:** Review the Draft; approve or request changes. On approval, run the Terra prompt in the chat handoff.
- **Watch out for:** Do not implement before approval; plan-session rule. Follow-up 2 remains a separate research contract (V6 lab home).

**tags:** ["planning", "v5", "ratings", "serving", "contract"]
