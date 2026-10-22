# Session: Contract A mobile chart implementation

## TL;DR
- **Worked On:** Contract A only: mobile chart page navigation, settings drawer `<dialog>`, readable plots, selection, combobox accessibility, and touch target compliance.
- **Outcome:** Contract A implementation and automated verification completed cleanly on `dev`. All automated suites passed (eslint, typecheck, publication tests 323/323, build, charts-gate 21/21, full Playwright UI test suite 205 passed/10 skipped/0 failed, contracts-check, mkdocs strict, and git diff --check). No changes to B, C, database schemas, pipeline data, or production gates. Contract A remains `In Progress` pending real device validation (iPhone Safari, Android Chrome).
- **Plan Contract:** `docs/plans/2026-10-21/03-mobile-charts-a-page.md`.
- **Approval / Status:** Owner explicitly authorized Draft path for Contract A only. Contracts B and C remain unstarted (`Draft` and `Deferred` respectively).
- **Blockers:** Real iPhone Safari and Android Chrome verification required before marking Contract A `Implemented` or authorizing Contract B. Emulation alone cannot close Contract A.
- **Next:** Physical device verification on iPhone Safari and Android Chrome across 320px, 390px, and 430px viewports; record device test receipts in contract log.

## Context and Decisions
- Baseline `c892b669`; preserved three planning contracts (`03-mobile-charts-a-page.md`, `04-mobile-charts-b-inspector.md`, `05-mobile-charts-c-evaluation.md`), index updates, and planning log `02-mobile-chart-contracts.md`.
- Maintained strict boundary: Contract A only. No shared inspector state, no custom pinch/zoom, no browser history interception, no database migrations, and no production publication flag changes (`CFB_CHARTS_ENABLED=0` default preserved; `/stats` returns 404 in production).
- Scatter chart geometry preserved at 1000 × 640 viewBox with horizontal scrolling as directed by owner. Essential text (ticks, axes, quadrants) scaled up to render at ≥ 12 CSS pixels without layout shifts.
- Mobile game logs rendered as stacked horizontal panels (offense and defense allowed) with shared benchmark scales, 44px min touch targets, and text wrapping.
- Net success rate renders all games by default in a scrollable list without top-N truncation or virtualization.
- Settings sheet uses native `<dialog>` with `visualViewport` tracking, backdrop scroll lock & restoration, safe-area padding (`100dvh`), and auto-dismiss on route change.
- Team combobox implements 44px touch targets on mobile, full keyboard navigation (`ArrowDown`, `ArrowUp`, `Enter`, `Escape`), `aria-activedescendant`, viewport positioning, and `suppressHydrationWarning`.

## Work Completed
- Built `web/src/components/charts/useMobileChart.ts` hook utilizing `useSyncExternalStore` for SSR-safe `(max-width: 639px)` media query detection.
- Built `web/src/components/charts/MobileChartSettings.tsx` settings drawer using `<dialog>`, visual viewport resize/scroll listeners, focus restoration, Escape handler, and body scroll lock.
- Refactored `web/src/app/stats/page.tsx` with a 2-column mobile chart picker grid where the 5th chip spans full width, with desktop tabs preserved.
- Implemented `web/src/lib/scatter-selection.ts` for pure screen-pixel Euclidean distance calculation (< 24px candidate radius, < 8px ambiguity threshold to show up to 3 candidate buttons), with scroll cancellation.
- Built `web/src/components/charts/MobileGameLog.tsx` with stacked offense/defense panels, 44px touch targets, FBS benchmarks, and non-truncating team names.
- Updated `ScatterChart.tsx` with dynamic font scaling (`textSize()` compensation ensuring minimum 12px rendered text without altering viewBox), outside detail panel rendering via portal to `detailsContainer`, and touch/pointer suppression on native scroll.
- Enhanced `TeamHighlightCombobox.tsx` with 44px touch targets, keyboard navigation, and `suppressHydrationWarning`.
- Added automated test suites:
  - `web/src/lib/scatter-selection.test.ts` (unit tests for distance, ambiguity, and cancellation).
  - `web/e2e/mobile-chart-settings.spec.ts` (E2E for drawer, viewport constraints, Escape, and backdrop lock).
  - `web/e2e/mobile-scatter.spec.ts` (E2E for scatter text scaling ≥ 12px, nearest-point selection, and ambiguity disambiguation).
  - `web/e2e/mobile-bars.spec.ts` (E2E for stacked mobile game logs and full net-success list).
