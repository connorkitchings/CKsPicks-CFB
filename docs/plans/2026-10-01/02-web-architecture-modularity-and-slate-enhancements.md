# Plan: Frontend Modularity, Shared Slate Architecture & Comparative Utility

- **Status:** Implemented
- **Created:** 2026-10-01
- **Planner:** Sol
- **Approval source:** User explicit approval in session ("Document the plan and proceed")
- **Implementation log:** `session_logs/2026-10-01/05-slate-modularity-and-utility-implementation.md`
- **Commit policy:** Commit with implementation

---

## Goal

Elevate the modularity, maintainability, and comparative utility of the Next.js web application (`web/`) following the introduction of dedicated **Picks** (`/`), **Results** (`/results`), and **Performance** (`/performance`) pages. Specifically:
1. Eliminate redundant page orchestration and layout trees between `/` and `/results` by extracting a unified, reusable `<WeeklySlateView>` server component.
2. Reduce duplicated JSX and layout thrashing in `GameRow.tsx` by consolidating the desktop and mobile betting comparison tables into a responsive `<BetComparisonTable>` component.
3. Boost comparative sports-analytics utility by rendering certified V5 Power Ranks (`#1`, `#14`) directly beside team names on all game cards.
4. Group game cards in `GamesList.tsx` by game day (Thursday / Friday / Saturday) with market target filtering (`All Picks`, `Spreads`, `Totals`) to eliminate scroll fatigue across 50+ game slates.
5. Provide a standardized slot on `GameRow` for the upcoming Matchup Deep Dive (Phase 2).

---

## Current State

- **Page Duplication**: `web/src/app/page.tsx` and `web/src/app/results/page.tsx` share ~80% identical server-component code (resolving target season/week, querying games, querying performance banners, handling test mode, wrapping `Header`, `GamesList`, `Footer`).
- **Table Duplication**: `GameRow.tsx` renders two distinct instances of `BetTable` (one inside `hidden sm:block`, one inside `sm:hidden`), duplicating the cells, labels, edge calculations, and result badges.
- **Missing Comparative Context**: Game cards display season win-loss records (`2-1`), but do not display team power ranks (`#4 Alabama vs #2 Georgia`), even though certified V5 power ratings exist in `v5_rating_snapshots` in Postgres.
- **Scroll Fatigue on 56-Game Slates**: `GamesList.tsx` renders all games in a single flat vertical list. On a typical FBS week with 50–70 games, finding games across Thursday, Friday, and Saturday requires excessive scrolling.
- **Filter Asymmetry**: While `/performance` now has `[All Picks] [Spreads] [Totals]`, `/` and `/results` lack target filtering.

---

## Proposed Approach

### 1. Reusable `<WeeklySlateView>` Component
Extract a server component `web/src/components/WeeklySlateView.tsx` that manages the standard page shell, skip link, `Header`, `Footer`, optional banners (`V5PerformanceBanner`, retrospective notes), `WeekNav`, and `GamesList`.
Both `web/src/app/page.tsx` and `web/src/app/results/page.tsx` become thin server wrappers that resolve their respective target week (upcoming vs scored) and render `<WeeklySlateView mode="picks" | "results" ... />`.

### 2. Consolidated Responsive `<BetComparisonTable>` Component
Extract the desktop/mobile dual table in `GameRow.tsx` into a single, clean component `web/src/components/BetComparisonTable.tsx`. Use CSS grid/flexbox and responsive classes rather than dual rendering trees, reducing component bundle size and DOM nodes.

### 3. V5 Team Power Ranks on Game Cards
Provide a cached server helper `getTeamRankMap(season)` in `web/src/lib/v5.ts` that maps each team name to their integer power rank (`1` to `N`) derived from the active certified V5 ratings snapshot.
Pass `rankMap` into `WeeklySlateView` -> `GamesList` -> `GameRow` -> `TeamLine`. Teams in the Top 25 (or all ranked FBS teams) display a sleek `#N` badge next to their team name.

