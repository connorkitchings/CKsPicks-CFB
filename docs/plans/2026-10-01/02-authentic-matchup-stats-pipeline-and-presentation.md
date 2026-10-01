# Authentic Matchup Stats: Pipeline Ingestion, Neon Schema, and Presentation

- **Status:** Draft
- **Created:** 2026-10-01
- **Planner:** Sol
- **Approval source:** Pending User Review
- **Implementation log:** Pending Terra Implementation
- **Commit policy:** Commit with implementation

## Goal

Provide authentic, football-accurate unit and team metrics on the `/matchup/[gameId]` page by:
1. Extracting verified season-to-date football measurements from the repository's play-by-play data lake (`byplay` and `drives` parquet files in R2) or certified CFBD team aggregates.
2. Ingesting these metrics into a canonical Neon Postgres table (`team_season_stats`) via an append-only migration (`0019_team_season_stats.sql`) and automated publisher (`scripts/pipeline/publish_team_stats.py`).
3. Presenting intuitive, high-signal metrics (Passing/Rushing EPA, Scoring Opportunities, Finishing Drives, Field Position, Explosiveness, Down Efficiencies) with authentic national ranks and percentiles.
4. Ensuring zero simulated, synthetic, or unverified statistical attributes exist anywhere in the application.

---

## Current State

1. **Web App Matchup Page (`/matchup/[gameId]`):**
   - The user requested Option C: all synthetic stats have been stripped.
   - Deep links from `GameRow.tsx` (Picks and Results tabs) have been removed so users cannot land on incomplete or empty placeholder cards.
   - The Matchup Hero displays only 100% genuine data:
     - Market lines (Spread & Total)
     - Model predictions (Spread, Total, and Model Leans)
     - Blitzkrieg V5 Certified Team Ratings & National Ranks (Overall, Offense, Defense)
     - Final Game Scores (for settled games)
   - A clear "Ingestion In Progress" section communicates what authentic metrics will be added.

2. **Data Pipeline & Measurements:**
   - In `src/cks_picks_cfb/ratings/observations.py` and `data_first_phase3_v2.py`, our pipeline already defines canonical measurements on the CFBD play stream:
     - `epa_pass` / `epa_rush` (Predicted Points Added on pass/rush scrimmage plays)
     - `success_rate`
     - `explosive_rate_20` (plays with 20+ yards gained)
     - `points_per_scoring_opportunity` (true drive points on scoring opportunities inside opponent 40)
     - `average_start_field_position` (start yards to goal)
     - `turnover_rate`
   - These metrics currently reside in Python dataframes and R2 parquet artifacts, but are not yet synced to Neon Postgres for web serving.

3. **Database Architecture:**
   - Neon Postgres currently stores `games`, `game_results`, `predictions`, `prediction_runs`, `site_week_selections`, and `v5_rating_snapshots`.
   - Migration chain is at `0018_create_cfb_ops_schema.py`.
   - `contracts/schema.sql` and `web/src/lib/schema.ts` represent the dual-stack contract.

---

## Proposed Approach

### 1. Selected Metrics (Clear Football Terminology)

