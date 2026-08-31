# Weekly Pipeline — 2026 Season

R2 is the durable content source of truth. Neon is the dataset/workflow control plane and derived serving database. The Next.js app reads the selected immutable run only when the explicit publication policy permits it; any non-`predictions` mode is fail-closed market-only rendering. Production never depends on repository-local data, model files, or mutable R2 pointers. V4 remains the active production/rollback bundle while rating work is isolated in shadow artifacts. See [2026 Data Platform](../architecture/data_platform_2026.md), the [Production Runbook](production_runbook.md), and the [2026 roadmap](../planning/roadmap.md).

## Required setup

Configure `CFBD_API_KEY`, `CFB_STORAGE_BACKEND=r2`, the R2 credentials, and the pipeline-role `DATABASE_URL`. Preview and replay use `PREVIEW_DATABASE_URL`; it must differ from production. Production R2 credentials point at the same bucket as Preview (`cks-picks-cfb-preview`) — immutable artifacts are checksummed and environment-neutral, and environment separation is enforced by Neon branch, not bucket. Apply the checksummed history to the target Neon branch with `make migrate-db` (append-only migrations 0002–0008).

Upload route artifacts and configure the ten-cell manifest URI/checksum in the launch config `conf/weekly_bets/v4_2026.yaml` (V4 bundle `week0-2026-v4-strict-20260818-r2`; `conf/weekly_bets/v2_preview_2026.yaml` remains the wired fallback). Weekly dataset refs are selected from the catalog and frozen in each pipeline-run manifest, never in static configuration.

For rehearsal, point `PREVIEW_DATABASE_URL` at an isolated Neon branch and connect that branch to a Vercel Preview deployment.

## Local Preview credentials

`preview-2026` is the durable 2026 Preview branch. Its pipeline and migration
credentials live only in the local macOS Keychain; Vercel receives the separate
read-only web credential. Run Preview operations through the wrapper so the
legacy `.env` values cannot target the wrong branch:

```bash
zsh scripts/ops/with_preview_env.sh make migrate-db
zsh scripts/ops/with_preview_env.sh make readiness \
  YEAR=2026 WEEK=0 AS_OF=YYYY-MM-DD ENV=preview
```

The wrapper injects `PREVIEW_DATABASE_URL` for Preview pipeline operations and
the migration-only `DATABASE_URL` for `make migrate-db`. Never use the
`cks_preview_migrator` or `cks_preview_pipeline` connection in Vercel.

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

Readiness fails unless R2 and Neon connect, the run-aware schema exists, the FBS-vs-FBS schedule has unique game IDs, the point-in-time snapshot is complete (or the explicit display-only prior fallback has its required inputs), all ten route cells of the promoted model bundle load with matching checksums, contracts match, and the web app lints, typechecks, and builds.

## Progressive publish and freeze

Before publishing a week after any completed games, rebuild the cumulative
current-season inputs in the intended environment. `prepare-week` is required
for Week 1 and every subsequent week (it is not needed for Week 0 which is
pure preseason). `prepare-week` is resumable and captures its own source
lineage; it preserves the frozen 2021–2025 baseline rather than rerunning
model selection.

```bash
make prepare-week YEAR=2026 WEEK=1 AS_OF=YYYY-MM-DDTHH:MM:SSZ ENV=preview
make readiness YEAR=2026 WEEK=1 AS_OF=YYYY-MM-DDTHH:MM:SSZ ENV=preview
```

It fails if Gold is stale for the requested cutoff, target-week rows do not
cover the canonical schedule, outcomes disagree with completed schedule games,
or a team with completed 2026 games lacks current-season features.

Publish and rerun as lines arrive. Every mutating Make target requires an
explicit `ENV`; there is no implicit production default:

```bash
# Preview rehearsal
make publish-week YEAR=2026 WEEK=N AS_OF=YYYY-MM-DDTHH:MM:SSZ ENV=preview \
  CONFIG=conf/weekly_bets/v2_preview_2026.yaml

# Production (launch model)
make publish-week YEAR=2026 WEEK=N AS_OF=YYYY-MM-DDTHH:MM:SSZ ENV=production \
  CONFIG=conf/weekly_bets/v4_2026.yaml
```

Set the requested `AS_OF` roughly five minutes ahead of the publish run so the
market capture falls before the cutoff.

Each invocation runs through `python -m cks_picks_cfb.ops`, creates a new run-specific R2 prefix, and records resumable steps in `ops.pipeline_steps`. Neon activation occurs in one transaction only after predictions validate. Missing lines are allowed; the site shows the model output with “Line unavailable—model prediction shown, no lean.”

The market step maps the checked-in canonical-week policy to CFBD's provider
week, records both week values, binds the Bronze capture to the pipeline run,
and builds immutable `market_quotes` and `market_snapshots` before freezing the
input ref set. For example, the August 29, 2026 slate is canonical Week 0 but
provider Week 1. The requested `AS_OF` must follow the market capture time;
the build fails closed rather than backdating a late capture.

