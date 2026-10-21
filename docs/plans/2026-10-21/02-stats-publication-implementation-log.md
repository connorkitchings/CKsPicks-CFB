# Stats publication implementation log

- **Date:** 2026-10-21
- **Contract:** Phase 4 of [Site reorganization, design consistency and performance](01-site-reorganization-and-performance.md), which runs tasks 2 to 6 of [Charts pre-publication verification](../2026-10-20/03-charts-pre-publication.md) against `/stats`
- **Status:** Edge-state audit and runbook written; real-data review, Preview review, measurements and owner acceptance are not yet done.

## Edge-state coverage

Paths are relative to `web/`. "Added" marks a test written during this audit.

| Edge state | Covered by | Gap and resolution |
|---|---|---|
| (a) Release without chart relations (`chartSet` null) shows Stats unavailable; navigation still fine | Resolver gives `chartSet` null for missing, partial or unknown relations: `src/lib/season-release.test.ts:185`, `:193`, `:198-205`. Page arrival notice: `e2e/charts.spec.ts:304` (`fixture=unsupported`). Cache key for a null set: `src/lib/release-cache.test.ts:62` | Navigation on the unavailable page was not asserted. Added `e2e/charts.spec.ts:315` (four items, page heading present, no picker, HTTP 200). The query-layer `null` return of `getChartsDb` needs a database and has no unit test; the page branch that consumes it is covered |
| (b) Retained `charts_v1` release shows release-backed PPA only, no explosiveness toggle | Resolver: `src/lib/season-release.test.ts:156`, `:162`. Efficiency rows: `src/lib/charts.test.ts:319`. Page: `e2e/charts.spec.ts:351` (`fixture=v1`, no `efficiency-metric-switcher`, `PPA/play`). Metric reset across navigation: `e2e/charts-capability.spec.ts:6`, `:22`. Game log metrics: `src/lib/chart-gamelog.test.ts:164` | None |
| (c) Unavailable chart query shows the unavailable card, not an error page | `e2e/charts.spec.ts:304-313` (`fixture=error`, `adjusted-error`); possession `e2e/charts-possession.spec.ts:107`; rating trajectory `e2e/charts-ratings.spec.ts:120` | None. Net success, efficiency and game log read only the base load, which `fixture=error` covers |
| (d) Week or team with no chart rows | Team without games: `e2e/charts.spec.ts:294` (Wyoming), `:242`; `src/lib/charts.test.ts:168`, `:192`; `src/lib/chart-gamelog.test.ts:131`; `e2e/charts-gamelog.spec.ts:75`. No completed weeks (net success, game log): notice strings in `src/app/stats/page.tsx` | No test reached the "This chart starts after Week 2 is complete." notice (a release with no stored adjusted or possession windows). Added `e2e/charts.spec.ts:326` using `fixture=slate` |
| (e) Disabled gate returns 404 for `/stats` and `/charts`, including query parameters | `e2e-charts-gate/charts-disabled.spec.ts:7` (both bases, nine query strings, no Stats link in navigation); three-item navigation `:19`; server HTML without JavaScript `:43`; flag parsing `src/lib/charts-gate.test.ts:5`. Redirect with query: `e2e/redirects.spec.ts` | None |
| (f) `?team=` with an unknown team | Parser: `src/lib/chart-config.test.ts:31`. Page: `e2e/charts.spec.ts:562` (efficiency). | Other charts were not exercised. Added `e2e/charts.spec.ts:336`, which combines an unknown team with every week-based chart |
| (g) `?week=` out of range or malformed | Coercion: `src/lib/charts.test.ts:116`; Week 0 and 1 coercion on tab switch `e2e/charts.spec.ts:141` | Page behaviour for `99`, `-1`, `abc`, `1.5`, `123` was not tested. Added `e2e/charts.spec.ts:336` (status 200, no notice, clamped to the latest week) |
| (h) Window loaders keyed by week cannot create unbounded release-cache entries | Not covered | Audited `src/app/stats/page.tsx`: the request value must match `^\d{1,2}$`, then `coerceWeek(requested, available)` replaces it with a stored week, and `getTeamAdjustedEpa` / `getTeamPossessionAdjusted` receive `week + 1`, which is always a stored `as_of_week` (`adjustedThroughWeeks` is the stored window minus one). The game log uses `max(adjustedWeeks)`. So distinct cache keys are bounded by the stored windows and no clamp was missing. Added the invariant as `src/lib/charts.test.ts:134` |

## Defects found and fixed

| Defect | Location | Fix |
|---|---|---|
| None found in application code. The audit found test gaps only (rows (a), (d), (f), (g), (h) above) | | Tests added in `web/e2e/charts.spec.ts` and `web/src/lib/charts.test.ts` |

## Real-data review matrix

Filled during owner testing.

| Chart | Week or window | Team | Reviewer | Result | Notes |
|---|---|---|---|---|---|
| | | | | | |

## Preview review

Filled during owner testing.

| Check | Date | Deployment | Result | Notes |
|---|---|---|---|---|
| | | | | |

## Performance numbers

Filled during owner testing. Source: `node web/scripts/measure-routes.mjs <url>`, local and Vercel Preview, cold and warm.

| Route | Environment | Cold TTFB | Warm TTFB | Notes |
|---|---|---|---|---|
| | | | | |

## Owner acceptance

Filled during owner testing.

| Decision | Owner | Date | Defect list or notes |
|---|---|---|---|
| | | | |
