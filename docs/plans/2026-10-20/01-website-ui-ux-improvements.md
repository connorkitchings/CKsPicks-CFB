# Website UI/UX Foundations, Unified App Shell, Matchup Hero & Performance Benchmark

- **Status:** Approved
- **Created:** 2026-10-20
- **Planner:** Sol
- **Approval source:** Owner plan judgment and explicit Terra implementation authorization in chat on 2026-10-20
- **Implementation log:** `session_logs/2026-10-20/02-website-ui-ux-implementation.md` (pending)
- **Commit policy:** Separate plan commit or commit with implementation **only after** the Week 8 market refresh release is completed (see Release coupling gate below)

## Goal and acceptance

Fix verified CSS/theme defects, unify the site masthead (`Header`), `ThemeToggle`, `Footer`, and container widths across all 8 web routes, surface already-computed matchup hero metadata (`spreadSource`, `totalSource`, edge deltas, unit ranks) and "Biggest Mismatches" on `/matchup/[gameId]`, add the project's primary `52.4%` (`-110` break-even) benchmark context to `/performance`, and resolve the `TeamHighlightCombobox` hydration mismatch on `/charts`.

Implementation is complete only when every acceptance criterion and validation check below passes:

1. **CSS Foundations (WS2):**
   - `:root` sets `color-scheme: light` and `html.dark` sets `color-scheme: dark` in `web/src/app/globals.css`, paired with `<meta name="color-scheme" content="light dark" />` in `web/src/app/layout.tsx`.
   - `--surface-elevated` is defined in `:root` (`#ffffff`) and `html.dark` (`#1c1917`) and mapped as `--color-surface-elevated: var(--surface-elevated)` inside `@theme inline` so `bg-surface-elevated` renders an opaque elevated surface on `ShareButton.tsx` and `matchup/[gameId]/page.tsx`.
   - Headings (`h1, h2, h3`) apply `text-wrap: balance` and prose paragraphs (`p`) apply `text-wrap: pretty` without altering game-card heights.
2. **Unified App Shell & Container Alignment (WS1 Narrowed):**
   - All 8 routes (`/`, `/results`, `/matchup`, `/matchup/[gameId]`, `/ratings`, `/performance`, `/charts`, `/methodology`) render a single compact `<Header>` (with `ThemeToggle`) above `<SiteNav>` on desktop (`sm+`) and a single `<Footer>` at the bottom.
   - Neither `SlateView` (`/`, `/results`) nor `/matchup` nor `/matchup/[gameId]` renders `<Header>` or `<Footer>` twice.
   - `SiteNav` desktop width matches each route's content container (`sm:max-w-5xl` on `/ratings` and `/performance`, `sm:max-w-7xl` on `/charts`, and `sm:max-w-4xl` on `/`, `/results`, `/matchup*`, and `/methodology`).
   - Mobile first-card clearance on `/` and `/results` at `390×844` (including the 34px bottom safe-area inset in `web/e2e/mobile-slate.spec.ts`) passes without regression.
