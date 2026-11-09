# All underdog picks, not just the top 5

- **Status:** Implemented
- **Created:** 2026-11-09
- **Planner:** Sol
- **Approval source:** Owner asked for every underdog pick in the session of 2026-11-09 and accepted the space trade-off
- **Implementation log:** `session_logs/2026-11-09/02-all-underdog-picks-impl.md`
- **Commit policy:** Commit with implementation (owner pre-authorised commit, push, PR and merge to `dev`; never `main`)

## Goal and acceptance

The Underdog picks view lists every qualifying game for the week, and the season straight-up record counts every qualifying pick from every scored week. This supersedes the "top 5" cap in `docs/plans/2026-11-08/model-underdog-picks.md` (Definition, `underdogRecord`) and the record-cap decision in `docs/modeling/record_methodology.md`.

Acceptance:
- `underdogPicks(games, n)` keeps its ranking (gap, then kickoff, then game id) and returns every pick when `n` is omitted. `underdogRecord(weeks)` counts all picks per scored week, straight up, ties excluded, as before.
- Card: the first 5 rows show as today; when more exist, a "Show all N" button (44px target, `aria-expanded`) reveals the rest in the same order and flips to "Show fewer". State is local and starts collapsed on every load. Nothing changes when there are 5 or fewer.
- The record line reads "x–y straight up, all picks"; the phone and inline wording otherwise stays. No odds, prices, payouts, units or ROI.
- The Biggest edges view, its record and the phone height budget (`#game-1` above "Main navigation" at 390x844, no `<details open>` on load) are unchanged.
- Docs: `record_methodology.md` Underdog picks section and a decision-log entry state that the record now counts every qualifying pick (previously the top 5 per week), and why.

Out of scope: loaders and the SQL, `topLeans`, `modelCrossesMarket`, definitions of what qualifies.

## Ordered changes

1. `web/src/lib/slate.ts`: remove the top-5 cap from `underdogRecord` and make the list count optional; update `slate.test.ts` (replace the "only each week's top five" test with one proving all picks count, ordering unchanged).
2. `web/src/components/slate/UnderdogPicks.tsx` / `FeaturedGames.tsx`: list all picks with the "Show all N" control; record wording.
3. `web/e2e/*.spec.ts` and fixtures (additive only): cover collapsed-by-default, expand and collapse, and count of rows. Week 6 in the fixture has game 204 only; add a fixture state with more than 5 picks only if possible without changing existing `homeLine`, `predSpread` or game counts; otherwise cover the toggle with a unit test of a pure helper.
4. Docs as above.

## Validation

```bash
cd web && npm run test:publication
make check
make web-e2e
git diff --check
```

Preview readback (read-only, local app with `CFB_PUBLICATION_MODE=predictions`): the app's record equals an independent SQL recomputation over all qualifying picks for Weeks 0 to 10, and Week 11 lists all 8 picks.

## Handoff/amendments

One worker-large subagent implements; the orchestrator validates. Amendments:

1. **Reason:** no fixture week can have more than 5 underdog picks without changing existing `homeLine`, `predSpread` or game counts. **Previous:** e2e coverage of expand and collapse. **Revised:** the collapse rule is covered by a unit test of the exported pure helper `visibleRows`; the button wiring was checked by hand against the Preview readback below, with no automated test. **Impact:** one acceptance item is verified by the readback only.

Readback (2026-11-09, read-only, local app on Preview with `CFB_PUBLICATION_MODE=predictions`): the app shows 2026: 23–57 straight up, all picks; an independent SQL recomputation over every qualifying pick for Weeks 0 to 10 gives 23 wins, 57 losses, 0 ties, 0 ungraded (80 picks). Week 11 shows 5 rows with "Show all 8"; expanding lists 8 and collapsing returns to 5. Validation: `npm run test:publication` 474 passed, 1 skipped; `make check` passed; `make web-e2e` 447 passed, 10 skipped plus the known expected-failure market board test.
