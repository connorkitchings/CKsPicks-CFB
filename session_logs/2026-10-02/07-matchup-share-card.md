# Session: Matchup share card

## TL;DR
- **Worked On:** One shareable image per matchup (statsowar-style), driven by a Share button on the matchup page.
- **Outcome:** `ShareButton` + `ShareCard` export a fixed 1080x1350 (2160x2700 at 2x) dark card: header, both teams with records and Model Rank, forecast and lines, both offense-vs-defense panels (12 rows each), a "Biggest mismatches" callout, notes and trademark line. Share (native sheet), Copy image, or Download PNG.
- **Plan Contract:** reviewed in-session (fast path on `dev`); plan approved with decisions below.
- **Approval / Status:** User chose 4:5 portrait, everything on the card, a Share button (not a server image route), button hidden when stats are unpublished, no retrospective label, site name only.
- **Blockers:** Playwright e2e not run (the user's local server holds Next's lock).
- **Next:** run `npx playwright test` after stopping the local server; release when ready; optional later phase: an `ImageResponse` route so the page link unfurls with the card.

## Work Completed
- `web/src/components/matchup/ShareCard.tsx`: fixed canvas with literal dark colors; logos via `logoSrc(name, "lg", "dark")` plain `<img>` (never `TeamLogo`, which swaps by the viewer's theme); kickoff time in Eastern.
- `ShareButton.tsx`: card mounted only while an image is made; `html-to-image` `toBlob` at 2x; waits for fonts and images; Safari double pass; copy wired synchronously in the click (Safari keeps the gesture); share falls back to a second tap when a browser refuses a delayed share; capability checks via `useSyncExternalStore` (no hydration mismatch).
- `lib/team-stats.ts`: `rowGap` (shared with `rowEdge`), `topMismatches`, `mismatchSentence`, `rankTier` (shared with `getRankBadgeClass`); `lib/matchup-format.ts` holds the kickoff/venue formatters (avoids a hero/card import cycle).
- Dependency: `html-to-image` 1.11.13. npm rewrote 25 unrelated `"dev": true` flags in the lockfile; reverted and added only the new package entries.

## Validation
- [x] lint, typecheck, `test:publication` (108).
- [x] Real data: exported from a light-mode browser, logos are the dark variants; PNG is 2160x2700; all 56 Week 5 matchups render without overflowing the canvas.
- [x] Layout defects found and fixed from the first real export: forecast box overlapped the team names; a long label widened one grid row.
- [ ] Playwright e2e (two new tests in `e2e/matchup.spec.ts`): not run yet.

## Amendments and Blockers
- The hero shows the kickoff in the server's time zone; the card pins Eastern. They agree on the user's machine; if the hero is ever served from a UTC host, make it explicit too.
- Not covered by an e2e test: market-mode card (no fixture game is in market mode); the button hiding when `stats` is null (all fixture games have stats).
