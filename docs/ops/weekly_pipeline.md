# Weekly Pipeline — 2026 Season

> **V5 production status (2026-09-27):** The [current V5 status](../modeling/v5_status.md) and [Week 5 line-refresh record](../../session_logs/2026-09-27/14-week5-line-refresh-candidate.md) document the accepted V5 model family and authorized live activation. Production serves V5 best-quote replay replacement runs (`2026w{0..4}-v5replay-bestquote-20260926-r3`), with Weeks 0–4 scored after certified Week 4 finals, and the selected Week 5 live run `2026w5-5d436e58c072` (56 predicted games, all 56 with spread and total lines). Certified V5 team ratings are served from `v5_rating_snapshots`; the earlier Week 5 V5 run is the immediate same-week rollback and V4 frozen runs remain available for prior slates.

R2 is the durable content source of truth. Neon is the dataset/workflow control plane and derived serving database. The Next.js app reads the selected immutable run only when the explicit publication policy permits it; any non-`predictions` mode is fail-closed market-only rendering. Production never depends on repository-local data, model files, or mutable R2 pointers. See [2026 Data Platform](../architecture/data_platform_2026.md), the [Production Runbook](production_runbook.md), and the [2026 roadmap](../planning/roadmap.md).

## Required setup

Configure `CFBD_API_KEY`, `CFB_STORAGE_BACKEND=r2`, the R2 credentials, and the pipeline-role `DATABASE_URL`. Preview and replay use `PREVIEW_DATABASE_URL`; it must differ from production. Production R2 credentials point at the same bucket as Preview (`cks-picks-cfb-preview`) — immutable artifacts are checksummed and environment-neutral, and environment separation is enforced by Neon branch, not bucket. Apply the checksummed history to a verified target Neon branch with `scripts/pipeline/migrate_db.py --database-url` or `--database-env` (append-only migrations through 0018). `make migrate-db` is disabled because `ENV=preview` did not select a database. On this host, use `zsh scripts/ops/with_preview_env.sh <command>` for Preview branch-scoped database roles and `zsh scripts/ops/with_production_pipeline_env.sh <command>` for the restricted `cks_prod_pipeline` role on production.

### V5 weekly operations & ratings publication

The [product transformation contract](../plans/2026-09-23/01-v5-product-transformation.md) and [ratings publication contract](../plans/2026-09-26/03-v5-ratings-publication-and-navigation.md) govern active V5 operations.

Weekly boundary: `close-week (N-1)` → verified ratings refresh and
`project-v5-ratings` → `prepare-week (N)` → `readiness` → reviewed publication.
Prospective V5 publication still requires its own exact release authorization.

1. **Ratings refresh and projection before `prepare-week`:**
   After `close-week (N-1)` and stabilized finals, run the operator-controlled repair → measurements → rating replay chain and its independent verifiers. Follow [the V5 weekly operator](v5_weekly_operator.md) for exact immutable inputs and receipts. Project the verified replay into `v5_rating_snapshots` before `prepare-week (N)`; projection does not depend on a selected prediction run:
   ```bash
   zsh scripts/ops/with_production_pipeline_env.sh \
     uv run python -m cks_picks_cfb.ops project-v5-ratings \
       --year 2026 \
       --environment production \
       --rating-manifest-uri artifacts/research/data-first-football-v1/possession-v1/rating-replay/runs/<run_id>/retained-rating-replay-manifest.json
   ```
   - **Ordering & Preconditions:** Requires a verified rating manifest in R2 with matching independent verifier, verified parents, active pipeline lease (`assert_active_pipeline_lease`), and `v5_release_policy`. Run the analogous command through `with_preview_env.sh` for Preview first.
   - **Timeline labels:** The baseline before Week 0 is `preseason`. A refresh after Week 0 finals is `post-week 0` and feeds Week 1; after Week 1 it is `post-week 1` and feeds Week 2, and so on. Labels describe the last included results, not a hardcoded database field. The exact manifest SHA and cutoff identify the generation.
   - **Currency check:** Inspect projected current rows, then run `prepare-week`; its final readiness step checks one generation, its team coverage, and the latest completed kickoff plus the six-hour availability buffer. A missing database connection, missing rows, ambiguous generation, or stale cutoff blocks ready state.
     `week` on a current row is that team's last played week, so rows from one generation can have different week values.
     ```sql
     SELECT week, source_manifest_sha256, cutoff_utc, count(DISTINCT team) AS teams
     FROM v5_rating_snapshots
     WHERE season = 2026 AND snapshot_class = 'current'
     GROUP BY week, source_manifest_sha256, cutoff_utc
     ORDER BY cutoff_utc DESC;
     ```
   - **Idempotency & Fail-Closed:** Snapshots use `ON CONFLICT (snapshot_id) DO NOTHING`. If projection fails, transactions roll back; predictions remain served while `/ratings` displays a graceful empty/unavailable state.
   - **No `v5_cycle.py` edits required:** The command is already wired in `src/cks_picks_cfb/ops/__main__.py:2002-2018`.
   - **Exceptional Rollback:**
     ```sql
     -- Executed via with_production_pipeline_env.sh under active pipeline lease:
     DELETE FROM v5_rating_snapshots WHERE source_manifest_sha256 = '<sha>';
     ```

