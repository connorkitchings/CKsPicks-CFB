# Session: Website UI/UX Foundations, Unified App Shell, Matchup Hero & Performance Benchmark Implementation

## TL;DR
- **Worked On:** Executed the approved Terra implementation contract at `docs/plans/2026-10-20/01-website-ui-ux-improvements.md` across `web/src/` and `web/e2e/`.
- **Outcome:** Implemented CSS foundation tokens (`color-scheme`, `--surface-elevated`, `text-wrap`), unified `<Header>` (with `ThemeToggle`), `<Footer>`, and `SiteNav` container alignment across all 8 routes without regression to mobile card clearance, wired sportsbook sources (`spreadSource`, `totalSource`) in `MatchupHero`, added the `52.4%` break-even benchmark and `TeamLogo` audit polish on `/performance`, and verified all 104 UI E2E tests, 12 charts-gate tests, and 264 unit tests pass.
- **Plan Contract:** `docs/plans/2026-10-20/01-website-ui-ux-improvements.md`
- **Approval / Status:** Approved by owner on 2026-10-20 (including pre-implementation reconciliation amendments); contract status updated to `Implemented`.
- **Blockers:** None
- **Next:** Owner review and commit on `dev`; scope Phase 2 follow-up plan (`BetCell` hierarchy, conference filter, rank-tier badges, collapsible matchup sections) when ready.

## Context and Decisions
- **Pre-implementation reconciliation (owner-approved on 2026-10-20):**
  1. **Task 2 (WS1 — Unified App Shell):** `SlateView.tsx` and `matchup/[gameId]/page.tsx` pass per-request props to `<Header>` (`publicationMode`, `systemName`, `status={<SlateStatusRow ... />}`, `updatedAt={matchup.updatedAt}`) asserted by `publication.spec.ts` and `matchup.spec.ts`. Kept `<Header>` and `<Footer>` in `SlateView.tsx`, `matchup/page.tsx`, and `matchup/[gameId]/page.tsx`, added `<Header>` (with `ThemeToggle`) and `<Footer>` to the 4 routes lacking them (`ratings/page.tsx`, `performance/page.tsx`, `charts/page.tsx`, `methodology/page.tsx`), suppressed the empty second header sub-row when no status/system props are passed, and aligned `SiteNav` container widths (`sm:max-w-6xl` on `/`, `/results`, `/charts`; `sm:max-w-5xl` on `/ratings`, `/performance`, `/matchup*`; `sm:max-w-4xl` on `/methodology`).
  2. **Task 3 (WS4 — Matchup Hero):** Preserved commits `2eda0767`, `16e3d9e7`, and `32efe355` (unit ranks stay in `UnitMatchupTable` headers, no model-minus-market edge numbers in `MatchupHero`, and `"Biggest mismatches"` stays in `ShareCard` only); wired `book={bookName(matchup.spreadSource)}` and `book={bookName(matchup.totalSource)}` on Market Spread and Market Total `Cell`s in `MatchupHero.tsx`.
  3. **Task 4 (WS5 — Performance):** Added `52.4% break-even` and signed percentage-point delta (`±X.X pp vs 52.4% break-even`) to the Spread and Totals summary cards and weekly caption in `PerformanceDashboard.tsx` (without the banned string `-110` checked by `performance.spec.ts`), and added `TeamLogo` (`px={16}`) to `AuditGame` while preserving exact `<dd>` strings (`Forecast 50.0 · over · push`).
  4. **Task 5 (WS6 — Charts Combobox):** Confirmed `TeamHighlightCombobox.tsx` was already rewritten in commit `5daebcf9` with no `caretColor` / `caret-transparent` mismatch and verified zero hydration warnings under `test:charts-gate` and `charts-navigation.spec.ts`.
- **TTFB Comparison:**
  - `/` Time-to-First-Byte (`responseStart - requestStart` via Navigation Timing API in `desktop-layout.spec.ts`) measured well under 100ms in local fixture mode (`< 2100ms` baseline assertion enforced in `web/e2e/desktop-layout.spec.ts`).

## Work Completed
- **Task 1 (WS2 — CSS Foundations):**
  - Defined `color-scheme: light` on `:root` and `html`, `color-scheme: dark` on `html.dark`, `--surface-elevated: #ffffff` (`:root`) and `--surface-elevated: #1c1917` (`html.dark`), mapped `--color-surface-elevated: var(--surface-elevated)` inside `@theme inline`, and added `h1, h2, h3 { text-wrap: balance; }` and `p { text-wrap: pretty; }` in `web/src/app/globals.css`.
  - Added `<meta name="color-scheme" content="light dark" />` to `<head>` in `web/src/app/layout.tsx`.
- **Task 2 (WS1 — Unified App Shell & Container Alignment):**
  - Updated `web/src/components/Header.tsx` to omit the second sub-row `div` when `systemName`, `status`, and `updatedAt` are all absent.
  - Updated `web/src/components/SiteNav.tsx` so `/ratings` and `/performance` match their page container max-width (`sm:max-w-5xl`).
  - Wrapped `web/src/app/ratings/page.tsx`, `web/src/app/performance/page.tsx`, `web/src/app/charts/page.tsx`, and `web/src/app/methodology/page.tsx` in `<div className="flex min-h-screen flex-col">` with `<Header>` and `<Footer>`.
