# Session: Mobile scatter details panel

## TL;DR

- **Worked On:** Mobile scatterplot difficulty reported by the owner.
- **Outcome:** After a touch selection, the details panel scrolls clear of the bottom tab bar. Repro tests for dense clusters and scrolled pages were added; both already passed, and WebKit with finger offsets of 0, 4 and 7px also selected correctly.
- **Plan Contract:** [`docs/plans/2026-11-08/mobile-scatter-details.md`](../../docs/plans/2026-11-08/mobile-scatter-details.md)
- **Approval / Status:** Implemented.
- **Blockers:** The market board chart is unreachable from the URL (`ready: false`); its tap test is `test.fail()` until it ships.
- **Next:** None.

**tags:** ["web", "charts", "mobile"]

## Context and Decisions

- The panel's buttons sat behind the fixed tab bar on adjusted and possession (long description text). A first version scrolled on every selection and made a keyboard test flaky, because the scroll event cancels a tap in progress; the final version scrolls only for touch selections and only when covered.

## Files Modified

- `web/src/components/charts/ScatterChart.tsx`, `web/e2e/mobile-scatter.spec.ts`, the contract and this log.

## Validation

- [x] `mobile-scatter.spec.ts` 5 of 5 runs; `make check`; `make web-e2e` 435 passed, 10 skipped; `git diff --check`

## Handoff Notes

- **Resume at:** nothing outstanding.
