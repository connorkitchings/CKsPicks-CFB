# Session: Publish Stats and Retire CFB_CHARTS_ENABLED Gate

## TL;DR

- **Worked On:** Added `data-scroll-behavior="smooth"` to `<html>` to resolve Next.js 16 navigation warnings; removed the `CFB_CHARTS_ENABLED` publication gate across the entire application and tests so Stats is permanently enabled and public; moved `/charts` redirects natively into `next.config.ts`; retired edge middleware `web/src/proxy.ts` and the disabled-gate test suite; verified full test suites and production build.
- **Outcome:** Stats (`/stats`) is now a standard, public top-level tab alongside Games, Ratings and Model. Vercel Preview and Production deployments require zero environment variable configuration to serve the full site.
- **Plan Contract:** Phase 4 of [`docs/plans/2026-10-21/01-site-reorganization-and-performance.md`](../../docs/plans/2026-10-21/01-site-reorganization-and-performance.md)
- **Approval / Status:** Owner explicitly requested retiring `CFB_CHARTS_ENABLED` and publishing Stats.
- **Blockers:** None.
- **Next:** Push `dev` to GitHub to trigger the Vercel Preview build for owner physical device review over the weekend.

**tags:** ["web", "stats", "charts", "publication", "nextjs"]

## Context and Decisions

- Prior architecture used `CFB_CHARTS_ENABLED=1` as an environment gate, serving HTTP 404 and a 3-tab navigation when unset.
- During build audit, it was discovered that Next.js statically baked a prerendered 404 into `/stats` during `next build` because `ChartsPage` checked `!isChartsEnabled()` synchronously before awaiting search parameters. Removing the gate makes `/stats` naturally dynamic without static 404 hazards.
- The `/charts` $\to$ `/stats` 307 redirects were previously handled in `web/src/proxy.ts`. Moving them directly into `next.config.ts` allows Vercel edge CDN routing to handle redirects without invoking an Edge Middleware function, improving routing performance.
- Retired `web/src/lib/charts-gate.ts`, `web/src/lib/charts-gate.test.ts`, `web/playwright.charts-gate.config.ts`, `web/e2e-charts-gate/`, and the disabled-mode CI step.

## Work Completed

- Added `data-scroll-behavior="smooth"` to `<html>` in `web/src/app/layout.tsx`.
- Removed `isChartsEnabled` import and `chartsEnabled` prop from `web/src/app/layout.tsx`.
- Simplified `web/src/components/SiteNav.tsx` to unconditionally display all 4 items (Games, Ratings, Stats, Model) and use `grid-cols-4` on mobile.
- Updated `web/src/app/stats/page.tsx` to directly export async `ChartsPage` without synchronous gate wrapper.
- Added `/charts` and `/charts/:path*` 307 redirects to `web/next.config.ts` and deleted `web/src/proxy.ts`.
- Deleted `web/src/lib/charts-gate.ts`, `web/src/lib/charts-gate.test.ts`, `web/playwright.charts-gate.config.ts`, and `web/e2e-charts-gate/charts-disabled.spec.ts`.
- Removed `charts-gate.test.ts` and `test:charts-gate` script from `web/package.json`.
- Removed `test:charts-gate` step from `.github/workflows/ci.yml`.
- Removed `CFB_CHARTS_ENABLED=1` from `web/playwright.config.ts` webServer command.
- Removed `CFB_CHARTS_ENABLED` from `scripts/ops/run_web_local.sh`, `web/.env.example`, `.env.example`, `web/README.md`, `README.md`, `AGENTS.md`, and `docs/status.md`.

## Files Modified

- `web/src/app/layout.tsx` — Add `data-scroll-behavior="smooth"`, remove `isChartsEnabled`
- `web/src/components/SiteNav.tsx` — Always render 4 items and mobile `grid-cols-4`
- `web/src/app/stats/page.tsx` — Directly export async `ChartsPage`
- `web/next.config.ts` — Add `/charts` redirects
- `web/package.json` — Remove `charts-gate` test entries
- `web/playwright.config.ts` — Remove `CFB_CHARTS_ENABLED=1` from dev server command
- `.github/workflows/ci.yml` — Remove `test:charts-gate` CI step
- `scripts/ops/run_web_local.sh` — Remove `CFB_CHARTS_ENABLED` references
- `web/.env.example` — Remove `CFB_CHARTS_ENABLED`
- `.env.example` — Remove `CFB_CHARTS_ENABLED`
- `web/README.md` — Update Stats documentation and verification commands
- `AGENTS.md` — Update navigation description
- `README.md` — Update navigation description
- `docs/status.md` — Update navigation note
- `web/e2e/redirects.spec.ts` — Update comment

## Files Deleted

- `web/src/proxy.ts`
- `web/src/lib/charts-gate.ts`
- `web/src/lib/charts-gate.test.ts`
- `web/playwright.charts-gate.config.ts`
- `web/e2e-charts-gate/charts-disabled.spec.ts`

## Validation

- [x] `npm --prefix web run typecheck` (0 errors)
- [x] `npm --prefix web run lint` (0 errors, 0 warnings)
- [x] `npm --prefix web run test:publication` (324 passed, 1 skipped)
- [x] `npm --prefix web run build` (Turbopack production build succeeded; `/stats` marked dynamic)
- [x] `PLAYWRIGHT_PORT=3200 npm --prefix web run test:ui` (Full Playwright browser suite: 211 passed, 10 skipped, 0 failed)
- [x] `make check` (ruff, contracts, 32 quality checks, 2213 pytest tests, mkdocs strict, web lint/typecheck/publication/build all passed)
- [x] `git diff --check` (clean)

## Handoff Notes

- **Resume at:** Commit changes and push `dev` to GitHub.
- **Watch out for:** Once pushed, Vercel will build a Preview deployment with Stats permanently live. Owner can test directly on actual mobile devices over the weekend.
