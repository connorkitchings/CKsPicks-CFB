# CFB Model Guide — Single Source of Truth

**Last Updated**: 2026-08-09  
**Status**: Active — 2026 Season Execution

This is the canonical entry point for all project documentation. All other docs link here or are linked from here.

---

## 🎯 2026 Season Execution

**Status**: Phase 1 complete, Phase 2 next — see [Execution Plan](planning/2026_historical_bootstrap_week0_execution.md) and [Roadmap](planning/roadmap.md).

The 2026 season follows a 6-phase execution plan to launch a live Vercel web app
showing every FBS game's spread + total lean by August 29 Week 0:

1. **Phase 1: Encode Adjudications** ✅ — Legacy market quarantine + canonical Week 0 policy
2. **Phase 2: Historical Bootstrap** ⬜ — Import 2021–2025 data to preview R2/Neon
3. **Phase 3: Silver Reconciliation** ⬜ — Reconcile games across sources
4. **Phase 4: Gold + Baselines** ⬜ — Temporal OOF predictions for 2022–2024
5. **Phase 5: Model Selection** ⬜ — Ten-route bundle for 2026
6. **Phase 6: Week 0 Readiness** ⬜ — Preseason snapshot + live rehearsal

**Key Documents**:

- [Execution Plan](planning/2026_historical_bootstrap_week0_execution.md) — 6-phase plan with exit gates
- [Roadmap](planning/roadmap.md) — Timeline and status
- [2026 Data Platform](architecture/data_platform_2026.md) — Immutable lake/catalog architecture
- [Early-Season Regimes](modeling/early_season_regimes.md) — Five completed-game routing contract
- [Weekly Pipeline](ops/weekly_pipeline.md) — Publish/freeze/close operations
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
| Troubleshoot data issues       | [Data & Paths](ops/data_paths.md) + [Data Quality](ops/data_quality.md)                           |
| Monitor model performance      | [Monitoring Dashboard](ops/monitoring.md)                                                         |
| Rollback a model               | [Rollback SOP](ops/rollback_sop.md)                                                               |

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

1.  **Raw Ingestion** → Fetch from CollegeFootballData.com API into local raw storage.
2.  **Aggregation** → Run `scripts/pipeline/run_pipeline_generic.py` to transform raw plays into aggregated `byplay`, `drives`, and `team_game` datasets in processed storage.
3.  **Validation** → Run `scripts/pipeline/validate_data.py` to verify the quality and integrity of the aggregated data.
4.  **Feature Engineering** → Generate point-in-time, opponent-adjusted features for modeling (`team_week_adj`).
5.  **Modeling** → Train models using the V2 Experimentation Workflow.
6.  **Inference** → Derive spreads/totals, calculate edges, and apply betting policy.

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
- [Production Deployment](ops/production_deployment.md) — Champion Model deployment (Phase 4)
- **[Monitoring Dashboard](ops/monitoring.md)** — **NEW:** Streamlit dashboard for performance tracking
- **[Rollback SOP](ops/rollback_sop.md)** — **NEW:** Model rollback procedure
- **[Data Quality](ops/data_quality.md)** — **NEW:** 3-layer validation system
- [Data Paths & Storage](ops/data_paths.md) — External drive configuration, partitioning
- [MLflow Usage](ops/mlflow_mcp.md) — Experiment tracking, model registry

### Planning & Roadmap

**Where we're going: roadmap, active initiatives**

- [Project Roadmap](planning/roadmap.md) — High-level strategy and timeline
- [Active Initiatives](planning/) — Current research and development tracks
- [Implementation Contracts](plans/index.md) — Approved task-level Sol-to-Terra handoffs
- [Points-For Model (Archive)](archive/points_for_model.md) — Historical: rejected architecture

### Research

**Exploratory work: PRDs, prototypes, investigations**

- [Probabilistic Power Ratings](research/ppr_prd.md) — Bayesian team ratings (active research)
- [Research Archive](research/archive/) — Completed or abandoned investigations

### Decisions

**Why we chose: decision history and rationale**

- [Decision Log](decisions/decision_log.md) — All major modeling and architecture decisions
- [Open Decisions (Archive)](archive/open_decisions.md) — Historical unresolved/planning decisions

---

