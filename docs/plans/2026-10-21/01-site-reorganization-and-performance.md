# Site reorganization, design consistency and performance (web)

- **Status:** Implemented (published to Production with the `dev` to `main` release of 2026-10-25; review log `session_logs/2026-10-25/01-final-site-review.md`)
- **Created:** 2026-10-21
- **Planner:** Sol
- **Approval source:** Owner approval of the plan in the 2026-10-21 planning session
- **Implementation log:** Stats publication log (`session_logs/2026-10-21/04-stats-publication-implementation-log.md`); session log `session_logs/2026-10-21/01-site-reorganization-and-performance.md`
- **Commit policy:** Commit with implementation; one worktree branch off `dev` per phase; nothing lands while a prepared release candidate is waiting for `run_season.py release`

## Goal and acceptance

Adding Charts takes the phone bottom bar from 4 to 5 tabs, which is too crowded at 390px. Stabilize the site before Charts goes public: speed, organization, appearance and readability.

Owner decisions:

- **4 tabs:** Games (Picks and Results merged; renamed from Matchups by the owner on 2026-10-21) · Ratings · Stats (Charts renamed) · Model (Performance and Methodology merged).
- **Model:** a written explainer of how V5 works plus the record. No pipeline change; publishing bridge coefficients is a later, separate contract.
- **In scope:** a shared Card and Notice design system, links to the existing unlinked `/teams/[team]` pages, and Stats publication (still gated by the owner flipping the Vercel variable).
- **Not in scope:** moving the rating trajectory chart to Ratings.

Done when every phase passes its checks (see Validation), the speed targets in Phase 1 are measured on Preview, and the redirect, layout and real-data checks pass.

## Baseline and constraints

Inspected on `dev` at `c18241c6`, Next 16.2.10.

- **No cross-request caching.** Every main route reads `searchParams`, so `revalidate = 300` has no effect. Loaders use only React `cache()`. Each request first runs 3 serial release-lookup queries (`web/src/lib/season-release-context.ts`). `/` runs about 15–18 queries (10–12 serial); `/matchup/[gameId]` about 15 serial. Duplicates and loops: `getScoredWeeks` runs twice; `getBiggestEdgesRecord` queries once per week (N+1); completed games → venues → frozen lines run one after another (`web/src/lib/queries.ts`).
- **Chart math ships to Picks, Results and Ratings** via conference helpers imported from `web/src/lib/charts.ts` (about 38K).
- **Logos download twice:** each renders as a light and a dark `<img>`, both eager. `/ratings` renders about 552 images (`TeamLogo.tsx`).
- **Oversized payloads:** `/ratings` sends 27-field rating objects (a 64-character hash on each of 138 rows); `/performance` sends every graded game; the efficiency chart sends about 1.5k rows to plot about 136 points.
- **Content rendered twice:** `ResponsiveDisclosure` renders children twice (duplicate `id="calibration-heading"`, `TopLeans` sort runs 4 times).
- **Inconsistent styling:** about 65 inline card variants with mixed radius and shadow; 3 places that pick page width; root `loading.tsx` is slate-shaped for every route.
- **Bugs:** the empty-state button is unreadable (`bg-accent` + `text-accent-ink`, `SlateView.tsx:147`); raw `<a>` tags cause full reloads (`SlateView.tsx:145,151`); `StatCard.tsx` is unused.

## Ordered changes

### Phase 1: Performance (no visible change)

