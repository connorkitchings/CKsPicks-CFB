# CFB Model Guide — Single Source of Truth

**Last Updated**: 2026-08-19  
**Status**: Active — 2026 Week 0 launch (production live)

This is the canonical entry point for all project documentation. All other docs link here or are linked from here.

---

## 🎯 2026 Season Execution

**Status**: Buildout complete — production live; game-week operations remain.
See [Roadmap](planning/roadmap.md) and the active
[Week 0 Launch Contract](../plans/2026-08-18/week0-launch-execution.md)
(Stages 4–5 pending game week).

The 2026 season followed a 6-phase execution plan to launch a live Vercel web
app showing every FBS game's spread + total lean by August 29 Week 0:

1. **Phase 1: Encode Adjudications** ✅ — Legacy market quarantine + canonical Week 0 policy
2. **Phase 2: Historical Bootstrap** ✅ — 7,156 eligible objects imported to preview R2/Neon (2026-08-13)
3. **Phase 3: Silver Reconciliation** ✅ — Games reconciled across sources (2026-08-14)
4. **Phase 4: Gold + Baselines** ✅ — Temporal OOF predictions for 2022–2024 (2026-08-14)
5. **Phase 5: Model Selection** ✅ — V4 ten-route bundle `week0-2026-v4-strict-20260818-r2` (2026-08-18)
6. **Phase 6: Week 0 Launch** 🟡 — Production live 2026-08-18 (`market` mode); game-week ops Aug 25–29

**Key Documents**:

- [Week 0 Launch Contract](../plans/2026-08-18/week0-launch-execution.md) — **Active** operations (Stages 4–5)
- [Execution Plan](planning/2026_historical_bootstrap_week0_execution.md) — 6-phase buildout (complete)
- [Roadmap](planning/roadmap.md) — Timeline and status
- [2026 Data Platform](architecture/data_platform_2026.md) — Immutable lake/catalog architecture
- [Early-Season Regimes](modeling/early_season_regimes.md) — Five completed-game routing contract
- [Weekly Pipeline](ops/weekly_pipeline.md) — Publish/freeze/close operations
- [Production Runbook](ops/production_runbook.md) — As-built production operations
- [Decision Log](decisions/decision_log.md) — Historical decisions

---

## 📖 Modeling Process Reference

The V2 4-phase experimentation workflow is retained as a modeling-process
reference. It is **not** the current operating framework — the 2026 execution
plan supersedes it for the 2026 season.

- [V2 Workflow](process/experimentation_workflow.md) — 4-phase modeling process (reference)
- [Promotion Framework](process/promotion_framework.md) — 5-gate rigor system
- [V2 Baseline](modeling/baseline.md) — Ridge regression philosophy

---

## 🚀 Quick Start

### First Time Here?

