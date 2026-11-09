# Underdog picks on the Games page

- **Status:** Implemented
- **Created:** 2026-11-08
- **Planner:** Sol
- **Approval source:** Owner approved the plan in the planning session of 2026-11-08
- **Implementation log:** `session_logs/2026-11-08/03-model-underdog-picks-impl.md`
- **Commit policy:** Commit with implementation (owner approves commit, push and PR)

## Goal and acceptance

The Games page (`/`) gains an "Underdog picks" section, a sibling of "Biggest edges", listing games where the model picks the market underdog to win outright. It is about who the model picks to win, not odds. No prices, payouts, units or ROI appear anywhere (none are stored; moneylines are barred from the model).

Acceptance: the section renders in fixture mode on phones (collapsed) and from 640px (inline); the mobile vertical-budget tests still pass; unit tests, `make check`, `make web-e2e` and `git diff --check` pass; the Preview readback agrees with the fixtures.

Out of scope: schema, migration, pipeline and methodology changes; odds, prices and staking; changes to `topLeans` or `modelCrossesMarket`.

## Baseline and constraints

- Branch `connorkitchings/model-underdog-picks` off `origin/dev` (7505a4c2), own PR, not stacked on the model-performance-dashboard branch.
- The market favorite is decided by the **consensus pre-kickoff line** (`market_snapshots.spread`, reached via the prediction's `market_snapshot_id`), not the shopped line on the cards, so a near pick'em is never shown as an upset because of line shopping.
- Spread sign: `predictedSpread` is the forecast home margin (positive when home wins). The market's implied home margin is `canonicalSpread === 0 ? 0 : -canonicalSpread` (never `-0`).
- `overlaySelection` only overlays the shopped quote (`homeTeamSpreadLine`, `spreadLean`, `edgeSpread`, `spreadSource`); it never touches `canonicalSpread`, `predictedSpread` or final scores. `applyFrozenLines` (`web/src/lib/queries.ts`, about L451) is what matters for replay and legacy rows.
- `checkRows` (`web/src/lib/row-guard.ts`) reports `undefined` as missing even for `nullable: true`.

## Definition

- Model favorite: the team `predictedSpread` favors. A game is an underdog pick when both margins are non-zero and disagree: `sign(predictedSpread) !== sign(-canonicalSpread)`. Pick'em (consensus 0) and a model margin under 0.05 are excluded (no favorite, no call), matching `modelCrossesMarket`'s |margin| < 0.05 rule.
- Only games in prediction mode and not final, as with `topLeans`. Ranked by the gap between the model's margin and the market's implied margin, largest first, top 5.
- Order (list and record): `b.gap - a.gap || a.startDate.getTime() - b.startDate.getTime() || a.gameId - b.gameId`.
- Finished games are graded straight up (model's winner vs actual final score; ties excluded), the same rule as `modelPickedWinner` in `web/src/lib/team-games.ts`.
- `underdogRecord` counts each scored week's top 5 underdog picks, matching `biggestEdgesRecord` (`slate.ts`, `bucket.slice(0, n)`) and the 5-row display. Title shows "x–y straight up".
- Copy: "The model picks the underdog to win" and "Straight-up record: picks won outright".

## Ordered changes

1. **Canonical line on slate rows.** Add optional `canonicalSpread: number | null` to `PredictionGame` (`web/src/lib/queries.ts`), read with one left join to `market_snapshots` via `predictions.market_snapshot_id` in the slate loader (no correlated subquery). Verify the join binds under `seasonReleaseDb` against Preview; compare row counts before and after. Backfill in `applyFrozenLines`: `canonicalSpread: row.canonicalSpread ?? frozen.spread`. Add `canonicalSpread: OPTIONAL_NUMBER` to `PREDICTION_GAME_SPEC` (`row-guard.ts`), `canonicalSpread: null` on the sample game in `row-guard.test.ts` and in the legacy fallback mapper in `queries.ts` (about L895). Missing snapshot gives `null`: the row is excluded and counted nowhere (fails closed).
2. **Pure helpers in `web/src/lib/slate.ts`** (no DB imports): `underdogPicks(games, n = 5)`, an `UnderdogPick` type reusing `Lean`/`TopLean` shapes, `underdogRecord(games, weeks)`. Reuse `modelSpreadView` / `marketSpreadView` from `betting-format.ts` for names and display. Do not change `topLeans` or `modelCrossesMarket`.
3. **Component `web/src/components/slate/UnderdogPicks.tsx`**, modelled on `TopLeans.tsx`: `<section aria-label="Underdog picks">`, rows link to `#game-{id}`, each showing the model's pick, the consensus line and the gap. Collapsed on phones through `ResponsiveDisclosure` (open from 640px), no disclosure starts open, 44px targets. Hidden when the week is final or no game qualifies, with no empty shell.
4. **Wire-up.** `SlateView.tsx` `extras` after `TopLeans`; `SlateList.tsx` ordering (phones: under the pinned bar, below Biggest edges). Season record loader next to `loadBiggestEdgesRecord` (`queries.ts`), sharing its scored-weeks query or left-joining `marketSnapshots` (on `predictions.marketSnapshotId`) and `gameResults`.
5. **Mobile vertical budget.** `mobile-slate.spec.ts` (L19, L46) requires the bottom of `#game-1` above "Main navigation" at 390x844 including a 34px safe area (about 24px of headroom today). A second full-width collapsed `<details>` would add about 52px and fail. So on phones the collapsed disclosures in the `extras` wrapper (currently `space-y-2 sm:space-y-4`) go side by side: `grid grid-cols-2 has-[details[open]]:grid-cols-1 gap-2 sm:grid-cols-1 sm:gap-4`, with compact single-line phone `<summary>` labels so neither wraps past one 46px row. Collapsed height above `#game-1` must not grow; `details[open]` count 0 stays asserted.
6. **Fixtures (`web/src/test/fixtures/slate.ts`).** Keep Week 5 at 10 games and Week 4 at 9; leave every existing `homeLine` and `predSpread` untouched (`publication.spec.ts` asserts Oklahoma +4.0 / "Model: Oklahoma -2.0" on `#game-9`, Biggest edges 7-3-0, Week 4 4-3-1; `mobile-slate.spec.ts` asserts anchors `#game-3, #game-9, #game-1, #game-8, #game-5`). Default `canonicalSpread` to `homeLine`; override `canonicalSpread: 0` on Week 5 game 4 (Georgia at Alabama, shown +1.5, `predSpread` 0.4): a consensus pick'em that only looks like an upset on the shopped line. Game 9 (Texas at Oklahoma, canonical +4, model +2.0, gap 6.0) is the true consensus underdog pick. For Week 4 straight-up grading, check which existing finished games already have `sign(predSpread) !== sign(-homeLine)`; if more are needed adjust only `canonicalSpread` on two Week 4 games, never `homeLine`.
7. **Tests.** Unit (`slate.test.ts`): home underdog, away underdog, pick'em excluded, `-0` guard, margin under 0.05 excluded, gap ordering and top-5 cap with the tie-break, final games excluded from the list, record counts a win, a loss and a tie. E2E: `mobile-slate.spec.ts` (collapsed on phones, anchors, 44px, `details[open]` 0) and `desktop-layout.spec.ts` (inline from 640px); update `publication.spec.ts` region lists for phases where Biggest edges appears; banned-word check on `/` for the new section ("ROI", "profit", "units", "net return", "-110", moneyline prices).
8. **Docs.** "Underdog picks" section in `docs/modeling/record_methodology.md` (definition, consensus line, straight-up grading, top-5 cap and tie-break, exclusions); decision-log entry (display-only; no odds; consensus line chosen over the shopped line).

## Validation

```bash
cd web && node --experimental-strip-types --test src/lib/slate.test.ts src/lib/row-guard.test.ts
make check
make web-e2e
git diff --check
```

- Read-only Preview readback of the Games page: about 10 upset picks, confirm each model winner differs from the consensus favorite by team name, and no game with consensus 0 appears. Compare slate row counts before and after the join. Screenshots at 390 and 320 wide.

## Backfill check (2026-11-08)

Every scored 2026 week is in the season record: Weeks 1 to 10 each have at least 5 underdog picks (Week 0 has none: the model never disagreed with the market), so the record is 50 picks, 13–37. Week 6 has three games with no retained consensus line; they are excluded (fails closed) and cannot be backfilled because no snapshot exists. Finished weeks do not display the section by design (it follows Biggest edges).

## Handoff/amendments

Approved by the owner. Implementation by one worker-large subagent (shared intermediate state); the orchestrator runs validation. Commit, push and PR need the owner's go-ahead. Preview readback is read-only. Risks: spread sign (pick'em and `-0` tests plus the name check); consensus vs shopped line disagreeing with the card's line in rare cases (the row shows the consensus line); few qualifying games per week (section hides when empty); small-sample season record (counts only, no luck wording); one extra join on the slate query (row counts and timing compared).

Amendments:

1. **Reason:** the season record needed to reach the page, and the phone vertical budget needed a shorter first disclosure. **Previous:** file scope excluded `web/src/app/(games)/page.tsx` and `TopLeans.tsx`. **Revised:** `page.tsx` loads `getUnderdogRecord` beside `getBiggestEdgesRecord`; on phones the "Biggest edges" summary shows only the title and its season record moves inside the opened content (the record still shows in the inline heading from 640px). **Impact:** no assertion changed; `publication.spec.ts` still checks `2026: 7–3–0`.
2. **Reason:** "Underdog picks" wrapped past one row at 320px and failed two `mobile-games.spec.ts` tests. **Previous:** phone summary "Underdog picks". **Revised:** phone summary "Underdogs"; the inline heading and the region name stay "Underdog picks". **Impact:** none beyond the label.
3. **Reason:** consistency with `topLeansRecord`. **Previous:** `underdogRecord(games, weeks)`. **Revised:** `underdogRecord(weeks)` takes one array of games per scored week. **Impact:** none.
4. **Reason:** one section alone should not sit in half a row. **Previous:** the grid in item 5 only. **Revised:** adds `[&>:only-child]:col-span-full` to the `extras` wrapper. **Impact:** none.

## Readback results (2026-11-08, read-only, local app on Preview release `preview-season-2026-5d50a63ef62a6751f30d7599`)

- Predictions are public only with `CFB_PUBLICATION_MODE=predictions`, so the app was started locally with that set; the live Preview default (market mode) hides the section just as it hides Biggest edges.
- Join: the slate loader and `getUnderdogRecord` run against Preview with no error; Week 11 renders its 67 games, the same count as before the change (plain left join, no row multiplication).
- Season record: the app shows 13–37 straight up; an independent SQL recomputation (each scored week's top 5 by gap, Weeks 0–10: 13 wins, 37 losses, 0 ties, 0 ungraded) gives the same. Biggest edges is unchanged at 55–55–0.
- Week 11 picks (model pick over market favorite, consensus line, gap): Georgia State over Georgia Southern (+5.5, 8.7); Michigan State over Washington (+3.5, 8.6); NC State over Syracuse (+2.5, 7.3); Mississippi State over Auburn (+3.5, 7.0); Ball State over Buffalo (+3, 6.3). Each model pick differs from the consensus favorite by team name, and no game with a consensus of 0 qualifies (0 in the full SQL set).
- Screenshots at 390 and 320 wide: both disclosures collapsed side by side on one row, no horizontal scroll; 1280 wide shows the section inline.

