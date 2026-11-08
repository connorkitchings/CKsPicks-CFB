# Session: Matchup rating breakdown (planning and implementation)

## TL;DR

- **Worked On:** A "How the ratings are built" section on the matchup page, driven by the V5 ratings audit finding that Georgia–Florida offense ordering is correct but not visible. Planned, implemented, reviewed against real Preview data, and revised for readability.
- **Outcome:** Implemented and merged into local `dev` (head `7f7386c8`). Not pushed, no PR. Production is untouched.
- **Plan Contract:** `docs/plans/2026-11-08/02-matchup-rating-breakdown.md`
- **Approval / Status:** The owner approved the plan and each later revision. Push and PR have not been requested; the owner said not to push to production yet.
- **Blockers:** None
- **Next:** Owner decides when to push `connorkitchings/matchup-rating-breakdown` and open a PR into `dev`; a separate `dev` to `main` release PR takes it to production.

**tags:** ["web", "matchup", "ratings"]

## Context and Decisions

- Data comes from the staged rating components, matched by `${snapshotId}:${role}` and checked against the rendered rating; any mismatch or inconsistency shows that card as unavailable. `team_possession_adjusted` is deliberately not used.
- Each of the four units gets a card; the section is on the matchup page only (owner decisions).
- Review on real Preview data (Georgia, Western Michigan, Akron, Missouri) showed the first design was hard to follow: the summary read like a formula, defense signs looked backwards, and it never said the rating measures only points per possession. Revisions, each owner-approved and recorded as an amendment in the contract:
  - plain-language card sentences and a rating line ("above/below average");
  - a running season-to-date table (`cumulativeByWeek`) as the main view, with the per-game table kept in a nested disclosure so effects still add up to the rating;
  - disclosure names "Week by week" and "Each game's effect on the rating".
- Facts established along the way (documented, not code-traced): the V5 rating is opponent-adjusted points per possession plus a shrinking preseason prior; the other stats are diagnostics. Overall is the average of offense and defense. Forecasts add a non-offense scoring offset through a fixed Ridge bridge. Adjusted values are re-scored each week against current opponent estimates, so a past game's adjusted number drifts.
- Preview holds 15 releases; each stores its own copy of every component row. The app reads one release (`WHERE release_id = <active release>`), so copies never reach the page.
- Not shown: a league-average PPP, because it is not stored with the components. Out of scope: estimator, schema, migration, model changes; the audit branch integration.

## Work Completed

- Worktree `connorkitchings/matchup-rating-breakdown` off `origin/dev` (`7505a4c2`); five commits on top, fast-forwarded into local `dev`.
- Verified the page against the Preview database for Georgia, Western Michigan, Akron and Missouri: ratings, possessions and prior weights match, and prior plus game contributions equals the stored rating to 12 decimals.
- Found and fixed two existing e2e tests (`logos.spec.ts`, one in `matchup.spec.ts`) that raced the streamed page content; they passed 16 of 16 on `origin/dev` and failed on this branch before the wait.

## Files Modified

- `web/src/lib/rating-breakdown.ts` and `rating-breakdown.test.ts` (new)
- `web/src/components/matchup/RatingBreakdown.tsx` (new)
- `web/src/lib/matchup.ts`, `matchup-rating-query.ts` and its test, `rating-periods.ts`, `v5.ts`, `release-cache.ts`
- `web/src/app/matchup/[gameId]/page.tsx`
- `web/src/test/fixtures/matchup.ts`
- `web/e2e/matchup-ratings-breakdown.spec.ts` (new); `matchup.spec.ts`, `matchup-rank-colors.spec.ts`, `matchup-tape.spec.ts`, `mobile-matchup.spec.ts`, `desktop-layout.spec.ts`, `logos.spec.ts`
- `web/package.json`, `web/README.md`
- `docs/plans/2026-11-08/02-matchup-rating-breakdown.md`, this log

## Validation

- Unit tests: 27 tests, 26 pass, 1 skipped (existing Postgres integration test needing `TEST_DATABASE_URL`).
- `make check`: passed.
- `make web-e2e`: 432 passed, 10 skipped, 0 failed.
- `git diff --check`: clean.
- Real-data check: the page was loaded read-only against Preview through `make web-local ENV=preview`, and the four units rendered ready for a Week 11 game; figures cross-checked in SQL as above.
- Not done: fixture screenshots at every size in the contract (a subset was reviewed), and no check on Production data.
