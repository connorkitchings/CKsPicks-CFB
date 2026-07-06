# CK's Picks — Web App

Next.js 16 / React 19 / Tailwind CSS v4 app that displays the model's weekly leans for every FBS game. Deployed to Vercel; reads predictions from Neon Postgres.

## Stack

- **Framework:** Next.js 16 (App Router, TypeScript)
- **DB:** Neon Postgres serverless, accessed via `@neondatabase/serverless` + Drizzle ORM
- **Styling:** Tailwind CSS v4
- **Logos:** Synced from `../Logos/` into `public/logos/` on every `predev` / `prebuild`

## Local Development

```bash
# 1. Copy env template and fill in your Neon connection string
cp .env.example .env
#   then edit .env:
#   DATABASE_URL=postgres://user:password@ep-xxx.region.aws.neon.tech/dbname?sslmode=require

# 2. Apply the schema migration (one-time)
psql "$DATABASE_URL" -f db/migrations/0001_init.sql

# 3. Install deps + run dev server
npm install
npm run dev
```

Open http://localhost:3000.

> The dev server will start even without `DATABASE_URL` — the home page will render a friendly "Database not connected" banner instead of crashing.

## Scripts

| Command | Description |
|---|---|
| `npm run dev` | Start dev server (with logo sync) |
| `npm run build` | Production build (with logo sync) |
| `npm run start` | Run the production build locally |
| `npm run lint` | ESLint |
| `npm run typecheck` | TypeScript typecheck (no emit) |
| `npm run db:migrate` | Apply `0001_init.sql` to `$DATABASE_URL` |
| `npm run db:generate` | Regenerate Drizzle migration from `schema.ts` |
| `npm run db:studio` | Open Drizzle Studio (DB browser) |

## Project Structure

```
web/
├── db/
│   └── migrations/
│       └── 0001_init.sql    # Schema (apply once to Neon)
├── drizzle.config.json
├── public/
│   └── logos/               # Auto-synced from ../Logos/ on build
├── scripts/
│   └── sync-logos.mjs       # predev/prebuild hook
└── src/
    ├── app/
    │   ├── layout.tsx        # Root layout, metadata
    │   ├── page.tsx          # Home: current-week dashboard
    │   ├── globals.css
    │   └── api/health/route.ts  # Health endpoint
    ├── components/
    │   ├── Header.tsx        # Header + Footer
    │   ├── GameRow.tsx       # Per-game row with leans
    │   ├── LeanBadge.tsx     # Spread + total visual chips
    │   └── RecordBanner.tsx  # YTD spread/total record
    └── lib/
        ├── db.ts             # Drizzle client (lazy, build-safe)
        ├── schema.ts         # Drizzle schema (mirrors 0001_init.sql)
        ├── queries.ts        # getCurrentWeek / getGamesForWeek / etc.
        └── teams.ts          # Team-name → logo URL mapping
```

## Deploying to Vercel

1. Push the repo to GitHub.
2. Import the project at https://vercel.com/new.
3. **Set Root Directory to `web/`** (Vercel will detect Next.js automatically).
4. Add `DATABASE_URL` to Environment Variables (Vercel → Project → Settings → Environment Variables).
5. Deploy. Subsequent `git push` to `main` auto-deploys.

The home page is ISR-cached with a 5-minute revalidation window, so new predictions published by the Python pipeline appear within ~5 minutes on the live site.

## Data Flow

```
Python pipeline                 Neon Postgres                Vercel
─────────────                   ─────────────                ──────
generate_weekly_bets.py   →     games table           →     page.tsx (ISR 5m)
publish_to_db.py          →     current_week table    →     RecordBanner
score_to_db.py            →     game_results,         →     (after games finish)
                                 system_stats
```

See `../docs/ops/weekly_pipeline.md` for the full weekly workflow.
