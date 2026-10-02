# Session: Matchup share card

## TL;DR
- **Worked On:** One shareable image per matchup (statsowar-style), driven by a Share button on the matchup page.
- **Outcome:** `ShareButton` + `ShareCard` export a fixed 1080x1350 (2160x2700 at 2x) dark card: header, both teams with records and Model Rank, forecast and lines, both offense-vs-defense panels (12 rows each), a "Biggest mismatches" callout, notes and trademark line. Share (native sheet), Copy image, or Download PNG.
- **Plan Contract:** reviewed in-session (fast path on `dev`); plan approved with decisions below.
- **Approval / Status:** User chose 4:5 portrait, everything on the card, a Share button (not a server image route), button hidden when stats are unpublished, no retrospective label, site name only.
- **Blockers:** none at close-out (e2e now run; see Close-out).
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
- [x] Playwright e2e: both share tests pass (see Close-out).

## Amendments and Blockers
- The hero shows the kickoff in the server's time zone; the card pins Eastern. They agree on the user's machine; if the hero is ever served from a UTC host, make it explicit too.
- Not covered by an e2e test: market-mode card (no fixture game is in market mode); the button hiding when `stats` is null (all fixture games have stats).

## Later in the session
- Share card follow-ups: mismatches rebuilt as one box per panel with rank badges and "who by how many spots" (the global top 3 repeated one matchup); a PPA that rounds to zero shows no sign; notes split into clean lines; a footnote "— = not enough clean data" when a card shows a blank value (`hasMissingValue`).
- Data issue found from the Vanderbilt card (blank points per scoring opportunity): the play-by-play running score is non-monotonic for about a third of team-games. Documented in `docs/data/known_issues.md`; investigation deferred by the user.

## Close-out (CI and release)
- **Both sessions closed together:** this session plus the edge-constraints session (logs 08 and 09: configs, serving builder, `backfill_v5_unconstrained_grades.py`, backup snapshots, docs) went out in one release commit.
- **CI finding:** CI runs the full browser suite (`npm run test:ui`) with no `web/.env`. A clean checkout (no env files) reproduced CI: `53d346b` passed 33/33, but committed `dev` failed 18 tests. First failing commit: `914dbc9` (the matchup refinement commit, which also carried the Picks/Results prototype port). Cause: the rewritten slate tests assume `CFB_PUBLICATION_MODE=predictions`, which the developer's local `web/.env` sets and CI does not (it defaults to market mode), plus one stale assertion (`heading "Season"`; the component renders plain text).
- **Fix:** `web/playwright.config.ts` now starts its dev server with `CFB_PUBLICATION_MODE=predictions`; the stale assertion is updated. Also removed an earlier stale assertion of mine (edge numbers on the matchup page). Result on a clean checkout with no env vars: 43/43.
- **Method note:** the e2e dev server shares `.next` with a running `npm run dev`, so I tested a clean `git worktree` instead; Turbopack rejects a symlinked `node_modules`, so it is cloned with `cp -Rc` (instant on APFS). Documented in `web/README.md`.
- **Left uncommitted on purpose:** an unfinished Picks/Results card redesign in the working tree ("Best bets", team filter, `BetCell`; `Header`, `SiteNav`, `globals.css`, `slate/*`, `publication.spec.ts`, `ratings.test.ts`). With it applied, 9 e2e tests fail even in predictions mode, so it was not released.
- **Docs updated at close-out:** `docs/status.md` (release state, in-flight), `docs/plans/index.md` (port plan Implemented), `docs/ops/production_runbook.md` (removed the stale `CFB_ENABLE_TEST_PAGE` mention), `web/README.md` (Share card, PPA label, e2e setup), `.codex/QUICKSTART.md` (the optional-flags line), `docs/data/known_issues.md`.
- **Open at close-out:** user-run production republish of team stats (`ppa_per_play`); Week 5 close with `backfill_v5_unconstrained_grades.py --week 5 --grades-only`; the data issues in `known_issues.md`; the unfinished card redesign.
- **CI rehearsal on a clean checkout of the release commit (no env files, CI's env vars):** `ruff format --check` (caught an unformatted `backfill_v5_unconstrained_grades.py`, fixed in `272b97e`), `ruff check`, contracts validation, `pytest -W error -n 4` with `CFBD_API_KEY=ci-placeholder` and a disposable local PostgreSQL 14 (scratchpad, TCP only, deleted afterwards) for the migration integration tests: 1626 passed, 2 skipped; web `lint`, `typecheck`, `test:publication` (110), `build`, `CI=1 test:ui` (43/43); `mkdocs build --strict`.

