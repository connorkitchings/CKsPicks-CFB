# Project File Map

> **Quick navigation guide for the CKsPicks-CFB codebase**
>
> Find files fast. Know where things live.
>
> _Regenerated 2026-08-19 against the actual tree._

---

## Project Root

```
CKsPicks-CFB/
├── AGENTS.md                    # 👈 START HERE - Universal AI assistant guide
├── CLAUDE.md                    # Redirect to AGENTS.md
├── GEMINI.md                    # Redirect to AGENTS.md
├── README.md                    # User-facing project overview
├── Makefile                     # All pipeline/web/ops targets (make help)
├── pyproject.toml               # Dependencies and tool config (uv)
├── nx.json / project.json       # Nx task runner (pipeline + web projects)
├── mkdocs.yml                   # Docs site
├── .env                         # Environment variables (create from .env.example)
└── .pre-commit-config.yaml      # Pre-commit hooks
```

---

## AI Assistant Files

```
.agent/                          # AI assistant workspace
├── CONTEXT.md                   # Project architecture and domain knowledge
└── skills/                      # Workflow automation
    ├── CATALOG.md               # Skills catalog
    ├── start-session/SKILL.md   # Session initialization
    ├── plan-session/            # Sol planning → implementation contracts
    │   ├── SKILL.md
    │   └── assets/implementation-contract-template.md
    ├── implement-plan/SKILL.md  # Terra contract execution
    └── end-session/SKILL.md     # Session cleanup

.codex/                          # Quick reference guides
├── QUICKSTART.md                # Essential commands
├── HYDRA.md                     # Hydra config guide
└── MAP.md                       # This file
```

---

## Source Code (`src/cks_picks_cfb/`)

```
src/cks_picks_cfb/
├── train.py                     # Canonical Hydra training entry point
├── model_bundle.py / model_bundle_v3.py   # Bundle manifests, loading, validation
├── preseason.py                 # Compatibility facade for focused preseason modules
├── preseason_features.py / preseason_matchups.py / preseason_blends.py
├── scoring.py / loader.py / artifacts.py
├── config/                      # champion.py, experiments.py
├── data/                        # Ingestion + lake
│   ├── storage/                 # Storage abstraction (base, local, r2, factory)
│   ├── silver/                  # Silver layer (contracts, builders)
│   ├── the_odds_api.py          # Timestamped market quotes (canonical)
│   ├── sources.py / schema_contracts.py    # Typed source contracts
│   ├── lake.py / catalog.py     # Immutable Bronze/Silver/Gold + catalog registry
│   ├── history.py               # Historical bootstrap
│   ├── reconciliation.py        # Cross-source game reconciliation
│   ├── week_policy.py           # Canonical Week policy routing
│   ├── runtime.py               # ENV resolution + guards
│   └── games.py, plays.py, teams.py, venues.py, game_stats.py,
│       betting_lines.py, weather (ingest at scripts/pipeline/ingest_weather.py),
│       coaches.py, rosters.py, recruiting.py, rankings.py, ratings.py,
│       external_ratings.py
├── features/
│   ├── pipeline.py              # Feature engineering pipeline
│   ├── point_in_time.py         # Kickoff-ordered PIT loading + regime routing
│   ├── aggregations/            # Aggregations (drives, team_game, team_season, opponent_adj)
│   ├── byplay/                  # Play enrichment & data corrections (enrichment, corrections)
│   ├── core.py                  # Backward-compatible shim -> aggregations
│   ├── regimes.py / rolling_ewma.py  # Pure routing + point-in-time EWMA helpers
│   ├── weather.py / situational.py / external.py
│   ├── selector.py / persist.py
│   └── internal_ratings.py
├── models/
│   ├── regime_training.py       # Route candidates (Ridge/CatBoost/blend)
│   ├── game_ordinal_training.py # Games 1–4 ordinal tournament
│   ├── early_season.py / v4_feature_variants.py / baselines.py
│   ├── training_policy.py       # Result-only promotion + chronology guards
│   ├── promotion.py             # Predictive gates
│   ├── market_grading.py / predictive_evaluation.py
│   └── v1_baseline.py, v2_*.py  # Legacy V2-era variants (history)
├── ops/                         # Resumable state machine
│   ├── __main__.py              # python -m cks_picks_cfb.ops (publish/freeze/close/replay)
│   ├── state_machine.py / lease.py / data_audit.py
├── inference/                   # Weekly input, routing, edge, and manifest helpers
├── training/                    # train.py (regime training internals)
├── db/                          # migrations.py (applies contracts/migrations)
├── analysis/                    # unadjusted.py
├── utils/                       # validation.py (DataValidationService),
│                                # mlflow_tracking.py, model_registry.py,
│                                # lineage_tracking.py, local_storage.py, ...
└── flows/                       # Prefect-era flows (legacy)
```

