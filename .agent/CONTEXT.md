# Project Context

> **Domain Knowledge and Architecture for CKsPicks-CFB**
>
> This file contains project-specific context that AI assistants should understand when working with this codebase.

---

## Project Overview

A college football betting model that predicts point spreads and over/under
totals, published as weekly leans on a public Vercel web app.

**Domain:** Sports betting / predictive analytics
**Sport:** NCAA Division I FBS College Football
**Prediction Targets:** Point spreads, over/under totals (per completed-game regime)
**Data Sources:** CollegeFootballData.com API (games/plays/stats/preseason) + The Odds API (timestamped market quotes) + weather ingestion
**Time Period:** V4 uses its immutable 2021–2025 lineage. New data-first research
uses 2015–2019 and 2021–2025 as development evidence, excludes 2020, and relies
on future pre-kickoff freezes for independent evidence.
**Production:** https://c-ks-picks-cfb.vercel.app (Neon Postgres + Cloudflare R2)

---

## Architecture Overview (2026, as built)

### Data Platform: immutable Bronze/Silver/Gold lake

```
CFBD / The Odds API / weather
    ↓ hardened, fail-closed ingestion (point-in-time captures)
Bronze (src/cks_picks_cfb/data/) — immutable request-level captures,
    SHA-256 checksums, Neon catalog registry (7,163 captures)
    ↓ resumable builders (make build-silver / import-history)
Silver (src/cks_picks_cfb/data/silver/, history.py) — reconciled
    season-scoped teams/venues/schedules/games/plays/outcomes/weather/
    market_quotes + quarantined legacy_market_references
    ↓ kickoff-ordered point-in-time assembly
Gold / model-ready (scripts/pipeline/assemble_model_ready_features.py,
    build_temporal_matchups.py, build_v4_preseason_feature_reference.py)
    — regime-routed features + 2022–2024 OOF baselines
    ↓ sealed tournament → locked 2025 → unchanged refit
Model bundles (model_bundle.py, model_bundle_v3.py) — checksummed
    ten-route manifests in R2 (artifacts/preview|production/models/...)
    ↓ ops state machine (publish → freeze → close)
Neon Postgres (prediction_runs, predictions, games, game_results,
    system_stats, current_week + catalog/ops schemas) → Vercel (ISR 5-min)
```

Key invariants:

- R2 is the durable source of truth; Neon is the derived web-serving DB.
- `CFB_STORAGE_BACKEND='r2'` is the production path; `'local'` + `CFB_MODEL_DATA_ROOT` is the dev fallback. Never `./data/`.
- Untimestamped legacy betting lines live in `legacy_market_references` and can never produce leans, grades, ROI, model features, or selection input.
- 2020 is excluded from every input, label, fold, prior, and successor-v2
  artifact. The expanded 2015–2019 corpus is research-only; it does not alter
  V4's sealed lineage.
- Every mutating operation goes through `python -m cks_picks_cfb.ops` with an explicit `ENV`; failed steps activate nothing.

### Modeling: ten-route regime design

The production model evaluates spread and total **independently per
completed-game regime**: `game_1`, `game_2`, `game_3`, `game_4`, and
`established` (4+ completed games). A matchup uses the route of its
least-experienced team; each team keeps its own exposure count and
empirical-Bayes shrinkage weight. Legacy labels (`preseason`, `one_game`,
`two_games`, `three_games`) remain readable for historic artifacts only.

Chronology (frozen):

- Selection folds: train 2021→test 2022, 2021–2022→2023, 2021–2023→2024 (OOF).
- Locked test: train 2021–2024, evaluate 2025 once after the design SHA freezes.
- Production refit: unchanged design on 2021–2025.

Candidate families per route: prior-only baseline, direct Ridge, direct
CatBoost, points-derived Ridge/CatBoost, and frozen blends. Lowest OOF MAE
wins inside a 0.10 MAE tie ordered by simplicity; failed challengers revert
to the prior-only baseline. Market data never enters features or selection.

**Current production bundle (V4):** `week0-2026-v4-strict-20260818-r2`
(design SHA `ae34ddc7…`, config `conf/weekly_bets/v4_2026.yaml`). Selected
2026-08-18 via sealed tournament (4/8 challenger routes beat baseline);
locked-2025 anti-regression passed on all 8 routes. Uses the strict
point-in-time reference with `prior_core` features only
(`prior_only_fallback` — additive preseason families lacked pre-kickoff
effective-time evidence). All 8 Week 0 games route to `game_1`
(spread: direct CatBoost; total: prior-quality baseline fallback).
Model lineage: V2 preview (`week0-2026-preview-20260814`) → V3 games-ordinal
(`week0-2026-games-ordinal-v3-20260816-r2`) → V4 strict.

The as-built modeling flow is:

```text
immutable canonical data → team-game measurements → recency aggregation
→ iterative opponent adjustment → point-in-time matchup features
→ empirical-Bayes shrinkage → V4 regime routing → spread/total prediction
→ market edge and publication
```

