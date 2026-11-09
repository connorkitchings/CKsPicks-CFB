# Session: All underdog picks (implementation)

## TL;DR

- **Worked On:** Implemented `docs/plans/2026-11-09/all-underdog-picks.md`: the Underdog picks view lists every qualifying pick and the season straight-up record counts every pick, not just each week's top 5.
- **Outcome:** Implemented and validated in the worktree, uncommitted.
- **Plan Contract:** `docs/plans/2026-11-09/all-underdog-picks.md`
- **Approval / Status:** Contract approved by the owner; Implemented.
- **Blockers:** None, one test gap (see Amendments and Blockers).
- **Next:** None.

**tags:** ["web", "games-page", "underdog-picks"]

## Context and Decisions

- `underdogRecord(weeks)` no longer takes a cap and grades every pick per scored week; `underdogPicks(games, n?)` returns all picks when `n` is omitted. Ranking (gap, kickoff, game id) is unchanged.
- `slate.ts` gains `COLLAPSED_ROWS` (5) and the pure `visibleRows(rows, expanded)`, used by `UnderdogPicksBody` so the collapse rule is unit-testable.
- `UnderdogPicksBody` holds local `expanded` state (collapsed on every load). With more than 5 picks it shows a `Show all N` / `Show fewer` button (`min-h-11`, `aria-expanded`). With 5 or fewer nothing changes.
- Record text is now `x–y straight up, all picks` in the heading and the phone line.
- `FeaturedGames` calls `underdogPicks(games)`; the Biggest edges view, `topLeans`, `modelCrossesMarket`, loaders and queries are untouched.

## Work Completed

- `web/src/lib/slate.ts`, `slate.test.ts` (replaced the top-five record test with an all-picks test; added tests for no-cap `underdogPicks` and `visibleRows`).
- `web/src/components/slate/UnderdogPicks.tsx`, `FeaturedGames.tsx`, `SlateView.tsx` (comment).
- `web/e2e/publication.spec.ts` (record wording; no toggle with one pick).
- Docs: `docs/modeling/record_methodology.md`, `docs/decisions/decision_log.md`.

## Files Modified

- `web/src/lib/slate.ts`, `web/src/lib/slate.test.ts`
- `web/src/components/slate/UnderdogPicks.tsx`, `FeaturedGames.tsx`, `SlateView.tsx`
- `web/e2e/publication.spec.ts`
- `docs/modeling/record_methodology.md`, `docs/decisions/decision_log.md`
- `session_logs/2026-11-09/02-all-underdog-picks-impl.md` — this log

## Validation

- [x] `cd web && npm run test:publication` (475 tests, 474 passed, 1 skipped, 0 failed)
- [x] `make check` passes
- [x] `make web-e2e` (447 passed, 10 skipped; the one cross is the known market-board `test.fail()` case)
- [x] `git diff --check` clean

## Amendments and Blockers

- No fixture week can hold more than 5 underdog picks without changing existing `homeLine`, `predSpread` or game counts, so no e2e covers the expand/collapse click. The collapse rule is covered by the `visibleRows` unit test; the button wiring is in `UnderdogPicksBody`.
- `mobile-slate.spec.ts` and `desktop-layout.spec.ts` assertions (`/2026: 2–0 straight up/`, record line) still match the new wording and were not edited.

## Handoff Notes

- **Resume at:** nothing outstanding.
- **Watch out for:** the displayed Underdog record will rise in count because more picks now count; Biggest edges keeps its top-5 cap.