---

## Scripts

```
scripts/
├── cli.py                       # Main CLI (ingest etc.)
├── data/                        # CFBD → R2/local ingestion CLIs
│   ├── ingest_season.py, ingest_week.py, ingest_preseason.py
│   └── estimate_historical_odds_backfill.py
├── ops/
│   └── with_preview_env.sh      # Preview Keychain DB wrapper
├── pipeline/                    # ~40 production pipeline scripts, incl.:
│   ├── preflight.py             # Weekly env/storage/DB checks
│   ├── migrate_db.py            # Append-only migrations (0002–0008)
│   ├── build_silver.py, build_history_silver.py, build_team_game_dataset.py,
│   │   build_temporal_matchups.py, build_regime_features.py,
│   │   assemble_model_ready_features.py, build_v4_preseason_feature_reference.py
│   ├── build_schedule_week_policy.py, build_week_market_snapshot.py
│   ├── generate_game_ordinal_candidates.py, evaluate_game_ordinal_predictions.py,
│   │   refit_game_ordinal_bundle.py, refit_regime_bundle.py,
│   │   generate_baseline_predictions.py, evaluate_regimes.py,
│   │   select_preseason_blend.py
│   ├── generate_weekly_bets.py  # Weekly predictions
│   ├── publish_to_db.py         # R2 artifact → Neon (--from-artifact)
│   ├── publish_model_artifact.py, publish_model_bundle_v2.py
│   ├── freeze_week.py, replay_season.py, refresh_game_outcomes.py
│   ├── score_to_db.py, score_weekly_bets.py, generate_system_stats.py
│   ├── export_cfbd_pickem.py    # CFBD Model Pick'em exporter
│   ├── ingest_weather.py, snapshot_week_inputs.py, cache_running_season_stats.py,
│   │   cache_weekly_stats.py, combine_history_versions.py, seed_data_corrections.py
│   └── compare_preview_model_bundles.py, publish_review.py
│       # Archived wrappers and legacy publishers live in scripts/archive/.
└── archive/                     # points_for, tests (historical)
```

---

## Configuration (`conf/`)

```
conf/
├── config.yaml                  # defaults: model=linear, features=matchup_v1,
│                                #   training=default, preprocessing=none
├── model/                       # linear, elastic_net, catboost_v1, xgboost_v1,
│                                #   champion, ensemble_v1, stacking_v1, catboost_classifier
├── features/                    # matchup_v1/v2/v2_pruned, opponent_adjusted_v1,
│                                #   recency_weighted_v1, extended_v1, interaction_v1,
│                                #   internal_*, cover_classifier_v1, ablation_baseline
├── experiment/                  # week0_regimes, preseason_regimes, v2_* (history), legacy/
├── training/                    # default, week0_2026 (frozen chronology)
├── weekly_bets/                 # v4_2026 (LAUNCH), v3_preview_games_ordinal_2026,
│                                #   v2_preview_2026, v2_champion
├── policy/                      # canonical_week_2026_v1.yaml (Week 0 game IDs)
├── preprocessing/ paths/ hydra/ sweeper/ research/ legacy/ validation.yaml
```

---

## Tests

```
tests/                           # 54 files — 355 passed / 2 skipped (2026-08-19)
├── test_migrations.py           # Empty + legacy schema migration validation
├── test_history_bootstrap.py    # Import resumability/checksums
├── test_silver_reconciliation.py
├── test_model_bundle_v3.py / test_game_ordinal_training.py
├── test_v4_feature_reference.py
├── test_legacy_market_references*.py  # Quarantine contract tests (17)
├── test_runtime_target.py, test_training_policy.py, test_aggregations_core.py, ...
└── fixtures/
```