1. **Humans**: Read [Getting Started](#getting-started) below
2. **AI Assistants**: Start with `AGENTS.md` (repo root) for session protocols, then return here for domain knowledge

### I Need To...

| Task                           | Go To                                                                                             |
| ------------------------------ | ------------------------------------------------------------------------------------------------- |
| **Understand 2026 execution**  | [Execution Plan](planning/2026_historical_bootstrap_week0_execution.md)                           |
| **See current roadmap**        | [Roadmap](planning/roadmap.md)                                                                    |
| Set up development environment | [Getting Started](#getting-started)                                                               |
| Run the weekly pipeline        | [Weekly Pipeline](ops/weekly_pipeline.md)                                                         |
| Understand model routing       | [Early-Season Regimes](modeling/early_season_regimes.md)                                          |
| Run an experiment              | [Experiments](experiments/index.md) + [Promotion Framework](process/promotion_framework.md)       |
| Add a new feature              | [Feature Engineering](modeling/features.md) + [Feature Registry](project_org/feature_registry.md) |
| Review betting policy          | [Betting Policy](modeling/betting_policy.md)                                                      |
| Check recent decisions         | [Decision Log](decisions/decision_log.md)                                                         |
| Troubleshoot data issues       | [Data & Paths](ops/data_paths.md) + [Data Validation](ops/validation.md)                           |
| Run production operations      | [Production Runbook](ops/production_runbook.md)                                                  |
| Rollback a model               | [Production Runbook](ops/production_runbook.md) (frozen-run reselection)                          |

---

## 📖 Documentation Structure

### Process & Workflow

**How we work: development standards, ML workflow, AI collaboration**

- [ML Workflow](process/ml_workflow.md) — Train/Test/Deploy split, model versioning
- [Development Standards](process/development_standards.md) — Code style, testing, documentation
- [Experimentation Workflow](process/experimentation_workflow.md) - The V2 process for all modeling.
- [Data Quality Validation Workflow](process/data_quality_workflow.md) - Automated checks for data integrity.
- [Opponent-Adjustment Analysis Workflow](process/adjustment_analysis_workflow.md) - Process for validating adjustment iterations.
- [Session Checklists](process/checklists.md) — Kickoff and closing workflows
- [Session Logs](../session_logs/) — Chronological development history

### Data Pipeline Flow

1.  **Raw Ingestion** → Fetch from CollegeFootballData.com / The Odds API into immutable Bronze captures (R2 lake).
2.  **Silver Reconciliation** → Season-scoped teams, venues, schedules, games, plays, outcomes, weather, market quotes.
3.  **Gold Features** → Kickoff-ordered point-in-time, opponent-adjusted features with completed-game regime routing.
4.  **Modeling** → Ten-route V4 bundle (5 regimes × 2 targets), sealed selection + locked 2025 + 2021–2025 refit.
5.  **Inference & Publishing** → Weekly runs publish via the ops state machine → Neon → Vercel (fail-closed publication modes).

### Modeling & Features

**What we build: models, features, evaluation criteria**

- [Modeling Baseline](modeling/baseline.md) — Current production architecture
- [Feature Catalog](modeling/features.md) — All engineered features and definitions
- [Generated Feature Dictionary](modeling/feature_dictionary.md) - Auto-generated dictionary of all available features.
- [Feature Registry](project_org/feature_registry.md) — Active feature groups (Hydra configs)
- [Experiments Index](experiments/index.md) — Experiment tracking and results
- [Betting Policy](modeling/betting_policy.md) — Unit sizing, exposure rules, risk management
- [Calibration](modeling/calibration.md) — Model calibration and bias correction

### Operations

**How we run: pipelines, deployment, data management, monitoring**

- [Weekly Pipeline](ops/weekly_pipeline.md) — 5-step production workflow
- [Production Runbook](ops/production_runbook.md) — As-built production operations (Vercel/Neon/R2)
- [Production Deployment](ops/production_deployment.md) — Legacy V2 deployment doc (superseded)
- [Rollback SOP](ops/rollback_sop.md) — Legacy V2 rollback (superseded — see runbook)
- [Data Quality](ops/data_quality.md) — Legacy validation doc (superseded — see validation.md)
- [Data Validation](ops/validation.md) — `DataValidationService` usage
- [Data Paths & Storage](ops/data_paths.md) — Historical cleanup record; current storage is the R2 lake
- [MLflow Usage](ops/mlflow_mcp.md) — Experiment tracking (development only)

### Planning & Roadmap

**Where we're going: roadmap, active initiatives**

- [Project Roadmap](planning/roadmap.md) — High-level strategy and timeline
- [Active Initiatives](planning/) — Current research and development tracks
- [Implementation Contracts](plans/index.md) — Approved task-level Sol-to-Terra handoffs
- [Points-For Model (Archive)](archive/points_for_model.md) — Historical: rejected architecture

### Research

**Exploratory work: PRDs, prototypes, investigations**

- [Probabilistic Power Ratings](research/ppr_prd.md) — Bayesian team ratings (research; not adopted for 2026)
- [Power Ratings](research/power_ratings.md) — PPR overview (research; not adopted)

### Decisions

**Why we chose: decision history and rationale**

- [Decision Log](decisions/decision_log.md) — All major modeling and architecture decisions
- [Open Decisions (Archive)](archive/open_decisions.md) — Historical unresolved/planning decisions

---

## 🎯 Getting Started

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) for dependency management
- [Docker](https://www.docker.com/) for the MLflow tracking UI (development only)
- CollegeFootballData.com API key
- Cloudflare R2 credentials (production data path) or a local data drive (fallback)

### Installation

```bash
# Clone repository
git clone https://github.com/connorkitchings/CKsPicks-CFB.git
cd CKsPicks-CFB

# Install dependencies
uv sync --extra dev

# Activate environment
source .venv/bin/activate

# Configure environment
cp .env.example .env
# Edit .env and set:
#   CFB_STORAGE_BACKEND='r2' + CFB_R2_* credentials (or 'local' + CFB_MODEL_DATA_ROOT)
#   CFBD_API_KEY='your_api_key'

# Verify installation
uv run pytest -q
uv run ruff check .
```

### Essential Environment Variables

**CRITICAL**: Durable data lives in the Cloudflare R2 immutable lake
(`CFB_STORAGE_BACKEND='r2'`). The local backend
(`CFB_STORAGE_BACKEND='local'`) reads/writes an external drive and must never
create `./data/` in the project root.

```bash
# R2 backend (production path)
CFB_STORAGE_BACKEND='r2'
CFB_R2_BUCKET / CFB_R2_PREVIEW_BUCKET='your_bucket'
CFB_R2_ACCOUNT_ID / CFB_R2_ACCESS_KEY / CFB_R2_SECRET_KEY=...

# Local backend (dev fallback)
CFB_MODEL_DATA_ROOT='/Volumes/CK SSD/Coding Projects/cfb_model/'

# API access
CFBD_API_KEY='your_api_key_here'
```

---

## 🏗️ Project Architecture

### Directory Structure

```
CKsPicks-CFB/
├── src/                      # Library code (package: cks_picks_cfb)
│   ├── config/               # Path configuration, constants
│   ├── data/                 # Data ingestion and access
│   ├── features/             # Feature engineering pipeline
│   ├── models/               # Training, evaluation, prediction
│   ├── inference/            # Production inference
│   └── utils/                # MLflow, storage utilities
├── scripts/                  # CLI entry points
│   ├── pipeline/             # Production pipeline scripts
│   ├── analysis/             # Analysis and validation
│   ├── experiments/          # Research and optimization
│   └── cli.py                # Main CLI
├── docs/                     # Documentation (you are here!)
│   ├── guide.md              # This file (hub)
│   ├── process/              # How we work
│   ├── modeling/             # What we build
│   ├── ops/                  # How we run
│   ├── planning/             # Where we're going
│   ├── research/             # Exploratory work
│   ├── decisions/            # Why we chose
│   ├── experiments/          # Experiment tracking
│   └── archive/              # Historical/obsolete docs
├── conf/                     # Hydra configuration
│   ├── config.yaml           # Top-level defaults
│   ├── model/                # Model configs
│   ├── features/             # Feature set definitions
│   ├── experiment/           # Pre-packaged experiments
│   └── weekly_bets/          # Betting policy configs
├── tests/                    # Test suite
├── artifacts/                # V2 outputs (see docs/ops/artifacts_structure.md)
│   ├── mlruns/               # MLflow tracking
│   ├── models/               # Trained models (baseline, candidates, production)
│   ├── experiments/          # Experiment outputs (metrics, plots)
│   ├── production/           # Weekly predictions, scoring, monitoring
│   └── validation/           # Data quality, walk-forward validation
├── archive/                  # Unused scripts, configs, notebooks
├── session_logs/             # Development session history
├── AGENTS.md                 # Universal AI assistant entry point
├── CLAUDE.md                 # Redirect to AGENTS.md
└── README.md                 # Project overview
```

### Data Pipeline Flow

1. **Raw Ingestion** → Immutable Bronze captures (CFBD + The Odds API) in the R2 lake
2. **Silver Reconciliation** → Season-scoped canonical datasets
3. **Gold Features** → Point-in-time, opponent-adjusted, regime-routed
4. **Modeling** → Ten-route V4 bundle (sealed selection → locked 2025 → refit)
5. **Inference** → Weekly runs publish via the ops state machine → Neon → Vercel

See [Weekly Pipeline](ops/weekly_pipeline.md) for production workflow.

---

## 🎲 Current Production Model

**As of 2026-08-18**: the V4 ten-route bundle `week0-2026-v4-strict-20260818-r2`
(config `conf/weekly_bets/v4_2026.yaml`, design SHA `ae34ddc7…`).

| Property | Value |
| --- | --- |
| Routes | 10 (game_1–game_4 regimes × spread/total, plus established anchor) |
| Selection | Sealed 2022–2024 temporal OOF tournament |
| Locked test | 2025 (all 8 challenger routes passed anti-regression) |
| Production refit | 2021–2025 (unchanged design) |
| Features | `prior_core` only (`prior_only_fallback`; CFBD talent feed empty) |
| Week 0 routing | All 8 games → `game_1` (spread: direct CatBoost; total: prior-quality baseline) |

2025 betting simulation (research only, legacy quarantined lines): +17.9 units
combined (+3.1% ROI). Production is display-only in fail-closed `market` mode —
no high-confidence leans are published.

See [Early-Season Regimes](modeling/early_season_regimes.md) and the
[launch contract](../plans/2026-08-18/week0-launch-execution.md) for details.

---

## 🔧 Common Workflows

### Weekly Production Pipeline

```bash
# 1. Pregame publish: refresh schedule/lines → predict → R2 artifact → Neon
make publish-week YEAR=2026 WEEK=0 AS_OF=YYYY-MM-DD ENV=production CONFIG=conf/weekly_bets/v4_2026.yaml

# 2. Freeze before kickoff
make freeze-week YEAR=2026 WEEK=0 ENV=production

# 3. After games: score + stats
make close-week YEAR=2026 WEEK=0 ENV=production
```

See [Weekly Pipeline](ops/weekly_pipeline.md) and the
[Production Runbook](ops/production_runbook.md).

### Training a New Model

```bash
# Train with Hydra experiment config
PYTHONPATH=src uv run python -m cks_picks_cfb.train experiment=week0_regimes

# Debug configuration
PYTHONPATH=src uv run python -m cks_picks_cfb.train --cfg job --resolve
```

### Health Checks

```bash
# Format and lint
uv run ruff format . && uv run ruff check .

# Run tests
uv run pytest -q

# Build documentation
mkdocs build --quiet
```

---

## 📊 Key Performance Metrics

**Definitions** (see [Modeling Baseline](modeling/baseline.md)):

- **Hit Rate**: Percentage of correct predictions against the spread/total
- **Breakeven**: 52.4% hit rate required to profit at -110 odds
- **ROI**: Return on investment assuming -110 juice
- **Volume**: Number of bets meeting threshold criteria

**Historical status (2025 V2 live performance — legacy models, reference only)**:

- Spread: 50.1% hit rate (237-236-11) — Below breakeven ⚠️
- Total: 51.4% hit rate (95-90-0) — Below breakeven ⚠️

The 2026 V4 system is evaluated on predictive gates (MAE vs baseline) and
anti-regression, not market ROI (historical lines are quarantined). See
[Experiments Index](experiments/index.md).

---

## 🚨 Common Pitfalls

### 1. Data Not on External Drive

**Problem**: Script creates `./data/` in project root
**Solution**: Always load `CFB_MODEL_DATA_ROOT` from env; fail loudly if not set

### 2. Train/Test Data Leakage

**Problem**: Including test year in training data
**Solution**: Use expanding 2022–2024 selection folds, locked 2025 testing, then refit the frozen design on 2021–2025 for 2026.

### 3. Hardcoded Paths

**Problem**: Using `/Users/...` or `./data/`
**Solution**: Always use `os.getenv("CFB_MODEL_DATA_ROOT")`

### 4. Modifying Betting Policy in Code

**Problem**: Changing unit sizing or exposure rules programmatically
**Solution**: Only read and apply policy from [Betting Policy](modeling/betting_policy.md)

See [Data Paths](ops/data_paths.md) for full troubleshooting.

---

## 📚 Learning Paths

### New Developer

1. Read this guide → [Getting Started](#getting-started)
2. Review [Development Standards](process/development_standards.md)
3. Explore [Modeling Baseline](modeling/baseline.md)
4. Try running [Weekly Pipeline](ops/weekly_pipeline.md) on historical data

### Data Scientist / Researcher

1. Start with [Modeling Baseline](modeling/baseline.md) and [Feature Catalog](modeling/features.md)
2. Review [Experiments Index](experiments/index.md) for current state
3. Check [Decision Log](decisions/decision_log.md) for recent changes
4. Read [ML Workflow](process/ml_workflow.md) for train/test protocols

### AI Assistant

1. Read `AGENTS.md` for session protocols
2. Review this guide for navigation
3. Check [Session Checklists](process/checklists.md) for workflows
4. Always verify data root before ANY data operations

---

## 🔗 External Resources

- [Project Repository](https://github.com/connorkitchings/CKsPicks-CFB)
- [CollegeFootballData.com API](https://collegefootballdata.com/exporter)
- [MLflow Documentation](https://mlflow.org/docs/latest/index.html)
- [Hydra Configuration](https://hydra.cc/docs/intro/)

---

## 📝 Changelog

### 2025-12-04: Repository Reorganization

- Created `docs/guide.md` as single source of truth
- Reorganized docs into process/, modeling/, ops/, planning/, research/ buckets
- Created archive/ for unused scripts and configs
- Archived legacy decision log
- Purged stale artifacts (preserved 2025 Week 15 predictions)

### 2025-12-03: ML Workflow Standardization

- Fixed train/test split (removed 2024 from training)
- Retrained v5 models with proper split
- Created `docs/project_org/ml_workflow.md`

### 2025-12-01: PPR Prototype

- Implemented Probabilistic Power Ratings with Gaussian Random Walk
- Created backtest script for walk-forward validation

---

**Questions or issues?** Check the [Decision Log](decisions/decision_log.md) or create a session log entry.
