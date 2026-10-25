# Session: Website UI/UX Review and Implementation Contract

## TL;DR
- **Worked On:** Comprehensive architecture, UI/UX, and aesthetic review of all 8 Next.js web routes (`web/src/`), incorporation of the owner's "approve with changes" judgment, and persistence of the Phase 1 Sol-to-Terra implementation contract.
- **Outcome:** Persisted approved implementation contract at `docs/plans/2026-10-20/01-website-ui-ux-improvements.md` and registered it in `docs/plans/index.md`.
- **Plan Contract:** `docs/plans/2026-10-20/01-website-ui-ux-improvements.md`
- **Approval / Status:** Approved with changes by the owner on 2026-10-20 (`Approved`)
- **Blockers:** None for planning; web implementation commits must land only after the Week 8 market refresh release is completed to avoid invalidating a prepared `code_sha` pin.
- **Next:** Execute `docs/plans/2026-10-20/01-website-ui-ux-improvements.md` in a fresh Terra task using `.agent/skills/implement-plan/`.

## Context and Decisions
- **Verified Codebase Defects:**
  - `bg-surface-elevated` is used in `web/src/components/matchup/ShareButton.tsx:84` and `web/src/app/matchup/[gameId]/page.tsx:108` without a definition in `web/src/app/globals.css`.
  - `color-scheme` is not set on `:root` or `html.dark` in `web/src/app/globals.css`.
  - `<Header>` (with `ThemeToggle`) and `<Footer>` are rendered only inside `SlateView.tsx`, `matchup/page.tsx`, and `matchup/[gameId]/page.tsx`, leaving `/ratings`, `/performance`, `/charts`, and `/methodology` without a masthead, theme toggle, or footer, and `SiteNav.tsx` uses `sm:max-w-4xl` on `/ratings` and `/performance` where the pages use `max-w-5xl`.
  - `MatchupHero.tsx` omits already-fetched `spreadSource`, `totalSource`, edge deltas, and unit ranks from `web/src/lib/matchup.ts`, and `UnitMatchups.tsx` does not surface `topMismatches` from `web/src/lib/team-stats.ts`.
  - `TeamHighlightCombobox.tsx` has an inline `caretColor` vs. `caret-transparent` SSR/client hydration mismatch.
- **Owner Plan Judgment Adjustments:**
  - Excluded items owned by the earlier Week 8 stabilization plan (`web/src/app/page.tsx` N+1 query, dead-module deletions `StatCard`/`RecordBanner`/`HistoricalModelContext`/`EdgeNote`/`ResultLeanRow`, and `TopLeans.tsx` edits) to avoid merge conflicts.
  - Dropped the "Strong Edges" filter (conflicts with the display-only betting policy in `docs/modeling/betting_policy.md`).
  - Preserved the 2026-10-19 `/ratings` display decision (`5060aa60`: SOR as rank only, single SOS measure as rank, no WAA or `±SD` uncertainty displayed).
  - Split Phase 2 follow-ups (`BetCell` hierarchy, conference filter, rank-tier badges, collapsible matchup sections) from the Phase 1 ("Now") contract and deferred general `/charts` polish while `/charts` is 404 in Production.

## Work Completed
- Audited all 8 routes (`/`, `/results`, `/matchup`, `/matchup/[gameId]`, `/ratings`, `/performance`, `/charts`, `/methodology`), shared components, data-fetching helpers, and Playwright E2E specs.
- Updated the review and phased plan artifact with the owner's "approve with changes" judgment.
- Created `docs/plans/2026-10-20/01-website-ui-ux-improvements.md` and indexed it in `docs/plans/index.md`.

## Files Modified
- `docs/plans/2026-10-20/01-website-ui-ux-improvements.md` - Created Phase 1 Sol-to-Terra implementation contract
- `docs/plans/index.md` - Added contract entry under Current Execution
- `session_logs/2026-10-20/01-website-ui-ux-review-plan.md` - Created planning session log

## Validation
- [x] `git diff --check`
- [x] `uv run mkdocs build --quiet` (passed; `--strict` reported zero warnings on `docs/plans/2026-10-20/01-website-ui-ux-improvements.md` and `docs/plans/index.md`, with 1 pre-existing link warning in `docs/planning/weekly-operations-process-review.md`)

## Amendments and Blockers
- None.

## Handoff Notes
- **Resume at:** Open a fresh Terra session with `.agent/skills/implement-plan/` targeting `docs/plans/2026-10-20/01-website-ui-ux-improvements.md`.
- **Watch out for:**
  1. Do not commit web changes to `dev`/`main` between `run_season.py prepare` and `run_season.py release` (wait until after the Week 8 market refresh is released).
  2. Keep `<Header>` compact on mobile so `web/e2e/mobile-slate.spec.ts` (`390×844` first-card clearance) passes, and ensure `SlateView` and matchup pages do not double-render `<Header>` or `<Footer>`.
  3. Keep the "Biggest Mismatches" callout in `UnitMatchups.tsx` outside `UnitMatchupTable.tsx` so `table.locator("xpath=preceding-sibling::div[1]")` in `web/e2e/desktop-layout.spec.ts` continues to match the unit header `div`.

**tags:** ["planning", "web", "ui-ux", "accessibility", "matchup", "performance"]
