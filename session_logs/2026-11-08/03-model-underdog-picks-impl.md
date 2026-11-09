# Session: Underdog picks on the Games page (implementation)

## TL;DR

- **Worked On:** Implemented the approved contract `docs/plans/2026-11-08/model-underdog-picks.md`: an "Underdog picks" section next to "Biggest edges", with a season straight-up record.
- **Outcome:** Implemented and validated in the worktree, uncommitted. Preview readback is still to do (orchestrator).
- **Plan Contract:** `docs/plans/2026-11-08/model-underdog-picks.md`
- **Approval / Status:** Contract approved by the owner. Commit, push and PR have not been requested.
- **Blockers:** None
- **Next:** Preview readback (about 10 upset picks, names differ from the consensus favorite, no consensus-0 game, slate row counts before and after the join), then the owner decides on commit and PR.

**tags:** ["web", "games-page", "underdog-picks"]

## Context and Decisions

- The market favorite comes from the consensus line (`market_snapshots.spread` via `predictions.market_snapshot_id`), not the shopped line. A missing snapshot gives `null`, which excludes the game.
- The pure logic is in `web/src/lib/slate.ts` (`underdogPicks`, `underdogRecord`); `topLeans` and `modelCrossesMarket` are untouched.
- Phones: the collapsed disclosures in the extras wrapper are a two-column grid (one column when any is open, and from 640px). The phone summary labels are short ("Biggest edges", "Underdogs"); the season records moved into the opened content on phones and stay in the inline heading from 640px.
- `underdogRecord` takes one array of games per scored week (like `topLeansRecord`), not a flat list plus a weeks argument.
- Fixtures: Week 5 game 4 gets `canonicalSpread: 0`; Week 4 games 104 and 109 get a consensus line that makes the model's side the underdog (both won, so the fixture record is 2–0). No `homeLine` or `predSpread` changed.

## Work Completed

- `web/src/lib/queries.ts`: `canonicalSpread` on `PredictionGame`, a left join to `market_snapshots` in the slate loader, a backfill in `applyFrozenLines`, `null` in the legacy mapper, and `getUnderdogRecord`.
- `web/src/lib/row-guard.ts`: `canonicalSpread` in `PREDICTION_GAME_SPEC`.
- `web/src/components/slate/UnderdogPicks.tsx` (new), `SlateView.tsx`, `SlateList.tsx` (comment), `TopLeans.tsx` (short phone summary), `web/src/app/(games)/page.tsx` (record wiring).
- Docs: `docs/modeling/record_methodology.md`, `docs/decisions/decision_log.md`.

## Files Modified

- `web/src/lib/queries.ts`, `row-guard.ts`, `row-guard.test.ts`, `slate.ts`, `slate.test.ts`, `release-cache.ts` (comment)
- `web/src/components/slate/UnderdogPicks.tsx`, `SlateView.tsx`, `SlateList.tsx`, `TopLeans.tsx`
- `web/src/app/(games)/page.tsx`
- `web/src/test/fixtures/slate.ts`
- `web/e2e/mobile-slate.spec.ts`, `desktop-layout.spec.ts`, `publication.spec.ts`
- `docs/modeling/record_methodology.md`, `docs/decisions/decision_log.md`
- `session_logs/2026-11-08/03-model-underdog-picks-impl.md` — this log

## Validation

- [x] `cd web && node --experimental-strip-types --test src/lib/slate.test.ts src/lib/row-guard.test.ts` (54 passed)
- [x] `make check` passes
- [x] `make web-e2e` (427 passed, 10 skipped)
- [x] `git diff --check` clean
- [x] Preview readback (orchestrator, 2026-11-08): app record 13–37 equals an independent SQL recomputation; Week 11 picks differ from the consensus favorite by name; no consensus-0 game; screenshots at 390, 320 and 1280. Details in the contract.

## Amendments and Blockers

- `web/src/app/(games)/page.tsx` and `TopLeans.tsx` were not in the original file list but are needed for the record wiring and the phone summary budget.
- A first version kept "Underdog picks" as the phone summary and wrapped at 320px; two `mobile-games.spec.ts` tests failed until the label became "Underdogs".

## Handoff Notes

- **Resume at:** nothing outstanding; merged to `dev` through its own PR.
- **Watch out for:** the fixture record is 2–0 (every finished fixture game was won by the model's side), so a fixture loss is covered only by unit tests.
