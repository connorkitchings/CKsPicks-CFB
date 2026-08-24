# Session: Vercel Web App Polish (6 UX items)

## TL;DR
- **Worked On:** UX polish pass on the Next.js web app — week navigation, filter+sort, dark-mode toggle, real "Updated" timestamp, loading/error boundaries, programmatic branding (favicon + OG).
- **Completed:** All 6 selected items. Lint + typecheck + build all clean. Live `npm run start` smoke verified every new route and component renders against the real Neon DB (746 games).
- **Blockers:** None.
- **Next:** Eyeball in `npm run dev`; then wire up Vercel project (set `DATABASE_URL`, Root Directory → `web/`). Optionally tackle the `/about` methodology page (deferred this session). 2026 season model retrain decision still pending.

## Changes Made

### New files (7)
- **`web/src/components/ThemeToggle.tsx`** — light/dark/system cycle button using `useSyncExternalStore` (subscribes to localStorage); persists choice, falls back to `prefers-color-scheme` when unset.
- **`web/src/components/WeekNav.tsx`** — prev/next anchors + `<select>` dropdown over `getAvailableWeeks()`. URL-driven (`/?season=&week=`), shareable, ISR-cached per combination.
- **`web/src/components/GamesList.tsx`** — client wrapper around `<GameRow>` list with team search box, "High confidence" toggle, and sort select (kickoff / spread edge / total edge).
- **`web/src/app/loading.tsx`** — skeleton matching Header + RecordBanner + GameRow layout to prevent shift during ISR refresh.
- **`web/src/app/error.tsx`** — route error boundary with "Try again" `reset()` button; complements the inline amber banner (which still handles the expected "DATABASE_URL not set" first-deploy case).
- **`web/src/app/icon.tsx`** — 32×32 "CK" monogram favicon via `next/og` `ImageResponse` (brand-blue field, matches `LeanBadge` accent).
- **`web/src/app/opengraph-image.tsx`** — 1200×630 OG image with "CK's Picks" wordmark + tagline; surfaced via `openGraph`/`twitter` metadata.

