# 2026 Data Platform

## Authority boundaries

- R2 is authoritative for immutable provider captures, normalized datasets,
  feature/evaluation datasets, model bundles, prediction runs, and scored files.
- Neon `catalog` selects exact dataset versions and stores lineage/quality results.
- Neon `ops` owns pipeline attempts, step resumption, waivers, activation history,
  and reconciliation. `current_week` and `prediction_runs` are the only active and
  frozen run authority.
- Neon `public` is the derived serving model. The web application has read-only
  access and continues to use Drizzle over Neon HTTP.
- Local disks are explicit scratch/cache space only. Production code may not infer
  a local `./data` root or read a mutable latest dataset.

## Immutable paths

```text
lake/bronze/provider=cfbd/entity=<entity>/content_sha=<sha>/data.parquet
lake/bronze/provider=cfbd/entity=<entity>/content_sha=<sha>/observations/<capture>.json
lake/silver/dataset=<dataset>/version=<version>/data.parquet
lake/gold/dataset=<dataset>/version=<version>/data.parquet
artifacts/<environment>/models/<bundle>/manifest.json
artifacts/<environment>/predictions/year=<year>/week=<week>/run_id=<run>/
artifacts/<environment>/scored/year=<year>/week=<week>/run_id=<run>/
```

Identical provider payloads reuse one content object but create distinct observation
records. Silver and Gold version IDs include content, explicit parent refs, cutoff,
schema, code SHA, and config SHA. A rebuild with identical inputs reuses the version.

## Data contracts

`cks_picks_cfb.data.lake` defines `DatasetRef`, `SourceCapture`, `BuildRequest`,
`MarketQuote`, and `MarketSnapshot`. Dataset reads verify SHA-256 before decoding.
Corrupt partition objects are copied to `lake/quarantine/` and fail the operation.

`SourceAdapter` is provider-neutral. CFBD is the only Week 0 adapter; retry is
bounded with exponential backoff and jitter, failures are classified, and incomplete
pagination fails closed. R2 ingestion dual-write defaults on for the R2 backend.
Set `CFB_REQUIRE_CATALOG=1` in production so capture registration cannot be skipped.

Market policy `consensus_then_median_v1` selects spread and total independently:
valid CFBD Consensus first, otherwise the median of each provider's newest valid
quote. Every quote remains in Bronze; the selected quote IDs, rule, provider counts,
and deterministic snapshot ID travel with the prediction.

## ML inputs and bundles

Production `model_bundle_v2` inference requires:

- All ten spread/total × 0/1/2/3/4+ routes.
- Durable artifact URIs and checksums for every route.
- Explicit feature lists with bookmaker-derived columns rejected by contract.
- Monotone spread and total prior weights for completed-game counts 0–4.
- Exact Gold training feature refs in the model bundle. Weekly Silver/Gold refs are
  catalog-selected and frozen in the pipeline-run manifest.
- Labeled training years 2021–2025, with 2019 allowed only as the early-2021 prior
  source and 2020 excluded from all data lineage.

The generator reads those refs via checksum verification and records them in the
prediction-run manifest and `prediction_runs.input_dataset_refs`. MLflow and local
model paths are development-only; production fails without durable artifacts.

## Database changes

`contracts/schema.sql` is the reconstructed current schema. Existing databases use
the append-only files in `contracts/migrations/`; `scripts/pipeline/migrate_db.py`
records checksums in `schema_migrations` and rejects edited history.

`game_results` holds objective outcomes. `prediction_grades` holds line-dependent
spread/total grades keyed by run, game, and target. Records and ROI derive from the
selected scored run per week, never from one global grade on a game.

Group roles are created for least privilege: `cks_web` (read), `cks_pipeline`
(operational writes), and `cks_migrator` (DDL). Deployment login roles should inherit
exactly one group role.

## Weekly state machine

```bash
python -m cks_picks_cfb.ops readiness ...
python -m cks_picks_cfb.ops publish-week ...
python -m cks_picks_cfb.ops freeze-week ...
python -m cks_picks_cfb.ops close-week ...
python -m cks_picks_cfb.ops replay-season ...
python -m cks_picks_cfb.ops reconcile ...
python -m cks_picks_cfb.ops audit-data ...
```

Each command takes one advisory lock per environment/season/week and records durable
step attempts. Resume with the same `--pipeline-run-id`; completed idempotent steps
are skipped. Prediction run IDs are chosen before generation and passed through every
later step. R2 objects are staged first, and activation is a Neon transaction.

Set `CFB_REVALIDATION_URL` and `REVALIDATION_SECRET` for signed on-demand Vercel
revalidation. The site's five-minute ISR remains the fallback.

## Deployment sequence

1. Apply migrations on an isolated Neon branch with `make migrate-db`.
2. Enable R2 dual-write and compare Bronze/Silver/Gold keys, schemas, counts, and
   hashes for 2021–2026.
3. Publish a complete preview `model_bundle_v2`; each run selects its own dataset refs.
4. Rehearse Weeks 0–5 for 2021–2025, then all of 2025, using the preview bucket,
   Neon branch, and Vercel Preview.
5. Promote credentials/configuration only after row/grade equivalence and crash,
   resume, freeze, waiver, and reconciliation tests pass.

Legacy serving columns/views remain available through the first successfully closed
2026 week. No new production run may depend on them.