2. **Weekly Run Replay & Serving:**
   The resumable operator supports `project-v5-ratings`, `publish-replay-week`, and `score-replay-week` with stable `--pipeline-run-id` values on retry. Public selection is managed via `scripts/pipeline/select_public_run.py` with exact season, week, run ID, reason, and environment. Inspect `site_week_selection_history`, `current_week`, `/api/health`, and populated browser pages after each selection.

Upload route artifacts and configure the ten-cell manifest URI/checksum in the launch config `conf/weekly_bets/v4_2026.yaml` (V4 bundle `week0-2026-v4-strict-20260818-r2`; `conf/weekly_bets/v2_preview_2026.yaml` remains the wired fallback). Weekly dataset refs are selected from the catalog and frozen in each pipeline-run manifest, never in static configuration.

For rehearsal, point `PREVIEW_DATABASE_URL` at an isolated Neon branch and connect that branch to a Vercel Preview deployment.

## Local Preview credentials

`preview-2026` is the durable 2026 Preview branch. Its pipeline and migration
credentials live only in the local macOS Keychain; Vercel receives the separate
read-only web credential. Run Preview operations through the wrapper so the
legacy `.env` values cannot target the wrong branch:

```bash
zsh scripts/ops/with_preview_env.sh \
  uv run python scripts/pipeline/migrate_db.py --database-env DATABASE_URL
zsh scripts/ops/with_preview_env.sh make readiness \
  YEAR=2026 WEEK=0 AS_OF=YYYY-MM-DD ENV=preview
```

The wrapper injects `PREVIEW_DATABASE_URL` for Preview pipeline operations and
the migration-only `DATABASE_URL` for the explicit migration command. Verify
the branch before applying migrations. Never use the
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
a team with completed 2026 games lacks current-season features, or the projected
ratings generation is absent, incomplete, ambiguous, or stale. `prepare-week`
uses the database branch selected by `ENV`; there is no offline rating bypass.
This gate protects `prepare-week`. The separate V5 weekly operator binds its
forecast to independently verified rating evidence; its `prepare` component
is a prediction-artifact step, not the `prepare-week` Gold operation.

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

Each invocation runs through `python -m cks_picks_cfb.ops`, creates a new run-specific R2 prefix, and records resumable steps in `ops.pipeline_steps`. Neon activation occurs in one transaction only after predictions validate. Missing lines are allowed for an early progressive publish; the site shows the model output with “Line unavailable—model prediction shown, no lean.” Follow the [weekly close/open and freeze checklist](v5_weekly_operator.md#weekly-close-open-and-freeze-checklist): reconcile source, Silver, and published spread/total coverage against every scheduled FBS game, then recheck source availability before release and freeze. A published null line may reflect an older capture even when the provider now has a line.

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
5. Unified no-bet rule: an edge below 1.0 point publishes no lean and no
   side for either target (`Spread Bet`/`Total Bet` = "No Bet"; lean columns
   `null`). Sub-1.0 targets keep their quote selection (lineage for the
   displayed market point) but receive no grade. Totals in [1.0, 1.5) keep
   their displayed side but stay ungraded (lean-only zone); the total grade
   threshold remains 1.5. Label thresholds come from the weekly config
   (`spread_edge_threshold`, `total_lean_threshold`); the artifact bet
   labels are authoritative for published leans.

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
