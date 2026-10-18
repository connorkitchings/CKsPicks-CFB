# Session: Explosiveness Metric Switcher on Efficiency Chart

## TL;DR
- **Worked On:** Added an interactive explosiveness metric switcher to the **Efficiency vs Explosiveness** chart (`/charts?chart=efficiency`).
- **Outcome:** Delivered a clean toggle between the owner's selected candidate metrics: **20+ Yard Rate** (`explosive_rate`, default) and **Yards / Success** (`yards_per_success`). Updated chart title to "Efficiency vs Explosiveness", dynamically switched y-axes, national ranks, tooltips, tables, and 2x PNG export cards. Backed by verified research data in `web/src/lib/explosiveness-data.generated.ts`.
- **Plan Contract:** Fast path under owner decision following Revision 5 research comparison.
- **Approval / Status:** Owner requested and explicitly selected: "Let's go with Explosive Rate (20+ yard) and Yards/Success. And keep the toggle". Committed as `2e918dfb` on `dev`.
- **Blockers:** None.
- **Next:** Push `dev` to `origin/dev` or prepare `dev` -> `main` promotion when ready.

## Context and Decisions
- In Revision 5 of the charts module plan, an offline empirical comparison evaluated two candidate measures of college football explosiveness:
  1. 20+ yard play rate (frequency of explosive plays)
  2. Yards per successful play (magnitude of success downs)
- After reviewing the comparison and seeing both in action, the owner approved providing **both** on the site via an interactive toggle rather than eliminating one.
- The chart's primary identity is now **Efficiency vs Explosiveness** (Success Rate on X, Explosiveness on Y), with 20+ Yard Rate as the default.
- Defense appropriately inverts both metrics (fewer 20+ yard plays allowed and fewer yards/success allowed plot up and right as better defense).

## Work Completed
- **Explosiveness Dataset:** Generated `web/src/lib/explosiveness-data.generated.ts` containing 1,380 team-windows across Weeks 2–6 and national FBS averages.
- **Charts Transform (`web/src/lib/charts.ts`):**
  - Added `EfficiencyMetric = "ppa" | "explosive_rate" | "yards_per_success"`.
  - Updated `efficiencyPoints` to support switching between metrics and pulling FBS reference averages.
  - Updated `CHART_TITLES.efficiency` to `"Efficiency vs Explosiveness"`.
  - Updated `CHART_FOOTNOTES.efficiency`.
- **Charts UI (`web/src/components/charts/ChartsView.tsx`):**
  - Added metric toggle in `chart-controls` for `kind === "efficiency"`.
  - Dynamically bound y-axis labels, formatters (`formatPercent` for 20+ rate, `X.X yds` for yards/success), national competition ranks, tooltips, and export cards.
- **Page Wrapper (`web/src/app/charts/page.tsx`):**
  - Supported `metric` searchParam with `"explosive_rate"` default and forwarded `initialMetric` and `rows` to `ChartsView`.
- **Unit & Publication Tests (`web/src/lib/charts.test.ts`):**
  - Added test verifying candidate explosiveness data extraction and defense inversion.
  - Verified `CHART_TITLES["efficiency"] === "Efficiency vs Explosiveness"`.

## Files Modified
- `web/src/app/charts/page.tsx` - forwarded `rows` and `initialMetric` based on `metric` searchParam.
- `web/src/components/charts/ChartsView.tsx` - interactive switcher, dynamic y-axis and formatting.
- `web/src/lib/charts.ts` - `EfficiencyMetric` type, candidate dataset lookup in `efficiencyPoints`, title and footnote updates.
- `web/src/lib/charts.test.ts` - test assertions for efficiency title and explosiveness extraction.
- `web/src/lib/explosiveness-data.generated.ts` - precomputed 1,380 team-windows from research comparison dataset.

## Validation
- [x] `npm --prefix web run typecheck` (0 errors)
- [x] `npm --prefix web run test:publication` (190 passed, 0 failed)
- [x] `make contracts-check` (passed)
- [x] `uv run ruff check .` (passed)
- [x] `git diff --check` (clean)
- [x] Live local web test on `http://127.0.0.1:3000/charts?chart=efficiency`

## Amendments and Blockers
- None.

## Handoff Notes
- **Resume at:** `dev` is clean and 3 commits ahead of `origin/dev` (`c3766676`, `59125cd0`, `2e918dfb`). Ready to push or merge to `main`.
- **Watch out for:** Local dev server is running on port 3000. External SSD is unmounted on host, so pipeline tests requiring R2/local raw parquets need the drive mounted before running python pipeline tasks.

**tags:** ["web", "charts", "efficiency", "explosiveness", "ui"]
