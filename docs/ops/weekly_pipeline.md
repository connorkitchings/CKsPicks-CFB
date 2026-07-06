# Weekly Pipeline — 2026 Season (Web App Deliverable)

> **Goal:** Every week during the 2026 season, regenerate model predictions for the upcoming FBS slate and publish them to the Neon Postgres database that powers the Vercel web app.

---

## Pipeline Overview

```
┌──────────────────────┐   ┌──────────────────────┐   ┌─────────────────────┐
│  1. Ingest           │ ─►│  2. Generate Bets    │ ─►│  3. Publish to DB   │
│  (CFBD API → R2)     │   │  (CSV artifact)      │   │  (Postgres upsert)  │
└──────────────────────┘   └──────────────────────┘   └─────────────────────┘
                                                                │
                                                                ▼
                                                    ┌─────────────────────┐
                                                    │  4. Vercel App      │
                                                    │  (reads via ISR)    │
                                                    └─────────────────────┘
                                                                │
                                               After games finish:
                                                                ▼
                                                    ┌─────────────────────┐
                                                    │  5. Score to DB     │
                                                    │  (results + stats)  │
                                                    └─────────────────────┘
```

---

## Prerequisites (one-time setup)

1. **Neon Postgres** — create a project at https://console.neon.tech and copy the connection string (`DATABASE_URL`).
2. **Apply the schema migration:**
   ```bash
   psql "$DATABASE_URL" -f web/db/migrations/0001_init.sql
   ```
3. **Set environment variables** in `.env`:
   ```
   DATABASE_URL=postgres://...?sslmode=require
   CFBD_API_KEY=...
   CFB_STORAGE_BACKEND=r2
   ```
4. **Vercel project** — import the repo at https://vercel.com/new, set:
   - **Root Directory:** `web/`
   - **Build Command:** `npm run build` (auto-detected)
   - **Environment Variable:** `DATABASE_URL` (same Neon connection string)

---

## Weekly Workflow

### Step 1: Ingest upcoming-week data

```bash
PYTHONPATH=.:src uv run python scripts/data/ingest_plays.py --year 2026 --week N
PYTHONPATH=.:src uv run python scripts/pipeline/cache_running_season_stats.py
```

### Step 2: Generate weekly bets (existing pipeline)

```bash
PYTHONPATH=.:src uv run python scripts/pipeline/generate_weekly_bets.py \
    --config conf/weekly_bets/v2_champion.yaml \
    --year 2026 --week N
```

This writes `data/production/predictions/2026/CFB_weekN_bets.csv` — the canonical artifact for both the email publisher and the web app.

### Step 3: Publish to Postgres

```bash
# Via Make (preferred):
make db-publish YEAR=2026 WEEK=N

# Or directly:
PYTHONPATH=.:src uv run python scripts/pipeline/publish_to_db.py \
    --year 2026 --week N \
    --config conf/weekly_bets/v2_champion.yaml
```

This upserts every game into the `games` table and updates the `current_week` singleton. The Vercel app's ISR cache (5-minute revalidate) will pick up the new week automatically.

### Step 4: (After games finish) Score results

```bash
# Once the scored CSV is produced by score_weekly_bets.py:
PYTHONPATH=.:src uv run python scripts/pipeline/score_weekly_bets.py --season 2026 --week N

# Then upsert results + refresh YTD system_stats:
make db-score YEAR=2026 WEEK=N
```

---

## Backfilling Historical Data (optional)

To populate Postgres with 2024 / 2025 history (useful for the YTD banner on day one):

```bash
# Predictions (do NOT update current_week singleton):
for YEAR in 2024 2025; do
    for CSV in data/production/predictions/$YEAR/CFB_week*_bets.csv; do
        WEEK=$(echo "$CSV" | grep -oE 'week[0-9]+' | grep -oE '[0-9]+')
        PYTHONPATH=.:src uv run python scripts/pipeline/publish_to_db.py \
            --year $YEAR --week $WEEK --no-update-current
    done
done

# Results + YTD stats:
make db-score YEAR=2024
make db-score YEAR=2025

# Finally, set the current week to the latest 2025 week:
PYTHONPATH=.:src uv run python scripts/pipeline/publish_to_db.py \
    --year 2025 --week 14
```

---

## Health Checks

```bash
# App health (from any environment with the Vercel URL):
curl https://<your-vercel-domain>/api/health

# DB row counts:
psql "$DATABASE_URL" -c "SELECT season, week, COUNT(*) FROM games GROUP BY 1,2 ORDER BY 1,2;"
psql "$DATABASE_URL" -c "SELECT * FROM current_week; SELECT * FROM system_stats;"
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| App shows "Database not connected" | `DATABASE_URL` missing in Vercel env | Add it in project settings, redeploy |
| Page renders but "No active week published" | `current_week` row still at `(0, 0)` | Run `publish_to_db.py` without `--no-update-current` |
| Logos broken for some teams | Team name in CFBD doesn't match logo filename | Extend `TEAM_LOGO_MAP` in both `scripts/pipeline/publish_picks.py` and `web/src/lib/teams.ts` |
| YTD record shows 0-0 | `score_to_db.py` hasn't been run for this season | Run `make db-score YEAR=YYYY` |

---

_Last Updated: 2026-07-06_