Rather than esoteric jargon (e.g., Parker Fleming's DROE or Eckel Rate), we adopt 8 intuitive, standard football metrics:

| Metric Name | Unit Role | Calculation / Formula | Football Meaning |
|---|---|---|---|
| **Passing EPA/play** | Offense & Defense | Total passing PPA / pass attempts | Efficiency and explosiveness through the air |
| **Rushing EPA/play** | Offense & Defense | Total rushing PPA / rush attempts | Down-to-down ground game efficiency |
| **Scoring Opp Rate** | Offense & Defense | Drives reaching opponent 40 / total drives | Ability to create quality scoring chances |
| **Pts / Scoring Opp** | Offense & Defense | Points scored on drives reaching 40 / scoring opp drives | Red zone / finishing efficiency (touchdowns vs FGs/turnovers) |
| **Avg Start Field Pos** | Offense & Defense | Average starting yardline (e.g. Own 31.5) | Special teams impact and hidden yardage |
| **Explosive Play Rate** | Offense & Defense | % of plays gaining 20+ yards | Big-play generation / prevention |
| **Early Downs EPA** | Offense & Defense | PPA on 1st & 2nd downs | Staying on schedule before late-down pressure |
| **3rd/4th Down Conv %** | Offense & Defense | 3rd & 4th down conversions / attempts | Situational execution to sustain or stall drives |

### 2. Database Schema: `team_season_stats`

Add a migration `0019_team_season_stats.sql` and Python migration entry in `scripts/pipeline/migrate_db.py`:

```sql
CREATE TABLE team_season_stats (
    season INTEGER NOT NULL,
    as_of_week INTEGER NOT NULL,
    cutoff_utc TIMESTAMPTZ NOT NULL,
    team TEXT NOT NULL,
    -- Offense Metrics
    off_epa_pass DOUBLE PRECISION NOT NULL,
    off_epa_rush DOUBLE PRECISION NOT NULL,
    off_scoring_opp_rate DOUBLE PRECISION NOT NULL,
    off_pts_per_scoring_opp DOUBLE PRECISION NOT NULL,
    off_avg_start_field_pos DOUBLE PRECISION NOT NULL,
    off_explosive_rate DOUBLE PRECISION NOT NULL,
    off_early_down_epa DOUBLE PRECISION NOT NULL,
    off_late_down_conv_rate DOUBLE PRECISION NOT NULL,
    -- Defense Metrics
    def_epa_pass DOUBLE PRECISION NOT NULL,
    def_epa_rush DOUBLE PRECISION NOT NULL,
    def_scoring_opp_rate DOUBLE PRECISION NOT NULL,
    def_pts_per_scoring_opp DOUBLE PRECISION NOT NULL,
    def_avg_start_field_pos DOUBLE PRECISION NOT NULL,
    def_explosive_rate DOUBLE PRECISION NOT NULL,
    def_early_down_epa DOUBLE PRECISION NOT NULL,
    def_late_down_conv_rate DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (season, as_of_week, team)
);

CREATE INDEX idx_team_season_stats_lookup ON team_season_stats (season, as_of_week);
```

### 3. Ingestion & Publishing Pipeline

Create `scripts/pipeline/publish_team_stats.py`:
- Aggregates season-to-date play-by-play data through the target week cutoff.
- Handles FBS team naming reconciliation via `contracts/teams.py`.
- Computes raw values and national rankings (1 to 134) across all FBS teams.
- Upserts records to `team_season_stats` in Neon Postgres using atomic transactions (`ON CONFLICT (season, as_of_week, team) DO UPDATE`).
- Can run locally or in CI/weekly operating cadence.

### 4. Web Serving Layer & UI Presentation

1. **`web/src/lib/matchup.ts`**:
   - Query `team_season_stats` for `(season, as_of_week)` matching the game's point in time.
   - Compute national rankings and rank badges dynamically across the active season cohort.
   - Populate `awayOffVsHomeDef` and `homeOffVsAwayDef` with authentic rows.
2. **`web/src/components/matchup/UnitMatchupTable.tsx`**:
   - Layout: **Offense on the left**, **Defense on the right** with team logos above unit headers.
   - Display metric name, Offense value + rank badge, Defense value + rank badge.
3. **Re-link deep link in `web/src/components/GameRow.tsx`**:
   - Once data is verified in Neon, restore the `Matchup Breakdown →` deep link on Picks and Results game cards.

---

## Scope

### Included
- Creation of `0019_team_season_stats` migration in `scripts/pipeline/migrate_db.py`, `contracts/schema.sql`, and `web/src/lib/schema.ts`.
- Implementation of `scripts/pipeline/publish_team_stats.py` to extract from CFBD / R2 play lake and upsert to Neon.
- TypeScript data access layer in `web/src/lib/matchup.ts` reading authentic rows.
- Reintegration of `UnitMatchupTable` into `web/src/app/matchup/[gameId]/page.tsx`.
- Safe restoration of deep links in `web/src/components/GameRow.tsx`.
- Test coverage for statistical rankings, sign orientation (lower is better for defense vs higher is better for offense), and edge cases.

### Excluded
- Re-introduction of win probability calculations without an authorized empirical calibration contract.
- Point-margin score projections that simply split the market total by predicted spread without separate offensive scoring model approval.
- Modifying the core Blitzkrieg V5 ratings lineage or Hydrated model configurations.

---

## Affected Components and Contracts

- `contracts/schema.sql` & `contracts/schema.ts`: Schema contract updates.
- `web/src/lib/schema.ts`: Drizzle ORM definition.
- `scripts/pipeline/migrate_db.py`: Migration 0019 definition.
- `scripts/pipeline/publish_team_stats.py`: New ingestion script.
- `web/src/lib/matchup.ts`: Data query and ranking computation.
- `web/src/components/matchup/UnitMatchupTable.tsx`: UI table presentation.
- `web/src/app/matchup/[gameId]/page.tsx`: Page integration.
- `web/src/components/GameRow.tsx`: Re-enabling deep links after validation.

---

## Implementation Tasks

### Task 1 — Schema Contract & Migration 0019
**Files:**
- `contracts/schema.sql`
- `contracts/schema.ts`
- `web/src/lib/schema.ts`
- `scripts/pipeline/migrate_db.py`

**Changes:**
- Define `team_season_stats` table with comprehensive unit fields.
- Add migration `0019` to `migrate_db.py`.
- Validate with `make contracts-check` or Nx schema check.

**Acceptance criteria:**
- Schema files are in complete sync across Python, TypeScript, and SQL.
- Migration runs idempotently.

---

### Task 2 — Pipeline Extraction & Ingestion Script
**Files:**
- `scripts/pipeline/publish_team_stats.py`
- `tests/test_publish_team_stats.py`

**Changes:**
- Build aggregation query over play/drive records up to week cutoff.
- Calculate all 8 offensive and defensive metrics.
- Reconcile team names with `canonical_team_name()`.
- Upsert rows into `team_season_stats` in Neon.

**Acceptance criteria:**
- Outputs valid rows for all 134 FBS teams for the target season and week.
- No nulls in key metrics.
- Idempotent execution.

---

### Task 3 — Web Data Fetching & Ranking Engine
**Files:**
- `web/src/lib/matchup.ts`
- `web/src/lib/matchup.test.ts`

**Changes:**
- Update `getMatchupData(gameId)` to query `team_season_stats`.
- Compute ranks (1–134) with proper sort direction:
  - Higher is better for offense (EPA, scoring opp rate, PPSO, explosive rate, early down EPA, conversion rate).
  - Lower is better for defense (EPA allowed, scoring opp rate allowed, PPSO allowed, explosive rate allowed, conversion rate allowed).
- Return populated `awayOffVsHomeDef` and `homeOffVsAwayDef` lists.

**Acceptance criteria:**
- Unit test validates that team ranks correctly invert for defense (rank 1 = lowest EPA allowed).
- Missing team data gracefully falls back to empty or unranked indicators without crashing.

---

### Task 4 — UI Table Assembly & Deep Link Restoration
**Files:**
- `web/src/components/matchup/UnitMatchupTable.tsx`
- `web/src/app/matchup/[gameId]/page.tsx`
- `web/src/components/GameRow.tsx`

**Changes:**
- Re-embed `UnitMatchupTable` inside `page.tsx`.
- Wire `MatchupHero` and unit tables with real data.
- Restore the `Matchup Breakdown →` link on `GameRow.tsx` cards.

**Acceptance criteria:**
- `/matchup/[gameId]` displays real data for both units.
- Clicking deep link from Picks or Results smoothly navigates to the matchup card.

---

## Testing Strategy

- `python -m pytest tests/test_publish_team_stats.py`: Verify statistical calculation and schema adherence.
- `npm run test:publication` in `web/`: Validate ranking logic, sign inversions, and null safety.
- `npm run typecheck`: Ensure zero TypeScript errors across all modified components.
- Browser test via subagent: Visually verify table headers, rank badges, and mobile responsiveness.

---

## Risks and Edge Cases

- **Early Season Sample Size (Weeks 0–3):** Small sample sizes can create extreme outlier EPA or 100% conversion rates. Rank badges should handle ties cleanly.
- **FCS Opponents:** Scrimmage plays vs FCS opponents should follow CFBD / repo filtering standards to avoid skewing FBS rates.
- **Fail-Closed State:** If `team_season_stats` has not been published yet for a future week, the page must gracefully show the ratings-only view instead of crashing.

---

## Definition of Done

- [ ] Migration 0019 applied to Neon.
- [ ] Pipeline publisher script executed and verified in Neon database.
- [ ] Web data layer queries real database records with zero synthetic fallback.
- [ ] Unit-vs-Unit table renders authentic data on `/matchup/[gameId]`.
- [ ] Matchup deep links re-enabled on Picks and Results cards.
- [ ] All tests and TypeScript checks pass.
- [ ] Plan status updated to `Implemented`.
