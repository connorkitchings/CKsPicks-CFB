# 2026 Data Platform

## Authority boundaries

- R2 is authoritative for immutable provider captures, normalized datasets, model bundles, season runs, verification reports and serving projections. Local disks are explicit scratch/cache space; no implicit local `./data` root or mutable latest dataset is permitted.
- Neon `catalog` records captures, exact dataset versions, lineage and quality results. Neon `ops` retains source/build attempts and reconciliation history.
- Neon `public.season_releases` is the active season-serving authority. Its unique active row per `(environment, season)` binds the active week, model/revision/grading-policy identities, code/config identities, run manifest and verification checksums. Release-scoped projection tables provide one consistent website snapshot.
- `season_release_history` records activation and rollback transitions. Legacy `current_week`, `prediction_runs` and selected-week records remain readable fallback/history when there is no active season release; they do not override an active release.
- The web application has read-only access and uses Drizzle over Neon HTTP. See the [weekly runbook](../ops/weekly_runbook.md) for environments, credentials and operations, and [Current Status](../status.md) for active identities.

## Immutable capture and build contracts

```text
lake/bronze/provider=cfbd/entity=<entity>/content_sha=<sha>/data.parquet
lake/bronze/provider=cfbd/entity=<entity>/content_sha=<sha>/observations/<capture>.json
lake/silver/dataset=<dataset>/version=<version>/data.parquet
lake/gold/dataset=<dataset>/version=<version>/data.parquet
```

Identical provider payloads reuse a content object but create distinct observation records. New v2 dataset identities bind content, explicit parents, normalized cutoff, partitions, schema, code and configuration; parent URIs are excluded. V1 manifests remain historical evidence. Dataset reads verify SHA-256 before decoding. Failed validation does not publish a canonical lake object or manifest. `DatasetRef`, `SourceCapture`, `BuildRequest`, `MarketQuote` and `MarketSnapshot` define the lake interfaces.

The revision builder resolves the registered Preview capture inventory into explicit schedule, finals, by-play, drives, reconciliation and cumulative market refs. It records truthful capture times and pins exact score-reconciliation exceptions. The prepared run does not silently pick the latest dataset by creation time. A changed manifest or code identity can change provenance strings even when football business content is identical; parity comparisons may normalize only documented provenance identities, never market selections or grades.

Canonical schedule policy preserves `provider_week` and assigns canonical weeks through versioned game-ID mappings. Source lineage retains provider labels; the website and controller use canonical weeks.

## Football model and market separation

V5 uses the sealed model manifest, through-2025 fit and earlier-only observations. Its development seasons are 2015–2019 and 2021–2025, with 2020 excluded. `season_verification_v2` verifies earlier-week cutoffs, no refit, no market fields in features, paired predictions, checksums, exact reconciliation and serving integrity. V4's old ten-route `model_bundle_v3` interface is historical; see the [V4 retrospective](../modeling/v4_retrospective.md).

Retained pre-kickoff quotes have precedence per game-target; only completed non-live targets may use an explicitly supplied CFBD retrospective fallback. Direction comes from the canonical target snapshot and grading shops the best linked quote for that side. Quote timestamps, prices, benchmark class and lineage remain recorded. Missing eligible quotes leave targets ungraded. See [record methodology](../modeling/record_methodology.md).

Untimestamped exports remain quarantined as `legacy_market_references` with `exact_replay_eligible=false`, `grading_eligible=false`, `lean_eligible=false` and `timestamp_status=missing_authentic_timestamp`. They cannot masquerade as retained canonical quotes or enter model features; a separately declared retrospective benchmark must retain its provenance class.

## Database and release lifecycle

`contracts/schema.sql` reconstructs the current schema. Existing databases apply append-only `contracts/migrations/` via `scripts/pipeline/migrate_db.py`; `schema_migrations` pins checksums and rejects rewritten history. Objective finals remain distinct from target/line-dependent grades. In the controller path, release-scoped grades and summaries are the serving source; legacy `prediction_grades` and `system_stats` are fallback/history only.

The supported sequence is revision build → commit inputs → prepare from a clean tree → verify → stage/release in Preview → exact approved Production release. A commit between prepare and release invalidates the prepared code identity. Activation switches the complete season atomically; Production requires matching Preview proof. The restricted pipeline login stages and activates through guarded database interfaces, while owner rollback uses the separate owner credential. Legacy publish/freeze/close writers are not the weekly operating path.

Release IDs in the database are environment-prefixed; the controller accepts bare `season-2026-...` IDs and normalizes them for the explicit environment, refusing a mismatched prefix. `season_releases` enforces one active release per environment and season. Signed on-demand Vercel revalidation refreshes caches after activation; five-minute ISR remains the fallback.

The August 18 lake/bootstrap and V4 launch are historical milestones in the [launch contract](../plans/2026-08-18/week0-launch-execution.md). The October 14 controller cutover supersedes that per-week serving design; its first weekly update remains an acceptance requirement in the [season operations contract](../plans/2026-10-14/01-season-operations-and-week7-bridge.md).