For Week 0, Vercel now exposes the reviewed active run in predictions mode:

```bash
CFB_PUBLICATION_SEASON=2026
CFB_PUBLICATION_WEEKS=0,1   # comma-separated; add each week after publish + freeze
CFB_PUBLICATION_MODE=predictions
```

Each progressive manual publish remains a separate immutable market/prediction
snapshot. Record its run ID, checksum, market-capture time, and cutoff after a
successful health check; a later publish does not overwrite the earlier one.
The public page shows only the latest snapshot. No Week 0 scheduler is active,
so this history represents manual observations rather than continuous market
coverage. Only the exact `predictions` value enables model output; every other
value remains market-only.

Before kickoff, freeze the active run:

```bash
make freeze-week YEAR=2026 WEEK=N ENV=preview
```

Freeze requires predictions and both line types for every eligible game. A genuine provider exception can be recorded explicitly:

```bash
make freeze-week YEAR=2026 WEEK=N ENV=preview WAIVER="provider did not list total for game 123"
```

Frozen runs are immutable. Historical pages select the newest frozen/scored run, while the active week selects `current_week.active_run_id`.

## Close and replay

After finals — **run on Tuesday** (not Monday). CFBD takes ~24–48 h to finalize
all game scores after weekend play; running close-week on Monday often produces
`away_points`/`home_points` missing errors from the Silver game_outcomes build.

```bash
make close-week YEAR=2026 WEEK=N AS_OF=YYYY-MM-DDTHH:MM:SSZ ENV=production
```

Scoring resolves the frozen run from Neon, verifies that run's immutable R2 artifact, and writes run-specific `prediction_grades`. It requires an immutable `game_outcomes` reference with a completed outcome for every frozen eligible game. Cancellations require explicit game-ID/reason waivers and are retained in the scored manifest without a grade.

Rehearse a historical season against an isolated preview database:

```bash
make replay-season YEAR=2025 ENV=preview
```

The replay command refuses to run unless `PREVIEW_DATABASE_URL` is set and differs from `DATABASE_URL`.

## Early-season routing

Completed games are counted per team. The matchup regime label uses the lesser count:

| Completed games | Route |
|---:|---|
| 0 | Game 1 prior/preseason route |
| 1 | Game 2 direct, points-derived, or monotone blend champion |
| 2 | Game 3 direct, points-derived, or monotone blend champion |
| 3 | Game 4 route, evaluated against the established model |
| 4+ | Established current-season model |

Weights must be selected from training-year out-of-fold predictions and decrease monotonically. The preseason snapshot builder supports any scheduled week, so byes do not force an established route. A regime that has not passed promotion remains display-only and cannot receive high-confidence branding.

The only supported general training entry point is:

```bash
PYTHONPATH=src uv run python -m cks_picks_cfb.train
```

Generate candidates with `experiment=week0_regimes`. Selection uses temporal 2022–2024 OOF predictions, 2025 is the locked test, and the unchanged production design refits on 2021–2025. Early 2021 may use 2019 only as its prior source; 2020 remains entirely excluded.

V4 activation requires a strict immutable feature reference. A reconstructed
historical reference is research-only and the candidate evaluator/refitter
reject it unless the evaluation is explicitly invoked with `--research-only`;
no reconstructed report can create a loadable prediction bundle.

## CFBD Model Pick'em

Model Pick'em uses a separate, short-lived `CFBD_PREDICTION_TOKEN`; the regular `CFBD_API_KEY` cannot submit contest picks. Always reconcile the authenticated contest slate before submission:

```bash
make export-pickem YEAR=2026 WEEK=0 VALIDATE=1
make export-pickem YEAR=2026 WEEK=0 DRY_RUN=1
```

The exporter submits one `{gameId, pick}` request per matched FBS-vs-FBS game and deliberately excludes totals. Do not use `SUBMIT=1` until the user has supplied a current prediction token and approved the final slate.

For launch operations, pass the exact private run CSV with `--input-csv` rather
than relying on fallback path discovery. Record the run ID, artifact checksum,
contest reconciliation, and final payload together. Refresh/export/reconcile
may be automated; the POST remains a separate approval-gated command.

## Health and recovery

`/api/health` reports the schema version, active run/state, expected/predicted/lined coverage, artifact freshness, data cutoff, and last successful publish. It never returns database error details.

Useful checks:

```bash
psql "$DATABASE_URL" -c "SELECT run_id, season, week, state, expected_games, predicted_games, lined_games FROM prediction_runs ORDER BY created_at DESC;"
psql "$DATABASE_URL" -c "SELECT season, week, active_run_id FROM current_week WHERE id = 1;"
curl https://<preview-domain>/api/health
curl https://c-ks-picks-cfb.vercel.app/api/health   # production
```

Any prediction, upload, validation, or database failure exits nonzero. Do not continue manually to activation after a failed step; correct the failure and create a new run.

Resume an interrupted operation with the same `--pipeline-run-id` through the Python CLI. Use `make reconcile YEAR=2026 ENV=preview` to catalog inactive/orphaned artifacts.
