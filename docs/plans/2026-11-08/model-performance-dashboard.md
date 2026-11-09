# Model performance dashboard

- **Status:** Implemented
- **Created:** 2026-11-08
- **Planner:** Sol
- **Approval source:** Owner approved the plan in the planning session of 2026-11-08
- **Implementation log:** `session_logs/2026-11-08/02-model-performance-dashboard-impl.md`
- **Commit policy:** Commit with implementation (owner approves commit, push and PR)

## Goal and acceptance

`/model` gains the market's error beside the model's for the same games, large-miss metrics, a season-to-date trend, and a clear separation of accuracy from profitability. The model is compared to the **retained pre-kickoff line** only; closing-line comparison is out of scope (no true closing line exists; capture timestamps are fetch times, `docs/modeling/record_methodology.md`).

Acceptance: every section below renders on `/model` in fixture mode at 320, 390, 640 and 1280 wide with no horizontal scroll; unit tests, `make check`, `make web-e2e` and `git diff --check` pass; the Preview readback agrees with the fixtures.

Out of scope: schema, migration, pipeline and V5 methodology changes; staking; units and ROI (the 2026-10-03 decision stays: no profit, units or ROI on `/model`).

## Baseline and constraints

- Branch `connorkitchings/model-performance-dashboard` off `origin/dev` (7505a4c2).
- The displayed line (`predictions.home_team_spread_line` / `total_line`) is the shopped best quote. The canonical pre-kickoff line is `market_snapshots.spread` / `total` (`spread_rule` / `total_rule`), reached via `prediction_grades.market_snapshot_id` or `prediction_market_selections.snapshot_id`, per target.
- The record is settled at the best quote inside the canonical snapshot (`grading.py`, `select_best_quote`). The official W-L-P is unchanged; only the model-vs-line error comparison uses the canonical line.
- Line source is stored in `prediction_grades.grading_version`: `model_side_best_quote_v2:retained_prekickoff` or `:cfbd_retrospective`.
- `e2e/model.spec.ts` bans "ROI", "profit", "units", "net return", "closing line" and "-110" on `/model`.

## Ordered changes

1. **Loader, `web/src/lib/v5.ts` `getV5PerformanceDetail`.** Do not add more correlated scalar subqueries (see `docs/plans/2026-10-29/01-web-read-performance.md`). Join `prediction_grades` once per target on `(run_id, game_id, target)` (carries `result`, `grading_version`, `market_snapshot_id`) and `market_snapshots` via that id (`spread`, `total`, `spread_rule`, `total_rule`) using aliased left joins or one lateral per target; consolidate the existing `result` subqueries into the join if behaviour stays identical. Check generated SQL binds under `seasonReleaseDb`; compare row counts and the existing summary before and after. Add fields as optional to `DetailRow` and `GradedGamePick`; extend `PERFORMANCE_DETAIL_SPEC` in `web/src/lib/row-guard.ts` (nullable numbers/strings). Add per-week `ungradedGames` to `WeekPerformanceRow` (selected games with no final score or no eligible line).
2. **New pure module `web/src/lib/performance-market.ts`** (no DB imports): `lineSourceOf(gradingVersion)` → `prekickoff` | `retrospective` | `unknown` (unparseable fails closed to `unknown`); `comparableGames`, `marketComparison`, `weeklyMarketComparison`, `worstMisses`, `lineSourceCounts`; `BIG_MISS_POINTS = 28`.
3. **New pure module `web/src/lib/performance-trend.ts`:** `weeklyAndCumulative(games, weeks)`, `breakEvenBand(decided)`.
4. **`web/src/app/model/page.tsx`:** compute server-side; pass the client compact results (trend rows, comparisons, top-10 worst misses per target, line-source counts, plus existing per-game results). Add `searchParams?: Promise<{ fixture?: string }>` awaited only inside the `isUiTestMode()` branch (pattern: `web/src/app/teams/[team]/page.tsx`); add a `?fixture=partial` variant for empty states.
5. **UI, `web/src/components/PerformanceDashboard.tsx` plus new `web/src/components/model/RecordTrendChart.tsx`.** Final page, in order: pick record cards (with the luck-band caveat below the two KPI cards so the Spread card stays above y = 330 on 390x844); season trend (one panel per target, "Show as table"); week by week (This week and Season to date per target); model vs the betting line (one card per target); season-wide diagnostics ("Average miss, every game with a final score (N games)"). Reuses `Card`, `Disclosure`/`ResponsiveDisclosure`, `SummaryLine`, `Notice`, `accuracyRecord`, `BREAK_EVEN_PCT`, `niceTicks`, `ChartTable`. Phone: no disclosure starts open, no horizontal scroll at 390 and 320, 44px targets. Copy: "average miss", "leaned", "betting line", "against the spread" spelled out; no "MAE", "bias", "closing line" or profit language; `pp` for win-rate gaps, `pts` for game points; "Win rate shows how often picks were right; it is not a betting result." The biggest-misses section and the target selector were removed (amendments 5 and 6).
6. **Method page `web/src/app/model/method/page.tsx` (~L90-92):** optional link to the same-game comparison.
7. **Docs:** "Model page market comparison" section in `docs/modeling/record_methodology.md` (inclusion rule, canonical line, threshold, tie rule); decision-log entry for the threshold and caveat band.

