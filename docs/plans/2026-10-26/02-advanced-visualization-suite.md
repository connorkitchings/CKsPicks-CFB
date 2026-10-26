# Advanced Visualization Suite: Situational, Resume, Market, and Matchup Analytics

- **Status:** Implemented
- **Created:** 2026-10-26
- **Planner:** Sol
- **Approval source:** User explicit authorization (2026-10-26)
- **Implementation log:** `session_logs/2026-10-26/03-advanced-visualization-suite-implementation.md`
- **Commit policy:** Commit with implementation

## Goal and acceptance

Deliver five high-impact, experimental comparisons and visualizations to the Crest CFB site across the **Graphs (`/stats`)** and **Matchup (`/matchup/[gameId]`)** pages, leveraging existing release projection tables (`team_season_stats`, `team_resume`, `v5_rating_snapshots`, `predictions`, and `games`).

### Observable Success Criteria
1. **Situational Football (`chart=downs`):** Under `/stats` (Teams group), a scatter plot of **Early Down EPA** ($x$) vs. **3rd/4th Down Conversion Rate** ($y$) with offensive and defensive role toggles, quadrant annotations ("Unstoppable Engine", "On-Schedule Only", "Cardiac / Big-Play", "Struggling"), conference filtering, and team highlighting.
2. **Finishing Drives (`chart=finishing-drives`):** Under `/stats` (Teams group), a scatter plot of **Scoring Opportunity Rate** ($x$) vs. **Points per Scoring Opportunity** ($y$) with offensive and defensive toggles, quadrant labels ("Lethal Finishers", "Stall at the 30", "Opportunistic / Big-Play", "Empty Drives"), conference filtering, and team highlighting.
3. **Resume vs. Dominance (`chart=resume-quality`):** Under `/stats` (Teams group), a scatter plot comparing **V5 Rating Dominance** ($x$) vs. **Strength of Record (SOR)** ($y$), highlighting "Championship Contenders", "Unlucky Giants", and "Smoke & Mirrors / Overachievers".
4. **Slate Market Board (`chart=market-board`):** Under `/stats` (Games group), a scatter plot comparing **Market Spread / Total** ($x$) vs. **Model Forecast** ($y$) with a $y = x$ consensus diagonal, highlighting game edges ($\ge 3.0$ pts) across the weekly FBS slate.
5. **Head-to-Head 5 Factors Tape:** On `/matchup/[gameId]`, a rich, aesthetic bi-directional comparison component visualising the Five Core Factors (Overall Efficiency, Explosiveness, Finishing Drives, 3rd/4th Down Conversions, Turnover Margin) between opposing units.
6. **No Breaking Changes:** Existing charts (`net-success`, `efficiency`, `adjusted`, `possession`, `game-log`) and existing URL query parameters remain 100% functional; PNG export continues to work for all chart kinds.
7. **Verification:** `npm --prefix web run lint`, `npm --prefix web run typecheck`, `npm --prefix web run test:publication`, `npm --prefix web run build`, and `make check` all pass cleanly.

---

## Baseline and constraints

- **Branch / Worktree:** Branch `dev` (clean worktree at commit `7c9b7ddd`).
- **Data Lake & Storage:** Strictly read-only against the active release in Neon Postgres through Drizzle with ISR. Zero database migrations or pipeline modifications are needed—all required tables (`season_release_team_season_stats`, `season_release_team_resume`, `season_release_v5_rating_snapshots`, `season_release_games`, `season_release_predictions`) already exist in Migration 0025/0028.
- **Fixture Support:** `CFB_UI_TEST_MODE=1` must support every new chart with robust test fixtures in `web/src/test/fixtures/charts.ts` to allow hermetic Playwright and unit tests.
- **Mobile First & UI Rhythm:** Every new view must integrate with `MobileStickyBar`, `SETTINGS_SLOT_ID`, and respect `PHONE_PAGE_RHYTHM`.

---

## Ordered changes

### Task 1: Data Queries & Specs (`web/src/lib/chart-queries.ts`, `web/src/lib/charts.ts`)
- In `web/src/lib/chart-queries.ts`:
  - Add `getTeamSeasonStats(season: number, asOfWeek?: number)` loader to query `season_release_team_season_stats` (`metric`, `value`, `rank`, `cohort_size`).
  - Add `getTeamResume(season: number, periodId?: string)` loader to query `season_release_team_resume` (`sor`, `sor_rank`, `sos_played_elite`, `overall_rank`, `wins`, `losses`).
  - Add `getSlateMarketComparison(season: number, week: number)` loader to query paired `games` and `predictions` (market spread/total vs. predicted margin/total).
  - Add typed row specifications and guard functions (`guardRows`) matching database contracts.
