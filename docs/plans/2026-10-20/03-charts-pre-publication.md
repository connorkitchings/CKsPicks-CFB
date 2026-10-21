# Charts pre-publication verification

- **Status:** Draft
- **Created:** 2026-10-20
- **Planner:** Sol
- **Approval source:** Pending (owner approval of this contract; publication itself needs a separate owner decision)
- **Implementation log:** Pending
- **Commit policy:** Commit with the work it governs; each verification result is recorded in the implementation log

## Goal and acceptance

`dev` is now the branch for testing and preparing Charts before they are published. This contract defines what "ready to publish" means, so the publication decision is made from recorded evidence rather than from the fact that the code exists.

Charts is ready to publish only when every item holds:

1. A real-data visual review of every ready chart is recorded, on desktop and at 390px, in light and dark themes, for the current week and at least one earlier week.
2. A review of an enabled Preview deployment built from `dev` is recorded and accepted by the owner.
3. Failure and edge states are verified: a release without chart relations, a retained `charts_v1` release, an unavailable chart query, and a team or week with no data.
4. Chart requests are measured and acceptable, and do not affect the speed of Picks, Results, Ratings or Performance.
5. The exact publication step and its rollback are written down and rehearsed on Preview.
6. The owner records the publication decision. Until then Production keeps `CFB_CHARTS_ENABLED` unset and `/stats` returns 404.

## Baseline and constraints

Charts was renamed Stats by the [2026-10-21 reorganization plan](../2026-10-21/01-site-reorganization-and-performance.md); `/charts` references below now mean `/stats`.

Inspected on `dev` at `78c90e34`.

- **Gate.** `isChartsEnabled` returns true only for the exact string `CFB_CHARTS_ENABLED=1` (`web/src/lib/charts-gate.ts`). Unset, empty, `0` and anything else disables Charts everywhere, including local development and Preview. The root layout resolves the flag on the server and passes a boolean to `SiteNav`; a disabled `/stats` returns a real HTTP 404 before any chart parameter or data is read ([gate contract](../2026-10-18/02-charts-publication-gate.md)). Changing the flag needs a rebuild or redeploy.
- **Charts in the registry** (`web/src/lib/chart-config.ts`): net success rate, efficiency vs explosiveness, adjusted PPA/play, possession efficiency, and game log are `ready: true`. V5 rating trajectory is built but `ready: false` by owner decision, reserved for a later move to the Ratings tab. It stays out of this contract's scope.
- **Data.** Preview and Production both serve the `resume_v1` projection set, which serves the `charts_v2` chart tables. Migrations 0026, 0027 and 0028 are applied on both ([status](../../status.md)). No further migration is needed to publish. Retained `charts_v1` and `core_v1` releases remain readable and show the unavailable or reduced states.
- **Existing evidence.** The Charts fixture suites, the gate suite (`npm run test:charts-gate`) and CI all pass on `dev`. A fixture screenshot review of 32 screenshots and 12 PNG exports was done on October 18; it is not owner acceptance and does not cover real data. The Week 8 `charts_v2` candidate passed all 24 verification checks and its tables matched the earlier certified snapshot ([parity evidence](../2026-10-18/01a-parity-evidence.md)).
- **Owner position.** Charts Production approval has been withheld pending manual review ([expansion contract](../2026-10-18/01-charts-review-and-expansion.md)). Local completion, a green CI run or Preview acceptance does not authorize Production.
- **Excluded:** model code, ratings, grading, release or projection format, the rating trajectory chart, and any Production flag change.
- **Cannot be done from the repository:** setting an environment variable in Vercel. The owner makes that change.

## Ordered changes

### 1. Keep the plan statuses honest

The Charts contracts ([module](../2026-10-16/01-charts-module.md), [expansion](../2026-10-18/01-charts-review-and-expansion.md), [ratings and possession](../2026-10-18/03-charts-ratings-and-possession.md)) are In Progress, with this contract as their open item. Their statuses and the plan index say so (done in the commit that adds this contract).

### 2. Real-data local review

- **Run:** `CFB_CHARTS_ENABLED=1 make web-local` (Preview database, read-only). `make web-local` passes the environment through to the dev server; confirm `/stats` shows four navigation items (three while the gate is off).
- **Review matrix:** each of the five ready charts, at 1280px and 390px, in light and dark themes, for the current week and one earlier week, with and without a highlighted team (`team=`), including the table view, the conference filter and the keyboard tooltip. Export a PNG from each chart in both themes.
- **Record:** a short table in the implementation log with the defects found, each with the chart, width, theme and a screenshot path. Defects block publication; cosmetic notes do not.
- **Acceptance:** zero blocking defects, or the owner accepts each remaining one in writing.
- **Optional fixture screenshots** for regression comparison: `CFB_CHART_VISUALS=1 npm run test:ui -- e2e/charts-visual.spec.ts --workers=1` (fixture data only; files go to the ignored `test-results/`).