## Metric definitions

- Spread sign: `predictedSpread` is the forecast home margin; market implied home margin is `canonicalSpread === 0 ? 0 : -canonicalSpread` (never `-0`). Actual margin = home minus away; actual total = home plus away.
- Record: unchanged. Win % = W/(W+L), pushes excluded, null shown as "—"; gap to 52.4% in "pp".
- Comparison set per target: grade present, both final scores, model forecast, non-null canonical line, `lineSourceOf` = `prekickoff`. Pushes included. Retrospective and unknown excluded and counted in the footnote.
- Model error = prediction minus actual; line error = line-implied minus actual. Average miss = mean absolute error; lean = mean signed error. Round only for display.
- Closer: model closer iff `|modelError| < |lineError|` strictly; line closer iff strictly greater; exact ties are "even". "Model closer in X of N games" has N excluding ties; even count shown beside it.
- Big misses: absolute error strictly greater than `BIG_MISS_POINTS`; worst-10 by model absolute error descending, ties by `gameId` ascending.
- Small-sample band: 52.4 ± 1.96·√(0.524·0.476/n), used only to choose caveat wording.

## Decisions (defaults accepted at approval)

1. Big-miss threshold 28 points (alternative 21), fixed before 2026 tail numbers are examined (`evaluation.md`).
2. Statistical "within normal luck of break-even" caveat wording.
3. Retrospective-graded games excluded from the comparison; count shown.
4. Old all-finals average-miss diagnostic kept and relabelled.
5. Units and ROI stay off `/model`.
6. Exact error ties excluded from the percentage denominator, shown as "even".
7. Scatterplot: separate item below; the owner has not yet said which chart failed.

## Validation

```bash
cd web && node --experimental-strip-types --test src/lib/performance-market.test.ts src/lib/performance-trend.test.ts src/lib/row-guard.test.ts
make check
make web-e2e
git diff --check
```

