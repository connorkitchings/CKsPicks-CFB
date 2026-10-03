# Session: Mobile display and performance improvements for Ratings and Performance pages

## TL;DR
- **Worked On:** Extended the mobile display, layout, and performance enhancements established on the Picks and Results pages to the **Ratings** (`/ratings`) and **Performance** (`/performance`) pages.
- **Outcome:**
  - **Ratings Page:**
    - Created `RatingsView` client component with instant client-side team search and 1-tap `✕` clear (styled to prevent iOS auto-zoom via `text-base sm:text-xs`).
    - Added team logos (`TeamLogo`) alongside team names with initials fallback.
    - Added 3-way sort selector (Overall, Offense, Defense) and pre-filter rank preservation.
    - Designed mobile-optimized row list (`sm:hidden`) with zero horizontal scrolling displaying rank, logo, team, net rating, and offense/defense split badges.
    - Converted methodology box to an interactive, compact collapsible accordion (`<details>`) saving substantial initial vertical viewport space.
    - Preserved full desktop table (`hidden sm:block`) with scope headers and rank columns, ensuring 100% compatibility with `ratings.test.ts`.
  - **Performance Page:**
    - Streamlined page spacing (`py-3 sm:py-6 space-y-4`).
    - Restructured top KPI cards into a mobile-friendly 2+1 grid (`grid grid-cols-2 gap-2.5 sm:gap-4 md:grid-cols-3`): Spread and Totals side-by-side in Row 1 with Net Betting Return spanning Row 2, saving >60% vertical scrolling on phones while preserving the 3-column layout on desktop.
    - Made Spread and Totals KPI cards interactively toggle the active target filter.
    - Replaced the wide horizontally scrolling weekly table on mobile with responsive weekly breakdown cards (`sm:hidden`) displaying week link, record, win rate, profit units, and ROI.
    - Preserved exact desktop comparison tables (`hidden sm:block overflow-x-auto`).
- **Approval / Status:** User approved.
- **Blockers:** None.
- **Next:** User stages and commits changes on `dev`, merges into `main`, and pushes to deploy.

## Files Modified
- `web/src/components/ratings/RatingsView.tsx` (new)
- `web/src/app/ratings/page.tsx`
- `web/src/lib/ratings.test.ts`
- `web/src/app/performance/page.tsx`
- `web/src/components/PerformanceDashboard.tsx`

## Validation
- [x] `npm --prefix web run typecheck` — passed (0 errors)
- [x] `npm --prefix web run lint` — passed (0 warnings/errors)
- [x] `npm --prefix web run test:publication` — passed (114/114 passing)
- [x] `npm --prefix web run build` — passed (all routes statically/dynamically generated in 1.1s)
- [x] `git diff --check` — passed (clean, no whitespace errors)

## Handoff Notes
- **Proposed commit message:**
  ```
  feat(web): mobile display and UX polish for ratings and performance pages

  - Ratings: client-side search with clear button, team logos, mobile card list, and collapsible methodology
  - Performance: 2+1 mobile KPI grid, interactive filter toggles, and mobile weekly breakdown cards
  - Maintain 100% desktop fidelity and test suite compatibility
  ```

**tags:** ["web", "ratings", "performance", "mobile-ux", "responsive"]