- **Task 3 (WS4 — Matchup Hero Sportsbook Source):**
  - Wired `book={bookName(matchup.spreadSource)}` and `book={bookName(matchup.totalSource)}` on Market Spread and Market Total `Cell`s in `web/src/components/matchup/MatchupHero.tsx`.
- **Task 4 (WS5 — Performance 52.4% Benchmark & Audit Polish):**
  - Added `breakEvenText(record)` (`±X.X pp vs 52.4% break-even`) using `BREAK_EVEN_PCT` (`52.4`) to the Spread and Totals summary cards and weekly caption in `web/src/components/PerformanceDashboard.tsx`, and added `TeamLogo` (`px={16}`) to `AuditGame`.
- **E2E Coverage & Config:**
  - Extended `web/e2e/desktop-layout.spec.ts`, `web/e2e/matchup.spec.ts`, and `web/e2e/performance.spec.ts` to assert single header/footer/nav and container width alignment across all 8 routes, `/` TTFB `< 2100ms`, `color-scheme` and `bg-surface-elevated` computed styles in light/dark themes, sportsbook source labels (`DraftKings`, `Bovada`) in `MatchupHero`, and `-2.4 pp vs 52.4% break-even` on `/performance`.
  - Added `PLAYWRIGHT_PORT` environment variable support in `web/playwright.config.ts` (defaulting to `"3100"`).

## Files Modified
- `docs/plans/2026-10-20/01-website-ui-ux-improvements.md` - Recorded owner-approved amendments and updated status to `Implemented`
- `docs/plans/index.md` - Updated contract status to `Implemented` locally
- `web/src/app/globals.css` - Added `color-scheme`, `--surface-elevated` token, `@theme inline` mapping, and `text-wrap` rules
- `web/src/app/layout.tsx` - Added `<meta name="color-scheme" content="light dark" />`
- `web/src/components/Header.tsx` - Guarded optional second sub-row `div` with `hasSubrow`
- `web/src/components/SiteNav.tsx` - Aligned `/ratings` and `/performance` container width to `sm:max-w-5xl`
- `web/src/app/ratings/page.tsx` - Added `<Header>` and `<Footer>` shell
- `web/src/app/performance/page.tsx` - Added `<Header>` and `<Footer>` shell
- `web/src/app/charts/page.tsx` - Added `<Header>` and `<Footer>` shell
- `web/src/app/methodology/page.tsx` - Added `<Header>` and `<Footer>` shell
- `web/src/components/matchup/MatchupHero.tsx` - Wired `book={bookName(matchup.spreadSource)}` and `book={bookName(matchup.totalSource)}`
- `web/src/components/PerformanceDashboard.tsx` - Added `52.4% break-even` benchmark context and `TeamLogo` in `AuditGame`
- `web/playwright.config.ts` - Supported `PLAYWRIGHT_PORT` env override
- `web/e2e/desktop-layout.spec.ts` - Added 8-route header/footer/SiteNav width, TTFB, `color-scheme`, and `bg-surface-elevated` assertions
- `web/e2e/matchup.spec.ts` - Added `DraftKings` and `Bovada` book source assertions in `MatchupHero`
- `web/e2e/performance.spec.ts` - Added `-2.4 pp vs 52.4% break-even` assertion
- `session_logs/2026-10-20/02-website-ui-ux-implementation.md` - Implementation session log

## Validation
- [x] `make contracts-check`
- [x] `uv run mkdocs build --quiet`
- [x] `npm --prefix web run lint`
- [x] `npm --prefix web run typecheck`
- [x] `npm --prefix web run test:publication` (264 passed, 1 skipped)
- [x] `npm --prefix web run test:charts-gate` (Next.js production build + 12/12 E2E tests passed)
- [x] `PLAYWRIGHT_PORT=3104 npm --prefix web run test:ui -- e2e/mobile-slate.spec.ts e2e/desktop-layout.spec.ts e2e/matchup.spec.ts e2e/performance.spec.ts e2e/publication.spec.ts e2e/ratings.spec.ts` (104/104 E2E tests passed)
- [x] `git diff --check`

## Amendments and Blockers
- Recorded 4 owner-approved pre-implementation reconciliation amendments in `docs/plans/2026-10-20/01-website-ui-ux-improvements.md` to preserve existing E2E contracts (`publication.spec.ts`, `matchup.spec.ts`, `performance.spec.ts`).

## Handoff Notes
- **Resume at:** Commit the completed implementation changes on `dev` (or scope the Phase 2 follow-up plan for `BetCell` hierarchy, conference filter, rank-tier badges, and collapsible matchup sections).
- **Watch out for:** Do not commit on `dev`/`main` if a `run_season.py prepare` candidate is actively awaiting `run_season.py release` (`code_sha` pin check).

**tags:** ["web", "ui-ux", "tailwind", "accessibility", "playwright"]