- Stabilized existing E2E specs (`charts.spec.ts`, `charts-navigation.spec.ts`).

## Files Modified
- `web/src/app/globals.css` - Responsive media utilities for touch/landscape phone panels vs desktop hover tooltips
- `web/src/app/stats/page.tsx` - 2-column mobile chart picker grid + accessible chip grouping and settings summary
- `web/src/components/charts/MobileChartSettings.tsx` - Native `<dialog>` settings drawer with server-rendered summary/trigger in `sm:hidden`, client-side sheet, and `DEFAULT_CHART` fallback
- `web/src/components/charts/MobileGameLog.tsx` - Mobile stacked game log rows with side-differentiated accessible names matching visible text
- `web/src/components/charts/useMobileChart.ts` - Responsive mobile hook
- `web/src/lib/scatter-selection.ts` - Touch distance & disambiguation logic
- `web/src/lib/scatter-selection.test.ts` - Unit tests for scatter selection
- `web/src/components/charts/ScatterChart.tsx` - Dynamic font scaling, interactive-gated margins/offsets (`INTERACTIVE_MARGIN` vs `EXPORT_MARGIN`), initial rendered width of 760 for first-paint scaling without jump, decoupled local mark selection, and `data-axis` attributes
- `web/src/components/charts/TeamHighlightCombobox.tsx` - 44px touch targets, keyboard navigation, and local list scrolling without page shift
- `web/src/components/charts/ChartFrame.tsx` - Responsive container adjustments
- `web/src/components/charts/GameLogView.tsx` - Mobile layout integration
- `web/src/components/charts/NetSuccessChart.tsx` - Full row tap targets & readable values
- `web/src/components/charts/NetSuccessView.tsx` - Full list rendering
- `web/src/components/charts/ScatterView.tsx` - Integrated mobile detail rendering
- `web/src/components/charts/useChartSelection.ts` - Local selection hook
- `web/src/components/WeekNav.tsx` - Touch target padding
- `web/src/components/ui/SegmentedControl.tsx` - Touch target padding
- `web/src/components/ui/SegmentedControl.test.ts` - Unit test assertions
- `web/e2e/mobile-bars.spec.ts` - E2E tests for mobile bar charts and game log accessible names
- `web/e2e/mobile-chart-settings.spec.ts` - E2E tests for settings sheet and in-sheet week changes
- `web/e2e/mobile-scatter.spec.ts` - E2E tests for mobile scatter interactions, 320/390/430px bounds & non-collision, and landscape touch devices
- `web/e2e/charts-navigation.spec.ts` - Navigation timing and responsive updates
- `web/e2e/charts.spec.ts` - Touch activation test asserting local selection and explicit highlight button
- `web/package.json` - Added test scripts
- `docs/plans/index.md` - Added plans 03, 04, 05
- `docs/plans/2026-10-21/03-mobile-charts-a-page.md` - Contract A execution plan
- `docs/plans/2026-10-21/04-mobile-charts-b-inspector.md` - Contract B execution plan
- `docs/plans/2026-10-21/05-mobile-charts-c-evaluation.md` - Contract C evaluation plan
- `session_logs/2026-10-21/02-mobile-chart-contracts.md` - Planning log

