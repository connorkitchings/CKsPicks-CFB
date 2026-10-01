# Session: Streamline Performance Dashboard and Separate Picks vs Results

## TL;DR
- **Worked On:** Streamlined `/performance` (excluded unscored upcoming weeks, removed "replay" badges, implemented Option B KPI cards) and separated the active upcoming slate (**Picks**) from the historical scored archive (**Results**).
- **Outcome:** The site navigation now features 4 distinct, cohesive tabs: **Picks** (`/`), **Results** (`/results`), **Ratings** (`/ratings`), and **Performance** (`/performance`) with active tab highlighting. Scored historical weeks link directly to `/results?week=N`, while `/` focuses exclusively on this week's upcoming betting slate (Week 5).
- **Plan Contract:** N/A (fast path UX & navigation architecture refinement)
- **Approval / Status:** Authorized by user.
- **Blockers:** None.
- **Next:** Proceed to Phase 2: Matchup Deep Dive (Parker Fleming unit-vs-unit advanced stats).

## Context and Decisions
- **Performance Tab Refinements:**
  - **Unscored Week Exclusion:** Excluded upcoming weeks with 0 graded bets (Week 5) from the performance table.
  - **Badge & Arrow Cleanup:** Removed all "replay" badges and arrow symbols (`→`) from week labels in the breakdown table, leaving clean clickable text.
  - **Filter Labels:** Renamed filter buttons to **All Picks**, **Spreads**, and **Totals** (removing "Only" and "Targets").
  - **KPI Card Design (Option B):** 3 betting portfolio cards (`Spread Performance`, `Totals Performance`, `Net Betting Return`) + a dedicated full-width `Model Calibration` strip (`Spread MAE`, `Total MAE`, `95% CI Coverage`).
- **Separating Picks and Results:**
  - **Picks (`/`):** Actionable, forward-looking slate for the upcoming week (Week 5). Displays live market lines, model predictions, edges, kickoff times, and star picks without historical week clutter. Requests for past scored weeks seamlessly redirect to `/results?week=N`.
  - **Results (`/results`):** Archive for completed, graded games (Weeks 0–4). Includes `WeekNav` to browse past weeks, final scores, Win/Loss/Push result pills, and unit profit/loss.
  - **Performance (`/performance`):** High-level season ROI and P&L dashboard. Weekly breakdown rows deep-link directly to `/results?week=N`.
  - **Site Navigation (`SiteNav.tsx`):** Displays `Picks`, `Results`, `Ratings`, and `Performance` with active tab highlighting via `usePathname()`.

## Files Modified
- `web/src/components/SiteNav.tsx` - Updated navigation items and active path highlighting
- `web/src/components/WeekNav.tsx` - Added optional `basePath` prop for `/results` support
- `web/src/components/PerformanceDashboard.tsx` - Option B layout, removed replay badges, filtered empty weeks, updated week links to `/results`
- `web/src/lib/queries.ts` - Added `getScoredWeeks` and `getUpcomingWeeks` helpers
- `web/src/lib/v5.ts` - Filtered `data.weeks` to only scored weeks in `getV5PerformanceDetail`
- `web/src/lib/ratings.test.ts` - Updated navigation assertion test for 4 items
- `web/src/app/page.tsx` - Focused Picks on upcoming slates and redirected scored weeks to `/results`
- `web/src/app/results/page.tsx` - New dedicated route for browsing completed, scored weeks

## Validation
- [x] TypeScript typecheck: `npm run typecheck` (0 errors)
- [x] Publication test suite: `npm run test:publication` (41/41 passed)
- [x] ESLint: `npm run lint` (0 errors, 0 warnings)
- [x] Production build: `npm run build` (Next.js Turbopack succeeded for all 10 routes)
- [x] Contracts check: `make contracts-check` (passed)
- [x] HTTP verification:
  - `GET /` -> 200 OK (Week 5 Picks)
  - `GET /results` -> 200 OK (Week 4 Results)
  - `GET /ratings` -> 200 OK (Ratings)
  - `GET /performance` -> 200 OK (Performance dashboard)

## Handoff Notes
- **Resume at:** Phase 2 planning for Matchup Deep Dive (Parker Fleming unit-vs-unit advanced stats).
- **Git operations:** User executes manual commit per monorepo protocol.

**tags:** ["web", "sitenav", "performance", "picks", "results", "ui", "fast-path"]
