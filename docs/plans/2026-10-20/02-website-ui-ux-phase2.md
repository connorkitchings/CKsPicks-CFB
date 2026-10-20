# Website UI/UX Phase 2: BetCell Hierarchy, Conference Filters, Ratings Rank Badges & Collapsible Matchup Sections

- **Status:** Implemented
- **Created:** 2026-10-20
- **Planner:** Sol
- **Approval source:** Explicit owner Terra handoff in chat on 2026-10-20 (`Use the repository-local implement-plan skill and implement the approved contract at: docs/plans/2026-10-20/02-website-ui-ux-phase2.md`)
- **Implementation log:** `session_logs/2026-10-20/04-website-ui-ux-phase2-implementation.md`
- **Commit policy:** Commit with implementation (or separate plan commit if preferred); land web commits only when no `run_season.py prepare` candidate is awaiting `run_season.py release`

## Goal and acceptance

Complete the remaining approved items from the October 20 Website UI/UX review ("After that" scope): condense the `PredictionGameCard` `BetCell` hierarchy so picks scan faster and take less vertical space on phones, add conference filtering (`All FBS`, `Power Four + Notre Dame`, and individual FBS conferences) to `/ratings`, `/`, and `/results`, apply semantic rank-tier badges to national and résumé ranks on `/ratings`, and make secondary stat sections (`Situational / down and distance` and `Drive context`) collapsible and row-synchronized across unit matchup tables on `/matchup/[gameId]`.

Implementation is complete only when every acceptance criterion and validation check below passes:

1. **`BetCell` Hierarchy Condensation (WS3):**
   - In `web/src/components/slate/PredictionGameCard.tsx`, each `BetCell` places its target label (`Spread` / `Total`) and right-aligned context badge (`<ResultBadge>` / `Ungraded` on Results; sportsbook `lean.source` on Picks) on the top header row (`justify-between`).
   - On Picks (`results === false`), promoting `lean.source` (`DraftKings`, `Bovada`, `FanDuel`, etc.) into the top-right header row eliminates the 4th text line in `BetCell`, reducing vertical card height while keeping the pick (`[data-pick]`), `Model: <number>`, and `(+<edge>)` clearly separated.
   - On Results (`results === true`), `<ResultBadge>` remains in the top-right header row and `[lean.source, cover].filter(Boolean).join(" · ")` remains as the compact bottom caption.
   - All existing assertions in `web/e2e/publication.spec.ts` and `web/e2e/mobile-slate.spec.ts` (including 360px no-clip checks on `[data-pick]` and 390×844 first-card clearance above `SiteNav`) pass.
2. **Conference Filter on `/ratings`, `/`, and `/results` (WS3 & WS5):**
   - A shared conference-matching helper resolves CFBD team names and game-name aliases (`"Appalachian State"` ↔ `"App State"`, `"Southern Mississippi"` ↔ `"Southern Miss"`, etc.) against `RosterRow[]` (`team_season_roster`), supporting `"all"` (`All FBS`), `"p4"` (`Power Four + Notre Dame`), and each conference in `conferenceOptions(roster)`.
   - On `/ratings` (`RatingsView.tsx`), a Conference `<select>` (`data-testid="conference-filter"`, `aria-label="Filter by conference"`) filters displayed rows **after** `sosRanks` and `ranked` are computed so national ranks (`#`, `SOR`, `SOS Played/Remaining/Full`) are preserved when filtering by conference, and persists `conf=` across rating period links when non-default.
   - On `/` (`PicksSlate.tsx`) and `/results` (`ResultsSlate.tsx`), `SlateToolbar.tsx` renders a Conference `<select>` (`data-testid="conference-filter"`, `aria-label="Filter by conference"`) when `roster` is non-empty; a game matches when either `awayTeam` or `homeTeam` belongs to the selected conference group.
   - Mobile first-card clearance on `/` and `/results` at `390×844` (with and without the 34px bottom safe-area inset in `web/e2e/mobile-slate.spec.ts`) and desktop toolbar control max-height (`<= 40px` in `web/e2e/desktop-layout.spec.ts`) pass.