### Modified files (5)
- **`web/src/app/globals.css`** — added `@custom-variant dark (&:where(.dark, .dark *));` so `dark:` utilities respond to a `.dark` class instead of `prefers-color-scheme`; scoped the dark CSS vars under `html.dark`.
- **`web/src/app/layout.tsx`** — inline pre-paint theme script (no FOUC; treats unset as "system"); mounted `<ThemeToggle>` (fixed bottom-right); expanded `metadata` with `openGraph`, `twitter`, `metadataBase`; added `viewport.themeColor`.
- **`web/src/app/page.tsx`** — converted to async server component reading `searchParams` (Next 16 Promise shape); resolves target week from URL or `getCurrentWeek()`; clamps out-of-range weeks to latest available; hands `<GameRow>` list to `<GamesList>`; surfaces real `updatedAt` (max of games' `updated_at`, fallback to `current_week.updated_at`) to Header.
- **`web/src/components/Header.tsx`** — replaced `generatedAt: Date` (server render time) with `updatedAt: Date | null`; label changed to "Predictions updated …".
- **`web/src/lib/queries.ts`** — added `getAvailableWeeks(season)` (`SELECT DISTINCT week`); surfaced `games.updated_at` in `getGamesForWeek` and `current_week.updated_at` in `getCurrentWeek`.

## Testing
- [x] Python: 187 tests pass (`PYTHONPATH=.:src uv run pytest tests/ -q`)
- [x] Python: `ruff format .` clean (155 files unchanged); `ruff check .` reports only 11 pre-existing errors in `scripts/research/test_mlp.py` (untouched, documented in 2026-07-06/02)
- [x] Web: `npm run lint` clean (after refactoring `ThemeToggle` to `useSyncExternalStore` to satisfy React 19's `react-hooks/set-state-in-effect` rule)
- [x] Web: `npm run typecheck` clean
- [x] Web: `npm run build` succeeds — routes: `/` (dynamic, ISR 5m), `/api/health` (dynamic), `/icon` + `/opengraph-image` (static PNG)
- [x] Live smoke (`npm run start`): `/api/health` → `{"status":"ok","games":746}`; `/icon` → valid 32×32 PNG; `/opengraph-image` → valid 1200×630 PNG; `/` renders Header + RecordBanner + WeekNav + GamesList with all controls and a real DB-backed "Predictions updated" timestamp

## Technical Details

### Why `useSyncExternalStore` in ThemeToggle
React 19's eslint-plugin-react-hooks introduced `react-hooks/set-state-in-effect`, which flags `setState` calls inside `useEffect` (cascading render risk). The classic "read localStorage in effect, setState on mount" pattern for theme toggles now lints as an error. `useSyncExternalStore` is the idiomatic replacement: it provides `getServerSnapshot` ("system" during SSR) and `getSnapshot` (reads `localStorage.theme` after hydration), avoiding both the lint error and hydration mismatches.

### Why URL-driven week nav over client state
Anchor-based navigation with `?season=&week=` query params keeps URLs shareable, lets ISR cache each combination independently, and avoids a client-side data fetcher. The cost is a full RSC refresh on each navigation — acceptable given the data only changes weekly.

### Why both inline banner AND `error.tsx`
They serve different purposes:
- **Inline amber banner** (`page.tsx`) handles the *expected* "DATABASE_URL not set" first-deploy state with setup instructions. Caught in try/catch.
- **`error.tsx`** is the safety net for *unexpected* runtime errors (render bugs, transient Neon failures that escape the catch). Provides a "Try again" button via Next's `reset()`.

### Why programmatic branding (no asset files)
`app/icon.tsx` and `app/opengraph-image.tsx` use `next/og`'s `ImageResponse` to render brand visuals at build time — no PNG/SVG checked into the repo, automatically regenerated when the design changes, and trivially themeable (single source of truth for the "CK" monogram + brand blue `#2563eb`). Trade-off: `next/og` uses default sans-serif (no Geist) since loading custom fonts at build time is heavyweight.

### Tailwind v4 dark mode mechanics
Adding `@custom-variant dark (&:where(.dark, .dark *));` switches the `dark:` variant from `prefers-color-scheme` to a `.dark` class on `<html>`. The inline pre-paint script in `layout.tsx` applies the class based on `localStorage.theme` (defaulting to "system" = `prefers-color-scheme`), so existing `prefers-color-scheme` users get the same behavior without setting anything, and explicit choices persist.

## Notes for Next Session

**Resume at:**
- Eyeball the UI in `npm run dev` (especially mobile widths and the fixed-position ThemeToggle not overlapping content)
- Then deploy: Vercel → import repo → Root Directory `web/` → set `DATABASE_URL` env → deploy

**Key context:**
- All 2025 data (weeks 2-16, 746 games) is in Neon from the prior session, so week nav has real content to browse immediately
- The `/about` methodology page was offered but not selected this session — easy follow-up
- Model retrain decision (currently `linear_{spread,total}_target.joblib` on 2019-2023 / 2024 holdout; could retrain on 2019-2025) is still open and independent of the web app

**Watch out for:**
- `ThemeToggle` is `position: fixed bottom-4 right-4` — may overlap the Footer's GitHub link on small viewports. If it does, restyle to inline in the Header instead.
- The `metadataBase` URL in `layout.tsx` is hard-coded to `https://ckspicks-cfb.vercel.app` — update if the production domain differs.
- OG image uses default sans-serif (not Geist); acceptable for v1 but could be upgraded by loading a font binary into `ImageResponse` later.
- The "Predictions updated" timestamp reads `MAX(games.updated_at)` for the current week — if a week is ever partially republished, this reflects the newest row, not the bulk load time.

**Next steps:**
1. User reviews UI in `npm run dev` and we iterate on any visual issues
2. Deploy to Vercel
3. (Optional) `/about` methodology page
4. (Separate track) 2026 model retrain decision before Week 1

**tags:** ["web-app", "nextjs", "polish", "ux", "dark-mode", "week-nav", "filter-sort", "branding", "og-image", "react-19"]
