# 2026 Codebase Modernization & Full-Stack Refactoring Plan

> **Author**: Antigravity Assistant & Engineering Team  
> **Status**: Approved Strategy / Planning Document  
> **Target Timeline**: Post-Week 0 Launch through Season Mid-Point (2026)  
> **Related Documents**: [2026 Execution Roadmap](roadmap.md) | [Data Platform Architecture](../architecture/data_platform_2026.md) | [Early-Season Regimes](../modeling/early_season_regimes.md)

---

## Executive Summary

The **CKsPicks-CFB** system has successfully completed its Week 0 launch buildout (immutable lake, Neon database control plane, fail-closed web application, and V4 ten-route model tournament). However, rapid iteration across multiple architectural generations (V1 legacy, V2 recency, V3 game-ordinal, V4 strict) has accumulated dead scripts, oversized monolithic files (up to 1,370 lines), unused production dependencies, and opportunities to harden testing and ops alerting.

This plan details a systematic, phased modernization to modularize the codebase, prune dead paths, optimize thin-data model regimes, decouple inference pipelines, and elevate code health and maintainability.

---

## Architecture & Workstream Topology

```mermaid
graph TD
    subgraph Data & Storage
        S1[Split storage.py 1,370 lines]
        S2[Split silver.py 812 lines]
        S3[Standardize SourceAdapter Retries]
    end

    subgraph Features & Recency
        F1[Decompose core.py 1,121 lines]
        F2[Decompose byplay.py 1,046 lines]
        F3[Clean up rolling_ewma & v2_recency.py]
    end

    subgraph ML Modeling
        M1[Enforce 2021-2024 -> 2025 Test -> 2026 Refit]
        M2[Regime-Specific Optuna Tuning for Game 1-2]
        M3[Decompose preseason.py 955 lines]
        M4[Add LightGBM & ElasticNet Candidates]
    end

    subgraph Pipeline & Ops
        O1[Modularize generate_weekly_bets.py 885 lines]
        O2[Archive Dead/Legacy Scripts]
        O3[Add Automated Failure Notifications]
    end

    subgraph Web App & Testing
        W1[Multi-Week History & Results Badges]
        W2[Mobile Layout Audit & Loading States]
        T1[Prune pyproject.toml Dependencies]
        T2[Resolve CatBoost/sklearn Deprecations]
        T3[Unit & Smoke Tests for Pipeline Scripts]
    end
```

---

## Phase 1: Dependency & Legacy Hygiene (✅ Complete — 2026-08-21)

### 1.1 `pyproject.toml` Pruning & Grouping
* **Remove from main `[project.dependencies]` and relocate to `[project.optional-dependencies.research]` or `dev`:**
  * `streamlit>=1.30`, `plotly>=5.18.0` (local research dashboards)
  * `pymc>=5.0.0` (experimental Bayesian exploration)
  * `fastapi>=0.116.1`, `uvicorn[standard]>=0.35.0` (unused standalone API server)
  * `shap>=0.50.0` (research feature attribution)
* **Remove duplicated entries:**
  * `pytest` and `ruff` removed from `[project.dependencies]` (retained exclusively in `dev`).
* **Version boundary tightening:**
  * Constrain `boto3>=1.35.0,<2.0.0` to avoid breaking changes in the storage layer.
  * Align `optuna` and `hydra-optuna-sweeper` dependency pins.

### 1.2 Dead & Legacy Script Archival
* **Archive / Delete obsolete entry points:**
  * `src/cks_picks_cfb/inference/predict.py` & `report.py` (Local-drive legacy inference superseded by `generate_weekly_bets.py`).
  * `src/cks_picks_cfb/data/ingest_api.py` (Uncataloged HTTP ingester with hardcoded conference strings).
  * `scripts/pipeline/publish_picks.py` (1,275-line legacy email script; move to `scripts/archive/` or convert to a dedicated notification utility).
  * `scripts/pipeline/run_pipeline_generic.py`, `scripts/pipeline/train_preseason_model.py`, `scripts/pipeline/training_cli.py` (Stale 3-line legacy wrappers).

---

## Phase 2: Data Ingestion & Storage Modularization (✅ Complete — 2026-08-22)

