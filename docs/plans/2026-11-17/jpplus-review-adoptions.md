# JP+ review adoptions

- **Status:** Approved, deferred until after the offseason model and methods work
- **Created:** 2026-11-17
- **Planner:** Sol
- **Deferral:** Owner decided on 2026-11-17 not to implement before the offseason model work. When resuming, tasks A and C can proceed as written; revisit B (projected score) against the final totals behavior (V5 totals are close to flat) and D (method sections) against the final rating scale and model description before implementing.
- **Approval source:** Owner approval in the 2026-11-17 planning session (decisions recorded in [the JP+ site review](../../decisions/2026-11-17-jpplus-site-review.md)).
- **Implementation log:** Pending
- **Commit policy:** Commit on local dev as tasks complete (default)

## Goal and acceptance

Add four display-only features learned from the JP+ review, all from existing release data: a weekly movers panel, a projected score, a record by size of model-vs-market difference, and two explanatory sections on `/model/method`. Done when every task below meets its acceptance criteria, the listed checks pass, and the existing `mobile-slate.spec.ts`, `mobile-matchup.spec.ts` and `axe.spec.ts` stay green unmodified.

## Baseline and constraints

- Baseline: `dev` at `1036c7e1`, clean, matching `origin/dev`.
- Web-only (`web/`). Read the active release. No schema, migration, pipeline or model change.
- **Versioning:** keep site version 2.0.0 (on `dev` as `2843f5fb`, not yet released to `main`). Add the items to the 2.0.0 section of `CHANGELOG.md`. Do not change `web/package.json`, `pyproject.toml`, the lockfiles, `route.test.ts` or `publication.spec.ts`.
- **Out of scope:** rating scale change, simulations and futures, résumé per-game contributions, opening/current line or CLV views, historical archive, any betting presentation, share-card (`ShareCard.tsx`) export changes.
- Betting policy: copy is descriptive only; no "picks", "edge" or betting language.

## Ordered changes

### A. Weekly movers panel (Teams)

- Reuse `weeklyMovement(current, history)` from `web/src/lib/team-analysis.ts` (already behind the Weekly change and Rank movement columns in `web/src/components/ratings/TeamsHub.tsx`).
- New pure helper `topMovers(movement, n = 5)` in `team-analysis.ts`: risers are `change > 0` sorted largest first; fallers are `change < 0` sorted most negative first; ties by team name; teams without a comparison excluded. A team with 0 or positive change can never appear under Down; fewer than 5 is allowed.
- Always national (ignores the conference filter), so it matches the national ranks it shows.
- New `web/src/components/ratings/WeeklyMovers.tsx`, rendered only when `view === "rankings" && group === "strength"` and no text search query is active, above the Ratings table. Rows: logo and team link, current rank, rank change, rating change. Note: "Ranked by rating change, not rank, because ranks also move when other teams change. A change after a bye reflects other games."
- Wrap in `ResponsiveDisclosure` (collapsed below `sm`, open from `sm` up, as `FeaturedGames` and `ModelRecord` on `/`) so the phone list keeps the density fixed in `session_logs/2026-11-17/01-mobile-review-fixes.md` (finding 11).
- Hidden when the preceding certified week is missing (same rule as the Weekly change column).

### B. Projected score

- Sign convention: `predictedSpread` is the home margin (+ means home favored; see `lib/betting-format.ts`, `lib/performance-market.ts`). New pure helper in `web/src/lib/`: `projectedScore(predictedSpread, predictedTotal)` returning `{ home: (total + spread) / 2, away: (total − spread) / 2 }` to one decimal; `null` if either input is null.
- Display "Model score: Ball State 21.3, Ohio 35.5", away team first (matches `TeamPair` and `MatchupHero`).
- `PredictionGameCard`: add the line without growing the first card past the `mobile-slate.spec.ts` invariant (`cardBottom <= navigationTop` at 390x844 with the 34 px safe area); if it does not fit, show it on the card only from `sm` up.
- List view: desktop `SlateGameRow` only; phone `CompactGameRow` unchanged (keeps the `<= 96` px cap at 390 and `<= 120` px at 320).
- `MatchupHero`: add `predictedSpread: number | null` to `MatchupData` in `web/src/lib/matchup.ts` (from `view.predictedSpread`; never parse the formatted `modelSpread` string). Render the score below `[data-testid="forecast-grid"]` inside the forecast box, not as a grid cell, so the cell-height checks hold; keep `bet.y + bet.height < 480` (390x844) and `< 520` (320x568) in `mobile-matchup.spec.ts`. Use `PhoneSwap` / `phoneTeamName` so long names (Florida International, Kennesaw State) do not wrap at 320.
- Hidden in market-only publication mode, like other forecasts (`lib/publication.ts`).

