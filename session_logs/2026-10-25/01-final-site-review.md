# Final site review: Crest CFB (desktop and mobile)

Review of the four-tab site on Production data (read-only), served locally from `dev` at `5e49fddb` on `http://127.0.0.1:3200`. A page closes only on the owner's "accept".

## Who reviews what

- Owner: desktop dark and phone dark, by hand in the browser, on the page set and interactions in the plan.
- Assistant: light theme, the 1280 desktop width and the 320 phone width, by Playwright full-page captures against the local server (Production data, read-only), each image looked at before reporting. Both also run the plan's interaction checks that need no human (filters, sorts, exports, redirects).

## Review status

Columns: owner reviews dark (desktop 1440, phone 390); assistant reviews light, 1280 and 320. "ok" = looked at, no open defect. Real-device checks on the Vercel Preview were waived by the owner.

| Page | 1440 dark | 1440 light | 1280 light | 390 dark | 390 light | 320 |
|------|-----------|------------|------------|----------|-----------|-----|
| Games `/` | accepted (owner) | ok | ok | accepted (owner) | ok | ok |
| Matchup | reviewed (owner), no changes | ok | ok | reviewed (owner), no changes | ok | ok |
| Ratings | reviewed (owner), no changes | ok | ok | reviewed (owner), no changes | ok | ok |
| Team pages | reviewed (owner), no changes | ok | ok | reviewed (owner), no changes | ok | ok |
| Graphs `/stats` | reviewed (owner), no changes | ok | ok | reviewed (owner), no changes | ok | ok |
| Model, Method | reviewed (owner), no changes | ok | ok | reviewed (owner), no changes | ok | ok |
| Edges (404, redirects) | accepted (assistant checks, owner agreed) | ok | ok | reviewed (owner), no changes | ok | ok |
| Brand (favicon, OG, exports) | n/a | ok | n/a | n/a | n/a | n/a |

## Findings

| # | Page | Width | Theme | Evidence | Finding | Requested change | Decision |
|---|------|-------|-------|----------|---------|------------------|----------|
| 1 | Games `/` (Week 8, Saturday Oct 24) | 1440 | dark | owner screenshot 5; page data has 11 games with `startDate` `2026-10-24T04:00:00Z` | 11 games show "12:00 AM ET". `04:00Z` is exactly midnight Eastern, a date-only placeholder (kickoff time not yet known), not a real kickoff. They also sort first in the day. No time-TBD flag exists in the repo, so the placeholder cannot be told apart from data alone. | Proposed: show "Time TBD" for a kickoff at exactly 00:00 ET (CFB has no midnight kickoffs) and sort those last within the day. Separate question: confirm real kickoff times with the data source. | pending |
| 2 | Games `/` (Week 8) | 1440 | dark | owner screenshot 1; all 56 games have `homePoints` and `awayPoints` null | Week 8 shows the "Upcoming" tag and no scores although the games were played Oct 20 to 24. Production has not ingested Week 8 results (the Week 9 weekly release is separate runbook work), so the phase follows the data. The all-final check in the plan cannot be done on Week 8 today. | Decide: leave as is (accurate to the data), or reword the tag when every kickoff has passed. Review the final-score layout on an earlier scored week instead. | pending |
| 3 | Games `/` | 1440 | dark | owner screenshots 1 to 6 | Brand reads "Crest CFB". Cards, logos, model lines, edge colors, day headers, sticky day header and disclaimer render without NaN or missing values. | none | pending |
| 4 | Games, Time TBD | 1440 | light | `slices/games-light-y2850.png` | After the fix: 11 placeholder games read "Time TBD", 0 read "12:00 AM ET", week tag reads "Awaiting results", cards carry "Awaiting result". | none | fixed in `bf3db2bc`, pending owner accept |
| 5 | All pages | 1440, 390, 320 | light, dark | CI run 40209904848 | Browser tests failed on CI: the hydration marker lived in the root layout and fired while only the loading skeleton's app bar had hydrated, so two disabled app bars were in the DOM. | Move the marker into the page header, skip it on skeletons. | fixed in `51086dd9` |
| 6 | Team page (Texas) | 1440 | light | `slices/team-light-y0.png` | "NEXT GAME · WK 8 · SAT, OCT 24" shows a game that has already been played (the first unscored game). | Proposed: next game = first game whose kickoff has not passed. | approved by owner; fixed in the next commit |
| 7 | Graphs `/stats` | 1440 | light | `slices/stats-light-y0.png` | Nav says "Graphs", page heading says "Team charts". | Heading "Team graphs". | approved by owner; fixed in the next commit |
| 8 | Phone app bar | 390, 320 | light, dark | `slices/m-games-390L-y0.png` | Wordmark renders "CrestCFB" with no gap: the link is `inline-flex`, which drops the whitespace before the "CFB" span. | `ml-1` on the suffix. | fixed in `c713a853`, verified on Production data |
| 9 | Ratings, phone | 320 | dark | `slices/m-ratings-320D-y0.png` | The Filters button shows its "active" dot (and announces "Filters active") at the default view. `latestPeriod` takes the last timeline item, but production lists periods latest-first, so it is Preseason. Fixtures list oldest-first, so tests passed. | Pass the real default period from the page. | fixed in `c713a853`, verified on Production data |
| 10 | Matchup | 1440 | light | `slices/mu8-light-y0.png` | A Week 8 game that was played but has no score shows no marker on its matchup page (cards and schedules do). | Show the "Awaiting result" tag in the hero. | fixed in `c713a853`, verified on Production data |
| 11 | Matchup share card | 1440 | light | `inter/share-light-...png` | Header reads "Crest CFB  CFB · WEEK 7", repeating CFB. | Eyebrow "WEEK 7". | fixed in `c713a853` |
| 12 | Graphs `/stats` | 1440 | light | `charts/*` | None of the five shipped charts offers a table view; only the rating-trajectory chart (not shipped) does. The plan expected one. Exports for all five work in both themes with the `crest-` filename and "Crest CFB" footer. | none | informational |
| 13 | 404 pages (invalid game, unknown team) | 1440 | light | console | React logs "Encountered a script tag while rendering React component" (the theme script) on `notFound()` pages. No visible effect. | Look at it after publication. | deferred |
| 14 | Brand | n/a | n/a | `og.png`, `icon.png` | OpenGraph image and favicon say "Crest CFB" and "C". Wordmark weight renders regular, not bold (the font bundled for image generation has one weight); the 32px favicon "C" is thin. | none | informational |
| 15 | Graphs, phone settings sheet | 390, 320 | light | `phone/graphs-settings-*-light.png` | Controls in the Chart settings sheet have unrelated widths (select, segmented controls, week stepper), left-aligned. Usable; looks unfinished. | Optional: make the controls full width. | owner: leave as is; deferred past publication |
| 16 | Matchup (MTSU at FIU) | 1440 | dark | owner screenshot | In the narrow forecast card, long team names wrap: "Florida / International -10.0" in the Market, Model and Model Bet rows. Readable; phone layouts already use short names. | Optional: use the short team name in the card. | deferred, owner to decide |
| 17 | Team page schedule (Notre Dame) | 1440 | dark | owner screenshot | A bye week is a gap in the Wk column (7 then 9) with no "Bye" row. Correct, but a reader may think a game is missing. | Optional: add a "Bye" row. | deferred, owner to decide |

## Open checks for this page
- Earlier scored week (final scores and result tags), filters, List view, sort options.
- Light theme and the 1280 width.