- In `web/src/lib/charts.ts`:
  - Add types: `DownsScatterPoint`, `FinishingDrivesScatterPoint`, `ResumeScatterPoint`, `MarketBoardGamePoint`.
  - Add transformation pure functions mapping raw rows to scatter coordinates and metadata.

### Task 2: Chart Registry & Metadata Configuration (`web/src/lib/chart-config.ts`)
- In `web/src/lib/chart-config.ts`:
  - Expand `ChartKind` union: `'downs' | 'finishing-drives' | 'resume-quality' | 'market-board'`.
  - Define `CHART_REGISTRY` entries with titles, picker tab labels, descriptions, footnotes, and quadrant labels:
    - `downs`: group `'teams'`, controls `{ side: true, week: 'through-week', team: true }`.
    - `finishing-drives`: group `'teams'`, controls `{ side: true, week: 'through-week', team: true }`.
    - `resume-quality`: group `'teams'`, controls `{ side: false, week: 'through-week', team: true }`.
    - `market-board`: group `'games'`, controls `{ side: false, week: 'week', team: false }`.
  - Add export filename and title formatting for each new kind.

### Task 3: Scatter & Slate Board View Components (`web/src/components/charts/`)
- Adapt existing reusable `ScatterView` and `ScatterChart` to support the new metrics and quadrant configs:
  - Add `DownsView.tsx` (wrapping `ScatterView` for standard vs. passing downs).
  - Add `FinishingDrivesView.tsx` (wrapping `ScatterView` for red-zone / scoring opps).
  - Add `ResumeQualityView.tsx` (wrapping `ScatterView` for SOR vs. V5 rating).
  - Create `MarketBoardView.tsx` and `MarketBoardChart.tsx`: A specialized slate scatter plotting Market vs. Model with $y = x$ consensus diagonal, edge highlight color coding, and game detail hover tooltips.

### Task 4: Matchup "Tale of the Tape" Component (`web/src/components/matchup/`)
- Create `TaleOfTheTape.tsx`:
  - Visual divergent bar comparison contrasting Offense vs. Opposing Defense across the 5 Core Factors.
  - Interactive percentile pill badges, team primary color bars, and differential edge summaries.
  - Mount cleanly on `/matchup/[gameId]` below the primary game summary and above detailed unit tables.

### Task 5: Stats Page Integration & Test Fixtures (`web/src/app/stats/page.tsx`, `web/src/test/fixtures/`)
- In `web/src/app/stats/page.tsx`:
  - Connect loaders for new kinds in `load()`.
  - Render appropriate view based on `kind`.
- In `web/src/test/fixtures/charts.ts`:
  - Add deterministic test fixtures for `team_season_stats`, `team_resume`, and market comparisons.
  - Ensure fixture mode (`CFB_UI_TEST_MODE=1`) returns comprehensive mock data.

### Task 6: Unit & Publication Testing (`web/src/test/`)
- Add comprehensive unit tests verifying data transformations, quadrant allocations, and URL parameter round-tripping.
- Update `npm --prefix web run test:publication` and Playwright tests to cover all new views.

---

## Validation

1. **Static Analysis & Linting:**
   - `npm --prefix web run lint`
   - `npm --prefix web run typecheck`
   - `uv run ruff check .`
2. **Unit & Publication Suite:**
   - `npm --prefix web run test:publication`
   - `uv run pytest tests/`
   - `make contracts-check quality-check`
3. **Production Build & Rendering:**
   - `npm --prefix web run build`
   - Test rendering under `CFB_UI_TEST_MODE=1` across desktop and mobile screen dimensions.
4. **Export Integrity:**
   - Verify PNG export button generates valid download payloads for each new chart kind.

---

## Handoff / amendments

This plan is an exploratory expansion contract. Upon user approval, implement in order:
1. Data queries & pure transforms
2. Chart config & quadrant registries
3. Stats page scatter integrations
4. Matchup Tale of the Tape
5. Fixtures, tests, and build verification