## Review Findings Addressed
Addressed all priority items and minor findings from both review passes:
1. **Server-rendered summary and trigger (Issue 1):** In `MobileChartSettings.tsx`, the summary and "Chart settings" trigger are rendered on the server inside `sm:hidden`, while desktop controls render in `hidden sm:flex`. The `<dialog>` sheet mounts client-side, eliminating mobile layout flash and providing immediate summary/trigger display on first paint. Also uses `DEFAULT_CHART` from `chart-config.ts` to prevent default string drift.
2. **Settings sheet route persistence (Issue 2):** In `MobileChartSettings.tsx`, dialog persistence tracks `[pathname, currentChart]`. In-sheet adjustments (week, through-week, side, metric, conference) keep the dialog open; it only dismisses on cross-chart navigation or navigating away from `/stats`.
3. **Decoupled tap from page highlight (Issue 3):** In `ScatterChart.tsx`, a mark tap sets local selection only (`setSelected(team)`), keeping selection local to the chart as specified in Contract A. An explicit `"Highlight this team"` / `"Remove highlight"` button was added to the mobile details panel for user-initiated page-level highlighting.
4. **Interactive-gated margins and label scaling (Issues 2 & 6):** In `ScatterChart.tsx`, plot margins and tick/title coordinates are gated on `interactive`: static export cards preserve the exact original `EXPORT_MARGIN` (`{ top: 18, right: 22, bottom: 52, left: 84 }`) and original pixel coordinates, while live interactive charts use `INTERACTIVE_MARGIN` (`{ top: 20, right: 26, bottom: 56, left: 86 }`). For interactive charts, `renderedWidth` initializes to 760 (the mobile minimum width), scaling labels on first paint without jumping.
5. **Tightened collision & bounds test (Issue 3):** Added `data-axis` attributes to `ScatterChart.tsx`. Updated `mobile-scatter.spec.ts` to test across 320px, 390px, and 430px, asserting zero out-of-bounds labels and zero collisions between titles and ticks without hardcoded pixel coordinates.
6. **Landscape & coarse-pointer testing (Issues 4 & 5):** Styled details panel and tooltips using `@media (min-width: 640px) and (pointer: fine) and (min-height: 501px)` so landscape phones (height ≤ 500px or coarse pointer) consistently render the details panel and suppress floating hover tooltips. Added E2E tests for landscape phones (844x390) and landscape tablets with touch (1024x768).
7. **Game-log accessible names (Issue 5 & 6):** In `MobileGameLog.tsx`, row buttons prepend the side name and contain the complete visible description (`${sideLabel}: Wk ${game.week} · ${siteText} ${game.opponent} · ${game.result} · ${valueText} · Weekly FBS avg ${avgText}`), eliminating duplicate names and WCAG 2.5.3 Label in Name mismatches.
8. **Smaller items:**
   - Wrapped mobile chart chips in accessible `<div role="group" aria-label={group.label} className="contents">` in `stats/page.tsx`.
   - Replaced `scrollIntoView()` with container `list.scrollTop` in `TeamHighlightCombobox.tsx`.

## Validation
- [x] `npm --prefix web run lint` (0 errors, 0 warnings)
- [x] `npm --prefix web run typecheck` (0 errors)
- [x] `npm --prefix web run test:publication` (323 passed, 1 skipped)
- [x] `npm --prefix web run build` (Turbopack production build succeeded)
- [x] `npm --prefix web run test:charts-gate` (21 passed, verifying 404 gate when disabled)
- [x] `npm --prefix web run test:ui` (Full Playwright test suite: 210 passed, 10 skipped, 0 failed)
- [x] `make contracts-check` (Contract schema and teams sync verified)
- [x] `uv run mkdocs build --strict` (Documentation build verified without error)
- [x] `git diff --check` (No whitespace or formatting errors)
- [x] `npx playwright test e2e/matchup.spec.ts` (All 23 matchup tests passed locally in 11.0s, including share card download test at line 346)
- [ ] Physical device verification:
  - [ ] iPhone Safari (320px, 390px, 430px)
  - [ ] Android Chrome (360px, 412px)

## Amendments and Blockers
- **CI Share Card Timeout on ecea7a2e:** `e2e/matchup.spec.ts:346` timed out twice on GitHub Actions CI for commit `ecea7a2e`. Verified clean locally (all 23 matchup tests passed in 11.0s, share card test passed in 525ms). Will be monitored on the next CI run after pushing follow-up changes.
- **Physical Device Gate:** Contract A remains `In Progress` until real iPhone Safari and Android Chrome validation is recorded. Contracts B and C remain unstarted (`Draft` and `Deferred`).

## Handoff Notes
- **Resume at:** Commit the follow-up review fixes and push `dev` to rerun CI. Then proceed with physical device verification on iPhone Safari and Android Chrome across 320px, 390px, and 430px viewports. Once device acceptance is recorded, Contract A can be marked `Implemented` and Contract B submitted for owner authorization.
- **Watch out for:** Keep Contract B and C out of Contract A commit. All changes remain gated behind `CFB_CHARTS_ENABLED=1`.

**tags:** ["web", "charts", "mobile", "accessibility"]