1. **Measure first.** Query logger via `CFB_QUERY_LOG=1` (`web/src/lib/db.ts`); `MODE=start` in `scripts/ops/run_web_local.sh`; new `web/scripts/measure-routes.mjs` (time to first byte, cold and warm, median and p90, against local or Preview URLs). Record a baseline table in the implementation log: queries per route, TTFB, first-load JS from `.next/diagnostics/route-bundle-stats.json`, image requests on `/ratings`.
2. **Release-keyed data cache** (`web/src/lib/release-cache.ts`). `releaseCached(name, load)` wraps loaders in `unstable_cache`, keyed by deployment ID, environment, `releaseId`, `chartSet` and arguments, tagged `release:<id>`, never expiring. A codec preserves `Date` and `Map`. Bypassed when `CFB_UI_TEST_MODE=1`, when `CFB_DATA_CACHE=0` (kill switch) and for legacy requests with no release. `"use cache"`/`cacheComponents` are rejected. Wrap release-scoped loaders in `queries.ts`, `v5.ts`, `chart-queries.ts`, the team résumé read and `matchup.ts`; leave `getHistoricalModelContext` uncached. **Gate:** first confirm in `src/cks_picks_cfb/season/` that `prediction_runs` rows read through releases are never updated after activation (legacy `score_to_db.py`, `freeze_week.py`, `publish_to_db.py` do update that table). If immutability isn't proven, add run state to the cache key or cap entries at 1 hour.
3. **Active-release pointer.** `unstable_cache` with `revalidate: 60`, tag `release-pointer`. The per-request resolver still pins one release per request. Collapse `loadReleaseContext` into one query (Postgres `42P01` → `null`; fold the missing-projections check into the main SELECT); update `season-release.test.ts`. `/api/revalidate` also expires `release-pointer`.
4. **Query shape.** Parallelize `getGamesForWeek` sub-queries; batch frozen-lines lookups in `getBiggestEdgesRecord` and start it in parallel with the slate on `/`; wrap `getScoredWeeks` in `cache()`; add `getV5PerformanceSplit(season, week)` returning `{ before, week }` in one query; parallelize independent lookups in `getMatchupData`.
5. **Bundle, DOM and bug fixes.** Move conference helpers to `web/src/lib/conferences.ts` (re-exported from `charts.ts`); move `BREAK_EVEN_PCT` to `lib/betting-format.ts`; `TeamLogo` gets `loading="lazy" decoding="async"` plus a `priority` prop for `MatchupHero`; `ResponsiveDisclosure` renders children once (desktop forced open via `::details-content` under `@supports`); slim `RatingRow` for `RatingsView`; aggregate efficiency chart points on the server; fix the `SlateView` button (new `--accent-solid` / `--on-accent-solid` tokens and `Link`); delete `StatCard.tsx`; add `web/public/logos/v2.staging` to `.gitignore`.
6. **Targets.** Warm `/`: 0 database queries. After the pointer expires: 1 query. `/`, `/ratings`, `/model` ship no `lib/charts.ts` code. Measure again after steps 2 and 5, then on a Vercel Preview (0 warm queries; a Preview activation appears within 60s).

### Phase 2: Design system (no URL changes)

- New primitives in `web/src/components/ui/`: `Card` (single radius/border/shadow, `data-card`), `Notice` (info, warn, error, empty), `SectionHeading`/`Eyebrow` (`PageHeading` gains `eyebrow`), `ButtonLink` (primary, secondary), `Skeleton` (built from `Card`).
- Page width in one place: `web/src/lib/page-width.ts` (`slate` 6xl / `wide` 5xl / `narrow` 4xl, `pageWidthFor(pathname)`) plus `PageShell` (Header + `<main>` + Footer). `SiteNav` and `Header` use it; remove duplicated width logic.
- `globals.css` dark-mode glow selector becomes `html.dark [data-card]`.
- Replace inline card markup mechanically across about 27 files (chart internals excepted); replace the 4 hand-written notice cards with `Notice`.
- Root `loading.tsx` uses the Games shape inside `PageShell`; add `app/ratings/loading.tsx`.

### Phase 3: Reorganization (one commit)

**Navigation** (`SiteNav.tsx`): Games `/` (also `/matchup/*`) · Ratings `/ratings` (also `/teams/*`) · Stats `/stats` · Model `/model`. Phone bar `grid-cols-4`, or 3 while Stats is gated off. The flag keeps the name `CFB_CHARTS_ENABLED`.

**Redirects** (307 first; a follow-up commit moves to 308 after a week of owner acceptance):

| Old | New | Where |
|---|---|---|
| `/results?…` | `/?…` | `next.config.ts` |
| `/matchup` (index only) | `/?…` | `next.config.ts` |
| `/performance` | `/model` | `next.config.ts` |
| `/methodology` | `/model/method` (`#elite-reference` preserved) | `next.config.ts` |
| `/charts…` | `/stats…`, or 404 when the flag is off | `proxy.ts` |

`proxy.ts` matcher adds `/stats` and `/stats/:path*`. `app/charts` becomes `app/stats`; `chartHref` and `WeekNav` point to `/stats`.