### 4. Day Grouping & Target Filtering in `GamesList.tsx`
Enhance `GamesList.tsx`:
- Group sorted games by date (`Thursday, Oct 3`, `Friday, Oct 4`, `Saturday, Oct 5`).
- Add target filter tabs: `[All Picks] [Spreads] [Totals]` so users focusing strictly on spread or over/under bets can filter their view instantly.
- Retain existing `High Confidence Only` toggle and team search.

### 5. Future-Proofing for Matchup Deep Dive (Phase 2)
Add a clear, accessible slot/button in `GameRow` (e.g. `[ Matchup Details → ]` or clickable matchup title) that currently links or prepares the card for the Parker Fleming `@statsowar` unit-vs-unit profile card in Phase 2.

---

## Scope

### Included
- `web/src/components/WeeklySlateView.tsx` (New component)
- `web/src/components/BetComparisonTable.tsx` (New component)
- `web/src/components/GameRow.tsx` (Consolidated table, team rank badge, deep dive slot)
- `web/src/components/GamesList.tsx` (Day grouping headers, target filtering)
- `web/src/lib/v5.ts` (Add `getTeamRankMap(season)` query helper)
- `web/src/app/page.tsx` (Refactor to use `WeeklySlateView`)
- `web/src/app/results/page.tsx` (Refactor to use `WeeklySlateView`)
- Associated unit tests in `web/src/lib/`

### Excluded
- Database schema changes (uses existing Postgres tables `v5_rating_snapshots`, `predictions`, `games`).
- Parker Fleming unit-vs-unit deep dive visual metrics (deferred to Phase 2).
- Python ML pipeline or model training modifications.

---

## Affected Components and Contracts

- `web/src/components/WeeklySlateView.tsx`: New component encapsulating the weekly slate page layout.
- `web/src/components/BetComparisonTable.tsx`: New component replacing duplicate mobile/desktop tables.
- `web/src/components/GameRow.tsx`: Uses `BetComparisonTable`, displays team rank pills.
- `web/src/components/GamesList.tsx`: Supports Day Grouping and Target Filtering.
- `web/src/lib/v5.ts`: Exports `getTeamRankMap(season: number): Promise<Map<string, number>>`.
- `web/src/app/page.tsx`: Delegates presentation to `WeeklySlateView`.
- `web/src/app/results/page.tsx`: Delegates presentation to `WeeklySlateView`.

---

## Implementation Tasks

### Task 1 — Add Cached Team Rank Query (`getTeamRankMap`)

**Files:**
- `web/src/lib/v5.ts`

**Changes:**
- Add `getTeamRankMap = cache(async (season: number): Promise<Map<string, number>>)` that reads the active/latest certified ratings from `getCurrentRatings(season)` and maps `team -> rank (1..134)`.

**Acceptance criteria:**
- Fast in-memory lookup (`O(1)` per team).
- Automatically updates whenever the active rating snapshot advances.

**Validation:**
- Unit test in `web/src/lib/performance.test.ts` or `ratings.test.ts`.

---

### Task 2 — Extract Responsive `<BetComparisonTable>`

**Files:**
- `web/src/components/BetComparisonTable.tsx` (New)
- `web/src/components/GameRow.tsx`

**Changes:**
- Build `BetComparisonTable` accepting market spread/total, model spread/total, model bets, results, and profit units.
- Replace duplicate desktop (`hidden sm:block`) and mobile (`sm:hidden`) table JSX blocks in `GameRow.tsx` with a single unified component.

**Acceptance criteria:**
- Matches existing visual styling exactly on both mobile viewports (<640px) and desktop viewports (>=640px).
- Zero duplicate DOM nodes rendered in HTML output.

**Validation:**
- Check rendering on desktop and mobile viewports; verify all 41 test assertions pass.

---

### Task 3 — Integrate Team Power Rank Badges in `GameRow`

**Files:**
- `web/src/components/GameRow.tsx`

**Changes:**
- Update `TeamLine` to accept `rank?: number | null`.
- Display `#N` badge (e.g. `#1`, `#24`) with styling `text-xs font-bold text-accent-ink mr-1.5` before the team name for teams ranked in the Top 25 (or unranked if >25).
- Add matchup deep-dive link/button stub ready for Phase 2.

