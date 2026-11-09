# Featured card header and wording

- **Status:** Implemented
- **Created:** 2026-11-09
- **Planner:** Sol
- **Approval source:** Owner specified the changes after reviewing the card in the session of 2026-11-09
- **Implementation log:** `session_logs/2026-11-09/05-featured-card-header-impl.md`
- **Commit policy:** Commit with implementation (owner pre-authorised commit, push, PR to `dev`; owner merges; never `main`)

## Goal and acceptance

Three changes to the featured card on the Games page (`FeaturedGames`, `UnderdogPicks`, `TopLeans`):

1. The Biggest edges / Underdog picks control moves to the top right of the card header; the title (and the season record) stay top left. On phones, where the card is a collapsed disclosure, the control stays inside the opened card and must not push the layout past 320px wide; the header may wrap the control under the title when the width does not allow one row.
2. The Underdog view's intro line "The model picks the underdog to win" becomes "The model says the wrong team is favored".
3. The words "straight up, all picks" are removed from the season record text (heading and phone text), leaving `2026: 23–57`. The footer line "Straight-up record: picks won outright" stays and still explains the record.

Acceptance: copy and layout as above on the Underdog view; the Biggest edges view's header gets the same control position; no change to ranking, records, rows or the "Show all N" control; phone height budget (`#game-1` above "Main navigation" at 390x844, no `<details open>` on load), 44px targets and no horizontal scroll at 320px hold; no odds, prices or ROI.

Out of scope: loaders, `slate.ts`, definitions.

## Ordered changes

1. `web/src/components/slate/FeaturedGames.tsx` (header layout, control placement) and `UnderdogPicks.tsx` (intro line, record text).
2. Update e2e and unit assertions that match the old copy (for example regexes on "straight up" or "The model picks the underdog to win") and add one assertion for the new intro line and the absent phrase.
3. Docs: a line in the Underdog picks section of `docs/modeling/record_methodology.md` if it quotes the old copy; a decision-log entry only if wording was recorded there.

## Validation

```bash
cd web && npm run test:publication
make check
make web-e2e
git diff --check
```

## Handoff/amendments

One worker-large subagent implements; the orchestrator validates. Amendments:

1. **Reason:** the control needed a slot in the shared disclosure header. **Previous:** edits confined to `web/src/components/slate/*`. **Revised:** `ResponsiveDisclosure` gains an optional `action` slot; callers that do not pass it render as before. **Impact:** none for other callers.