**Games (`/`):** one week view across all weeks. `app/page.tsx` drops the scored-week redirect and upcoming-only filter; weeks = every available week plus the active week; default = requested week, else active week. `lib/slate-page.ts` drops `view`. `lib/slate.ts` adds `weekPhase(games)` (`upcoming` | `in-progress` | `final`) and a unified `SlateSort` (result sorts only when phase isn't `upcoming`). `SlateView`: heading "Week N" plus phase chip; `ModelRecord` shows season record before Week N plus the week's record once any game is graded, linking to `/model`; highlights: upcoming → `TopLeans`, in-progress → `TopLeans` + `ResultHighlights`, final → `ResultHighlights`. Cards choose per game (`PredictionGameCard results={isFinal(game)}`, same for market card). New `SlateList` replaces `PicksSlate` and `ResultsSlate`; merge `ResultGameRow` into `SlateGameRow`. Delete `app/results/`, `app/matchup/page.tsx`, `lib/matchup-index.ts` (and test) if unused. `MatchupHero` back link becomes "← Week N games" → `/?week=N`. Add fixture `slatePartial`.

**Model:** `/model` = current performance dashboard in `PageShell` plus `ModelTabs` ("Record" | "How it works"), data from the release cache. `/model/method` = static prerendered page: current `/methodology` sections (keep `id="elite-reference"`) plus new sections drawn only from `docs/modeling/v5_status.md` and `record_methodology.md` (points-per-possession ratings, learned prior ρ=0.60, exposure-weighted updates, uncertainty and intervals, Ridge bridge to spread and total, grading incl. pushes and the 52.4% break-even); no numbers not in those docs; `max-w-prose`. Delete `app/methodology/` and `app/performance/`. `RatingsView` link → `/model/method#elite-reference`. Update "Results tab" wording in `PerformanceDashboard`.

**Team pages:** add `teamHref()` in `lib/teams.ts`; link team names from Ratings rows (phone and desktop), `MatchupHero` names and a matchup-footer link (slate cards get no team link). `/teams/[team]`: `PageShell`, `generateMetadata`, correct name mapping (`ratingName()` for history, CFBD name for games; verify the ~9 legacy-name teams such as "San Jose State", "Hawai_i"), `notFound()` for unknown names.

**Skeletons:** per-route `loading.tsx` for `/stats`, `/model`, `/matchup/[gameId]`, `/teams/[team]`, each in `PageShell` at its own width.

**Docs in the same commit:** `docs/status.md` live checks; `docs/ops/weekly_runbook.md` live checks (new routes, 307s) and optional post-deploy warm-up; `docs/plans/2026-10-20/03-charts-pre-publication.md` (`/charts` → `/stats`, five nav items → four); `docs/plans/index.md`; `AGENTS.md` (4-tab interface).

### Phase 4: Stats publication

Run tasks 2–6 of the Charts pre-publication plan against `/stats`, with the Phase 1 measurement script as the evidence for its task 5: recorded real-data review matrix, Preview review, edge states, speed measurements, publication and rollback runbook. Owner actions: set `CFB_CHARTS_ENABLED=1` on Vercel Preview, accept, then set it on Production and redeploy. Rollback: unset and redeploy.

## Validation

Each phase passes: `npm --prefix web run lint`, `typecheck`, `test:publication`, `build`, `test:ui`, `test:charts-gate`; `make contracts-check`; `uv run mkdocs build --strict`; `git diff --check`.

Test changes:

| File | Change |
|---|---|
| `e2e/charts-navigation.spec.ts` | Names Games/Ratings/Stats/Model; `goto("/charts…")` in `e2e/charts*.spec.ts` → `/stats` |
| `e2e-charts-gate/charts-disabled.spec.ts` | 3 equal-width tabs at 390px; `/stats` and `/charts` both 404 with query strings |
| `e2e/publication.spec.ts`, `e2e/mobile-slate.spec.ts` | Merged week view: graded cards on a final week, leans on upcoming, an in-progress case |
| `e2e/desktop-layout.spec.ts` | `/` and `/stats` 1152; `/ratings`, `/model`, `/model/method`, `/matchup/1` 1024; team pages 896 |
| `e2e/matchup.spec.ts` | Team link present on Ratings and matchup pages, absent on slate cards; `/matchup?week=5` → `/?week=5` |
| `e2e/ratings.spec.ts`, `e2e/performance.spec.ts` | New Model URLs; no duplicate IDs |
| `e2e/logos.spec.ts` | Assert lazy loading |
| New `e2e/redirects.spec.ts` | Every redirect row, query preserved |
| Unit (`test:publication`) | `release-cache.test.ts` (codec round-trip, key contents, bypass under test mode and kill switch, no-release uncached); `season-release.test.ts` (single query, `42P01`); `weekPhase`/`sortSlate`; performance split |

Speed: before/after tables in the implementation log from `MODE=start CFB_QUERY_LOG=1 make web-local ENV=preview` and `node web/scripts/measure-routes.mjs <url>`, local and Vercel Preview. Real-data check on Preview: merged Games view on the current week (upcoming), Week 7 (final) and a Saturday in progress; every redirect; legacy-name team pages; light and dark at 390px and 1280px.

## Handoff/amendments

Risks:

- **Stale cache if release rows change after activation.** Mitigated by the immutability check and the `CFB_DATA_CACHE=0` kill switch.
- **Activations appear up to about 60s late.** Accepted; the signed `/api/revalidate` makes one appear immediately.
- **Every deploy starts with an empty cache** (key includes deployment ID).
- **Vercel's ~2 MB per cache entry limit.** The codec warns above 1.5 MB; split performance detail by week if close.
- **Bookmarks.** 307 first, 308 after acceptance; `/results?week=N` keeps its exact meaning.
- **Site domain.** `layout.tsx` uses `ckspicks-cfb.vercel.app` but the runbook checks `c-ks-picks-cfb.vercel.app`; confirm canonical before switching to 308.

Next action: implement Phase 1 in worktree branch off `dev`. Record amendments here with reason, previous approach, revised approach and impact.