**Acceptance criteria:**
- Top 25 teams display their V5 power rank.
- Unranked teams omit the rank badge without layout shift.
- Accessible ARIA labels (e.g. `aria-label="Rank 1 Oregon"`).

**Validation:**
- Local inspection at `http://localhost:3000` and `http://localhost:3000/results`.

---

### Task 4 — Add Day Grouping & Target Filter to `GamesList`

**Files:**
- `web/src/components/GamesList.tsx`

**Changes:**
- Add state `targetFilter: "all" | "spread" | "total"`.
- Add tab selector `[ All Picks ] [ Spreads ] [ Totals ]` in controls header.
- Group visible games chronologically by date (`Thursday, Oct 3`, `Friday, Oct 4`, `Saturday, Oct 5`).
- Render day divider headers with game counts (e.g. `Saturday, Oct 5 · 52 games`).

**Acceptance criteria:**
- Filtering by "Spreads" only displays games with active/graded spread picks.
- Filtering by "Totals" only displays games with active/graded total picks.
- Clear date section headers visually organize the 56-game slate.

**Validation:**
- Interactive testing on `http://localhost:3000` across all tabs and search inputs.

---

### Task 5 — Unify Slate Views with `<WeeklySlateView>`

**Files:**
- `web/src/components/WeeklySlateView.tsx` (New)
- `web/src/app/page.tsx`
- `web/src/app/results/page.tsx`

**Changes:**
- Create `WeeklySlateView` to encapsulate the shared page container, header, banners, `WeekNav`, and `GamesList`.
- Refactor `app/page.tsx` and `app/results/page.tsx` to call `WeeklySlateView`, passing `mode="picks"` and `mode="results"` respectively.

**Acceptance criteria:**
- `page.tsx` and `results/page.tsx` are compact (<50 lines each).
- Shared navigation, error handling, and container styles are unified in one place.

**Validation:**
- Next.js production build (`npm run build`) succeeds.
- Full test suite passes (`npm run test:publication`).

---

## Testing Strategy

1. **Unit & Fixture Tests**:
   - Verify `getTeamRankMap` returns correct ranks from fixture data.
   - Assert `SiteNav` continues to validate all 4 tabs (`Picks`, `Results`, `Ratings`, `Performance`).
2. **Visual & Browser Verification**:
   - Verify responsive behavior of `BetComparisonTable` on mobile (375px) and desktop (1280px).
   - Verify Day headers group games accurately based on game kickoff time in local timezone.
   - Verify Target filters (`All Picks`, `Spreads`, `Totals`) work seamlessly with High Confidence and Team Search.
3. **Contract Checks**:
   - Run `make contracts-check` to confirm zero contract regression.

---

## Risks and Edge Cases

- **Timezone Drift in Day Headers**: Kickoff times are UTC in Postgres. Grouping by day must format in user local time (`Intl.DateTimeFormat`) so a Friday night game doesn't appear under Saturday due to UTC offsets.
- **Unranked Teams**: Teams outside the top 25 should not display unsightly `#112` badges unless specifically requested; limiting the badge to Top 25 mirrors standard sports broadcasting conventions.
- **Test Mode Compatibility**: In `CFB_UI_TEST_MODE=1`, mock data should provide sensible ranks without throwing errors.

---

## Definition of Done

- [x] `getTeamRankMap` implemented and cached in `web/src/lib/v5.ts`.
- [x] `BetComparisonTable` extracted and deduplicated in `GameRow.tsx`.
- [x] Team rank badges (`#N`) rendered on all game cards.
- [x] Day grouping and target filters added to `GamesList.tsx`.
- [x] `WeeklySlateView` created and wired to `app/page.tsx` and `app/results/page.tsx`.
- [x] `npm run typecheck`, `npm run test:publication`, `npm run lint`, and `npm run build` pass with 0 errors.
- [x] Plan status updated to `Implemented`.