These foundations are reusable, but team quality is implicit across adjusted
measurements, priors, shrinkage, and route-specific prediction models. The
canonical intermediate product is a matchup feature row rather than a durable
team-state estimate. Predictive uncertainty is not yet modeled; weekly
inference emits null spread and total standard-deviation fields.

### Approved direction: data-first football forecasting

V4 remains the unchanged 2026 production champion and benchmark. The approved
target architecture is:

```text
verified data → validated football measurements → opponent adjustment
→ simple offense/defense ratings + uncertainty → spread/total forecasts
→ prospective evaluation → timestamped line comparison
```

Ratings will become the canonical offense, defense, overall-quality, and
uncertainty-bearing representation of team strength. Priors dominate when
evidence is sparse and observed performance gains credibility continuously;
the long-term design does not change modeling philosophy at hard completed-game
boundaries. Initial opponent adjustment remains upstream of rating estimation,
and later rating-assisted adjustment is a separately attributable challenger.

Development remains isolated from production activation. Completed R1/R2,
candidate-v1, and direct early-game work are historical evidence subject to the
data-first audit; the former R3/R4 sequence is superseded. The active sequence
is repository alignment, data audit and repair, measurement validation, simple
ratings, spread/total forecasting, and frozen prospective evaluation. Each
candidate must freeze before inspecting eligible future outcomes. Football-only
inputs may be admitted only when their preseason meaning, coverage, and timing
are proved; timestamped markets are comparison evidence after football-model
evaluation. See the data-first roadmap and modeling authority docs.

### Feature Engineering

- **Opponent adjustment:** iterative additive normalization (`adjustment_iteration`, typically 2–4) with league-mean centering.
- **Point-in-time correctness:** `src/cks_picks_cfb/features/point_in_time.py` — kickoff-ordered team-side views; no future leakage.
- **Regime routing:** completed-game counts per team; separate prior (preseason) and current-season blocks; empirical-Bayes shrinkage toward prior by exposure (plays/drives/games grids).
- **Naming:** `{home|away}_{off|def}_{metric}[_adj{N}][_last{M}]`; keep `season`, `week`, `game_id`, `team` keys.
- **Weather:** outdoor-game integrations via `features/weather.py`.
- Full catalog: `docs/modeling/measurement_catalog.md`; requirements:
  `docs/modeling/rating_system_requirements.md`; registry:
  `docs/project_org/feature_registry.md`.

### Configuration (Hydra)

```
conf/
├── config.yaml            # defaults: model=linear, features=matchup_v1,
│                          #   training=default, preprocessing=none, hydra=default
├── model/                 # linear, elastic_net, catboost_v1, xgboost_v1,
│                          #   champion, ensemble_v1, stacking_v1, catboost_classifier
├── features/              # matchup_v1/v2*, opponent_adjusted_v1, recency_weighted_v1,
│                          #   extended_v1, interaction_v1, internal_*, cover_classifier_v1
├── experiment/            # week0_regimes, preseason_regimes, v2_* (history), legacy/
├── training/              # default, week0_2026 (frozen chronology)
├── weekly_bets/           # v4_2026 (launch), v3_preview_games_ordinal_2026,
│                          #   v2_preview_2026, v2_champion
├── policy/                # canonical_week_2026_v1 (Week 0 game-ID assignments)
├── preprocessing/ paths/ hydra/ sweeper/ research/ legacy/
└── validation.yaml
```

Override patterns: `model=catboost_v1`, `features=matchup_v2`,
`experiment=week0_regimes`, `+key=value` to add, `~key` to delete. Debug with
`PYTHONPATH=src uv run python -m cks_picks_cfb.train --cfg job --resolve`.
See `.codex/HYDRA.md` for the full guide.

---

## Data Storage

### Durable store: Cloudflare R2 immutable lake (`CFB_STORAGE_BACKEND='r2'`)

- Bronze/Silver/Gold datasets as Parquet with SHA-256 checksums, registered in the Neon `catalog` schema with dataset versions.
- Buckets: preview `cks-picks-cfb-preview` (production R2 credentials point at the same bucket — immutable artifacts are environment-neutral; environment separation is by Neon branch).
- Weekly run artifacts: `artifacts/{preview|production}/...` (predictions, scored runs, refs, model bundles) — reproducible from run IDs.
- Local `artifacts/preview/` holds only working copies; durable refs live in R2.

### Dev fallback: local backend (`CFB_STORAGE_BACKEND='local'`)

Reads/writes the external drive at `CFB_MODEL_DATA_ROOT`
(`/Volumes/CK SSD/Coding Projects/cfb_model/`). Legacy layout
(`raw/`, `aggregated/`, `features/adj_iter_*`) is research-compat only.

### Web-serving: Neon Postgres

`games`, `game_results`, `system_stats`, `current_week` (web schema) +
`catalog`/`ops` schemas + `prediction_runs`/`predictions`. Append-only
migrations `contracts/migrations/0002`–`0008` via `make migrate-db ENV=...`.
Branches: `preview-2026` and production. Web access uses the read-only
`cks_prod_web` role.

---

## Key Modules (actual paths)