## 🎯 Getting Started

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) for dependency management
- [Docker](https://www.docker.com/) for MLflow and dashboard services
- CollegeFootballData.com API key
- External storage drive (for data)

### Installation

```bash
# Clone repository
git clone https://github.com/connorkitchings/cfb_model.git
cd cfb_model

# Install dependencies
uv sync --extra dev

# Activate environment
source .venv/bin/activate

# Configure environment
cp .env.example .env
# Edit .env and set:
#   CFB_MODEL_DATA_ROOT='/path/to/external/drive'
#   CFBD_API_KEY='your_api_key'

# Verify installation
uv run pytest -q
uv run ruff check .
```

### Essential Environment Variables

**CRITICAL**: All raw and processed data lives on an external drive, NOT in the project directory.

```bash
# Required
CFB_MODEL_DATA_ROOT='/Volumes/CK SSD/Coding Projects/cfb_model/'  # External drive path
CFBD_API_KEY='your_api_key_here'                                   # API access

# Optional
MLFLOW_TRACKING_URI='file://./artifacts/mlruns'                    # MLflow storage
```

**Always verify before ANY data operation**:

```python
import os
from pathlib import Path

data_root = os.getenv("CFB_MODEL_DATA_ROOT")
assert data_root and Path(data_root).exists(), f"Data root not accessible: {data_root}"
```

---

## 🏗️ Project Architecture

### Directory Structure

```
cfb_model/
├── src/                      # Library code
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

1. **Raw Ingestion** → Fetch from CollegeFootballData.com API
2. **Aggregation** → Plays → Drives → Team-Game → Team-Season
3. **Feature Engineering** → Opponent adjustment, recency weighting, interactions
4. **Modeling** → Points-For architecture (predict home/away scores)
5. **Inference** → Derive spreads/totals, calculate edges, apply policy

See [Weekly Pipeline](ops/weekly_pipeline.md) for production workflow.

---

## 🎲 Current Production Models

**As of December 2025 (v5 models)**:

| Model                    | Target | Architecture                | Features    | Performance (2024 Test)    |
| ------------------------ | ------ | --------------------------- | ----------- | -------------------------- |
| `spread_catboost_ppr` v5 | Spread | CatBoost ensemble (5 seeds) | ppr_v1      | 52.2% hit rate (226-207-8) |
| `totals_xgboost_ppr` v5  | Total  | XGBoost ensemble (5 seeds)  | standard_v1 | 58.6% hit rate (112-79-4)  |

**Key Configuration**:

- Selection Years: 2022–2024 temporal OOF; locked test 2025; production refit 2021–2025
- Test Year: 2024 (locked holdout)
- Deploy Year: 2025 (live production)
- Adjustment Iteration: 2 (opponent adjustment depth)
- Thresholds: 5.0 (spread), 7.5 (total)

See [Modeling Baseline](modeling/baseline.md) for full details.

---

## 🔧 Common Workflows

### Weekly Production Pipeline

```bash
# 1. Ingest latest week data
uv run python scripts/pipeline/cache_weekly_stats.py --year 2025

# 2. Generate predictions
uv run python scripts/pipeline/generate_weekly_bets.py --year 2025 --week 16

# 3. After games: Score performance
uv run python scripts/pipeline/score_weekly_bets.py --year 2025 --week 16
```

### Training a New Model

```bash
# Train with Hydra experiment config
PYTHONPATH=src uv run python -m cks_picks_cfb.train experiment=spread_catboost_ppr_v1

# Hyperparameter optimization
PYTHONPATH=src uv run python -m cks_picks_cfb.train mode=optimize

# Debug configuration
PYTHONPATH=src uv run python -m cks_picks_cfb.train --cfg job --resolve
```

### Running Analysis

```bash
# Verify baseline performance
uv run python scripts/analysis/verify_baseline_2024.py

# Threshold optimization
uv run python scripts/analysis/optimize_thresholds.py --year 2024

# SHAP feature importance
uv run python scripts/analysis/run_shap_analysis.py
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

**Current Status (2025 Live Performance)**:

- Spread: 50.1% hit rate (237-236-11) — Below breakeven ⚠️
- Total: 51.4% hit rate (95-90-0) — Below breakeven ⚠️

See [Experiments Index](experiments/index.md) for detailed tracking.

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

- [Project Repository](https://github.com/connorkitchings/cfb_model)
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
