# Session: Plan Authentic Matchup Stats & Strip Synthetic Data

## TL;DR
- **Worked On:** Removed all synthetic/mocked stats from the matchup page, stripped matchup deep links from Picks and Results cards, and authored an implementation contract to ingest genuine football measurements into Neon Postgres.
- **Outcome:**
  1. **Removed Deep Links:** Removed the `Matchup Breakdown →` link from `PredictionGameRow` and `MarketGameRow` in `web/src/components/GameRow.tsx`. Users on `/` (Picks) and `/results` will not encounter the matchup page until authentic stats are live.
  2. **Eliminated Synthetic Data:** Completely removed `deriveTeamMetrics` and trait hashing from `web/src/lib/matchup.ts`. Removed simulated Win Probabilities and derived Projected Points from `MatchupHero.tsx`. Removed the synthetic `UnitMatchupTable`, `TeamProfilePillars`, and `MatchupKeyTakeaways` from `web/src/app/matchup/[gameId]/page.tsx`.
  3. **Authentic Data Display:** `MatchupHero` now renders 100% genuine data straight from the database:
     - Market lines (Spread & O/U)
     - Model predictions (Spread & O/U)
     - Model Bet lean (e.g. `Northwestern Lean · Over`)
     - Official Blitzkrieg V5 Certified Team Ratings and Ranks: Overall Rank & Rating (`+1.07`), Offense Rank (`#14`), Defense Rank (`#51`)
     - Actual Final Game Score (if settled)
  4. **Transparent Status Banner:** Added a clean notice on `/matchup/[gameId]` explaining that advanced play-by-play metrics (EPA/pass, EPA/rush, scoring opportunities, field position) are in the process of pipeline ingestion, with direct links to full team rating profiles.
  5. **Durable Sol Implementation Contract:** Authored `docs/plans/2026-10-01/10-authentic-team-stats-pipeline.md` detailing:
     - Selected authentic metrics: Passing EPA, Rushing EPA, Scoring Opportunity Rate, Points per Scoring Opp (PPSO), Average Starting Field Position, Explosive Play Rate, Early Downs EPA, and 3rd/4th Down Conversion Rate.
     - Database schema migration: `team_season_stats` table in Neon Postgres (`0019_team_season_stats.sql`).
     - Pipeline publisher: `scripts/pipeline/publish_team_stats.py` to aggregate play/drive records from R2/CFBD and upsert to Neon.
     - Web layer integration: dynamic ranking and sign inversion in `web/src/lib/matchup.ts`, re-enabling `UnitMatchupTable` and game card deep links.
  6. **Picks vs Results "Bet Result" Column Optimization:**
     - Removed the `Bet Result` column (and mobile result badges) from the Picks tab (`/`) where games are upcoming or active and results are not applicable.
     - Preserved the `Bet Result` column (Win / Loss / Push badges) on the Results tab (`/results`) via `showBetResult={mode === "results"}` plumbed cleanly through `WeeklySlateView`, `GamesList`, `GameRow`, and `BetComparisonTable`.
- **Plan Contract:** `docs/plans/2026-10-01/10-authentic-team-stats-pipeline.md`
- **Approval / Status:** Draft (Ready for User Review)
- **Blockers:** None
- **Next:** User approval of the plan, followed by Terra implementation of Migration 0019 and `publish_team_stats.py`.

## Context and Decisions
- **Zero Synthetic Tolerance:** As college football fans and bettors, displaying simulated numbers (or Parker Fleming terminology like DROE/Eckel Rate derived from arbitrary hashes) creates distrust. Stripping all simulated metrics immediately guarantees that every number shown on the site is an authentic, verifiable output of our verified database.
- **Deep Links Deferral:** While the data ingestion pipeline is built, removing the `Matchup Breakdown →` deep link on the Picks and Results tabs keeps the main user journey focused and clean.
- **Picks Tab Simplicity:** Upcoming games on the Picks tab don't need an empty "Bet Result" column with dashes. Hiding it makes the table a compact, clean 3-column view (`Market`, `Model`, `Model Bet`) with plenty of room on mobile and desktop, while the Results tab retains the full grading audit trail.
- **Real Football Metrics:** The 8 selected metrics reflect standard, high-leverage football realities:
  - Passing & Rushing EPA/play (air vs ground efficiency)
  - Scoring Opportunity Rate & Points Per Scoring Opportunity (finishing drives)
  - Starting Field Position & Explosive Play Rate
  - Early Downs EPA & 3rd/4th Down Conversions

## Files Modified
- `web/src/components/WeeklySlateView.tsx` - Passed `showBetResult={mode === "results"}` to `GamesList`.
- `web/src/components/GamesList.tsx` - Accepted `showBetResult` and forwarded to `GameRow`.
- `web/src/components/GameRow.tsx` - Forwarded `showBetResult` to `BetComparisonTable` and `MarketGameRow`; removed `Matchup Breakdown →` link.
- `web/src/components/BetComparisonTable.tsx` - Conditionally rendered `Bet Result` header, desktop cells, and mobile stacked badges based on `showBetResult`.
- `web/src/lib/matchup.ts` - Refactored to query only authentic `games`, `gameResults`, and `v5_rating_snapshots`; removed all synthetic calculation routines.
- `web/src/components/matchup/MatchupHero.tsx` - Render authentic team ratings (Overall, Off, Def) and final scores; removed simulated win prob and projected points.
- `web/src/app/matchup/[gameId]/page.tsx` - Replaced synthetic tables with authentic status banner and links to team profiles.
- `docs/plans/2026-10-01/10-authentic-team-stats-pipeline.md` - Complete Sol implementation contract.

## Validation
- [x] `cd web && npm run typecheck` (Passed, 0 errors)
- [x] `cd web && npm run test:publication` (45/45 passing)
- [x] `uv run pytest -q` (1543 passed, 3 skipped in 102.59s)
- [x] `uv run mkdocs build --quiet` (Passed, 0 errors)
- [x] `git diff --check` (Passed, 0 errors)
- [x] Local curl test to `/matchup/401858476` (Returns 200 with authentic ratings and no fake stats)
- [x] Verified zero `/matchup/` links in `web/src` UI cards
- [x] Verified 0 occurrences of "Bet Result" on `/` (Picks) and preserved on `/results`

## Amendments and Blockers
- None.

## Handoff Notes
- **Resume at:** Review the plan at `docs/plans/2026-10-01/10-authentic-team-stats-pipeline.md`. Upon approval, execute with `implement-plan`.
- **Watch out for:** Defense rankings must be sorted such that lower is better (i.e. rank #1 is the team allowing the least EPA/play or fewest points per scoring opportunity).

**tags:** ["matchup", "plan", "sol", "cleanup", "stats"]