### C. Record by size of difference (Model page)

- Pure helper in `web/src/lib/` (for example `performance-bands.ts`), computed server-side in `clientView()` in `web/src/app/model/page.tsx` and added to `PerformanceView` (as `market` and `pairs` are), because `clientView` strips `gradedGames` to `{ week, spreadResult, totalResult }`.
- Difference is `abs(spreadEdge)` / `abs(totalEdge)` from `GradedGamePick` (the shopped quote that settled the grade), over all games with a non-null `spreadResult` / `totalResult`, including the three `cfbd_retrospective` Week 6 games. Not `canonicalSpread` / `canonicalTotal`.
- Half-open bands on the unrounded value: `diff < 3`, `3 <= diff < 5`, `diff >= 5`. Spread and total separate; show W-L-P, win %, decided count, and the 52.4% break-even reference.
- Unit test asserts the bands sum exactly to `overall.spread` and `overall.total`.

### D. `/model/method` content (`web/src/app/model/method/page.tsx`)

- New section `#reading-the-ratings` ("How to read the ratings"): units are standardized possession efficiency where 0 is the historical reference level and higher is better for both offense and defense; `overall_rating = (offense_rating + defense_rating) / 2` (V5 rating engine, `possession_live_replay.py`), so a displayed overall can differ by 0.01 from the average of the rounded displayed parts; what rank and weekly change mean. Other facts only from `docs/modeling/v5_status.md` and `docs/modeling/rating_system_requirements.md`.
- New section `#other-models` ("How Stratum differs from other models"): SP+, FPI and margin-of-victory models (Sagarin/Massey) in general public terms; Stratum's distinctions (possession-based, market-blind, point-in-time, live public record from Week 0).
- Add both IDs to the `CONTENTS` array; keep all existing IDs (`#team-strength`, `#prior`, `#updates`, `#forecasts`, `#grading`, ...) unchanged.
- Point the "Read the methodology" link in the `TeamsHub.tsx` footer "How to read these ratings" disclosure to `/model/method#reading-the-ratings`.

## Validation

- Unit tests (`npm run test:publication`): `topMovers` (ties, zero change excluded from both lists, missing comparison, fewer than 5); `projectedScore` (home favorite, away favorite, pick'em, null input); bands (sum equals headline, values exactly 3.0 and 5.0, 4.95, pushes, retrospective games included).
- Fixtures and Playwright specs in `web/e2e/`: movers present on Strength, absent on `?group=resume`, with a search query, and without a preceding week; collapsed on phones. Projected score on card, desktop list and matchup; absent from `CompactGameRow`. Bands table on `/model`. New method anchors resolve.
- `make check` and `make web-e2e`.
- Visual check at 1440 and 390 (and 320 for the matchup) in light and dark with `PORT=3112 make web-local ENV=production`.
- `git diff --check`, and `uv run mkdocs build --strict` for the documentation and session log.

## Handoff/amendments

- Approved; implement in a fresh task in a worktree. Implementation log: `session_logs/<date>/NN-jpplus-review-adoptions.md`. No push or deployment without separate exact release approval.
- A mechanical amendment may proceed only if architecture, interfaces, scope and acceptance remain unchanged; a material conflict returns to Sol for review. Record each amendment's reason, previous approach, revised approach and impact here. None so far.

### Copy-ready Terra prompt

> Implement the approved contract `docs/plans/2026-11-17/jpplus-review-adoptions.md` on a new worktree branched from local `dev`. Read `AGENTS.md` and `docs/status.md` first. Work through tasks A to D in order, commit each locally on the worktree branch with conventional commits, add the 2.0.0 `CHANGELOG.md` entries, and run `make check`, `make web-e2e` and the visual checks listed in the contract. Do not change version files, the share card, or anything listed as out of scope. Write the implementation log, integrate into local `dev`, and do not push or deploy.
