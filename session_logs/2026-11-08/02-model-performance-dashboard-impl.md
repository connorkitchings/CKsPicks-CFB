# Session: Model performance dashboard implementation

## TL;DR

- **Worked On:** Implemented the approved model performance dashboard contract on `/model`.
- **Outcome:** `/model` now shows the pick record with a luck-band caveat, a season trend chart, the model against the retained pre-kickoff betting line for the same games, the biggest misses, a week by week table with season-to-date records and average misses, and relabelled season-wide diagnostics. Loader joins replace the per-row grade subqueries and add the canonical line and grading version.
- **Plan Contract:** [`docs/plans/2026-11-08/model-performance-dashboard.md`](../../docs/plans/2026-11-08/model-performance-dashboard.md)
- **Approval / Status:** Approved by the owner on 2026-11-08; Implemented (owner asked to close out on 2026-11-08).
- **Blockers:** None. The scatterplot work moved to its own contract and PR (`mobile-scatter-details`).
- **Next:** Merged to `dev` through its own PR.

**tags:** ["web", "model-page", "performance"]

## Context and Decisions

- The record is settled at the best quote; only the error comparison uses the canonical line from `market_snapshots`, reached through `prediction_grades.market_snapshot_id`.
- Line source comes from the `prediction_grades.grading_version` suffix; anything unrecognized is "unknown" and excluded (fails closed).
- Big-miss threshold is 28 points, strictly greater than; exact error ties are "even" and excluded from the closer denominator.

## Work Completed

- Loader: `getV5PerformanceDetail` joins `prediction_grades` and `market_snapshots` once per target (aliased left joins) and returns `canonicalSpread`, `canonicalTotal`, `spreadGradingVersion`, `totalGradingVersion` and `weekRows`.
- Pure modules `performance-market.ts` and `performance-trend.ts` with `node:test` suites using hand-derived fixtures.
- `/model` page computes the views on the server and supports `?fixture=partial` in UI-test mode; dashboard and `RecordTrendChart` render the new sections.
- Method page links to the comparison; methodology doc section and decision-log entry added.

## Files Modified

- `web/src/lib/v5.ts`, `web/src/lib/row-guard.ts` — joins, new fields, spec
- `web/src/lib/performance-market.ts`, `performance-trend.ts` (+ tests), `row-guard.test.ts`, `performance-sections.test.ts`, `web/package.json`
- `web/src/app/model/page.tsx`, `web/src/app/model/method/page.tsx`
- `web/src/components/PerformanceDashboard.tsx`, `web/src/components/model/RecordTrendChart.tsx`
- `web/src/test/fixtures/performance-mobile.ts`, `web/src/test/fixtures/publication.ts`
- `web/e2e/model.spec.ts`, `web/e2e/mobile-model.spec.ts`
- `docs/modeling/record_methodology.md`, `docs/decisions/decision_log.md`, the contract

## Validation

- [x] `node --experimental-strip-types --test` on the market, trend, row-guard and performance-sections suites: 27 pass
- [x] `make check`: pass
- [x] `make web-e2e`: 436 passed, 10 skipped; one failure in `mobile-scatter.spec.ts` ("market board taps select a game"), a file owned by the separate scatterplot item
- [x] `npx playwright test e2e/model.spec.ts e2e/mobile-model.spec.ts`: 28 pass
- [x] `git diff --check`: clean
- [x] Preview readback (2026-11-08): sign convention, `retained_prekickoff` suffixes, 0 retrospective rows in all 14 releases, record and weekly parity with `origin/dev`, 562 games equals direct count; screenshots at 390 and 320 clean

## Amendments and Blockers

- Six amendments recorded in the contract (later redesigns: weekly table, per-target trend, removed selector, average-miss column and biggest-misses section; `unplayedGames` drives "In progress") (`WeekPerformanceRow` added as a new type; fixture records now 3–3–2; MAE relabelled).

## Handoff Notes

- **Resume at:** nothing outstanding.
- **Watch out for:** the joins now run against Preview and match `origin/dev` on every record; readback numbers are in the contract.

## Later redesigns and readback (2026-11-08)

- Redesigns after owner review: weekly table is Week plus This week and Season to date per target; trend is one panel per target; the target selector, KPI-card filter, per-week average-miss column and the biggest-misses section were removed; `WeekPerformanceRow.unplayedGames` fixes "In progress" (three finished Week 6 games with no retained line were ungraded but not unplayed).
- Fixed a stray ";" in the season-wide diagnostics sentence.
- Readback: see "Readback results" in the contract. No `docs/status.md` change (week and release state unchanged).