- Unit (`node:test`, added to `test:publication` in `web/package.json`): `performance-market.test.ts` with a hand-computed spread fixture (push, loss, tied market, big win, ungraded game, retrospective game) and a matching totals fixture; empty input gives `null`, never NaN; `unknown` suffix excluded; push-only week has null rate and carries season-to-date record; miss of exactly 28 not counted, counted at threshold 21; `canonicalSpread === 0` gives no `-0`; tie rule and denominator; per-week ungraded count. `lineSourceOf` (both real suffixes, null, unexpected string). `breakEvenBand(559)` ≈ [48.3, 56.5]; `breakEvenBand(0)` null. `row-guard.test.ts` accepts new nullable fields; `performance-sections.test.ts` source-text assertion for the `market_snapshots`/`grading_version` read.
- Lockstep e2e updates: `web/e2e/model.spec.ts` L56 keeps "-2.4 pp vs 52.4% break-even"; L63 "Spread MAE" updated for the rename; `web/e2e/mobile-model.spec.ts` L12 (Spread KPI above y = 330 at 390x844) and L32 (no group named "Pick target") pass unchanged; banned-word check extended to the new sections.
- Fixtures: extend `web/src/test/fixtures/performance-mobile.ts` (canonical lines, grading versions, one retrospective game, one tied market, one exact error tie, one pick'em with spread 0; recompute KPI assertions deliberately). e2e: comparison numbers, chart accessible name and table toggle, worst-miss links, no horizontal scroll at 320/390/640/1280, 44px "Misses for" control.
- Read-only Preview readback via `make web-local ENV=preview`: check about 10 games that `-canonicalSpread` matches the market favorite, that `grading_version` suffixes are present, and that the retrospective count matches known fallback history. If any disagrees, stop and report. Screenshots at 390 and 320.

## Handoff/amendments

Approved by the owner. Implementation by one worker-large subagent; the orchestrator runs validation. Commit, push and PR need the owner's go-ahead. Preview readback is read-only. Risks: spread sign error (fixture plus readback); `grading_version` drift (fails closed, excluded count shown); readers expecting the record settled at the displayed line (About text states the difference); small-sample noise (no weekly "beat the line" colouring); query cost (joins, not subqueries).

### Separate item: scatterplot touch repro (moved to `docs/plans/2026-11-08/mobile-scatter-details.md` and its own PR)

Add repro tests to `web/e2e/mobile-scatter.spec.ts`: (a) dense 138-team fixture `/stats?chart=efficiency&week=2&fixture=slate` on a 390px phone, a tap in a dense cluster gives a visible result in the viewport; (b) tap with `window.scrollY > 0` and `prefers-reduced-motion: no-preference` (`globals.css` ~L236 applies `transform: scale(0.985)` to `[role="button"]:active` at 639px and below) still lands on the intended team; (c) market board `/stats?chart=market-board` tap toggling. Step 2 only if one fails: focused fix under its own contract. If all pass, record the result and keep the tests.

### Amendments

1. **Reason:** `WeekPerformanceRow` does not exist in the code. **Previous:** add per-week `ungradedGames` to `WeekPerformanceRow`. **Revised:** add the type `WeekPerformanceRow { week; ungradedGames }` and `PerformanceDetail.weekRows`, one entry per graded week. **Impact:** additive; the publication fixture gained `weekRows`.
2. **Reason:** the fixture needed enough graded games to cover the retrospective, exact-tie, pick'em and big-miss cases. **Previous:** KPI assertions recomputed deliberately. **Revised:** the mobile fixture now has nine games over weeks 0 to 3 (week 3 in progress with two ungraded games), and both KPI cards read 3–3–2 at 50.0%, so the "-2.4 pp vs 52.4% break-even" assertion is unchanged. **Impact:** `e2e/model.spec.ts` record assertion changed from 1–1–1 to 3–3–2.
3. **Reason:** wording. **Previous:** the Spread KPI and the "Pick target" assertions stay. **Revised:** `Spread MAE` and `Total MAE` are now `Spread average miss` and `Total average miss`; the season-wide paragraph opens with "Average miss, every game with a final score (N games)". **Impact:** the `model.spec.ts` assertion follows the rename.
4. **Reason:** owner request after reviewing the page on production data. **Previous:** section order was pick record, season trend, model vs the betting line, biggest misses, week by week, diagnostics. **Revised:** pick record, season trend, week by week, model vs the betting line, biggest misses, diagnostics. **Impact:** layout order only; no assertions changed (`model.spec.ts` and `mobile-model.spec.ts` pass).
5. **Reason:** owner review of the page on production data. **Previous:** one combined trend chart; weekly table with a Spread/Totals selector, clickable KPI cards, per-week average miss and a 12-column layout; "In progress" driven by `ungradedGames`. **Revised:** (a) trend chart is one panel per target, dots for each week and a line for the season to date, no break-even line, with at most four week labels so the last two never collide; (b) the weekly table is Week plus This week and Season to date under Spread and Totals, one cell per period (record then win rate); (c) the target selector, the KPI-card filter, the weekly average-miss column and the "Overall Accuracy" line above the table are removed, and the page no longer ships per-week miss data; (d) `WeekPerformanceRow` gains `unplayedGames`, and "In progress" is driven by it, because three finished Week 6 games with no retained line were ungraded but not unplayed. **Impact:** `model.spec.ts` and `mobile-model.spec.ts` updated (no filter tests, KPI cards located by `[data-card]`, chart named per panel); `weeklyMarketComparison` stays in the pure module and its tests but is no longer used by the page. Preview readback (2026-11-08): sign convention, `retained_prekickoff` suffix and the 559/558 compared counts agree with the database; zero `cfbd_retrospective` rows exist in Preview.
6. **Reason:** owner review of the page. **Previous:** a "Biggest misses" section listed the ten worst model misses per target, with a "Misses for" control and links to `/matchup/[gameId]`; a per-week average-miss helper fed the weekly table. **Revised:** the section, its control, the page payload for it, `worstMisses`, `weeklyMarketComparison` and their tests and e2e checks are removed; the "Misses over 28 pts" counts stay in the model-vs-line cards, and the diagnostics sentence no longer mentions a target filter. **Impact:** the planned worst-10 ordering rule and the "Misses for" 44px-control check no longer apply.

### Readback results (2026-11-08, read-only Preview, active release `preview-season-2026-5d50a63ef62a6751f30d7599`, week 11)

- Spread sign: 10 random selected spread games joined to `season_release_games` for team names; in every row the team named by `-canonicalSpread` (negative favors home) is the market favorite. Two rows (Fresno State at San Jose State, consensus +7, model +1.9; South Carolina at Arkansas, consensus +8.5, model -8.4) are model-vs-market disagreements, as the rule predicts.
- Retrospective count: 0 `cfbd_retrospective` rows in every one of the 14 2026 Preview releases (active release: 1117 `retained_prekickoff` grades). No documented expectation exists, so none is asserted.
- Loader before and after (`origin/dev` at 7505a4c2 vs this build, same release, both via `make web-local ENV=preview`): spread record 271-279-9 and totals 267-289-2 (559 and 558 graded picks) identical; all 11 weekly spread and total records identical. The game count shown (562) equals a direct count of selected games with a final score (562 of 629 selected; 67 are unplayed Week 11).
- Screenshots of `/model` at 390 and 320 wide on real data: no horizontal scroll, all sections render.
- Defect found and fixed during the comparison: a stray ";" in the diagnostics sentence left over from removing the target selector.
