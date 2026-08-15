# CK's Picks — Web App

Next.js 16 / React 19 / Tailwind CSS v4 app for the explicitly configured public release scope. It defaults to schedule and market lines; model output requires a separate server-side opt-in. Deployed to Vercel and backed by Neon Postgres.

## Stack

- **Framework:** Next.js 16 (App Router, TypeScript)
- **DB:** Neon Postgres serverless, accessed via `@neondatabase/serverless` + Drizzle ORM
- **Styling:** Tailwind CSS v4
- **Logos:** Synced from `../assets/logos/` into `public/logos/` on every `predev` / `prebuild`

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
| `npm run test:publication` | Verify the fail-closed public prediction boundary |
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
│   └── logos/               # Auto-synced from ../assets/logos/ on build
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
3. **Set Root Directory to `web/`**. Do not deploy from the repository root.
4. Add `DATABASE_URL` and the `CFB_PUBLICATION_*` release variables to Vercel Environment Variables.
5. Deploy. Subsequent `git push` to `main` auto-deploys.

The home page is ISR-cached with a 5-minute revalidation window, so newly published schedule, market, or approved prediction data appears within about five minutes.

## 2026 launch scope

The public site defaults to **2026 Week 0 only**. It is a server-side
allowlist, so URL parameters cannot reveal historical weeks or an unapproved
future slate. Configure these Vercel environment variables for a controlled
expansion after the next week has passed preview readiness:

```bash
CFB_PUBLICATION_SEASON=2026
CFB_PUBLICATION_WEEKS=0       # Week 0 launch
CFB_PUBLICATION_MODE=market   # Fail-closed default: no model output
# CFB_PUBLICATION_WEEKS=0,1   # Enable only after Week 1 approval
# CFB_PUBLICATION_MODE=predictions  # Requires explicit release approval
```

`market` mode uses a dedicated database projection containing only matchup,
kickoff, market-line, score, and freshness fields. It does not select or render
model predictions, leans, edges, confidence, regime, model identity, or the
prediction-derived record banner. Any value other than the exact string
`predictions` remains market-only.

Deploy previews from the repository root, where the Vercel project is linked;
the project's configured Root Directory remains `web`. The root
`.vercelignore` uploads only the web application, not pipeline artifacts or
local data. Preview deployments must use the isolated preview Neon database.

## Data Flow

```
Python pipeline                 Neon Postgres                Vercel
─────────────                   ─────────────                ──────
generate_weekly_bets.py   →     prediction_runs,      →     page.tsx (ISR 5m)
publish_to_db.py          →     predictions, games    →     market-only or approved
                                current_week                 prediction view
score_to_db.py            →     game_results,         →     (after games finish)
                                 system_stats
```

See `../docs/ops/weekly_pipeline.md` for the full weekly workflow.
