# Flip between Biggest edges and Underdog picks

- **Status:** Implemented
- **Created:** 2026-11-09
- **Planner:** Sol
- **Approval source:** Owner asked for it and chose the defaults in the session of 2026-11-09 (Biggest edges is the default view; the card stays collapsed on phones)
- **Implementation log:** `session_logs/2026-11-09/01-underdog-flipper-impl.md`
- **Commit policy:** Commit with implementation (owner pre-authorised commit, push and PR to `dev`; never `main`)

## Goal and acceptance

The Games page shows one card, not two, for the model's featured games: a two-option control flips it between "Biggest edges" (default) and "Underdog picks". The card is collapsed on phones and open from 640px, as both sections are today.

Acceptance:
- One `<section aria-label="Biggest edges">` holds both views; Biggest edges shows first on every load.
- A `SegmentedControl` (label "Featured games view", options "Biggest edges" and "Underdog picks") appears only when both views have content; with no qualifying underdog game the card is exactly today's Biggest edges card, with no control.
- The Underdog view keeps its current content: "The model picks the underdog to win", the gap rows linking to `#game-{id}`, and the "Straight-up record: picks won outright" line with the season record. The Biggest edges view keeps its Spreads/Totals phone tabs and its record.
- The heading and the season record in the card follow the selected view.
- Phones: one full-width collapsed `<details>` with a short one-line summary (the view-flip control lives inside the opened card), `details[open]` count stays 0 on load, 44px targets, and `#game-1` still ends above "Main navigation" at 390x844. Since there is now one disclosure, the `extras` grid in `SlateView.tsx` no longer needs the side-by-side phone layout; restore the single-column spacing (`space-y-2 sm:space-y-4`) unless `ResultHighlights` still shares the row.
- No odds, prices, payouts, units or ROI anywhere. Hidden for finished weeks as today.

Out of scope: loaders, `slate.ts` helpers (`topLeans`, `underdogPicks`, records), data and methodology.

## Ordered changes

1. New client component `web/src/components/slate/FeaturedGames.tsx` composed from the existing `TopLeans` and `UnderdogPicks` bodies (refactor them into body components that render no section or disclosure of their own), owning the view state, the control, the single `ResponsiveDisclosure` and the heading/record per view. Remove the separate `TopLeans`/`UnderdogPicks` section wiring from `SlateView.tsx`.
2. Update e2e: `mobile-slate.spec.ts`, `desktop-layout.spec.ts`, `publication.spec.ts`, `mobile-games.spec.ts` for the single region; add tests that the default view is Biggest edges, that flipping shows the underdog rows (anchors, record line) and flips back, that the control is absent when there are no underdog picks, and that collapsed height and the `#game-1` budget hold on phones.
3. Docs: one line in the existing "Underdog picks" section of `docs/modeling/record_methodology.md` and a short decision-log entry (one card, flip control, default Biggest edges).

## Validation

```bash
cd web && npm run test:publication
make check
make web-e2e
git diff --check
```

## Handoff/amendments

One worker-large subagent implements; the orchestrator validates. Amendments:

1. **Reason:** no fixture week shows a visible card with no underdog pick (week 4 is final and hides the card, weeks 5 and 6 each have one), and adding a week needs changes to `page.tsx` and `slate-page.ts`, which are out of scope. **Previous:** an e2e test that the control is absent when no underdog picks exist. **Revised:** that case is not covered by a test; the branch is the `canFlip` check in `FeaturedGames.tsx`, and the data side (`underdogPicks` returns none) is covered by the unit tests in `slate.test.ts`. **Impact:** one acceptance item is verified by inspection only.

Validation results: `npm run test:publication` 472 passed, 1 skipped; `make check` passed; `make web-e2e` 447 passed, 10 skipped (plus the known expected-failure market board test); `git diff --check` clean.