| Area | Path |
|---|---|
| Ingestion adapters (CFBD, Odds API, weather) | `src/cks_picks_cfb/data/` (`sources.py`, `the_odds_api.py`, `runtime.py`) |
| Lake/catalog/reconciliation | `src/cks_picks_cfb/data/` (`lake.py`, `catalog.py`, `history.py`, `silver/`, `reconciliation.py`, `week_policy.py`) |
| Features | `src/cks_picks_cfb/features/` (`pipeline.py`, `point_in_time.py`, `aggregations/`, `byplay/`, `weather.py`, `situational.py`) |
| Regime/game-ordinal training | `src/cks_picks_cfb/models/` (`regime_training.py`, `game_ordinal_training.py`, `early_season.py`, `v4_feature_variants.py`, `baselines.py`, `training_policy.py`, `promotion.py`) |
| Market grading / evaluation | `src/cks_picks_cfb/models/` (`market_grading.py`, `predictive_evaluation.py`) |
| Bundles | `src/cks_picks_cfb/model_bundle.py`, `model_bundle_v3.py` |
| Ops state machine | `src/cks_picks_cfb/ops/` (`__main__.py`, `state_machine.py`, `contracts.py`, `notifier.py`, `lease.py`, `data_audit.py`) |
| Inference | `src/cks_picks_cfb/inference/weekly.py` + `scripts/pipeline/generate_weekly_bets.py` |
| Canonical training entry | `src/cks_picks_cfb/train.py` (Hydra) |
| Migrations | `src/cks_picks_cfb/db/migrations.py` + `contracts/migrations/` |
| Pipeline CLIs | `scripts/pipeline/` (~40 scripts: preflight, publish/freeze/close, silver/gold builders, tournament, refit, pickem export) |
| Validation service | `src/cks_picks_cfb/utils/validation.py` (`conf/validation.yaml`) |

Legacy V2-era model variants (`v1_baseline.py`, `v2_*.py`) are retained for
experiment history under `conf/experiment/v2_*` and `conf/legacy/`.

---

## Testing

- Full source-scope, branch-aware coverage gate is **60%**; the latest verified
  closure run recorded **414 passed, 2 skipped** and 60.02% coverage (2026-08-23).
- Coverage of: routing/edge cases (byes, cancellations, legacy labels), lake immutability + checksums, legacy-market quarantine (17 contract tests), migrations (empty + legacy schemas), publication fail-closed boundary (`web`), ops state machine, bundle loading.
- Quality gates: `uv run ruff format . && uv run ruff check .`, `uv run python contracts/validation.py`, `uv run mkdocs build --quiet`, `make contracts-check`, web lint/typecheck/build.
- Pattern: minimal fixtures, edge cases (empty DataFrames, single rows, missing columns); see existing tests in `tests/` for templates.

---

## Production Workflow (weekly cycle)

```bash
# Pregame: refresh schedule/lines → capture markets → predict → R2 artifact → Neon
make publish-week YEAR=2026 WEEK=0 AS_OF=<ts> ENV=production CONFIG=conf/weekly_bets/v4_2026.yaml

# Freeze the validated active run before kickoff (grades freeze against it)
make freeze-week YEAR=2026 WEEK=0 ENV=production

# Postgame: refresh finals → immutable outcomes → scored artifact → system_stats
make close-week YEAR=2026 WEEK=0 AS_OF=<ts> ENV=production

# Before a later week, rebuild cumulative 2026 Silver/Gold in Preview first
make prepare-week YEAR=2026 WEEK=1 AS_OF=<ts> ENV=preview
```

- Every mutating op runs through `python -m cks_picks_cfb.ops` with explicit `ENV`; failed steps activate nothing.
- `AS_OF` must be set ~5 minutes ahead of the publish run so the market capture falls before the cutoff.
- Publication modes: `market` (fail-closed, no model output) vs `predictions`.
  Production currently uses the explicitly approved `predictions` mode; every
  other value remains fail-closed.
- Health: `GET /api/health` (schema version, active run state, predicted/lined coverage, freshness).
- Pick'em export: `make export-pickem` (submission needs `CFBD_PREDICTION_TOKEN` + explicit approval).
- Rollback: frozen runs are immutable; reselect `current_week.active_run_id` to a prior frozen run. See `docs/ops/production_runbook.md`.

---

## Key Concepts

- **Point-in-time correctness:** only information available before kickoff may produce features; strict vs. reconstructed V4 reference tracks encode this (`docs/modeling/early_season_regimes.md`).
- **Opponent-adjusted stats:** raw stats are normalized against opponent quality via iterative additive adjustment.
- **Sealed selection:** candidates are chosen on 2022–2024 OOF only; the 2025 locked test runs once against a frozen design SHA; the unchanged design is refit on 2021–2025.
- **Fail-closed publication:** missing data, failed gates, or unapproved modes must degrade to display-only, never to inferred or leaked model output.
- **Kelly criterion / betting policy:** policy is documentation-first (`docs/modeling/betting_policy.md`); the 2026 site is display-only (post-MVP: auth/tracking).

---

_Last Updated: 2026-08-23_
_Domain knowledge and architecture reference_