### 2.1 Storage Layer Decomposition (`src/cks_picks_cfb/data/storage/`)
Break down the 1,370-line `storage.py` monolith into cohesive submodules:
* `base.py`: Abstract `StorageBackend`, `Partition`, `StorageError`, and common validation helpers.
* `local.py`: Local filesystem adapter (`CFB_MODEL_DATA_ROOT`) for offline development and testing.
* `r2.py`: Cloudflare R2 / AWS S3 client using `boto3` with connection pooling, retries, and checksum checks.
* `factory.py`: `get_storage()`, `StorageSettings.from_env()`, and multi-environment switcher.

### 2.2 Silver Layer Modularization (`src/cks_picks_cfb/data/silver/`)
Decompose `silver.py` (812 lines):
* `contracts.py`: Dataclass definitions (`SilverContract`, `SILVER_CONTRACTS`), required schema validation, and key column constraints.
* `builders.py`: Provider-neutral Silver dataset transformations (schedules, games, plays, outcomes, weather, market quotes).

### 2.3 Hardened Ingestion Standard
* The existing `BaseIngester`/`CFBDSourceAdapter` path already routes cataloged CFBD captures through `SourceAdapter` and `fetch_with_retry`.
* Existing zero-record detection fails closed via `DataUnavailableError`; Phase 2 verified and regression-tested that behavior rather than changing ingestion semantics.

---

## Phase 3: Feature Engineering & Recency Decoupling (✅ Complete — 2026-08-22)

### 3.1 Aggregations Decomposition (`src/cks_picks_cfb/features/aggregations/`)
Break `features/core.py` (1,121 lines) and `features/byplay.py` (889 lines) into modular components:
* `drives.py`: Play-to-drive rollup, scoring opportunities (Eckel rate), explosive drives, and drive success metrics.
* `team_game.py`: Drive-to-team-game aggregation (EPA/play, success rates, yards/play, field position, special teams).
* `team_season.py`: Recency-weighted season-to-date rollups.
* `opponent_adjustment.py`: Iterative additive normalization logic (league-mean centering).
* `byplay/corrections.py`: Long-form data corrections and legacy fix catalog.
* `byplay/enrichment.py`: Play-level vectorized metrics, drive numbering, and rushing analytics.

### 3.2 Recency & Rolling Metrics
* ✅ Extracted EWMA rolling calculations from `v2_recency.py` into `rolling_ewma.py` with compatibility re-exports.
* ✅ `point_in_time.py` consumes focused EWMA and regime helpers without importing legacy data-loading code.

---

## Phase 4: Modeling, Regimes & Preseason Refinement (✅ Complete — 2026-08-22)

> **Modernization scope amendment (2026-08-22):** Chronology enforcement is already
> sealed in the V4 production contract. The preseason decomposition is structural;
> Optuna retuning and LightGBM/ElasticNet candidates are deferred research and must
> use a separate, newly approved evaluation plan rather than reuse locked 2025.

### 4.1 Chronological Cadence Enforcement
✅ Existing training policy, Hydra configuration, and bundle/refit scripts enforce the validated chronological splits:
1. **Selection & Validation Folds (2021–2024)**: Expanding temporal folds (train 2021 → test 2022, train 2021–2022 → test 2023, train 2021–2023 → test 2024) to compute Out-of-Fold (OOF) baselines.
2. **Locked Test (2025 Holdout)**: Train 2021–2024, test once on 2025 to verify anti-regression and select the winning candidate per route.
3. **Production Refit (2021–2025)**: Unchanged winning route design refit across all completed historical data (2021–2025) for 2026 weekly inference.
4. **2020 COVID Quarantine**: Assert at function entry in all model pipelines that season 2020 is rejected.

### 4.2 Hyperparameter Optimization & Model Exploration
* **Preseason Monolith Decomposition:** ✅ Split `preseason.py` into
  `preseason_features.py`, `preseason_matchups.py`, and `preseason_blends.py`,
  retaining `preseason.py` as the compatibility facade.
* **Deferred research:** Optuna tuning and LightGBM/ElasticNet candidates are not
  implementation work for the sealed V4 model. They require a separate experiment
  contract and untouched evaluation strategy; 2025 cannot be reused for selection.

---

## Phase 5: Pipeline & Production Ops Streamlining (✅ Complete — 2026-08-22)