Run: `uv run pytest -q` (or `make test`, or `npx nx run pipeline:test`).

---

## Contracts (single source of truth)

```
contracts/
├── schema.sql / schema.ts       # Canonical DB schema (web copies must sync)
├── teams.py / teams.ts          # Team-name mappings
├── validation.py                # make contracts-check
└── migrations/                  # Append-only: 0002_prediction_runs …
                                 # 0008_game_4_ordinal_regime
```

---

## Web App (`web/`)

```
web/
├── README.md                    # Local-dev + deployment guide
├── package.json                 # Own toolchain (npm); scripts: dev/build/lint/typecheck
├── db/migrations/               # 0001_init.sql + deprecated-location README
└── src/
    ├── app/                     # App Router: page.tsx, api/health/route.ts
    ├── components/              # Header, GameRow, LeanBadge, RecordBanner, WeekNav, ...
    └── lib/
        ├── db.ts / schema.ts    # Drizzle client + synced schema copy
        ├── publication.ts       # Fail-closed market/predictions boundary
        ├── queries.ts / teams.ts
```

---

## Documentation (`docs/`)

```
docs/
├── index.md                     # Documentation hub + MkDocs landing
├── architecture/                # data_platform_2026.md, cfbd_point_in_time_pipeline.md
├── ops/                         # weekly_pipeline.md, production_runbook.md,
│                                #   validation.md, mlflow_mcp.md
├── modeling/                    # rating_system_requirements.md,
│                                #   measurement_catalog.md, evaluation.md, V4 regime contract
├── planning/                    # roadmap.md (current 2026 transition)
├── plans/                       # 👈 Task-level Sol→Terra implementation contracts
│   ├── index.md                 # Lifecycle rules
│   └── 2026-08-18/week0-launch-execution.md   # ACTIVE (Stages 4–5)
├── decisions/                   # decision_log.md (read for rationale)
├── cfbd/                        # Provider audit
├── data/                        # Current ingestion/data orientation
├── project_org/ experiments/    # V4 feature and experiment lineage
├── archive/                     # Historical V2, research, plans, schemas
```

---

## Data & Artifacts (NOT in repo)

- **Durable data:** Cloudflare R2 immutable lake (`CFB_STORAGE_BACKEND='r2'`); buckets incl. `cks-picks-cfb-preview` (shared by preview + production artifact store).
- **Local dev fallback:** external drive via `CFB_MODEL_DATA_ROOT` (`CFB_STORAGE_BACKEND='local'`).
- **Working artifacts:** `artifacts/preview|production/...` (runs, refs, bundles, comparisons); MLflow tracking at `artifacts/mlruns/` (development only).
- **Never** create `./data/` in the project root.

---

## Find by Task

| Task | Go to |
|---|---|
| Weekly publish/freeze/close | `make publish-week` / `freeze-week` / `close-week` → `src/cks_picks_cfb/ops/` |
| Add a pipeline step | `scripts/pipeline/` + `Makefile` target |
| Change DB schema | `contracts/migrations/` (append-only) + `contracts/schema.{sql,ts}` → `make contracts-check` |
| Modify measurements | `src/cks_picks_cfb/features/` + `conf/features/` + `docs/modeling/measurement_catalog.md` |
| Train/tune models | `PYTHONPATH=src uv run python -m cks_picks_cfb.train` (`conf/experiment/`) |
| Regime/tournament logic | `src/cks_picks_cfb/models/regime_training.py`, `game_ordinal_training.py` |
| Model bundles | `src/cks_picks_cfb/model_bundle*.py`, `conf/weekly_bets/v4_2026.yaml` |
| Market quotes policy | `src/cks_picks_cfb/data/the_odds_api.py` + `legacy_market_references` contracts |
| Web publication modes | `web/src/lib/publication.ts` + `CFB_PUBLICATION_*` envs |
| Validate data | `make audit-data`, `src/cks_picks_cfb/utils/validation.py` |
| Health check prod | `GET https://c-ks-picks-cfb.vercel.app/api/health` |

---

_Last Updated: 2026-08-19_
