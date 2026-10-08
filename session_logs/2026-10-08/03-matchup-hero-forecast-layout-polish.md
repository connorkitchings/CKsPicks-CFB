# Session Log: 2026-10-08 / 03-matchup-hero-forecast-layout-polish

## Task Overview
Fast-path UI polish for the matchup breakdown hero card (`web/src/components/matchup/MatchupHero.tsx`).
Following the addition of outcome badges (`Win` / `Loss` / `Push`) to completed game cards, resolve dynamic card sizing, column asymmetry, and baseline misalignment in the "Forecast & Lines" component.

## Key Changes
- **Fixed & Stable Desktop Card Width (`sm:w-[475px]`):**
  Replaced flexible `sm:min-w-[360px]` with a stable `sm:w-[475px]` footprint so the forecast card does not jump or change width when navigating between short-name teams (e.g., LSU) and long-name teams (e.g., Mississippi State).
- **Balanced 50/50 Columns (`grid-cols-[auto_minmax(0,1fr)_minmax(0,1fr)]`):**
  Changed the grid definition from asymmetric `[auto_minmax(0,1fr)_auto]` to balanced `[auto_minmax(0,1fr)_minmax(0,1fr)]`. Spread and Total headers and values now share equal width and center squarely over their columns.
- **Unified Baseline & Non-Wrapping Pick Badges:**
  Updated `Cell` to use `sm:flex-nowrap`, `whitespace-nowrap`, and `sm:text-[13px]`. This ensures long team picks (such as "Mississippi State" + `[Loss]`) remain on a single horizontal line on desktop viewports alongside "Under" + `[Loss]`, creating a unified row baseline.

## Files Changed
- `web/src/components/matchup/MatchupHero.tsx`

## Verification
- `npm run test:publication` in `web/`: 141 passed, 1 skipped (0 failures).
- `npm run typecheck` in `web/`: clean.
- `npm run lint` in `web/`: clean.
- `git diff --check`: clean.
- Live inspection on `http://127.0.0.1:3000/matchup/401856707` confirmed balanced columns and single-line bet alignment.

## Blockers / Open Items
- None for this fast-path task.
- Unrelated repair track files in the worktree (`src/cks_picks_cfb/quality/`, `tests/test_quality_*`, etc.) remain unstaged and untouched.

## Next Steps
- Stage `web/src/components/matchup/MatchupHero.tsx` and this session log, commit to `dev`, and push / PR to `main`.