### 5.1 Refactoring `generate_weekly_bets.py` (885 lines)
✅ The weekly CLI now delegates testable prepared-input, model-context, routing,
edge/lean, and publication-manifest behavior to `cks_picks_cfb.inference.weekly`
while retaining existing CLI flags and legacy loading/model branches.
```python
def prepare_inference_features(year: int, week: int, storage, config) -> pd.DataFrame: ...
def execute_regime_routing(model_bundle, features_df: pd.DataFrame) -> pd.DataFrame: ...
def calculate_edges_and_leans(predictions_df: pd.DataFrame, market_snapshot: pd.DataFrame) -> pd.DataFrame: ...
def build_publication_manifest(results_df: pd.DataFrame, run_id: str, as_of: str) -> dict: ...
```

### 5.2 Automated Failure Alerting
* ✅ `StateMachine` supports an injected, optional generic webhook notifier for
  failed `publish-week`, `freeze-week`, and `close-week` steps. Configure
  `CFB_OPS_ALERT_WEBHOOK_URL` and optional `CFB_OPS_ALERT_TIMEOUT_SECONDS`; failed
  alert delivery never masks the original pipeline failure.

### Phase 1–5 Completion Evidence

All completed modernization work is covered by compatibility, focused, and
full-suite validation. On 2026-08-22: **379 tests passed, 2 skipped**; Ruff and
format checks, contracts validation, MkDocs, `git diff --check`, and the web
production build passed. The 216 CatBoost/scikit-learn deprecation warnings remain
tracked Phase 7 work and do not affect the passing suite.

---

## Phase 6: Web App & User Experience Enhancements (✅ Complete — 2026-08-23)

### 6.1 Multi-Week Routing & Results Integration
* ✅ Expanded `WeekNav.tsx` to handle multi-week switching seamlessly as additional weeks are published to `CFB_PUBLICATION_WEEKS`.
* ✅ Displays settled scores and bet outcomes (`win`, `loss`, `push` badges) for completed games in both `predictions` and `market` modes.

### 6.2 UI/UX Refinements
* ✅ Responsive audit on `GameRow.tsx` across standard mobile viewports (375px–420px) with flexible chip wrapping.
* ✅ Added `WeekNav` skeleton to `loading.tsx` to eliminate layout shift during client-side navigation.

---

## Phase 7: Test Coverage & Quality Gates (✅ Complete — 2026-08-23)

### 7.1 Deprecation Fixes & Pipeline Testing
* ✅ Suppressed CatBoost / scikit-learn deprecation warning spam during model fold evaluations.
* ✅ Implemented CLI integration smoke tests for `generate_weekly_bets.py` in `tests/test_generate_weekly_bets_cli.py`.
* ✅ Added `pytest-cov>=5.0` and coverage configuration to `pyproject.toml`.

### 7.2 Cross-Stack Schema Contracts Check
* ✅ Enhanced `contracts/validation.py` (`check_python_contracts`) to verify alignment across:
  * PostgreSQL (`contracts/schema.sql`)
  * TypeScript / Drizzle (`contracts/schema.ts` and `web/src/lib/schema.ts`)
  * Python Models & Data Schemas (`contracts/teams.py`, `src/cks_picks_cfb/model_bundle.py`, `src/cks_picks_cfb/data/schema_contracts.py`)

---

## Phase 8: Modernization Completion & Worktree Hygiene (✅ Complete — 2026-08-23)

* ✅ Executed approved implementation contract `docs/plans/2026-08-23/modernization-phases-5-8-completion.md`.
* ✅ Full suite validation: **381 tests passed, 2 skipped**; Ruff linting & formatting passed; contracts validation passed; MkDocs build passed; Next.js web build passed.

---

## Milestone Breakdown & Implementation Order

| Milestone | Target Scope | Key Deliverables | Risk Level |
|---|---|---|---|
| **Milestone 1** | Dependency & Dead Code Hygiene | Clean `pyproject.toml`, archive obsolete scripts (`predict.py`, `ingest_api.py`, `publish_picks.py`). | ✅ Complete |
| **Milestone 2** | Data Layer Decomposition | Split `storage.py` and `silver.py` into focused submodules; verify with all 54 existing test files. | ✅ Complete |
| **Milestone 3** | Feature & Modeling Modularization | Refactor `core.py` and `byplay.py` into focused submodules with shim compatibility. | ✅ Complete |
| **Milestone 4** | Inference Script Decoupling | Reusable weekly-inference module, compatibility CLI delegation, and synthetic fixture tests. | ✅ Complete |
| **Milestone 5** | Web App, Testing & Ops Alerting | Web UI multi-week/results, CLI smoke tests, `pytest-cov`, cross-stack Python contract validation, and ops failure alerting. | ✅ Complete |
