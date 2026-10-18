# Session: Implement Charts publication gate

## TL;DR
- **Worked On:** Default-off Charts route/navigation publication gate (`CFB_CHARTS_ENABLED=1`), server layout integration, early route rejection, and disabled-mode production build tests.
- **Outcome:** Complete and verified locally. Charts remains unpublished everywhere by default; exact `1` opt-in required.
- **Plan Contract:** [Approved publication gate](../../docs/plans/2026-10-18/02-charts-publication-gate.md)
- **Approval / Status:** Owner's explicit implementation request on 2026-10-18; Implemented.
- **Blockers:** None for local work. Charts manual/publication approval remains withheld.
- **Next:** Owner-controlled integration with the newer Week 8 operational commits on `dev` before any weekly release.

## TODO
- [x] Persist approved plan and planning log; preserve existing worktree.
- [x] Implement server flag (`isChartsEnabled`), nav (`SiteNav` 4 vs 5 columns), and early route rejection ahead of data queries.
- [x] Verify enabled behavior and disabled production HTTP 404 responses (`test:charts-gate`).
- [x] Update documentation, review and record final evidence.

## Context and Decisions
- Exact string `"1"` enables; all other, unset, or empty values disable in every environment (production, preview, dev, fixtures).
- No public environment variable or client-side hide effect; root server layout evaluates the flag and passes the boolean to the client nav.
- `/charts` route performs synchronous rejection via `if (!isChartsEnabled()) notFound()` ahead of data loading or awaits.
- Existing stage/release migration requirements are unchanged. This controls UI publication only.
- No Vercel settings, git integration, migration or live activation performed here.

## Work Completed
- Added `web/src/lib/charts-gate.ts` with truth-table unit tests in `web/src/lib/charts-gate.test.ts`.
- Registered `charts-gate.test.ts` in `test:publication` (232 passed, 1 skipped).
- Updated `web/src/app/layout.tsx` to pass server-evaluated `isChartsEnabled()` to `<SiteNav />`.
- Updated `web/src/components/SiteNav.tsx` to omit Charts and use `grid-cols-4` on mobile when disabled; `grid-cols-5` when enabled.
- Gated `web/src/app/charts/page.tsx` synchronously with `if (!isChartsEnabled()) notFound()`.
- Added disabled-mode production build test suite `web/e2e-charts-gate/charts-disabled.spec.ts` with configuration `web/playwright.charts-gate.config.ts` and script `npm run test:charts-gate`.
- Documented local review opt-in, disabled production behavior, and rebuild requirements in `web/README.md`.

## Files Modified
- `web/src/lib/charts-gate.ts` - Server gate helper
- `web/src/lib/charts-gate.test.ts` - Unit tests for gate helper
- `web/src/app/layout.tsx` - Server layout flag evaluation
- `web/src/components/SiteNav.tsx` - Responsive 4- vs 5-item mobile navigation
- `web/src/app/charts/page.tsx` - Early route rejection
- `web/playwright.config.ts` - Explicit enabled test server flag
- `web/playwright.charts-gate.config.ts` - Disabled test configuration
- `web/e2e-charts-gate/charts-disabled.spec.ts` - Disabled production suite
- `web/package.json` - Added `test:charts-gate` script and registered test in `test:publication`
- `web/README.md` - Documented local review and deployment settings
- `docs/plans/2026-10-18/02-charts-publication-gate.md` - Marked Implemented

## Validation
- [x] `npm --prefix web run test:publication` (232 passed, 1 skipped).
- [x] `npm --prefix web run test:charts-gate` (10 passed in 2.1s against optimized production build).
- [x] `npm --prefix web run typecheck` (0 errors).
- [x] `npm --prefix web run lint` (0 errors, 1 pre-existing warning in SlateView.tsx).
- [x] `make contracts-check` (passed).
- [x] `git diff --check` (clean).

## Amendments and Blockers
- Parent expansion remains In Progress pending separate Preview acceptance. This gate completes locally without granting Charts public approval.

## Handoff Notes
- **Resume at:** Integrate expansion worktree with primary checkout's Week 8 commits under owner control before any weekly release.
- **Watch out for:** Preserve existing staged deletion of `explosiveness-data.generated.ts` and keep `CFB_CHARTS_ENABLED` unset/0 in Production.

**tags:** ["charts", "publication", "web", "verification"]
