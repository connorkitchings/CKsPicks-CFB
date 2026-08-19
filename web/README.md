# CK's Picks — Web App

Next.js 16 / React 19 / Tailwind CSS v4 app for the explicitly configured public release scope. It defaults to schedule and market lines; model output requires a separate server-side opt-in. Deployed to Vercel and backed by Neon Postgres.

**Production:** https://c-ks-picks-cfb.vercel.app (fail-closed `market` mode; published run `2026w0-79ec2aebcb00`, 8/8 Week 0 games, 8/8 lined, 0 high-confidence).

## Stack

- **Framework:** Next.js 16 (App Router, TypeScript)
- **DB:** Neon Postgres serverless, accessed via `@neondatabase/serverless` + Drizzle ORM
- **Styling:** Tailwind CSS v4
- **Logos:** Synced from `../assets/logos/` into `public/logos/` on every `predev` / `prebuild` (the checked-in `public/logos/` is the deployment fallback when the source is unavailable, e.g. Vercel builds)

## Local Development

```bash
# 1. Copy env template and fill in your Neon connection string
cp .env.example .env
#   then edit .env:
#   DATABASE_URL=postgres://user:password@ep-xxx.region.aws.neon.tech/dbname?sslmode=require

# 2. Apply database migrations (from the repo root — canonical history is
#    contracts/migrations/, currently 0001–0008; never edit applied migrations)
make migrate-db ENV=preview   # or run scripts/pipeline/migrate_db.py directly

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
| `npm run db:generate` | Regenerate Drizzle migration from `schema.ts` |
| `npm run db:studio` | Open Drizzle Studio (DB browser) |

> Schema provenance: `contracts/schema.ts` is the single source of truth; the
> local copy in `src/lib/schema.ts` must stay in sync (`make contracts-check`
> from the repo root). `npm run db:migrate` applies only the legacy
> `0001_init.sql` baseline — use the repo-root migration flow for the current
> append-only history.

## Project Structure

```
web/
├── db/
│   └── migrations/
│       ├── 0001_init.sql           # Baseline schema (legacy location)
│       ├── 0002_prediction_runs.sql
│       └── README.md               # Deprecated location — see contracts/migrations/
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
    │   └── api/health/route.ts  # Health endpoint (run state + coverage)
    ├── components/
    │   ├── Header.tsx        # Header + Footer
    │   ├── GameRow.tsx       # Per-game row with leans
    │   ├── LeanBadge.tsx     # Spread + total visual chips
    │   └── RecordBanner.tsx  # YTD spread/total record
    └── lib/
        ├── db.ts             # Drizzle client (lazy, build-safe)
        ├── schema.ts         # Drizzle schema (synced copy of contracts/schema.ts)
        ├── publication.ts    # Fail-closed publication-mode boundary
        ├── queries.ts        # getCurrentWeek / getGamesForWeek / etc.
        └── teams.ts          # Team-name → logo URL mapping
```

## Deploying to Vercel

1. Push the repo to GitHub.
2. Import the project at https://vercel.com/new.
3. **Set Root Directory to `web/`**. Do not deploy from the repository root.
4. Add the production `DATABASE_URL` (read-only `cks_prod_web` role on the
   production Neon branch) and the `CFB_PUBLICATION_*` release variables to
   Vercel Environment Variables.
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
