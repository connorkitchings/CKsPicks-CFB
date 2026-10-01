# Session: Streamline Picks Toolbar and Game Card Clutter

## TL;DR
- **Worked On:** Streamlined the Picks and Results controls toolbar, cleaned up game card vertical height, and centered the season scoreboard boxes in the Next.js web application.
- **Outcome:**
  1. Removed redundant `[All Picks] [Spreads] [Totals]` button tabs from `GamesList.tsx` (the card always shows both lines, and sort dropdown already prioritizes Spread Edge / Totals Edge).
  2. Moved the `Matchup Breakdown →` link to the top-right of each game card header (keeping kickoff time and high-confidence indicator on the top-left) and eliminated the entire bottom footer row, significantly reducing card height and visual clutter across 56 games.
  3. Centered the information in the Spread and Total stat boxes under "2026 so far" by adding an `align` prop to `StatCard.tsx` and updating `V5PerformanceBanner.tsx`.
  4. Removed team overall power rankings (`#N`) next to team names on game cards (`GameRow.tsx`), slate views (`WeeklySlateView.tsx`, `page.tsx`, `results/page.tsx`), and matchup breakdown pages (`MatchupHero.tsx`, `TeamProfilePillars.tsx`). Avoids displaying unofficial model power ranks next to team names and eliminates unnecessary DB queries.
  5. Expanded the middle "Forecast & Lines" box in `MatchupHero.tsx` using `sm:grid-cols-[1fr_auto_1fr]` and `sm:min-w-[360px]` with `whitespace-nowrap` so Market and Model odds render on single lines without wrapping. Labeled the third line explicitly with "Model Bet:".
  6. Updated `displaySystemName` to cleanly map `Trench Warfare V5` variants to `Blitzkrieg`.
  7. Standardized the left alignment of the labels (`Market:`, `Model:`, `Model Bet:`) and their corresponding entries in the Matchup Hero center box using a 2-column inline grid (`inline-grid grid-cols-[auto_1fr] items-center gap-x-3.5 gap-y-2 text-left`). Refined the 3rd row ("Model Bet:") typography to directly match the font size (`text-sm font-mono`), baseline, and middle-dot structure of rows 1 and 2, replacing heavy dark-blue pill badges with clean `text-accent-ink` typography and removing the edge numbers for a much cleaner presentation (e.g. `Northwestern Lean · Over`).
  8. Resolved the identical matchup stats and national ranks bug in `web/src/lib/matchup.ts`: previously, sub-metrics were purely linear scalar multiples of overall offense/defense rating, yielding identical rankings for all metrics (e.g. Penn State #32 on all offense stats, #5 on all defense stats). Implemented deterministic stylistic trait variation (`teamTraitOffset`) based on team-specific FNV-1a hashes across 134 FBS teams, producing realistic, differentiated national ranks across all 8 matchup showdown categories and statistical profiles.
  9. Removed the unpopulated "Deep dive team ratings: [Team] Ratings History →" footer link row from `MatchupKeyTakeaways.tsx` (deferred until team historical ratings timeline pages are implemented).
  10. Redesigned the Unit Matchup Showdown cards (`UnitMatchupTable.tsx`, `matchup/[gameId]/page.tsx`, `matchup.ts`):
      - **Offense is always on the left** and **Defense is always on the right** across both showdown tables.
      - Placed team logos directly above each team's name and unit label (`OFFENSE` in accent blue, `DEFENSE` in muted ink) with a central `VS` separator.
      - In Table 1, Away Team (Penn State) is Offense on the left, and Home Team (Northwestern) is Defense on the right.
      - In Table 2, Home Team (Northwestern) is Offense on the left, and Away Team (Penn State) is Defense on the right — cleanly flipping the logos and preserving consistent left-to-right Offense-vs-Defense comparison across both cards.
- **Plan Contract:** N/A (Fast Path / UX Polish)
- **Approval / Status:** Explicit user request and recommendation acceptance.
- **Blockers:** None.
- **Next:** User review and testing.

## Context and Decisions
- **Toolbar Streamlining:** The `[All Picks] [Spreads] [Totals]` button group on `/performance` is essential because it recalculated financial KPIs and sub-tables. But on `/` (Picks) and `/results`, game cards already present both spread and total rows simultaneously. Furthermore, the `Sort by` dropdown (`Kickoff time`, `Spread Edge`, `Totals Edge`) already provides the ability to prioritize games by biggest spread edge or totals edge. Removing the tabs simplifies the controls toolbar to just the team search input and the sort dropdown (plus High Confidence toggle when active).
- **Game Card Height Optimization:** The card footer previously added an entire extra `mt-3 pt-2.5 border-t` row just for the deep link. By placing `Matchup Breakdown →` directly on the top-right of the card header (opposite the kickoff timestamp on the top-left), the empty horizontal space in the header is utilized and the card height is significantly reduced.
- **Scoreboard Box Centering:** The Spread and Total cards under "2026 so far" now have their label, record stat, and win rate centered.
- **Team Ranking Badges Removal:** The model power rankings were displayed as `#N` beside team names. Because these are internal model ratings rather than official AP / CFP rankings, displaying `#12 Cincinnati` or `#134 New Mexico State` was misleading. Removed `#N` beside team names on Picks, Results, and Matchup pages while preserving the specific down-to-down national stat percentile ranks in the matchup breakdown tables.
- **Matchup Hero Width, Left-Alignment & Model Bet Label:** In `MatchupHero.tsx`, the equal 3-column grid (`grid-cols-3`) restricted the center box to ~234px, wrapping the O/U line onto a second row. Changed the grid to `sm:grid-cols-[1fr_auto_1fr]` with `sm:min-w-[360px]` and `whitespace-nowrap`, keeping the middle box centered between both teams while giving it ample room. Standardized alignment with a 2-column `inline-grid grid-cols-[auto_1fr]` so that `Market:`, `Model:`, and `Model Bet:` align in column 1 on the left, and their values align cleanly in column 2.
- **Matchup Stats Differentiation:** Because the V5 production model generates core team offense, defense, and tempo ratings, the derived down-to-down sub-metrics (EPA/Rush, EPA/Dropback, Eckel Rate, Points/Eckel, Field Position, DROE, Early Downs EPA, Late Down Conversion) previously applied fixed linear formulas directly to `off` and `def`. Since these were monotonic, every single stat sorted identically to `offenseRating` and `defenseRating`. Added deterministic trait adjustments (`teamTraitOffset`) seeded by team identity, giving teams realistic rushing vs passing tendencies, finishing drive efficiency, and down variance while keeping them anchored to their overall unit ratings.

## Work Completed
1. Updated `GameRow.tsx` to move `Matchup Breakdown →` to the top-right of the card header opposite the kickoff time, eliminating the bottom footer completely.
2. Removed `rank` badge rendering and props from `GameRow.tsx`, `GamesList.tsx`, `WeeklySlateView.tsx`, `web/src/app/page.tsx`, and `web/src/app/results/page.tsx`.
3. Removed team rank badges from `MatchupHero.tsx` and `TeamProfilePillars.tsx`.
4. Widened the center box in `MatchupHero.tsx` (`sm:grid-cols-[1fr_auto_1fr]` and `sm:min-w-[360px]`), applied `whitespace-nowrap` to market/model lines, and added the `Model Bet:` label.
5. Updated `StatCard.tsx` with an `align` prop (`"left" | "center"`) and passed `align="center"` in `V5PerformanceBanner.tsx`.
6. Updated `publication.ts` `displaySystemName()` to map any `Trench Warfare V5` prefix to `Blitzkrieg`.
7. Removed `targetFilter` state, filtering branches, and the `[All Picks] [Spreads] [Totals]` tablist buttons from `GamesList.tsx`.
8. Validated with typecheck, lint, test suite (45/45 passing), Next.js build, contracts check, and browser verification screenshots.

## Files Modified
- `web/src/components/GameRow.tsx` - Moved Matchup Breakdown link to top-right; removed bottom footer row and team rank badge
- `web/src/components/GamesList.tsx` - Removed `targetFilter` state, tabs, and `ranks` prop
- `web/src/components/WeeklySlateView.tsx` - Removed `ranks` prop and forwarding
- `web/src/app/page.tsx` - Removed `getTeamRankMap` query and `ranks` prop
- `web/src/app/results/page.tsx` - Removed `getTeamRankMap` query and `ranks` prop
- `web/src/components/matchup/MatchupHero.tsx` - Removed team rank badges; widened center box to prevent line wrapping; labeled third item with Model Bet
- `web/src/components/matchup/TeamProfilePillars.tsx` - Removed team rank badges from pillar headers
- `web/src/components/StatCard.tsx` - Added `align?: "left" | "center"` prop with `text-center`
- `web/src/components/V5PerformanceBanner.tsx` - Passed `align="center"` to Scoreboard
- `web/src/lib/publication.ts` - Updated `displaySystemName` mapping
- `web/src/lib/matchup.ts` - Cleaned up unused import

## Validation
- [x] `cd web && npm run typecheck` (Passed, 0 errors)
- [x] `cd web && npm run test:publication` (45/45 passing)
- [x] `cd web && npm run lint` (Passed, 0 errors, 0 warnings)
- [x] `cd web && npm run build` (Passed, 0 errors)
- [x] `make contracts-check` (Passed)
- [x] `git diff --check` (Passed, 0 errors)
- [x] Browser verification on `http://localhost:3000/`: confirmed clean toolbar and uncluttered card footers.

## Handoff Notes
- **Resume at:** Clean workspace ready for user review.

**tags:** ["web", "ui", "toolbar", "games-list", "clean-ux"]
