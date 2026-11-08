# Matchup page: "How the ratings are built"

- **Status:** Approved
- **Created:** 2026-11-08
- **Planner:** Sol
- **Approval source:** Owner approved this plan in the planning session (2026-11-08); decisions: each of the four units gets a summary line plus a collapsed per-game table; the section is on the matchup page only.
- **Implementation log:** Pending
- **Commit policy:** Commit with implementation. Commit, push and PR only on the owner's go-ahead.

## Goal and acceptance

The V5 ratings audit (`docs/modeling/v5_offense_defense_ratings_audit_2026.md`, branch `codex/v5-ratings-audit`) found the Georgia–Florida offense ordering is correct but not visible: Georgia leads raw PPP, Florida gets a larger opponent adjustment, and Georgia's stronger prior narrows the gap. The matchup page shows only raw stats and rank chips, so a reader cannot see why ranks differ from the raw tables.

Outcome: a "How the ratings are built" section on the matchup page that reads the already-staged `season_release_team_rating_components` (per-unit prior weight/contribution plus a per-game evidence ledger with `raw_ppp`, `adjusted_ppp`, `exposure`, `contribution`).

Done when every item under Validation passes and the section behaves as specified below. Out of scope: estimator, schema, migration or model changes; the audit's missing-artifact verification; integrating the audit branch.

## Baseline and constraints

- Branch `connorkitchings/matchup-rating-breakdown` off `origin/dev` (`7505a4c2`), in a worktree.
- Rendered snapshot equals component snapshot: `projection_football._snapshots` writes `{run}:current:post-week-{n}:{team}` and `{run}:pregame:{team}:preseason`; `build_rating_components` builds the same ids. The FK `team_rating_components.v5_snapshot_id → v5_rating_snapshots.snapshot_id` and the release verifier (`season/verification.py:933-958`, 1e-12 tolerance) enforce `rating_mean == {role}_rating`. Look-up key is the primary key `component_id = ${snapshotId}:${role}`.
- Displayed rating is the stored `rating_mean`, a z-scale value formatted by `ratingText` (`components/ratings/StatGrid.tsx:8`). Defense sign is reversed (allowing less gives a higher rating).
- Unit raw/adjusted PPP come from the evidence ledger as exposure-weighted means. Do not join `team_possession_adjusted` (post-week only, different mask, as-of-week join could pick the wrong generation).
- Opponent names come from `games` (every evidence `game_id` is scheduled).
- No new tables; both tables are already in `CORE_RELEASE_TABLES`.

## Ordered changes

All of 1–7 go to one owner (shared intermediate state).

1. **New pure module `web/src/lib/rating-breakdown.ts`** (no DB imports, like `rating-periods.ts`).
   - Types: `UnitRatingBreakdown` (`ready` | `unavailable` with reason `missing` | `mismatch` | `invalid` | `lookup`), `BreakdownGame`, `ExcludedGame`, `RatingBreakdown` (four units).
   - `componentId`; `parseComponent` (strict, never coerces; accepts a jsonb string and `JSON.parse`s it as a fallback); `opponentFor`; `excludedReasonLabel` (known codes mapped, fallback "failed a data-quality check"); formatters `pppText`, `contributionText` (3 dp), `priorPercent`.
   - `buildUnitBreakdown` guards, in order: no rendered row, snapshot id or component → `missing`; snapshot, rating team, role or source differs, or |`rating_mean` − rendered| > 1e-12 → `mismatch`; parse failure, |prior + Σcontribution − `rating_mean`| > 1e-9, Σexposure ≠ `usable_exposure`, or `completed_games` ≠ evidence length → `invalid`; otherwise compute means and sort rows by (week, gameId).
