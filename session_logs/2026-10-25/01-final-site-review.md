# Final site review: Crest CFB (desktop and mobile)

Review of the four-tab site on Production data (read-only), served locally from `dev` at `5e49fddb` on `http://127.0.0.1:3200`. A page closes only on the owner's "accept".

## Who reviews what

- Owner: desktop dark and phone dark, by hand in the browser, on the page set and interactions in the plan.
- Assistant: light theme, the 1280 desktop width and the 320 phone width, by Playwright full-page captures against the local server (Production data, read-only), each image looked at before reporting. Both also run the plan's interaction checks that need no human (filters, sorts, exports, redirects).

## Review status

| Page | 1440 dark | 1440 light | 1280 light | 390 dark | 390 light | 320 |
|------|-----------|------------|------------|----------|-----------|-----|
| Games `/` | in review | open | open | open | open | open |
| Matchup | open | open | open | open | open | open |
| Ratings | open | open | open | open | open | open |
| Team pages | open | open | open | open | open | open |
| Graphs `/stats` | open | open | open | open | open | open |
| Model, Method | open | open | open | open | open | open |
| Edges (404, redirects) | open | open | open | open | open | open |
| Brand (favicon, OG, exports) | open | open | open | open | open | open |

## Findings

| # | Page | Width | Theme | Evidence | Finding | Requested change | Decision |
|---|------|-------|-------|----------|---------|------------------|----------|
| 1 | Games `/` (Week 8, Saturday Oct 24) | 1440 | dark | owner screenshot 5; page data has 11 games with `startDate` `2026-10-24T04:00:00Z` | 11 games show "12:00 AM ET". `04:00Z` is exactly midnight Eastern, a date-only placeholder (kickoff time not yet known), not a real kickoff. They also sort first in the day. No time-TBD flag exists in the repo, so the placeholder cannot be told apart from data alone. | Proposed: show "Time TBD" for a kickoff at exactly 00:00 ET (CFB has no midnight kickoffs) and sort those last within the day. Separate question: confirm real kickoff times with the data source. | pending |
| 2 | Games `/` (Week 8) | 1440 | dark | owner screenshot 1; all 56 games have `homePoints` and `awayPoints` null | Week 8 shows the "Upcoming" tag and no scores although the games were played Oct 20 to 24. Production has not ingested Week 8 results (the Week 9 weekly release is separate runbook work), so the phase follows the data. The all-final check in the plan cannot be done on Week 8 today. | Decide: leave as is (accurate to the data), or reword the tag when every kickoff has passed. Review the final-score layout on an earlier scored week instead. | pending |
| 3 | Games `/` | 1440 | dark | owner screenshots 1 to 6 | Brand reads "Crest CFB". Cards, logos, model lines, edge colors, day headers, sticky day header and disclaimer render without NaN or missing values. | none | pending |
| 4 | Games, Time TBD | 1440 | light | `slices/games-light-y2850.png` | After the fix: 11 placeholder games read "Time TBD", 0 read "12:00 AM ET", week tag reads "Awaiting results", cards carry "Awaiting result". | none | fixed in `bf3db2bc`, pending owner accept |
| 5 | All pages | 1440, 390, 320 | light, dark | CI run 40209904848 | Browser tests failed on CI: the hydration marker lived in the root layout and fired while only the loading skeleton's app bar had hydrated, so two disabled app bars were in the DOM. | Move the marker into the page header, skip it on skeletons. | fixed in `51086dd9` |
| 6 | Team page (Texas) | 1440 | light | `slices/team-light-y0.png` | "NEXT GAME · WK 8 · SAT, OCT 24" shows a game that has already been played (the first unscored game). | Proposed: next game = first game whose kickoff has not passed. | pending owner decision |
| 7 | Graphs `/stats` | 1440 | light | `slices/stats-light-y0.png` | Nav says "Graphs", page heading says "Team charts". | Proposed: heading "Team graphs". | pending owner decision |
| 8 | Phone app bar | 390, 320 | light, dark | `slices/m-games-390L-y0.png` | Wordmark renders "CrestCFB" with no gap: the link is `inline-flex`, which drops the whitespace before the "CFB" span. | `ml-1` on the suffix. | fix in progress |
| 9 | Ratings, phone | 320 | dark | `slices/m-ratings-320D-y0.png` | The Filters button shows its "active" dot (and announces "Filters active") at the default view. `latestPeriod` takes the last timeline item, but production lists periods latest-first, so it is Preseason. Fixtures list oldest-first, so tests passed. | Pass the real default period from the page. | fix in progress |
| 10 | Matchup | 1440 | light | `slices/mu8-light-y0.png` | A Week 8 game that was played but has no score shows no marker on its matchup page (cards and schedules do). | Show the "Awaiting result" tag in the hero. | fix in progress |
| 11 | Matchup share card | 1440 | light | `inter/share-light-...png` | Header reads "Crest CFB  CFB · WEEK 7", repeating CFB. | Eyebrow "WEEK 7". | fix in progress |
| 12 | Graphs `/stats` | 1440 | light | `charts/*` | None of the five shipped charts offers a table view; only the rating-trajectory chart (not shipped) does. The plan expected one. Exports for all five work in both themes with the `crest-` filename and "Crest CFB" footer. | none | informational |
| 13 | 404 pages (invalid game, unknown team) | 1440 | light | console | React logs "Encountered a script tag while rendering React component" (the theme script) on `notFound()` pages. No visible effect. | Look at it after publication. | deferred |
| 14 | Brand | n/a | n/a | `og.png`, `icon.png` | OpenGraph image and favicon say "Crest CFB" and "C". Wordmark weight renders regular, not bold (the font bundled for image generation has one weight); the 32px favicon "C" is thin. | none | informational |

## Open checks for this page
- Earlier scored week (final scores and result tags), filters, List view, sort options.
- Light theme and the 1280 width.
