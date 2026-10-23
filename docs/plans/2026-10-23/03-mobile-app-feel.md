# Contract: Mobile app-feel pass across Games, Ratings, Stats and Model

- **Status:** Draft
- **Created:** 2026-10-23
- **Approval source:** Owner approved the plan in the 2026-10-23 session and asked for it to be implemented. Decisions: browser only (no manifest, service worker or install prompt), a compact app bar on phones, and commit the Stats and Ratings work first.
- **Implementation log:** `session_logs/2026-10-23/03-mobile-app-feel.md` (written at the end of each implementation session).
- **Commit policy:** Per-area commits on a short-lived branch off the pushed `dev`; each phase is shippable on its own. Owner executes pushes.
- **Related:** [Contract A: mobile chart page](../2026-10-21/03-mobile-charts-a-page.md) (amended 2026-10-23 for the phone scatter and compact header).

## Goal and acceptance

On phones (below 640px) most of the first screen is header, not data. Give all four tabs the app-like treatment already applied to Stats and Ratings: a compact app bar, one pinned control row, a summary line, primary data within about 300px of the top, and long explanations in disclosures. Desktop layouts do not change. Complete means the measured assertions below pass on every page and the owner has checked real iPhone and Android devices.

## Findings (phones)

- Games: about 500 to 560px of header, run-status row, week nav, season-record card, three disclosures and a toolbar before the first game card.
- Model: six heading or explanation blocks before the first number, plus two controls (KPI toggles and a segmented control) driving one filter.
- Shell: the site header is not sticky and takes two rows; four title patterns and three page shells; `theme-color` ignores the manual theme toggle; no `overscroll-behavior`; changing the week scrolls to the top.
- Duplication: the two bottom sheets copy about 45 lines of dialog logic, the pinned-bar class string is byte-identical in two files, and the phone-breakpoint check exists in three copies.

## Phase A: shared foundations (no visible change)

- `useSheet({ enabled, closeOn })` returning `{dialogRef, triggerRef, titleId, open, close}`, and `<BottomSheet>`, extracted from `RatingsFilterSheet.tsx` and `MobileChartSettings.tsx` (focus return, body scroll lock, `visualViewport` sizing, Escape). Both sheets switch to it; Stats keeps closing on chart change through `closeOn`.
- `<MobileStickyBar>` from the duplicated class string in `RatingsView.tsx` and `stats/page.tsx`, with `env(safe-area-inset-top)` and an opaque background; decide on backdrop blur once.
- Rename `charts/useMobileChart.ts` to a shared `useIsPhone` hook and replace the inline copies in `NetSuccessView.tsx` and `SlateGameList.tsx`.
- A shared summary-line component (from the Stats helper in `ChartFrame.tsx`) for Games, Ratings and Model, using "·" separators and no repeated season.

## Phase B: app shell

- Compact app bar on phones: one slim row with the page name. Season selector, theme toggle and "Updated" time move into a menu button built on `<BottomSheet>`. The brand shows only on Games. From 640px up the header is unchanged.
- Games run-status row collapses to one line under the app bar or into the menu; the Retrospective-replay state stays visible.
- `overscroll-behavior-y: none` on `body`; `scroll-padding-top` equal to the pinned bars.
- `theme-color` follows the manual theme toggle (theme script and `ThemeToggle`); dark value `#000` to match `--surface-page`.
- Week and season changes use `router.push(..., { scroll: false })` in `WeekNav.tsx` and `SeasonSelector.tsx`.

## Phase C: per page

- **Games** (`SlateView.tsx`, `components/slate/*`): pinned week navigator plus Filters button; search, conference and sort move into a Filters sheet with a quick search field kept; the title becomes a small "Week N · Upcoming" label; `ModelRecord` becomes one compact line that opens the full card; `TopLeans` and `ResultHighlights` stay collapsed and sit after the first few game cards (or become a chip row); the sticky day-group header is offset below the pinned bar.
- **Matchup detail:** the same compact bar with a back chevron ("Week N games"); hero compacted.
- **Ratings, Stats:** adopt the shared components with no behavior change; on Stats, put the settings trigger and summary where they do not duplicate the heading.
- **Model** (`app/model/page.tsx`, `PerformanceDashboard.tsx`): pinned Record / How it works tabs; remove the hand-rolled eyebrow and the duplicate cumulative-record `h2`; description in a disclosure; the KPI buttons become the single Spread / Totals filter (the segmented control goes); trailing explainers move into one disclosure.

## Phase D: polish

Press-state feedback on tappable cards; consistent 44px targets, card radius and spacing (one page padding and `space-y` value); skeletons match the new compact tops; `prefers-reduced-motion` respected for new sheet and bar transitions.

## Out of scope

Manifest, installability, service worker, offline mode, push notifications, native gestures, Contract B's chart inspector, desktop layout changes.

## Validation

1. Per phase: `npm --prefix web run lint`, `typecheck`, `test:publication`, a fresh fixture build (`CFB_UI_TEST_MODE=1 CFB_PUBLICATION_MODE=predictions npm --prefix web run build`), then `CI=1 npm --prefix web run test:ui`. Flake gate (`--repeat-each=20 --retries=0`) on changed specs.
2. New measured assertions at 390x844 and 320x568 on every page: the first data item's top is under about 330px, the pinned bar stays at top after an 800px scroll, sheets open above it and return focus on close, no horizontal overflow.
3. Owner check on production data (`make web-local ENV=production`) in a phone-sized window and on a real iPhone and Android device before closing the contract.
4. CI per-job timings compared against run `39993143753`; the browser job stays under about 3 minutes.

## Amendments

Mechanical amendments may proceed when architecture, interfaces, scope and acceptance remain unchanged; record reason, previous approach, revised approach and impact.