2. `web/src/lib/rating-periods.ts`: add `snapshotId?: string` to `Rating`. `web/src/lib/v5.ts`: add `snapshotId` to `RATING_SELECT` (and `getCurrentRatings`).
3. `web/src/lib/matchup-rating-query.ts`: `ratingComponentsQuery(db, season, sourceSha, componentIds)` (`component_id IN (≤4)`, no `cutoff_utc`/`as_of_week` predicate); `teamScheduleQuery(db, season, teams)` (home or away `IN`).
4. `web/src/lib/matchup.ts`: `releaseCached` loaders `getRatingComponents` and `getTeamSchedule` via `getSeasonDb`; run in the existing stage-2 `Promise.all` with `.catch(() => null)`; add `ratingBreakdown: RatingBreakdown` to `MatchupData` using existing `offenseRanks`/`defenseRanks`; the page never throws for this section; note both loaders in the `release-cache.ts` findings comment.
5. **New server component `web/src/components/matchup/RatingBreakdown.tsx`.** Reuse `Card`, `Disclosure` (native `<details>`, closed by default), `SectionHeading`, `ratingText`.
   - Placement in `web/src/app/matchup/[gameId]/page.tsx` after "Team stats", only when lineage is ready and stats are present. Existing unavailable cards unchanged.
   - Four cards in `lg:grid-cols-2`, paired like `UnitMatchups` (away offense / home defense, home offense / away defense).
   - Summary line `Raw PPP 3.25 → adjusted 3.60 → rating +1.84 (#5)`; defense reads "PPP allowed". Second line `Prior 17% · 6 games, 59 possessions`, plus "· N not used" when games were excluded. Preseason-only: "No completed games yet · rating is the preseason prior (100%)", no table.
   - "Game-by-game" table: opponent with week, possessions, raw, adjusted, contribution; last row "Preseason prior"; footer "Rating" (equals column sum); † marks missing-context rows; excluded games listed below with a plain reason; `overflow-x-auto`, `tabular-nums`.
   - Unavailable unit: "Breakdown unavailable for this rating…", `role="status"`, no numbers.
   - Rank is plain text, not `RankChip`.
6. **Intro copy:** the audit's sentence ("Ratings use opponent-adjusted scoring per possession plus a shrinking preseason prior. The tables show raw statistics and are not combined to form the rating."), then: prior plus per-game contributions add up to the rating; the prior's share shrinks as possessions accumulate (links to `/model/method#prior` and `#updates`); defense rows measure the opposing offense; ratings are on a standardized scale, not points; small rank gaps are near ties; incomplete-data games are left out or used without opponent context.
7. **Fixtures** in `web/src/test/fixtures/matchup.ts`: `fixtureBreakdown` builds synthetic component rows through the real `buildUnitBreakdown`. Default `/matchup/1` gets one excluded game and one missing-context row. `RATING_BREAKDOWN_MISMATCH_GAME_ID = 987657` (home defense off by 0.01 → unavailable). `PRESEASON_BREAKDOWN_GAME_ID = 987658` (all four units preseason-only). 987655/987656 keep their behavior; section absent there.
8. **Docs:** add the matchup section to `web/README.md`. Add one line to the audit report's follow-up table only if the audit branch has merged first; otherwise skip.

## Validation

- `web/src/lib/rating-breakdown.test.ts` (`node:test`, added to `test:publication` in `web/package.json`): weighted means and sum identity; defense pass-through; each mismatch cause (rating off by 1e-9, snapshot id, source, team, role); missing component and missing `snapshotId`; invalid cases (bad sum, exposure mismatch, string or NaN fields); preseason-only; missing-context and excluded-game mapping incl. unknown reason code; `opponentFor` home/away/absent; `componentId`.
- `matchup-rating-query.test.ts` (`drizzle.mock` + `.toSQL()`): components query params `[season, sha, ...ids]`, selects `evidence`, no cutoff/week predicate; schedule query uses an OR of two `IN` lists.
- New `web/e2e/matchup-ratings-breakdown.spec.ts`: `/matchup/1` (copy, 4 cards, summary regexes, disclosure closed then opens to table with prior last row and footer equal to rating, "allowed" on defense, † and excluded notes, method links); 987655/987656 section absent; 987657 one unavailable card and three ready; 987658 preseason-only copy and no tables; 390×844 and 320×568 touch viewports with all disclosures open have no horizontal page scroll and each summary ≥ 44px tall.
- Scope table-count assertions in `e2e/matchup.spec.ts` and `matchup-rank-colors.spec.ts` to the "Team stats" region.
- Commands:
  ```bash
  cd web && node --experimental-strip-types --test src/lib/rating-breakdown.test.ts src/lib/matchup-rating-query.test.ts
  make check
  make web-e2e
  git diff --check
  ```
