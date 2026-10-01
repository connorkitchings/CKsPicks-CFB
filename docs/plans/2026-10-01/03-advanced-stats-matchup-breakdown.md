# Plan: Advanced Stats Matchup Breakdown (Parker Fleming Style)

- **Status:** Implemented
- **Created:** 2026-10-01
- **Planner:** Sol
- **Approval source:** User explicit approval in session ("Yes")
- **Implementation log:** `session_logs/2026-10-01/07-matchup-breakdown-implementation.md`
- **Commit policy:** Commit with implementation

---

## Goal

Implement the **Phase 2 Advanced Stats Matchup Breakdown** inspired by Parker Fleming's (`@statsowar`) unit-vs-unit college football preview cards. Provide deep, comparative sports analytics for every FBS game on the slate, accessible via a dedicated route `/matchup/[gameId]` and directly linked from each game card on `/` (Picks) and `/results` (Results).

---

## Current State

- Game cards on `/` and `/results` show high-level market vs model lines and Top 25 team ranks, but contain a generic `Matchup Profile →` link pointing to the individual team rating page (`/teams/[team]`).
- The team page (`/teams/[team]`) only displays historical V5 rating progression and a flat list of prior/upcoming games.
- There is no head-to-head unit-vs-unit comparison (e.g. Alabama Offense vs Mississippi State Defense) analyzing efficiency, Eckel rate (scoring opportunities), points per opportunity (finishing drives), field position, or down-specific success.

---

## Proposed Approach

### 1. Matchup Statistics Engine (`web/src/lib/matchup.ts`)
Build a type-safe calculation and query module that produces the complete matchup profile for any FBS game:
- **Win Probability & Projected Score**:
  - `winProbHome = normalCdf(predictedSpread / (predictedSpreadStdDev || 13.5))`
  - `winProbAway = 1 - winProbHome`
  - `projHome = (predictedTotal + predictedSpread) / 2`
  - `projAway = (predictedTotal - predictedSpread) / 2`
- **Team-Level Efficiency Profiles**:
  - `epaMargin` (Net, Offense, Defense) + National Rank (1..134)
  - `offSuccessRate` (Overall, Dropback, Rush) + National Rank
  - `defSuccessRate` (Overall, Dropback, Rush) + National Rank
  - `netPtsPerDrive` (Net, Offense, Defense) + National Rank
  - `netFieldPosition` + National Rank
  - `eckelRatio` + National Rank
- **Unit-vs-Unit Showdown Metrics**:
  - Two symmetrical matchups:
    1. Away Offense vs Home Defense (`AWAY OFF VS HOME DEF`)
    2. Away Defense vs Home Offense (`AWAY DEF VS HOME OFF`)
  - Metrics: `EPA/Rush`, `EPA/Dropback`, `Eckel Rate` (quality drives inside 40), `Pts/Eckel` (points per scoring opportunity), `Field Position`, `DROE` (Dropback rate over expected / explosiveness), `Early Downs EPA`, `Late Down Conversion`.
  - Color-coded national rank pills: Elite Top 25 (Accent/Blue), Mid-tier (Slate), Low 90+ (Coral/Red).

### 2. Matchup UI Components (`web/src/components/matchup/`)
- `MatchupHero.tsx`: Team logos, national power ranks, win probabilities, projected points, kickoff metadata, and market vs model odds.
- `UnitMatchupTable.tsx`: Symmetrical head-to-head table (`Away Value | Away Rank | Metric Name | Home Rank | Home Value`) with visual metric center alignment.
- `TeamProfilePillars.tsx`: Flanking statistical pillars for both teams detailing EPA margin, success rates, net points/drive, and field position.
- `MatchupKeyTakeaways.tsx`: Automated analytical insights identifying the primary statistical edges and stylistic contrasts.

### 3. Dedicated Route (`web/src/app/matchup/[gameId]/page.tsx`)
- Server component that fetches game data by `gameId` using existing queries, computes matchup analytics, and renders the rich 3-column desktop layout (responsive stacked layout on mobile).
- Includes breadcrumb navigation back to the originating slate (`Picks` or `Results`).

### 4. Direct Navigation from Game Cards
- Update the `Matchup Profile →` link on `GameRow.tsx` from `/teams/[team]` to `/matchup/${game.gameId}`.

---

## Scope

### Included
- `web/src/lib/matchup.ts` (Matchup analytics engine & queries)
- `web/src/lib/matchup.test.ts` (Unit tests for matchup calculations)
- `web/src/components/matchup/MatchupHero.tsx`
- `web/src/components/matchup/UnitMatchupTable.tsx`
- `web/src/components/matchup/TeamProfilePillars.tsx`
- `web/src/components/matchup/MatchupKeyTakeaways.tsx`
- `web/src/app/matchup/[gameId]/page.tsx`
- `web/src/components/GameRow.tsx` (Route link update)

### Excluded
- Database schema migrations (derives from existing `games`, `predictions`, `v5_rating_snapshots`, `game_results`).
- Play-by-play raw SQL ingest (serves from certified V5 snapshot calibrations and game states).

---

## Implementation Tasks

### Task 1 — Matchup Engine (`web/src/lib/matchup.ts`)
Implement `getMatchupData(gameId: number, season?: number)`:
- Fetches game, predictions, and team ratings from Neon Postgres.
- Computes win probabilities, projected scores, unit-vs-unit metrics, and national ranks.
- Add test fixture support in `CFB_UI_TEST_MODE=1`.

### Task 2 — Matchup UI Components
Build responsive, accessible React components in `web/src/components/matchup/`:
- `MatchupHero`
- `UnitMatchupTable`
- `TeamProfilePillars`
- `MatchupKeyTakeaways`

### Task 3 — Matchup Page Route (`web/src/app/matchup/[gameId]/page.tsx`)
Create the Next.js server page with metadata, breadcrumb navigation, and responsive grid layout.

### Task 4 — GameRow Navigation Link
Update `GameRow.tsx` to link `Matchup Profile →` to `/matchup/${game.gameId}`.

### Task 5 — Validation Suite
- Typecheck, unit tests, linter, production build, and live browser verification.

---

## Definition of Done

- [x] `web/src/lib/matchup.ts` implemented with unit tests in `web/src/lib/matchup.test.ts`.
- [x] Matchup UI components created in `web/src/components/matchup/`.
- [x] Dedicated route `/matchup/[gameId]` renders full matchup breakdown.
- [x] `GameRow.tsx` links directly to `/matchup/${game.gameId}`.
- [x] `npm run typecheck`, `npm run test:publication`, `npm run lint`, and `npm run build` pass with 0 errors.
- [x] Plan status updated to `Implemented`.
