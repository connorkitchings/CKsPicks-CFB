# Session: Mobile app-style bottom navigation and QoL improvements

## TL;DR
- **Worked On:** (1) Responsive app-style bottom tab bar on mobile; (2) Mobile Quality of Life improvements across picks and results slates; (3) Mobile vertical space reduction (same-line Blitzkrieg + Frozen status badge, compact header and section padding).
- **Outcome:** 
  - `SiteNav` is now a mobile app-style fixed bottom tab bar on `< sm` with frosted glass backdrop blur, iOS safe-area padding, touch-friendly icons, and active indicators; seamlessly stays as clean top navigation on desktop (`sm:`).
  - Header on mobile now displays `Blitzkrieg` and `Frozen before kickoff` on the exact same line (`display: contents` wrapper + compact gap), with publication timestamp wrapping cleanly beneath, saving vertical height.
  - Reduced vertical padding across Header (`py-2.5 sm:py-3.5`), main container (`py-3 sm:py-6`, `space-y-3 sm:space-y-4`), and Best Bets (`p-3 sm:p-4`).
  - Search inputs on both slates upgraded to `text-base sm:text-sm` (stops iOS Safari auto-zooming on focus) and gain a 1-tap `✕` clear button.
  - Slate day headers (`Thursday, Oct 2`, `Saturday, Oct 4`) are now sticky with backdrop blur while scrolling down long slates.
  - Slate toolbar wraps cleanly on mobile (full-width search above, sort & view toggle side-by-side below).
  - Added `scroll-smooth` for smooth jumps from "Best Bets" to game cards, `touch-action: manipulation` (no 300ms tap delay), and `-webkit-tap-highlight-color: transparent`.
- **Approval / Status:** Fast path, user approved and verified.
- **Blockers:** None.
- **Next:** Proceed with the unified data-fix plan Phase 1 (`docs/plans/2026-10-03/01-unified-data-fix-and-matchup-rollout.md`) when ready.

## Context and Decisions
- Implemented responsive mobile bottom tab bar within the single `<nav aria-label="Main navigation">` so accessible tree and existing Playwright tests (`toHaveCount(1)`) pass without modification.
- Added `pb-16 sm:pb-0` to `<body>` in `web/src/app/layout.tsx` to prevent mobile bottom tab bar from obscuring footer or lowest content.
- Changed `SlateStatusRow` container to `contents sm:flex` so `[Blitzkrieg]` and `[• Frozen before kickoff]` become sibling flex items in the Header, guaranteeing they sit side-by-side on mobile.
- Hid native webkit search cancel button (`[&::-webkit-search-cancel-button]:hidden`) in favor of uniform, accessible SVG clear button across all mobile browsers.

## Work Completed
- `web/src/components/SiteNav.tsx`: Responsive navigation (fixed bottom bar on mobile with icons + labels, top nav on desktop).
- `web/src/components/Header.tsx`: Reduced vertical padding (`py-2.5 sm:py-3.5`), compact title font on mobile (`text-lg sm:text-xl`).
- `web/src/components/slate/SlateStatusRow.tsx`: Sits on same line as model chip; timestamp wraps cleanly with `basis-full sm:basis-auto`.
- `web/src/components/slate/SlateView.tsx`: Main container spacing reduced on mobile (`space-y-3 sm:space-y-4 py-3 sm:py-6`).
- `web/src/components/slate/TopLeans.tsx`: Added mobile-only segmented control (`[ Spreads ] [ Totals ]`) cutting vertical card height in half; unified rows to show the game matchup on the left (`Away @ Home`) and the backed team logo + line on the right (`[Logo] +21.0`), eliminating duplicate team logos and matching Totals structure.
- `web/src/components/slate/SlateGameCard.tsx`: Hid sportsbook line provider on mobile (`hidden sm:inline`) and formatted model spread into a direct, compact line (`Model: -5.9 (+3.4)`) on mobile while retaining full text on desktop.
- `web/src/components/slate/ResultGameCard.tsx`: Applied the same mobile line provider hiding and direct spread line formatting on results cards.
- `web/src/app/layout.tsx`: `scroll-smooth` on `<html>`, bottom padding `pb-16 sm:pb-0` on `<body>`.
- `web/src/components/slate/ModelRecord.tsx`: Refined record cells with category micro-pills, clean mono tracking, and win-rate status badges.
- `web/src/app/globals.css`: `touch-action: manipulation` on interactive elements, `-webkit-tap-highlight-color: transparent`, and dark mode card elevation highlight (`box-shadow: inset 0 1px 0 0 rgba(255, 255, 255, 0.06)`).
- `web/next.config.ts`: Set `devIndicators: false` to disable the Next.js floating overlay bubble in local development.
- `web/src/components/slate/PicksSlate.tsx`: Search input font size fix, quick clear button, mobile toolbar layout, sticky day headers with backdrop blur.
- `web/src/components/slate/ResultsSlate.tsx`: Same search, toolbar, and sticky day header improvements.

## Files Modified (This Session)
- `web/src/components/SiteNav.tsx`
- `web/src/components/Header.tsx`
- `web/src/components/slate/SlateStatusRow.tsx`
- `web/src/components/slate/SlateView.tsx`
- `web/src/components/slate/TopLeans.tsx`
- `web/src/components/slate/SlateGameCard.tsx`
- `web/src/components/slate/ResultGameCard.tsx`
- `web/src/components/slate/ModelRecord.tsx`
- `web/next.config.ts`
- `web/src/app/layout.tsx`
- `web/src/app/globals.css`
- `web/src/components/slate/PicksSlate.tsx`
- `web/src/components/slate/ResultsSlate.tsx`

## Validation
- [x] `npm --prefix web run typecheck` — passed (0 errors)
- [x] `npm --prefix web run lint` — passed (0 warnings/errors)
- [x] `npm --prefix web run test:publication` — passed (110/110)
- [x] `npm --prefix web run test:ui` — passed (43/43 Playwright e2e tests)
- [x] `npm --prefix web run build` — passed (all routes compiled in 1.1s)
- [x] `git diff --check` — passed (clean)

## Handoff Notes
- **Resume at:** `docs/plans/2026-10-03/01-unified-data-fix-and-matchup-rollout.md` Phase 1 (data audit/investigation).
- **Proposed commit message:**
  ```
  feat(web): add mobile bottom tab bar, same-line header status, and slate QoL polish

  - Dock SiteNav to screen bottom on mobile with app-style icons, backdrop blur, and safe area support
  - Move Blitzkrieg model chip and Frozen status badge to the same line on mobile
  - Reduce header, main container, and best bets vertical whitespace on mobile
  - Prevent iOS Safari auto-zoom on team search inputs (text-base sm:text-sm)
  - Add 1-tap clear button to team filter on picks and results slates
  - Make slate day headers sticky with backdrop blur while scrolling
  - Improve mobile toolbar layout to prevent ragged wrapping
  - Add scroll-smooth, touch-manipulation, and transparent tap highlight
  ```

**tags:** ["web", "mobile", "ui", "navigation", "fast-path"]
