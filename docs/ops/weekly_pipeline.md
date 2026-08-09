# Weekly Pipeline - 2026 Season

Goal: publish every FBS game for the active 2026 week to the Vercel web app, then close the week after finals are available.

R2 is the durable source of truth for raw data, processed features, prediction artifacts, and scored artifacts. Neon Postgres is a derived serving database for the web app tables: `games`, `game_results`, `system_stats`, and `current_week`.

## One-Time Setup

1. Set required environment variables in `.env`:
   ```bash
   DATABASE_URL=postgres://...?sslmode=require
   CFBD_API_KEY=...
   CFB_STORAGE_BACKEND=r2
   CFB_R2_BUCKET=...
   CFB_R2_ACCOUNT_ID=...
   CFB_R2_ACCESS_KEY=...
   CFB_R2_SECRET_KEY=...
   ```
2. Apply the database schema if Neon is new:
   ```bash
   psql "$DATABASE_URL" -f contracts/schema.sql
   ```
3. Configure Vercel with Root Directory `web/` and runtime env `DATABASE_URL`.
4. Verify the active path:
   ```bash
   make preflight YEAR=2026 WEEK=1
   ```

## Preseason Refresh

Run this in mid-August and again before Week 1 if CFBD publishes updated data:

```bash
make ingest-season YEAR=2026 ENTITIES=rosters,coaches,recruiting,rankings,games
make preflight YEAR=2026 WEEK=1
```

Known availability gates:
- 2026 teams, venues, and games are already present in R2.
- Rosters, coaches, recruiting, rankings, external ratings, betting lines, plays, and game stats depend on CFBD/API/provider publication timing.
- Early-season predictions use latest prior-season `processed/team_week_adj` features when teams have fewer than 4 current-season games. These rows are display-eligible but not high-confidence eligible.

### Optional Preseason Candidate

The Week 1 preseason candidate is disabled by default and does not alter the
publish contract. Capture each provider source once under an immutable date;
the same `--year` and `--as-of` combination must never be rerun:

```bash
PYTHONPATH=.:src uv run python scripts/data/ingest_preseason.py \
  --year 2026 --as-of YYYY-MM-DD
```

Backfill the required historical snapshots before training. The trainer
enforces 2019/2021-2023 training, 2024 locked holdout, and optional 2025
shadow validation. Select Week 2-3 weights from training-only rows, attach
them to the model bundle, and enable `preseason` in
`conf/weekly_bets/v2_champion.yaml` only when its embedded promotion result is
passing and the 2026 snapshot is complete. Otherwise the normal recency
fallback remains active.

## Pregame Publish

Run before each slate and rerun after meaningful line changes:

```bash
make publish-week YEAR=2026 WEEK=N
```

This target:
1. Runs preflight.
2. Refreshes the season schedule and the target week's betting lines.
3. Runs pre-aggregation for completed raw data already in R2.
4. Generates predictions and uploads `artifacts/production/predictions/year=YYYY/CFB_weekN_bets.csv`.
5. Publishes that durable artifact into Neon and updates `current_week`.

`make weekly YEAR=2026 WEEK=N` is an alias for `make publish-week`.

## Postgame Close

Run after finals are available:

```bash
make close-week YEAR=2026 WEEK=N
```

This target:
1. Refreshes final scores plus completed plays, betting lines, and game stats.
2. Runs pre-aggregation with completed plays.
3. Scores the durable prediction artifact and uploads `artifacts/production/scored/year=YYYY/CFB_weekN_bets_scored.csv`.
4. Upserts scored results into Neon and recomputes `system_stats`.

## Recovery Commands

Use these when a single step needs to be rerun:

```bash
# Preflight only
make preflight YEAR=2026 WEEK=N

# Refresh schedule only
PYTHONPATH=.:src uv run python scripts/data/ingest_season.py --year 2026 --entities games

# Refresh week lines only
PYTHONPATH=.:src uv run python scripts/data/ingest_week.py --year 2026 --week N --entities betting_lines

# Refresh completed week data only
PYTHONPATH=.:src uv run python scripts/data/ingest_week.py --year 2026 --week N --entities plays,betting_lines,game_stats

# Rebuild processed features
PYTHONPATH=.:src uv run python scripts/pipeline/run_pipeline_generic.py --year 2026

# Regenerate and upload prediction artifact
PYTHONPATH=.:src uv run python scripts/pipeline/generate_weekly_bets.py --year 2026 --week N --upload-artifact

# Publish prediction artifact to Neon
PYTHONPATH=.:src uv run python scripts/pipeline/publish_to_db.py --year 2026 --week N --from-artifact

# Score and upload scored artifact
PYTHONPATH=.:src uv run python scripts/pipeline/score_weekly_bets.py --year 2026 --week N --from-artifact --upload-artifact

# Publish scored artifact to Neon
PYTHONPATH=.:src uv run python scripts/pipeline/score_to_db.py --year 2026 --week N --from-artifact
```

## Health Checks

```bash
# App health
curl https://<your-vercel-domain>/api/health

# DB serving state
psql "$DATABASE_URL" -c "SELECT season, week FROM current_week;"
psql "$DATABASE_URL" -c "SELECT season, as_of_week, spread_wins, spread_losses, total_wins, total_losses FROM system_stats ORDER BY season;"
psql "$DATABASE_URL" -c "SELECT season, week, COUNT(*) FROM games GROUP BY 1,2 ORDER BY 1,2;"
```

## Modeling Track

The current `conf/weekly_bets/v2_champion.yaml` model is a 2026 display fallback. It should not be treated as a trusted betting edge. Modeling work resumes after the ops path is stable:

```bash
PYTHONPATH=.:src uv run python research/training/cross_validation.py --config conf/experiment/v2_walk_forward_cv.yaml
PYTHONPATH=.:src uv run python research/training/cross_validation.py --config conf/experiment/v2_catboost_walk_forward.yaml
PYTHONPATH=.:src uv run python research/analysis/shap_stability.py --output artifacts/analysis/shap_stability_report.md
```

Promotion requirements remain: no 2020 training data, no target leakage, positive stable ROI across walk-forward folds, and enough bet volume to matter.

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| App shows database error | `DATABASE_URL` missing in Vercel | Add env var and redeploy |
| No active week | `current_week` was not updated | Run `publish_to_db.py --from-artifact` without `--no-update-current` |
| Week 1 has predictions but no high-confidence games | Cold-start eligibility suppresses high confidence before 4 games/team | Expected early-season behavior |
| Scoring says no completed scores | CFBD games refresh has not published finals yet | Re-run `ingest_season --entities games` later |
| Logos missing | Team map mismatch | Update `contracts/teams.py`, `contracts/teams.ts`, web copies, then run `make contracts-check` |
