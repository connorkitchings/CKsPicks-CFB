# Weekly Pipeline — 2026 Season

> **V5 Preview path:** The [current V5 status](../modeling/v5_status.md) and [cutover contract](../plans/2026-09-22/04-v5-authority-simplification-and-site-cutover.md) govern the future replacement of V4. `conf/weekly_bets/v5_preview_2026.yaml` selects the explicit V5 live-forecast adapter only after it pins an independently verified current forecast. The adapter emits the existing immutable prediction-run artifact and keeps production activation disabled until a separate decision. V4 remains the rollback configuration.

R2 is the durable content source of truth. Neon is the dataset/workflow control plane and derived serving database. The Next.js app reads the selected immutable run only when the explicit publication policy permits it; any non-`predictions` mode is fail-closed market-only rendering. Production never depends on repository-local data, model files, or mutable R2 pointers. V4 remains the active production/rollback bundle while rating work is isolated in shadow artifacts. See [2026 Data Platform](../architecture/data_platform_2026.md), the [Production Runbook](production_runbook.md), and the [2026 roadmap](../planning/roadmap.md).

## Required setup

Configure `CFBD_API_KEY`, `CFB_STORAGE_BACKEND=r2`, the R2 credentials, and the pipeline-role `DATABASE_URL`. Preview and replay use `PREVIEW_DATABASE_URL`; it must differ from production. Production R2 credentials point at the same bucket as Preview (`cks-picks-cfb-preview`) — immutable artifacts are checksummed and environment-neutral, and environment separation is enforced by Neon branch, not bucket. Apply the checksummed history to the target Neon branch with `make migrate-db` (append-only migrations, currently through 0013 on Preview). On this host, use `zsh scripts/ops/with_preview_env.sh <command>` for Preview branch-scoped database roles rather than the `.env` placeholder URL.

### V5 transition operations (Preview only until activation)

The [product transformation contract](../plans/2026-09-23/01-v5-product-transformation.md) governs the release gates. The inference bundle is pinned in `conf/research/data_first_football_v1/live_forecast_v1.yaml`. Reconstruct retrospective 2026 games with `scripts/pipeline/build_v5_replay.py`: first save and review its dry-run JSON, then apply with the same arguments plus `--preflight-evidence` from a clean committed code SHA. Pin the resulting manifest URI and raw SHA-256 in `conf/weekly_bets/v5_replay_2026.yaml`. Replay has `evidence_class=replay`; it is never a frozen-before-kickoff forecast.

The resumable operator supports `project-v5-ratings`, `publish-replay-week`, and `score-replay-week` with `--environment preview` and stable `--pipeline-run-id` values on retry. Replay publication uses `--no-update-current`; selecting a public run is a separate `scripts/pipeline/select_public_run.py` action with exact season, week, run ID, reason, and environment. A same-slate V4 rollback uses that command's `--allow-v4-fallback` and the reviewed V4 run ID. Inspect `site_week_selection_history`, `current_week`, `/api/health`, and populated browser pages after each selection. Do not use this procedure to claim prospective evidence for replay.

The [manual V5 weekly operator](v5_weekly_operator.md) prepares a separate
reviewed preflight and apply for each refreshed-parent, forecast, readiness,
publication, freeze, and close component. It records stable ops receipts and
does not schedule runs. Production V5 publication requires an admin-written,
one-slate `v5_serving_authorizations` record bound to exact forecast,
readiness, config, model, and prediction artifact checksums; no such record
exists yet. V4 publication and fallback remain available.

After stabilized Week 4 finals, refresh Contracts 07 and 08 under new immutable IDs, run and independently verify Contract 09 on the current slate, and rehearse Preview publication, freeze, close, and V4 rollback. Assemble the exact artifacts and observations for a separate production activation decision. V4 execution remains available until one V5 publish/freeze/close cycle succeeds.

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

### Preseason Features Requirement (V4 Model)

**Critical:** The V4 model was trained on `point_in_time_matchups_v5` which includes preseason features (recruiting, returning production, talent composite). The operational pipeline must use the same feature set.

When rebuilding features with `assemble_model_ready_features.py`, you must include the `--preseason-features-ref-uri` parameter pointing to the correct preseason features dataset:

```bash
PYTHONPATH=.:src uv run python scripts/pipeline/assemble_model_ready_features.py \
  --core-ref-uri <core_ref_uri> \
  --baselines-ref-uri <baselines_ref_uri> \
  --preseason-features-ref-uri lake/gold/dataset=v4_preseason_team_features/version=8c47f6d5ccdced2365e4dfdd/manifest.json \
  --feature-track strict \
  --as-of <as_of_timestamp> \
  --output-ref-uri <output_uri> \
  --environment preview
```

**Why this matters:** Without preseason features, the model is asked to predict using a different feature set than it was trained on, leading to degraded accuracy (observed 36% win rate in 2026 vs 51% in 2025). This is especially critical in weeks 0-2 where current-season data is sparse and the model relies heavily on preseason priors.

**Validation:** After rebuilding features, verify the dataset is `point_in_time_matchups_v5` (not `point_in_time_matchups` v4):

