# Mobile scatter details panel above the tab bar

- **Status:** Implemented
- **Created:** 2026-11-08
- **Planner:** Sol
- **Approval source:** Owner reported on 2026-11-08 that all mobile scatterplots had difficulty; the dashboard contract's scatterplot item called for a focused fix under its own contract
- **Implementation log:** `session_logs/2026-11-08/04-mobile-scatter-details-impl.md`
- **Commit policy:** Commit with implementation

## Goal and acceptance

After a tap on a scatterplot dot on a phone, the details panel (team facts, "Highlight this team", "Clear details") is fully usable: its buttons sit above the fixed bottom tab bar without the viewer having to scroll.

Acceptance: `e2e/mobile-scatter.spec.ts` passes, including a new test per scatter (efficiency, adjusted, possession) that taps the highest visible dot with the chart just under the sticky bar and asserts "Clear details" ends above "Main navigation"; `make check`, `make web-e2e` and `git diff --check` pass.

Out of scope: the market board chart (`ready: false` in `CHART_REGISTRY`, unreachable from the URL; its tap test stays `test.fail()`); selection logic and hit radius.

## Baseline and constraints

- Finding: the panel renders under the plot. On adjusted and possession its bottom edge sat at about 849 and 827px on 390x844, behind the tab bar (top about 754px). Dot selection itself works in Chromium and WebKit with up to 7px finger offset.
- A programmatic scroll fires a `scroll` event that cancels a tap in progress (`ScatterChart` listens on `document`), so the panel scrolls only when it is actually covered, and only after a touch selection, never after keyboard selection.

## Ordered changes

1. `web/src/components/charts/ScatterChart.tsx`: a ref on the details panel, `scroll-mb-28`, and an effect that calls `scrollIntoView({ block: "nearest" })` when a touch selection leaves the panel below the top of the Main navigation bar (or the viewport bottom when none).
2. `web/e2e/mobile-scatter.spec.ts`: the dense-slate and scrolled-page repro tests, the new tab-bar tests, and the `test.fail()` market board test.

## Validation

```bash
cd web && npx playwright test e2e/mobile-scatter.spec.ts
make check
make web-e2e
git diff --check
```

Results: the new test failed on adjusted and possession before the change and passes after; `mobile-scatter.spec.ts` passed 5 of 5 runs; full suite 435 passed, 10 skipped.

## Handoff/amendments

Approved. No amendments.