### 3. Preview deployment review

- **Owner action:** set `CFB_CHARTS_ENABLED=1` for the Vercel **Preview** environment only, so builds of `dev` show Charts. Production stays unset. Redeploy after changing it.
- **Check on the Preview URL:** `/stats` returns 200, navigation shows four items, the five charts load real data, and Games, Ratings and Model behave as before.
- **Acceptance:** the owner reviews the deployment and records acceptance or a defect list.

### 4. Failure and edge states

Verify, against real Preview data where possible and otherwise with the existing fixtures:

- a release without chart relations, and a retained `charts_v1` release (efficiency shows release-backed PPA only, with no explosiveness toggle);
- an unavailable chart query shows the unavailable card, not an error page;
- a week or team with no chart rows;
- the disabled gate still returns 404 with query parameters (`npm run test:charts-gate`).

Each should already be covered by the existing suites; any gap found gets a test in the same commit as its fix.

### 5. Performance

- Measure time to first byte for each chart and `?team=` combination against Preview, cold and warm, and record the numbers.
- Confirm chart queries run only on `/stats`: `/`, `/ratings` and `/model` keep their time to first byte with Charts enabled.
- **Acceptance:** each chart's cold time to first byte is below the slowest existing page's, or the owner accepts the figure. If not, add the measurement to the defect list with the slow query.

### 6. Publication and rollback runbook

Write the publication procedure in `docs/ops/weekly_runbook.md` (new "Publishing Charts" section), so it exists before the decision:

1. Owner sets `CFB_CHARTS_ENABLED=1` in the Vercel **Production** environment and redeploys.
2. Verify `/stats` returns 200, navigation shows four items, `/api/health` is 200, and the four existing pages still work.
3. **Rollback:** unset the variable (or set `0`) and redeploy; `/stats` returns 404 and the navigation returns to three items. No data or release change is involved.

Rehearse steps 1 to 3 on Preview before the decision.

### 7. Weekly releases while Charts is unpublished

Each weekly Production release must keep staging with `resume_v1`, which requires the chart tables. After each release, repeat the Task 2 smoke check on the new week against Preview (a few charts, desktop only) so a regression in chart data is caught before publication, not after.

## Validation

- `npm --prefix web run lint`, `typecheck`, `test:publication`, `build`, `test:ui` (includes the Charts suites), and `test:charts-gate`.
- `make test` and `uv run ruff format --check . && uv run ruff check .` for any Python change.
- `uv run mkdocs build --strict` and `git diff --check` for the documentation.
- The recorded real-data review, Preview review, performance numbers and edge-state results listed above.

## Risks and stop gates

- **Publishing by accident.** Only the owner sets the Production variable. Nothing in this contract changes Production configuration.
- **Stale or partial chart data.** A release prepared without chart relations hides Charts for that release. The weekly checks in Task 7 catch it.
- **Real data differs from fixtures.** The fixture review does not cover real teams, week windows or long names; Task 2 is the guard.
- **Slow charts.** Task 5 gates publication on measured numbers.
- **Stop:** any blocking defect, any failed check, or any ambiguity about what the owner approved returns to the owner before further work.

## Handoff/amendments

- **Approval and resume gate:** the owner approves this contract. Approval authorizes the review, tests and documentation above. It does not authorize setting any Vercel variable, activating a release or publishing Charts.
- **Implementation log:** `session_logs/YYYY-MM-DD/NN-charts-pre-publication.md`, created by the implementing session.
- **Precise next action:** run Task 2 (local real-data review) and record the findings.
- **Progress (2026-10-20):** the owner walked all five ready charts on Preview data through `make web-local` and approved a round of polish (see `session_logs/2026-10-20/05-charts-review-and-polish.md`). That was an informal look, not the recorded review matrix in Task 2, and not Preview-deployment acceptance; the contract stays Draft until the owner approves it.
- **Amendments:** a mechanical amendment may proceed only if architecture, interfaces, scope and acceptance remain unchanged; a material conflict returns to the planner. Record each amendment's reason, previous approach, revised approach and impact here.