```bash
PYTHONPATH=.:src uv run python -c "
from cks_picks_cfb.data.storage import get_storage
import json
storage = get_storage()
manifest = json.loads(storage.read_bytes('<output_uri>').replace('data.parquet', 'manifest.json'))
print(f'Dataset: {manifest[\"dataset\"]}')
assert manifest['dataset'] == 'point_in_time_matchups_v5', 'Wrong dataset version!'
"
```

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

**The Odds API (opt-in second provider).** After `ingest_market`, the publish
flow includes an `ingest_market_quotes` step that captures the live The Odds
API NCAAF board (~2 credits) alongside the CFBD capture. It is disabled by
default; enable it by setting `CFB_ODDS_API_ENABLED=1` **and**
`THE_ODDS_API_KEY`. When enabled, the step is soft-fail: a provider error
records a loud warning and the publish proceeds CFBD-only — the snapshot
builder admits any registered `the_odds_api` captures and the
`consensus_then_median_v1` policy still prefers CFBD Consensus, so per-book
quotes fill gaps rather than displace consensus. Resuming a run never
re-issues the paid request.

**Neon quote persistence.** Activation writes the run's frozen
`market_quotes` rows and `market_snapshot_quotes` links in the same Neon
transaction as snapshots and predictions (`ON CONFLICT DO NOTHING`; a
snapshot-bearing run without a resolvable quotes ref fails closed).
`scripts/pipeline/backfill_market_quotes_db.py` retro-loads quotes from
catalog refs (`--season YYYY`, or explicit `--from-quotes-ref` URIs; use
`--dry-run` first).

For Week 0, Vercel now exposes the reviewed active run in predictions mode:

```bash
CFB_PUBLICATION_SEASON=2026
CFB_PUBLICATION_MODE=predictions
```

**Permanent best-quote market-line policy (`model_side_best_quote_v1`).** Every
future forecast selects the best executable pre-kickoff quote for each target
rather than displaying the `consensus_then_median_v1` snapshot value directly.
The canonical snapshot is still used to *establish the model's side* — so line
shopping cannot flip the direction — but the displayed point, edge, and grade
all derive from the single frozen raw quote selected by the service.

Selection rules (enforced by `select_best_quote()` in
`src/cks_picks_cfb/models/market_grading.py`):

1. Only quotes linked to the canonical snapshot, covering the same game and
   target, with a non-null point and side-specific price, and captured
   **strictly before kickoff** are eligible.
2. For the model's fixed side: highest signed spread point for spread; lowest
   point for over; highest point for under.
3. Equal points → better American price → quote ID ascending (deterministic).
4. A target with no eligible quote shows no lean (`null`) and receives no
   grade.  The system never substitutes a synthetic average, post-kickoff
   quote, or a quote from another game.

Each selection is recorded in the append-only `prediction_market_selections`
table (`run_id`, `game_id`, `target`, `quote_id`, `snapshot_id`, `side`,
`point`, `price`, `edge`, `policy_version`).  New grades must populate the
nullable `market_quote_id` column on `prediction_grades` so the exact quote
used for settlement is provable from the database.

Week availability needs no variable: the repo-owned range in
`web/src/lib/publication.ts` plus the explicit Neon public selection govern
each week. Publish, freeze, then select the reviewed run to reveal it.

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

### Historical season replay with a frozen selection-time bundle

`scripts/pipeline/replay_season_v4.py` replays a completed season week-by-week
using explicit immutable refs (certified point-in-time Gold, Silver schedule,
provider market snapshots/quotes, Silver outcomes) through the same
generate → publish → freeze → score → score_to_db loop:

```bash
PYTHONPATH=.:src uv run python scripts/pipeline/replay_season_v4.py \
  --year 2025 --environment preview \
  --config conf/weekly_bets/v4_2025_replay.yaml \
  --feature-ref-uri <certified-v5-ref> \
  --games-ref-uri <silver-games-ref> \
  --outcomes-ref-uri <silver-outcomes-ref> \
  --market-snapshots-ref-uri <ref> --market-quotes-ref-uri <ref>
```

Rules: each week's cutoff precedes its first kickoff; freezes record the
`historical replay` line-coverage waiver; promotion to production requires a
separate explicit approval, a `current_week` snapshot/restore around the run,
and `--confirm-production`. Never predict a completed season with the
production refit bundle (in-sample); use the selection-time model whose
training years exclude that season.

## Retrospective model context

The public prediction page may show a diagnostic-only prior-season context
panel. It is sourced from the immutable `historical_model_context` artifact,
not from `prediction_grades` or `system_stats`. Its reconstructed historical
market references are captured after the season and must never be described as
an official pregame betting record, ROI, or promotion evidence.

Build and publish a new context only from an approved, committed contract:

```bash
PYTHONPATH=src uv run python scripts/pipeline/build_historical_model_context.py --environment preview ...
PYTHONPATH=src uv run python scripts/pipeline/publish_historical_model_context.py --environment preview ...
PYTHONPATH=src uv run python scripts/pipeline/publish_historical_model_context.py --environment production ...
```

Apply the append-only database migration to Preview first, verify the exact
artifact checksum and aggregates there, then publish the same artifact to
production. The Vercel deployment is a separate user-managed release step.

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