3. **Rank-Tier Badges on `/ratings` (WS5):**
   - `RatingsView.tsx` uses `getRankBadgeClass(rank, cohortSize)` from `web/src/lib/team-stats.ts` to render semantic tier badges (`top` 20%, `high` next 25%, `mid` next 30%, `low` bottom 25%) on the national rank `#` column and the `SOR`, `SOS Played`, `SOS Remaining`, and `SOS Full` rank cells on desktop and mobile cards.
   - Preserves exact cell text (`#1`, `#2`, `—`) and `title` attributes (`"SOR 81.2"`, `"SOS Played 52.6"`, etc.) asserted by `web/e2e/ratings.spec.ts`, and does not introduce WAA, `±SD` uncertainty, or raw SOS numbers into cell text.
4. **Collapsible Secondary Matchup Sections (WS4):**
   - In `web/src/components/matchup/UnitMatchups.tsx` and `web/src/components/matchup/UnitMatchupTable.tsx`, `"Core possession efficiency"` remains always open, while `"Situational / down and distance"` and `"Drive context"` section headers render interactive toggle buttons (`aria-expanded="true"` by default) inside `<th scope="rowgroup" colSpan={3}>`.
   - Section collapse state is owned by `UnitMatchups.tsx` and shared by both `<UnitMatchupTable>` panels so collapsing or expanding a section on desktop (`lg+`) updates both side-by-side tables simultaneously and preserves horizontal row alignment (`expect(ra).toEqual(rb)` in `web/e2e/matchup.spec.ts`).
   - Preserves `UnitMatchupTable.tsx` DOM structure (`<table>`'s immediate preceding sibling `div` remains the unit header with two `img[data-logo]` elements) and centered `<th scope="rowgroup">` text geometry (`web/e2e/matchup.spec.ts` and `web/e2e/desktop-layout.spec.ts`).

## Baseline and constraints

- **Inspected branch and commit:** `dev` at `ddb08414` (`feat(web): unify app shell, fix surface-elevated & color-scheme tokens, and add hero books & 52.4% benchmark`), clean working tree.
- **Active releases:** `production-season-2026-2cdf8916d915e21b3f25fa71` and `preview-season-2026-2cdf8916d915e21b3f25fa71` (`resume_v1` projection set, which includes `season_release_team_season_roster`; see `docs/status.md`).
- **Release coupling gate:** Do not commit on `dev`/`main` between `run_season.py prepare` and `run_season.py release` (`code_sha` pin check).
- **Product policy & scope exclusions:**
  - Do **not** add an edge-strength filter (`>= 3.0 pt` or "Strong Edges") anywhere on the site (`docs/modeling/betting_policy.md`).
  - Do **not** display raw SOR, raw SOS, WAA, or `±SD` uncertainty in `/ratings` cells (`5060aa60`).
  - Do **not** edit `TopLeans.tsx`, `StatCard.tsx`, `RecordBanner.tsx`, `HistoricalModelContext.tsx`, `EdgeNote.tsx`, or `ResultLeanRow.tsx`.
  - Keep `/charts` gated behind `CFB_CHARTS_ENABLED` (404 in Production when unset/`0`).

## Ordered changes

### Task 1 (WS3): `PredictionGameCard.tsx` `BetCell` hierarchy condensation

- **Affected components:**
  - `web/src/components/slate/PredictionGameCard.tsx`
- **Changes:**
  1. In `BetCell` (`web/src/components/slate/PredictionGameCard.tsx`):
     - Change the top header row to `mb-1 flex items-center justify-between gap-1.5 text-xs font-medium text-ink-muted`:
       - Left: `<span className="uppercase tracking-wider">{kind === "spread" ? "Spread" : "Total"}</span>`
       - Right: `{grade ? <ResultBadge grade={grade} /> : results ? <span>Ungraded</span> : lean?.source ? <span className="truncate text-ink-muted">{lean.source}</span> : null}`
     - Render the pick line as `<p data-pick className={clsx("break-words text-sm font-semibold leading-snug", results ? "text-ink" : "text-accent-ink")}>{lean.pick}</p>`.
     - Render the model and edge line as:
       ```tsx
       <p className="mt-0.5 flex flex-wrap items-baseline gap-x-1.5 text-xs tabular-nums text-ink-muted">
         <span>Model: <span className="font-mono font-medium text-ink">{modelNumber(lean)}</span></span>
         <span className={clsx("font-mono font-semibold", edgeTone(lean.edge, kind))}>(+{lean.edge.toFixed(1)})</span>
       </p>
       ```
     - Render the bottom caption `<p className="mt-0.5 text-xs text-ink-muted">{[lean.source, cover].filter(Boolean).join(" · ")}</p>` only when `results && (lean.source || cover)` so Picks cards do not repeat `lean.source` on a 4th line.
- **Acceptance criteria:**
  - Picks cards render at most 3 text rows per `BetCell` while still displaying the sportsbook source (`DraftKings`, `Bovada`, `FanDuel`), `data-pick`, `Model: <number>`, and `(+<edge>)`.
  - Results cards continue to show `<ResultBadge>` in the header row and `lean.source` / `cover` below the model line.
- **Focused validation:**
  - `PLAYWRIGHT_PORT=3105 npm --prefix web run test:ui -- e2e/publication.spec.ts e2e/mobile-slate.spec.ts`

### Task 2 (WS3 & WS5): Conference filter on `/ratings`, `/`, and `/results`

- **Affected components:**
  - `web/src/lib/charts.ts`
  - `web/src/test/fixtures/charts.ts`
  - `web/src/test/fixtures/ratings.ts`
  - `web/src/app/ratings/page.tsx`
  - `web/src/components/ratings/RatingsView.tsx`
  - `web/src/app/page.tsx`
  - `web/src/app/results/page.tsx`
  - `web/src/components/slate/SlateView.tsx`
  - `web/src/components/slate/PicksSlate.tsx`
  - `web/src/components/slate/ResultsSlate.tsx`
  - `web/src/components/slate/SlateToolbar.tsx`
- **Changes:**
  1. In `web/src/lib/charts.ts`:
     - Export a helper `buildConferenceMap(roster: readonly RosterRow[]): Map<string, string | null>` (using `withGameNameAliases` from `./rating-names.ts` so both `"App State"` and `"Appalachian State"`, `"Southern Miss"` and `"Southern Mississippi"`, etc. map to their conference) and `matchesTeamConference(filter: ConferenceFilter, team: string, conferenceMap: ReadonlyMap<string, string | null>): boolean`.
  2. In `web/src/test/fixtures/charts.ts`:
     - Ensure `chartsRosterFixture` includes conferences for the teams used in `slate.ts` and `ratings.ts` fixtures (`Western Kentucky` -> `"Conference USA"`, `Southern Miss` -> `"Sun Belt"`, `Wisconsin` -> `"Big Ten"`, `Washington` -> `"Big Ten"`, `USC` -> `"Big Ten"`, `Tennessee` -> `"SEC"`, `Florida State` -> `"ACC"`, `Oklahoma` -> `"SEC"`) without changing the 16 `PLAYING` teams used by `buildGameRows()` (or export `slateRosterFixture: RosterRow[]` in `web/src/test/fixtures/slate.ts` and `ratingsRosterFixture: RosterRow[]` in `web/src/test/fixtures/ratings.ts` so `chartsRosterFixture` stays 100% untouched!). **Decision: Export dedicated `ratingsRosterFixture` in `web/src/test/fixtures/ratings.ts` and `slateRosterFixture` in `web/src/test/fixtures/slate.ts` so `chartsRosterFixture` and all `/charts` tests remain completely untouched.**
  3. On `/ratings` (`web/src/app/ratings/page.tsx` and `web/src/components/ratings/RatingsView.tsx`):
     - In `ratings/page.tsx`, accept `conf?: string` in `searchParams`, load `roster` (`ratingsRosterFixture` in `CFB_UI_TEST_MODE=1`, or `await getTeamSeasonRoster(season).catch(() => null) ?? []` in production), and pass `roster` and `initialConference={params.conf ?? "all"}` to `RatingsView`.
     - In `RatingsView.tsx`, add `conference` state (`useState<ConferenceFilter>(initialConference)`), include `conf` in `periodHref` when `conference !== "all"`, filter `visible` by `matchesTeamConference(conference, rating.team, conferenceMap)` alongside search query, and render `<select id="rating-conference" data-testid="conference-filter" aria-label="Filter by conference">` (`All FBS`, `Power Four + Notre Dame`, and `conferenceOptions(roster)`) in the search/filter bar with `min-h-11 sm:min-h-9` height.
  4. On `/` and `/results` (`page.tsx`, `results/page.tsx`, `SlateView.tsx`, `PicksSlate.tsx`, `ResultsSlate.tsx`, `SlateToolbar.tsx`):
     - Load `roster` (`slateRosterFixture` in `CFB_UI_TEST_MODE=1` when `publicationMode === "predictions"`, or `await getTeamSeasonRoster(season).catch(() => null) ?? []` in production) and pass `roster` through `SlateView` to `PicksSlate` and `ResultsSlate`.
     - In `SlateToolbar.tsx`, accept optional `conference?: ConferenceFilter`, `onConferenceChange?: (value: ConferenceFilter) => void`, and `conferences?: readonly string[]`. When `conferences && conferences.length > 0 && onConferenceChange`, render `<select id="slate-conference" data-testid="conference-filter" aria-label="Filter by conference">` (`All FBS`, `Power Four + Notre Dame`, and `conferences`).
     - Keep all `SlateToolbar` controls on a single row on 390px phones (`flex-nowrap sm:flex-wrap` or compact flex bases `flex-[1_1_6.5rem]`) so `SlateToolbar` height does not wrap to a second line on 390×844 phones and `mobile-slate.spec.ts` passes with full clearance.
- **Acceptance criteria:**
  - Filtering by conference on `/ratings` narrows visible rows while preserving each team's national rank (`#`, `SOR`, `SOS Played/Remaining/Full`).
  - Filtering by conference on `/` and `/results` narrows games to those where either `awayTeam` or `homeTeam` matches the selected conference group.
  - `mobile-slate.spec.ts`, `desktop-layout.spec.ts`, `ratings.spec.ts`, and `publication.spec.ts` pass.
- **Focused validation:**
  - `PLAYWRIGHT_PORT=3105 npm --prefix web run test:ui -- e2e/ratings.spec.ts e2e/mobile-slate.spec.ts e2e/desktop-layout.spec.ts e2e/publication.spec.ts`

### Task 3 (WS5): Rank-tier badges on `/ratings`

- **Affected components:**
  - `web/src/components/ratings/RatingsView.tsx`
- **Changes:**
  1. In `web/src/components/ratings/RatingsView.tsx`:
     - Import `getRankBadgeClass` from `@/lib/team-stats`.
     - Add a `RankPill` presenter component:
       ```tsx
       function RankPill({ rank, cohort }: { rank: number | null | undefined; cohort: number }) {
         const valid = isNumber(rank) ? rank : null;
         if (valid === null) return <>{DASH}</>;
         return (
           <span
             data-rank-tier
             className={clsx(
               "inline-flex h-5 min-w-5 items-center justify-center rounded px-1 font-mono text-xs tabular-nums",
               getRankBadgeClass(valid, cohort),
             )}
           >
             {rankText(valid)}
           </span>
         );
       }
       ```
     - In the desktop table (`<tbody>`), use `getRankBadgeClass(position, ratings.length)` on a pill inside the `#` cell, and render `<RankPill rank={...} cohort={ratings.length} />` inside the `SOR`, `SOS Played`, `SOS Remaining`, and `SOS Full` `<td>` cells (preserving `title={valueTitle(...)}` on the `<td>` and plain `—` when unranked).
     - On mobile cards (`<ul aria-label="Team ratings list">`), apply `getRankBadgeClass(position, ratings.length)` to the `<span aria-label={`National rank ${position}`}>` badge.
- **Acceptance criteria:**
  - Desktop and mobile `/ratings` rank cells render semantic tier styling (`getRankBadgeClass`) while preserving exact text (`#1`, `#2`, `—`) and `title` attributes asserted in `web/e2e/ratings.spec.ts`.
- **Focused validation:**
  - `PLAYWRIGHT_PORT=3105 npm --prefix web run test:ui -- e2e/ratings.spec.ts`

### Task 4 (WS4): Collapsible secondary sections in `UnitMatchups.tsx` & `UnitMatchupTable.tsx`

- **Affected components:**
  - `web/src/components/matchup/UnitMatchups.tsx`
  - `web/src/components/matchup/UnitMatchupTable.tsx`
- **Changes:**
  1. In `web/src/components/matchup/UnitMatchups.tsx`:
     - Add `const [collapsedSections, setCollapsedSections] = useState<ReadonlySet<MetricSection>>(() => new Set());`.
     - Create `toggleSection(section: MetricSection)` that toggles membership of `"situational"` or `"drive"` in `collapsedSections`.
     - Pass `collapsedSections` and `onToggleSection={toggleSection}` to both `<UnitMatchupTable>` components.
  2. In `web/src/components/matchup/UnitMatchupTable.tsx`:
     - Accept optional `collapsedSections?: ReadonlySet<MetricSection>` and `onToggleSection?: (section: MetricSection) => void`.
     - For `"situational"` and `"drive"` sections (`group.section !== "possession"`), when `onToggleSection` is provided, render an interactive button inside `<th scope="rowgroup" colSpan={3} className="pt-3 text-center align-bottom text-xs font-semibold uppercase tracking-wider text-ink-muted">`:
       ```tsx
       <button
         type="button"
         aria-expanded={!isCollapsed}
         onClick={() => onToggleSection(group.section)}
         className="inline-flex items-center justify-center gap-1 rounded px-1.5 py-0.5 text-xs font-semibold uppercase tracking-wider text-ink-muted hover:bg-surface-inset hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
       >
         <span>{group.label}</span>
         <span aria-hidden="true" className="text-[10px] leading-none">{isCollapsed ? "▸" : "▾"}</span>
       </button>
       ```
     - Wait: verify `web/e2e/matchup.spec.ts` line 44 (`table.locator("th[scope='rowgroup']", { hasText: label })`):
       - Because the `<button>` is an `inline-flex` child inside a `text-center` `colSpan={3}` `<th>`, `range.selectNodeContents(header).getBoundingClientRect()` centers across the full table width (`Math.abs(textBox.x + textBox.width / 2 - (tableBox.x + tableBox.width / 2)) < 4`).
     - When `!isCollapsed`, render `group.rows.map(...)` as before; when `isCollapsed` is true, omit the metric rows for that section in both tables simultaneously.
- **Acceptance criteria:**
  - All 3 sections start expanded on initial load (12 metric rows per table), preserving all existing `web/e2e/matchup.spec.ts` assertions.
  - Clicking `"Situational / down and distance"` or `"Drive context"` collapses that section in both side-by-side desktop tables simultaneously (`aria-expanded="false"`, row alignment `ra.toEqual(rb)` preserved) and clicking again re-expands it (`aria-expanded="true"`, 12 rows).
- **Focused validation:**
  - `PLAYWRIGHT_PORT=3105 npm --prefix web run test:ui -- e2e/matchup.spec.ts e2e/desktop-layout.spec.ts`

## Validation

Run all checks below before marking the contract `Implemented`:

1. **Repository & Documentation Gates:**
   - `make contracts-check`
   - `uv run mkdocs build --quiet`
   - `git diff --check`
2. **Web Static, Unit & Production Build Gates (`web/`):**
   - `npm --prefix web run lint`
   - `npm --prefix web run typecheck`
   - `npm --prefix web run test:publication`
   - `npm --prefix web run test:charts-gate`
3. **Playwright E2E Suites:**
   - `PLAYWRIGHT_PORT=3105 npm --prefix web run test:ui -- e2e/mobile-slate.spec.ts e2e/desktop-layout.spec.ts e2e/matchup.spec.ts e2e/performance.spec.ts e2e/publication.spec.ts e2e/ratings.spec.ts`
   - Add E2E assertions in:
     - `web/e2e/ratings.spec.ts`: Conference filter narrows rows while preserving national `#`, `SOR`, and `SOS` ranks; rank-tier badges (`[data-rank-tier]`) render on ranked cells.
     - `web/e2e/publication.spec.ts`: Conference filter on `/` and `/results` narrows games by team conference and resets cleanly to `All FBS`.
     - `web/e2e/matchup.spec.ts`: Clicking `"Situational / down and distance"` and `"Drive context"` section headers collapses/expands their rows across both tables while keeping desktop row tops aligned.

## Handoff/amendments

- **Approval and resume gate:** `Draft` awaiting owner approval or explicit Terra execution authorization for `docs/plans/2026-10-20/02-website-ui-ux-phase2.md`.
- **Release coupling reminder:** Do not commit on `dev`/`main` while a `run_season.py prepare` candidate is awaiting `run_season.py release`.
- **User-controlled commit policy:** Propose the commit message at closeout; the owner executes git operations manually.
- **Amendments:** None.
