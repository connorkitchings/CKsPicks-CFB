# Weekly Pipeline — 2026 Season

R2 is the durable content source of truth. Neon is the dataset/workflow control plane and derived serving database. The Next.js app reads only the selected immutable prediction run. Production never depends on repository-local data, model files, or mutable R2 pointers. See [2026 Data Platform](../architecture/data_platform_2026.md).

## Required setup

Configure `CFBD_API_KEY`, `CFB_STORAGE_BACKEND=r2`, the environment-specific R2 credentials, and the pipeline-role `DATABASE_URL`. Preview and replay both use `PREVIEW_DATABASE_URL`; it must differ from production. Apply the checksummed history to an isolated Neon branch with `make migrate-db`.

Upload route artifacts and configure the ten-cell manifest URI/checksum in `conf/weekly_bets/v2_champion.yaml`. Weekly dataset refs are selected from the catalog and frozen in each pipeline-run manifest, never in static configuration.

For rehearsal, point `PREVIEW_DATABASE_URL` at an isolated Neon branch and connect that branch to a Vercel Preview deployment.

## Data-ready trigger

Capture the immutable preseason sources once:

```bash
PYTHONPATH=.:src uv run python scripts/data/ingest_preseason.py \
  --year 2026 --as-of YYYY-MM-DD
```

Then run the complete readiness gate:

```bash
make audit-data YEAR=2026 ENV=preview
make readiness YEAR=2026 WEEK=0 AS_OF=YYYY-MM-DD ENV=preview
```

Readiness fails unless R2 and Neon connect, the run-aware schema exists, the FBS-vs-FBS schedule has unique game IDs, the point-in-time snapshot is complete, both promoted model checksums load, contracts match, and the web app lints, typechecks, and builds.

## Progressive publish and freeze

Publish and rerun as lines arrive:

```bash
make publish-week YEAR=2026 WEEK=N AS_OF=YYYY-MM-DD
```

Each invocation runs through `python -m cks_picks_cfb.ops`, creates a new run-specific R2 prefix, and records resumable steps in `ops.pipeline_steps`. Neon activation occurs in one transaction only after predictions validate. Missing lines are allowed; the site shows the model output with “Line unavailable—model prediction shown, no lean.”

Before kickoff, freeze the active run:

```bash
make freeze-week YEAR=2026 WEEK=N
```

Freeze requires predictions and both line types for every eligible game. A genuine provider exception can be recorded explicitly:

```bash
make freeze-week YEAR=2026 WEEK=N WAIVER="provider did not list total for game 123"
```

Frozen runs are immutable. Historical pages select the newest frozen/scored run, while the active week selects `current_week.active_run_id`.

## Close and replay

After finals:

```bash
make close-week YEAR=2026 WEEK=N
```

Scoring resolves the frozen run from Neon, verifies that run's immutable R2 artifact, and writes run-specific `prediction_grades`. It cannot score a mutable preview or a global game grade.

Rehearse a historical season against an isolated preview database:

```bash
make replay-season YEAR=2025 ENV=preview
```

The replay command refuses to run unless `PREVIEW_DATABASE_URL` is set and differs from `DATABASE_URL`.

## Early-season routing

Completed games are counted per team. The matchup regime label uses the lesser count:

| Completed games | Route |
|---:|---|
| 0 | Preseason/prior model |
| 1 | Direct Ridge, direct CatBoost, or monotone blend champion |
| 2 | Direct Ridge, direct CatBoost, or monotone blend champion |
| 3 | Direct Ridge, direct CatBoost, or monotone blend champion |
| 4+ | Current-season model only |

Weights must be selected from training-year out-of-fold predictions and decrease monotonically. The preseason snapshot builder supports any scheduled week, so byes do not force an established route. A regime that has not passed promotion remains display-only and cannot receive high-confidence branding.

The only supported general training entry point is:

```bash
PYTHONPATH=src uv run python -m cks_picks_cfb.train
```

Generate candidates with `experiment=week0_regimes`. Selection uses temporal 2022–2024 OOF predictions, 2025 is the locked test, and the unchanged production design refits on 2021–2025. Early 2021 may use 2019 only as its prior source; 2020 remains entirely excluded.

## Health and recovery

`/api/health` reports the schema version, active run/state, expected/predicted/lined coverage, artifact freshness, and last successful publish. It never returns database error details.

Useful checks:

```bash
psql "$DATABASE_URL" -c "SELECT run_id, season, week, state, expected_games, predicted_games, lined_games FROM prediction_runs ORDER BY created_at DESC;"
psql "$DATABASE_URL" -c "SELECT season, week, active_run_id FROM current_week WHERE id = 1;"
curl https://<preview-domain>/api/health
```

Any prediction, upload, validation, or database failure exits nonzero. Do not continue manually to activation after a failed step; correct the failure and create a new run.

Resume an interrupted operation with the same `--pipeline-run-id` through the Python CLI. Use `make reconcile YEAR=2026 ENV=preview` to catalog inactive/orphaned artifacts.
