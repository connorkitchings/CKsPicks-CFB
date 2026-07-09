# Weekly Pipeline — 2026 Season (Web App Deliverable)

> **Goal:** Every week during the 2026 season, regenerate model predictions for the upcoming FBS slate and publish them to the Neon Postgres database that powers the Vercel web app.

---

## Pipeline Overview

```
┌──────────────────────┐   ┌──────────────────────┐   ┌──────────────────────┐
│  1. Preflight        │ ─►│  2. Ingest + Preagg  │ ─►│  3. Generate Picks   │
│  (env/R2/Neon)       │   │  (CFBD API → R2)     │   │  (local CSV + R2)    │
└──────────────────────┘   └──────────────────────┘   └──────────────────────┘
                                                                  │
                                                                  ▼
                                                    ┌──────────────────────────┐
                                                    │  4. Publish R2 → Neon    │
                                                    │  (derived serving copy)  │
                                                    └──────────────────────────┘
                                                                  │
                                                                  ▼
                                                    ┌──────────────────────────┐
                                                    │  5. Vercel App          │
                                                    │  (reads Neon via ISR)   │
                                                    └──────────────────────────┘
```

**Source-of-truth boundary:** R2 is durable storage for raw data, processed features, and weekly prediction/scored artifacts. Neon is a derived serving database for the web app (`games`, `game_results`, `system_stats`, `current_week`).

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
   CFB_R2_BUCKET=...
   CFB_R2_ACCOUNT_ID=...
   CFB_R2_ACCESS_KEY=...
   CFB_R2_SECRET_KEY=...
   ```
4. **Vercel project** — import the repo at https://vercel.com/new, set:
   - **Root Directory:** `web/`
   - **Build Command:** `npm run build` (auto-detected)
   - **Environment Variable:** `DATABASE_URL` (same Neon connection string; only required web runtime variable)

---

## Weekly Workflow

### Supported path

```bash
# Validate config before a weekly run:
make preflight YEAR=2026 WEEK=N

# Full weekly cycle:
make weekly YEAR=2026 WEEK=N
```

`make weekly` runs:

1. Preflight checks for R2, Neon schema, artifact paths, and Vercel config assumptions.
2. `scripts/data/ingest_week.py` for raw week data.
3. `scripts/pipeline/run_pipeline_generic.py` for raw → processed pre-aggregations.
4. `scripts/pipeline/generate_weekly_bets.py --upload-artifact` to write a local working CSV and durable R2 artifact.
5. `scripts/pipeline/publish_to_db.py --from-artifact` to publish the durable R2 artifact into Neon.

### Recovery commands

```bash
# Re-run only ingestion:
make ingest-week YEAR=2026 WEEK=N

# Re-run pre-aggregation:
PYTHONPATH=.:src uv run python scripts/pipeline/run_pipeline_generic.py --year 2026

# Regenerate predictions and upload the durable artifact:
PYTHONPATH=.:src uv run python scripts/pipeline/generate_weekly_bets.py \
    --config conf/weekly_bets/v2_champion.yaml \
    --year 2026 --week N \
    --upload-artifact

# Publish the durable artifact into Neon:
PYTHONPATH=.:src uv run python scripts/pipeline/publish_to_db.py \
    --year 2026 --week N \
    --config conf/weekly_bets/v2_champion.yaml \
    --from-artifact
```

Local `data/production/...` CSVs are working copies for debugging and legacy scripts. The durable prediction artifact path is `artifacts/production/predictions/year=YYYY/CFB_weekN_bets.csv` in R2.

### After games finish

```bash
# Produce local scored CSV and upload durable scored artifact:
PYTHONPATH=.:src uv run python scripts/pipeline/score_weekly_bets.py \
    --year 2026 --week N \
    --from-artifact \
    --upload-artifact

# Upsert durable scored artifact into Neon and refresh YTD system_stats:
PYTHONPATH=.:src uv run python scripts/pipeline/score_to_db.py \
    --year 2026 --week N \
    --from-artifact
```

---

## Backfilling Historical Data (optional)

To populate Postgres with 2024 / 2025 history (useful for the YTD banner on day one):

```bash
# Predictions from durable R2 artifacts (do NOT update current_week singleton):
for YEAR in 2024 2025; do
    for WEEK in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16; do
        PYTHONPATH=.:src uv run python scripts/pipeline/publish_to_db.py \
            --year $YEAR --week $WEEK --from-artifact --no-update-current
    done
done

# Results + YTD stats from durable R2 artifacts:
PYTHONPATH=.:src uv run python scripts/pipeline/score_to_db.py --year 2024 --backfill-season --from-artifact
PYTHONPATH=.:src uv run python scripts/pipeline/score_to_db.py --year 2025 --backfill-season --from-artifact

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
| Logos broken for some teams | Team name in CFBD doesn't match logo filename | Extend `TEAM_LOGO_MAP` in `contracts/teams.py` + `contracts/teams.ts`, sync local copies, then run `make contracts-check` |
| YTD record shows 0-0 | `score_to_db.py` hasn't been run for this season | Run `PYTHONPATH=.:src uv run python scripts/pipeline/score_to_db.py --year YYYY --backfill-season --from-artifact` |

---

_Last Updated: 2026-07-06_
