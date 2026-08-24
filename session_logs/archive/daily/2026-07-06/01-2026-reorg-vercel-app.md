# Session: 2026 Repo Reorg → Vercel Picks App

## TL;DR
- **Worked On:** Reorg/refactor of the monorepo to add a Next.js web app (Vercel) that displays model leans for every FBS game, fed by Neon Postgres.
- **Completed:** All 5 phases (cleanup, DB layer, Next.js app, UI, docs). Python pipeline untouched and fully backward-compatible.
- **Blockers:** None — Neon account creation is the only remaining external step (user-side).
- **Next:** Create Neon project, set `DATABASE_URL`, run `web/db/migrations/0001_init.sql`, then `make db-publish YEAR=2025 WEEK=14` to validate end-to-end. Then connect Vercel.

## Changes Made

### Phase A — Repo cleanup & scaffolding
- **Removed stray root files:** `data_pipeline.log` (488KB), `resume_processed.py`, `scripts/repro_issue.py`, `.reorganization_preserve/` (1.5MB)
- **Archived:** `dashboard/monitoring.py` → `archive/dashboard_v1/`; `templates/email_weekly_picks_v{1,2}.html` + `email_last_week_review.html` → `archive/templates/`; `REFACTORING_PLAN.md` + `REFACTORING_STATUS.md` → `docs/history/`
- **Scaffolded `web/`:** Next.js 16.2.10, React 19.2.4, TypeScript, Tailwind v4, ESLint (via `create-next-app` non-interactive)
- **Added web deps:** `@neondatabase/serverless`, `drizzle-orm`, `drizzle-kit`, `clsx`, `dotenv`
- **pyproject.toml:** added `psycopg[binary]>=3.2`; added `web` to pytest `norecursedirs`

### Phase B — Database layer
- **`web/db/migrations/0001_init.sql`** — schema for `games`, `game_results`, `system_stats`, `current_week` + enums + indexes + views
- **`web/src/lib/schema.ts`** — Drizzle ORM types mirroring the SQL
- **`web/src/lib/db.ts`** — lazy-initialized Neon client (Proxy pattern; build-safe without `DATABASE_URL`)
- **`web/src/lib/queries.ts`** — `getCurrentWeek`, `getGamesForWeek`, `getSystemStats`, `getRecentHighConfidenceGames`
- **`scripts/pipeline/publish_to_db.py`** — reads predictions CSV, derives leans/edges, upserts to Postgres, updates `current_week`
- **`scripts/pipeline/score_to_db.py`** — backfills `game_results`, recomputes `system_stats`
- **`tests/test_publish_to_db.py`** — 15 unit tests (no DB required); all pass

### Phase C/D — Next.js app
- **`web/src/app/page.tsx`** — server component; ISR (5-min revalidate); graceful DB-not-connected state
- **`web/src/app/layout.tsx`** — metadata
- **`web/src/app/api/health/route.ts`** — health endpoint (`/api/health`)
- **Components:** `Header.tsx` (+ Footer), `RecordBanner.tsx`, `GameRow.tsx`, `LeanBadge.tsx` (+ TotalLeanChip)
- **`web/src/lib/teams.ts`** — `TEAM_LOGO_MAP` + `logoUrl()` (mirrors Python map)
- **`web/scripts/sync-logos.mjs`** — predev/prebuild hook copies 338 logos from `../Logos/` to `public/logos/`

### Phase E — Docs & Makefile
- **`AGENTS.md`** — new "Dual-Stack Architecture (2026)" section + updated Quick Facts
- **`README.md`** — new deliverable description, structure, commands
- **`Makefile`** — `web-dev`, `web-build`, `web-lint`, `web-typecheck`, `db-publish YEAR=... WEEK=...`, `db-score YEAR=...`
- **`docs/ops/weekly_pipeline.md`** — full data-flow diagram + weekly workflow + backfill recipe
- **`web/README.md`** — local-dev guide + project structure + Vercel deploy steps

## Testing
- [x] Python: 187 tests pass (`PYTHONPATH=.:src pytest tests/ -q`); +15 new publish_to_db tests
- [x] Python: `ruff format` clean; `ruff check` clean on all touched files (11 pre-existing errors in `scripts/research/test_mlp.py` are unrelated)
- [x] Web: `npm run lint` clean, `tsc --noEmit` clean, `npm run build` succeeds (ISR 5m on `/`, dynamic on `/api/health`)
- [x] End-to-end: parsed real `data/production/predictions/2025/CFB_week14_bets.csv` → 67 games, 39 home leans, 28 away leans, 23 high-confidence
- [ ] Live DB integration — pending Neon account creation (user)

## How to Activate (when user has Neon)

```bash
# 1. Create Neon project at https://console.neon.tech, copy DATABASE_URL
# 2. Apply schema
psql "$DATABASE_URL" -f web/db/migrations/0001_init.sql

# 3. Backfill 2025 history (predictions + results)
make db-score YEAR=2025   # runs score_to_db --backfill-season
for WEEK in 10 11 12 13 14; do
    make db-publish YEAR=2025 WEEK=$WEEK
done
# Reset current_week to latest:
PYTHONPATH=.:src uv run python scripts/pipeline/publish_to_db.py --year 2025 --week 14

# 4. Local dev
cd web && cp .env.example .env  # paste DATABASE_URL
npm run dev

# 5. Deploy
# Vercel → import repo → set Root Directory to web/ → add DATABASE_URL env → deploy
```

## Notes for Next Session

- **Neon setup complete (2026-07-06):** Project `CK's Picks - CFB` (`red-cloud-34959964`) in Neon org `Connor-Kitchings-Projects` (`org-cool-bread-04623514`). `.neon` context file committed at repo root. DATABASE_URL populated in root `.env` and `web/.env` via `neonctl env pull`.
- **2025 data backfilled:** All 2025 prediction weeks (weeks 2-16, 746 games total) published to Neon. YTD record computed through week 15: spread 359-383-3, total 311-266-6. Current week set to 2025 week 14.
- **End-to-end verified:** `npm run build` + `npm run start` → homepage renders 67 games for week 14 with team names, logos, leans, predicted spreads/totals, high-confidence flags, and YTD record banner. `/api/health` returns `{"status":"ok","games":746}`.
- **Model status unchanged:** V2 Champion still at break-even (2025: spread ~-8% ROI, total ~+2% ROI). The web app displays this transparently via the YTD record banner + "display only — not betting advice" footer.
- **2026 season prep (separate task):** before Week 1, the model needs fresh 2026 data ingestion and a retrain decision (reuse `linear_spread_target.joblib` / `linear_total_target.joblib` vs retrain). The web app is agnostic to which model produced the CSV.
- **Email publisher preserved:** `scripts/pipeline/publish_picks.py` still works (uses `templates/email_weekly_picks_v3.html`). Can be deprecated later once the web app is the primary channel.
- **Performance note:** Neon serverless cold starts can add ~500ms latency on first request; mitigated by ISR (5-min revalidate) + Vercel edge caching.
- **Logo normalization sync:** `TEAM_LOGO_MAP` is now in 3 places (`publish_picks.py`, `publish_to_db.py`, `web/src/lib/teams.ts`) — flagged in AGENTS.md as a convention to keep in sync.

**tags:** ["reorg", "web-app", "nextjs", "neon", "postgres", "drizzle", "vercel", "2026-season"]