- Fixture screenshots of `/matchup/1`, `/matchup/987657`, `/matchup/987658` at 390 and 320 wide.
- Read-only Preview check on one real Week 11 matchup: all four units `ready`, jsonb arrives parsed (or string fallback works), numbers look sane.
- Risks: float tolerance on real data could surface as "invalid" (fail-closed; Preview check catches it). Missing-context adjusted PPP differs slightly from `team_possession_adjusted` (label says "as used by the rating"). `ShareButton` serializes `matchup` and now includes the breakdown (<10 KB); accepted.

## Handoff/amendments

- Approved by the owner. Implementation by one worker-large subagent in this worktree; the orchestrator runs validation. Commit, push and PR need the owner's go-ahead.
- Amendments:
  - **Table columns (mechanical).** Previous: separate "Poss." column plus a 22rem minimum table width. Revised: possessions sit under the opponent name ("Wk 1 · 20 poss."), the table has no minimum width, and cell padding is tighter. Reason: at phone widths the contribution column (which holds the prior and rating values) was clipped inside the scroll area. Impact: none on interfaces or scope; the e2e spec now asserts no inner horizontal scroll at 390 and 320 wide.
  - **Existing e2e waits (mechanical).** `logos.spec.ts` and one test in `matchup.spec.ts` now wait for streamed content to be visible before reading it. They passed 16 of 16 on `origin/dev` and failed on this branch before the wait, because the larger page widens the window before the streamed content replaces the loading shell.
  - **Plain-language presentation (owner-requested after reviewing real Preview data).** Previous: summary line `Raw PPP 3.25 → adjusted 3.60 → rating +1.84 (#5)`, a "Game-by-game" disclosure with a "Contrib." column and a "Preseason prior" row, and a longer intro. Revised: a generated plain sentence per card (`adjustmentSentence`: tougher, weaker or about-average opponents, with a 0.05 threshold), a line "Rating +x.xx (#n), above/below average" (`ratingStanding`), a muted line giving the preseason estimate's share of the rating, a "Show the math" disclosure with an "Effect on rating" column and a "Preseason estimate" row, and a three-sentence intro that says the rating measures only points per possession, 0 is average, higher is better (including defense), and the Team stats tables do not feed it. A league-average PPP is not shown because it is not stored with the components. Reason: the owner found the original hard to understand, notably the defense sign and what the tables fed. Impact: copy and presentation only; no data, query, guard or unavailable-logic change. The hero assertion in `e2e/matchup.spec.ts` that no `Rating +n` text appears is now scoped to the hero (`[data-side]`).
  - **Season-to-date main table (owner-requested after reviewing real Preview data).** Previous: "Show the math" held the per-game table (one row per game with possessions, raw, adjusted and effect on rating). Revised: "Show the math" holds a running season-to-date table (`cumulativeByWeek`: one row per week, cumulative exposure-weighted raw and adjusted PPP, "+ opponent" line, † when any included game lacked opponent context, last row equal to the card headline), a caption saying adjusted values re-score past games with today's opponent ratings, and a sentence on how the rating blends the season-to-date adjusted number with the preseason estimate. The per-game table moved, unchanged, into a nested closed "Audit detail" disclosure so the effects still add up to the rating. No cumulative rating or cumulative effect is shown, because a running total of effects is not the rating at that point (effects are scaled by the final weights). Reason: single games of 9–14 possessions are noisy and the trend was hard to follow. Impact: presentation only; no data, query, guard or unavailable-logic change.
  - **Not done:** the read-only Preview check on a real Week 11 matchup needs the Preview database and is still open.