3. **Matchup Hero & Biggest Mismatches (WS4 Selective):**
   - `MatchupHero.tsx` displays `spreadSource` and `totalSource` via `Cell`'s `book` prop, shows model spread/total edge deltas (`edgeSpread` / `modelSpreadEdge` and `edgeTotal` / `modelTotalEdge` in pts) on the Lean cells, and includes national unit ranks (`#offenseRank`, `#defenseRank`) alongside `adjOffEpa` and `adjDefEpa` in the Rating Strip.
   - `UnitMatchups.tsx` surfaces a compact "Biggest Mismatches" summary above the unit tables using `topMismatches([awayOffVsHomeDef, homeOffVsAwayDef], 3)` and `mismatchSummary(m)` from `web/src/lib/team-stats.ts` whenever at least one mismatch has `rankGap >= 20`.
   - `UnitMatchupTable.tsx` preserves its DOM structure (`table`'s immediate preceding sibling `div` remains the unit header with two `img[data-logo]` elements, required by `web/e2e/desktop-layout.spec.ts`).
4. **Performance 52.4% Benchmark & Audit Polish (WS5 Narrowed):**
   - `PerformanceDashboard.tsx` displays the `52.4%` (`-110` break-even) benchmark context in the Spreads and Totals headline summary cards and marks `52.4%` on the "By week" win-rate progress bars.
   - `AuditGame` rows in `PerformanceDashboard.tsx` use `ResultBadge` and `TeamLogo` instead of plain `(W)` / `(L)` / `(P)` text.
   - `/ratings` continues to show SOR as rank only, one SOS measure (against the average FBS team) as rank, and no WAA or `±SD` uncertainty (preserving commit `5060aa60`).
5. **Charts Combobox Hydration Fix (WS6 Defect Only):**
   - `TeamHighlightCombobox.tsx` removes the conflicting inline `style={{ caretColor: "var(--foreground)" }}` vs. `caret-transparent` class so SSR and client hydration emit identical attributes with zero React hydration warnings.

## Baseline and constraints

- **Inspected branch and commit:** `dev` at `41ed720b` (`feat(web): sort ratings by clicking headers and show SOS as ranks`), clean working tree, aligned with `origin/dev` and `main`.
- **Active releases:** `production-season-2026-2cdf8916d915e21b3f25fa71` and `preview-season-2026-2cdf8916d915e21b3f25fa71` (see `docs/status.md` for live authority).
- **Release coupling gate (CRITICAL):** `run_season.py release` requires `HEAD` to equal the prepared candidate's `code_sha` and a clean working tree. Any web commit after `prepare` forces a re-prepare. **Do not commit or merge web implementation changes on `dev`/`main` while a Week 8 market refresh candidate is prepared and awaiting release; land web commits only after the Week 8 line refresh is released.**
- **Overlap exclusions (owned by the earlier Week 8 stabilization plan):**
  - Do **not** edit the `team_game_stats` N+1 query in `web/src/app/page.tsx`.
  - Do **not** delete `StatCard.tsx`, `RecordBanner.tsx`, `HistoricalModelContext.tsx`, `EdgeNote.tsx`, or `ResultLeanRow.tsx`.
  - Do **not** edit `TopLeans.tsx` ("Best Bets" / top leans area).
- **Product policy constraints:**
  - Do **not** add an edge-strength filter (`>= 3.0 pt` or "Strong Edges") anywhere on the site; filtering by edge strength nudges users toward "best bets" and conflicts with `docs/modeling/betting_policy.md`.
  - Do **not** re-introduce raw SOR, raw SOS, WAA, or `±SD` uncertainty on `/ratings` unless the owner explicitly reverses the 2026-10-19 display decision (`5060aa60`).
  - Keep `CFB_CHARTS_ENABLED` off (`0` or unset) in Production; `/charts` must continue returning HTTP 404 when disabled.
- **Deferred to a separate Phase 2 follow-up plan ("After that"):**
  - `PredictionGameCard.tsx` `BetCell` hierarchy condensation
  - Conference filter on `/ratings` and slates
  - Rank-tier badges on `/ratings`
  - Collapsible secondary stat sections in `UnitMatchupTable.tsx`
  - General `/charts` visual polish

## Ordered changes

### Task 1 (WS2): CSS foundations and missing surface token

- **Affected components:**
  - `web/src/app/globals.css`
  - `web/src/app/layout.tsx`
- **Changes:**
  1. In `web/src/app/globals.css`:
     - Add `color-scheme: light;` to `:root` and `color-scheme: dark;` to `html.dark`.
     - Add `--surface-elevated: #ffffff;` to `:root` and `--surface-elevated: #1c1917;` to `html.dark`.
     - Add `--color-surface-elevated: var(--surface-elevated);` inside `@theme inline`.
     - Add scoped rules `h1, h2, h3 { text-wrap: balance; }` and `p { text-wrap: pretty; }`.
  2. In `web/src/app/layout.tsx`:
     - Add `<meta name="color-scheme" content="light dark" />` inside `<head>`.
- **Acceptance criteria:**
  - Computed background color of the share button in `ShareButton.tsx` and the "All Week N Matchups" button in `matchup/[gameId]/page.tsx` is non-transparent in both light and dark themes.
  - Computed `color-scheme` on `document.documentElement` is `"light"` in light mode and `"dark"` in dark mode.
- **Focused validation:**
  - `cd web && npx tsc --noEmit && npm run lint`

### Task 2 (WS1 Narrowed): Unified app shell (`Header`, `ThemeToggle`, `Footer`) and `SiteNav` width alignment

- **Affected components:**
  - `web/src/components/Header.tsx`
  - `web/src/components/SiteNav.tsx`
  - `web/src/app/layout.tsx`
  - `web/src/components/SlateView.tsx`
  - `web/src/app/matchup/page.tsx`
  - `web/src/app/matchup/[gameId]/page.tsx`
- **Changes:**
  1. Move `<Header />` (with `ThemeToggle`) and `<Footer />` into the shared layout flow in `web/src/app/layout.tsx` (with `<Header />` rendered above `<SiteNav />` and `<Footer />` rendered after `{children}`).
  2. Remove the duplicate `<Header>` and `<Footer>` renders from `web/src/components/SlateView.tsx`, `web/src/app/matchup/page.tsx`, and `web/src/app/matchup/[gameId]/page.tsx`.
  3. Keep `Header` compact on mobile (`< 640px`) so the total vertical height above the first game card on `/` and `/results` does not increase. If `SlateView` previously passed `dataUpdatedAt` to `<Header>`, retain the freshness timestamp either in `SlateView`'s slate summary bar or via a compact slot so no information is lost and mobile height stays within budget.
  4. In `web/src/components/SiteNav.tsx`, update the container max-width calculation:
     - `/charts` -> `sm:max-w-7xl`
     - `/ratings` or `/performance` -> `sm:max-w-5xl`
     - all other routes (`/`, `/results`, `/matchup*`, `/methodology`) -> `sm:max-w-4xl`
     - Do the same alignment on `<Header>` and `<Footer>` inner containers (or use `max-w-5xl` consistently where appropriate) so the masthead and nav align cleanly across desktop viewports.
  5. Do **not** add an active bottom bar indicator to `SiteNav`.
- **Acceptance criteria:**
  - Every route (`/`, `/results`, `/matchup`, `/matchup/[gameId]`, `/ratings`, `/performance`, `/charts` when enabled, `/methodology`) has exactly one `<header>` (or masthead banner), one `ThemeToggle` button, one `<nav aria-label="Main navigation">`, and one `<footer>`.
  - `web/e2e/mobile-slate.spec.ts` passes at `390×844` (both standard and 34px bottom safe-area inset).
- **Focused validation:**
  - `cd web && npx playwright test e2e/mobile-slate.spec.ts e2e/desktop-layout.spec.ts`

### Task 3 (WS4 Selective): Matchup hero metadata and Biggest Mismatches callout

- **Affected components:**
  - `web/src/components/matchup/MatchupHero.tsx`
  - `web/src/components/matchup/UnitMatchups.tsx`
- **Changes:**
  1. In `web/src/components/matchup/MatchupHero.tsx`:
     - Pass `book={data.spreadSource}` to the Market Spread `Cell` and `book={data.totalSource}` to the Market Total `Cell`.
     - Format the spread edge delta (`data.edgeSpread ?? data.modelSpreadEdge`) and total edge delta (`data.edgeTotal ?? data.modelTotalEdge`) as sub-labels (`+{edge.toFixed(1)} pt edge` when present) on the Spread Lean and Total Lean `Cell`s.
     - In `RatingStrip`, display `awayRating.offenseRank` / `awayRating.defenseRank` and `homeRating.offenseRank` / `homeRating.defenseRank` (`#rank`) alongside `adjOffEpa` and `adjDefEpa`.
  2. In `web/src/components/matchup/UnitMatchups.tsx`:
     - Compute `const mismatches = topMismatches([awayOffVsHomeDef, homeOffVsAwayDef], 3);` using `topMismatches` and `mismatchSummary` from `web/src/lib/team-stats.ts`.
     - When `mismatches.length > 0`, render a compact "Biggest Mismatches" callout block inside `UnitMatchups.tsx` **above** the grid of `UnitMatchupTable` components (never inside `UnitMatchupTable.tsx` between the unit header `div` and `<table>`).
- **Acceptance criteria:**
  - On `/matchup/[gameId]`, Market Spread and Market Total cells show the sportsbook source when available, Lean cells show the point edge, Rating Strip shows Off/Def national ranks, and "Biggest Mismatches" renders when `topMismatches` is non-empty.
  - `web/e2e/desktop-layout.spec.ts` unit-table header logo assertion (`table.locator("xpath=preceding-sibling::div[1]")`) and `web/e2e/matchup.spec.ts` pass.
- **Focused validation:**
  - `cd web && npx playwright test e2e/matchup.spec.ts e2e/desktop-layout.spec.ts`

### Task 4 (WS5 Narrowed): Performance 52.4% break-even benchmark and audit row polish

- **Affected components:**
  - `web/src/components/PerformanceDashboard.tsx`
- **Changes:**
  1. In `PerformanceDashboard.tsx`:
     - Add the `52.4%` (`-110` break-even) reference benchmark to the Spreads and Totals summary cards (showing both `52.4% break-even` and the signed delta in percentage points when `decided > 0`).
     - In the "By week" table (`WeekRow`), add a subtle vertical tick mark at `left: 52.4%` on the win-rate bar track (`title="52.4% break-even at -110"`).
     - In `AuditGame`, replace the plain text `({g.spreadResult})` / `({g.totalResult})` markers with `ResultBadge` and add compact `TeamLogo` icons (`size={16}`) next to the away and home team display names.
  2. Do **not** alter `RatingsView.tsx` to display raw SOR, raw SOS, WAA, or `±SD` uncertainty.
- **Acceptance criteria:**
  - `/performance` displays the `52.4%` break-even benchmark on summary cards and weekly bars, and uses `ResultBadge` + `TeamLogo` in the expandable weekly audit rows.
  - `web/e2e/performance.spec.ts` passes.
- **Focused validation:**
  - `cd web && npx playwright test e2e/performance.spec.ts`

### Task 5 (WS6 Defect Only): `TeamHighlightCombobox` hydration fix

- **Affected components:**
  - `web/src/components/charts/TeamHighlightCombobox.tsx`
- **Changes:**
  1. In `web/src/components/charts/TeamHighlightCombobox.tsx` (near line 121), remove the inline `style={{ caretColor: "var(--foreground)" }}` that conflicts with `caret-transparent` in `className`, and use a single deterministic class (`caret-current`) so server HTML and client hydration match.
- **Acceptance criteria:**
  - Visiting `/charts` with `CFB_CHARTS_ENABLED=1` and `CFB_UI_TEST_MODE=1` produces zero React hydration warnings or console errors.
- **Focused validation:**
  - `cd web && npm test`

## Validation

Run all checks below before marking the contract `Implemented`:

1. **Repository & Documentation Gates:**
   - `make contracts-check`
   - `uv run mkdocs build --strict`
   - `git diff --check`
2. **Web Static, Unit & Production Build Gates (`web/`):**
   - `cd web && npm run lint`
   - `cd web && npx tsc --noEmit`
   - `cd web && npm test`
   - `cd web && CFB_UI_TEST_MODE=1 npm run build`
3. **Playwright E2E Suites Across All 8 Routes (`/`, `/results`, `/matchup`, `/matchup/[gameId]`, `/ratings`, `/performance`, `/charts`, `/methodology`):**
   - `cd web && npx playwright test e2e/mobile-slate.spec.ts` (verifies `390×844` first-card clearance on `/` and `/results` with and without 34px safe-area inset)
   - `cd web && npx playwright test e2e/desktop-layout.spec.ts` (verifies desktop layout, container alignment, and `UnitMatchupTable` header logos across light and dark themes; update header/nav assertions if needed to verify `<Header>` is present on all routes and rendered once)
   - `cd web && npx playwright test e2e/matchup.spec.ts` (add assertions for hero book source, edge delta, unit ranks, and "Biggest Mismatches")
   - `cd web && npx playwright test e2e/performance.spec.ts` (add assertion for `52.4%` break-even benchmark visibility)
   - `cd web && npx playwright test e2e/publication.spec.ts e2e/production-gates.spec.ts` (verifies all public routes + `/charts` 404 gate when `CFB_CHARTS_ENABLED=0` and zero hydration warnings when `CFB_CHARTS_ENABLED=1`)
4. **TTFB Performance Baseline Comparison:**
   - Measure Time-to-First-Byte (TTFB) on `/` before and after the shell change against the `~2.1 s` baseline (`curl -s -o /dev/null -w "%{time_starttransfer}\n" http://localhost:3000/`) and record the comparison in the Terra implementation session log.

## Handoff/amendments

- **Approval and resume gate:** Approved with changes by the owner on 2026-10-20. Ready for a fresh Terra implementation session using `.agent/skills/implement-plan/` with this exact path (`docs/plans/2026-10-20/01-website-ui-ux-improvements.md`).
- **Release coupling reminder:** Terra may implement and validate locally in an isolated branch/worktree or after confirming the Week 8 market refresh release status, but **no commit may land on `dev`/`main` between `run_season.py prepare` and `run_season.py release`**.
- **User-controlled commit policy:** Propose the commit message at the end of the session; the owner executes git commit/push operations manually.
- **Amendments:** None yet. Mechanical amendments may proceed only if architecture, interfaces, scope, and acceptance remain unchanged; any material conflict returns to Sol.
