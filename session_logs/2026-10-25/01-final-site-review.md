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

## Open checks for this page
- Earlier scored week (final scores and result tags), filters, List view, sort options.
- Light theme and the 1280 width.
