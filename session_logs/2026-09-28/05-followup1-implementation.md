# Session: Implement Follow-up 1 (default-view selection binding)

## TL;DR
- **Worked On:** Implemented the approved Follow-up 1 contract binding ratings serving labels to served data.
- **Outcome:** All three tasks complete; full web validation green. Contract marked **Implemented**. No model, artifact, selection, or migration change.
- **Plan Contract:** `docs/plans/2026-09-28/v5-default-view-selection-binding.md` (Implemented).
- **Approval / Status:** User authorized this exact path ("go"). Git operations remain user-executed per policy.
- **Blockers:** None.
- **Next:** User commits and pushes; then optionally draft Follow-up 2 (estimator review) or proceed to Week 5 freeze.

## Context and Decisions
- Mechanical deviation recorded (no architecture/scope change): pure helpers live in new dependency-free `web/src/lib/rating-periods.ts` instead of `v5.ts`, because plain `node:test` cannot resolve extensionless drizzle imports. `v5.ts` re-exports all moved names, so existing `@/lib/v5` importers are untouched. `RATING_SELECT` and query logic otherwise unchanged.
- Existing `ratings.test.ts` certified-cutoff assertions now read `rating-periods.ts`; serving-behavior assertions still read `v5.ts`.

## Work Completed
- Task 1: `defaultPeriodForRows` helper; default branch derives label from `getCurrentRatings` rows; `generations[0]` label path deleted.
- Task 2: `ownerSourceForCutoff` helper; frozen-tab backfill pinned to cutoff-owning source; explicit `null` fails closed to frozen-rows-only; preseason tab unchanged (selected source).
- Task 3: new `default-view-selection.test.ts` (8 behavioral tests) wired into `test:publication`; `v5_status.md` follow-up note recorded.

## Files Modified
- `web/src/lib/rating-periods.ts` — new pure module (types, certified map, two helpers).
- `web/src/lib/v5.ts` — default-branch binding, explicit-SHA priors, owner-source backfill query, re-exports.
- `web/src/lib/default-view-selection.test.ts` — 8 new behavioral tests.
- `web/src/lib/ratings.test.ts` — certified-map assertions redirected to new module.
- `web/package.json` — new test file added to `test:publication`.
- `docs/modeling/v5_status.md` — fix note.
- `docs/plans/2026-09-28/v5-default-view-selection-binding.md` — Approved → Implemented.
- `session_logs/2026-09-28/05-followup1-implementation.md` — this record.

## Validation
- [x] `npm run test:publication`: 37 passed (29 existing + 8 new)
- [x] `npm run lint`, `npm run typecheck`: clean
- [x] `npm run build`: succeeds
- [x] `uv run mkdocs build --quiet`: clean
- [x] `git diff --check`: clean
- [ ] User commits and pushes (manual per policy)

## Amendments and Blockers
Module-placement deviation as noted above; within implementation judgment, no contract amendment required.

## Handoff Notes
- **Resume at:** `git add` the 8 files above, commit, push. Proposed message in chat handoff.
- **Watch out for:** Expected rendered `/ratings` output is unchanged in the aligned state; any content diff post-deploy is a defect. Follow-up 2 still undrafted.

**tags:** ["v5", "ratings", "serving", "implementation", "web"]
