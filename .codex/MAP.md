# Project File Map

> **Quick navigation guide for CFB Model codebase**
>
> Find files fast. Know where things live.

---

## Project Root

```
cfb_model/
├── AGENTS.md                    # 👈 START HERE - Universal AI assistant guide
├── CLAUDE.md                    # Redirect to AGENTS.md
├── GEMINI.md                    # Redirect to AGENTS.md
├── README.md                    # User-facing project overview
├── REFACTORING_PLAN.md         # Current refactoring plan
├── pyproject.toml               # Dependencies and tool config
├── .env                         # Environment variables (create from .env.example)
├── .gitignore                   # Git ignore rules
└── .pre-commit-config.yaml     # Pre-commit hooks
```

---

## AI Assistant Files

```
.agent/                          # AI assistant workspace
├── CONTEXT.md                   # Project architecture and domain knowledge
└── skills/                      # Workflow automation
    ├── CATALOG.md               # Skills catalog
    ├── start-session/           # Session initialization
    │   └── SKILL.md
    └── end-session/             # Session cleanup
        └── SKILL.md

.codex/                          # Quick reference guides
├── QUICKSTART.md                # Essential commands
├── HYDRA.md                     # Hydra config guide
└── MAP.md                       # This file
```

---

## Source Code

```
src/
├── __init__.py
├── config.py                    # Path configuration and constants
│
├── data/                        # Data ingestion
│   ├── ingest_api.py           # Core API client
│   ├── plays.py                # Play-by-play data
│   ├── games.py                # Game results
│   ├── teams.py                # Team metadata
│   └── betting_lines.py        # Market lines
│
├── features/                    # Feature engineering
│   ├── pipeline.py             # Main aggregation pipeline
│   ├── core.py                 # Core aggregation functions
│   ├── byplay.py               # Play-level transformations
│   ├── weather.py              # Weather integration
│   ├── selector.py             # Feature selection
│   └── persist.py              # Caching layer
│
├── models/                      # ML models
│   ├── train_model.py          # Main training script (Hydra)
│   ├── features.py             # Feature loading
│   ├── betting.py              # Bet generation
│   ├── calibration.py          # Model calibration
│   └── ensemble.py             # Ensemble management
│
└── utils/                       # Utilities
    ├── __init__.py             # Package init
    ├── logging.py              # Structured logging
    ├── validation.py           # Data validation
    └── local_storage.py        # Storage abstraction
```

---

## Scripts

```
scripts/
├── pipeline/                    # Production pipeline
│   ├── train_production_points_for.py
│   ├── generate_weekly_bets.py
│   ├── score_weekly_bets.py
│   └── cache_running_season_stats.py
│
├── analysis/                    # Analysis tools
│   ├── compare_models.py
│   ├── run_shap_analysis.py
│   ├── analyze_calibration.py
│   └── generate_performance_report.py
│
├── experiments/                 # Research scripts
│   ├── optimize_hyperparameters.py
│   ├── run_points_for_experiment.py
│   └── run_feature_selection.py
│
├── debug/                       # Debugging utilities
│   ├── debug_features.py
│   ├── inspect_model.py
│   ├── list_models.py
│   └── check_data_columns.py
│
└── data/                        # Data management
    ├── ingest_plays.py
    ├── ingest_season.py
    └── regenerate_features.py
```

---

## Configuration

```
conf/
├── config.yaml                  # Main Hydra config
│
├── model/                       # Model configs
│   ├── catboost.yaml
│   ├── xgboost.yaml
│   ├── ridge.yaml
│   └── lgbm.yaml
│
├── features/                    # Feature sets
│   ├── standard_v1.yaml
│   ├── recency_v1.yaml
│   ├── pace_v1.yaml
│   └── spread_shap_pruned.yaml
│
├── experiment/                  # Experiments
│   ├── spread_catboost_baseline_v1.yaml
│   └── total_xgboost_v1.yaml
│
├── tuning/                      # Optuna search spaces
│   ├── catboost_optuna.yaml
│   └── xgboost_optuna.yaml
│
├── paths/                       # Data paths
│   └── default.yaml
│
└── weekly_bets/                 # Betting policies
    └── default.yaml
```

---

## Tests

```
tests/
├── test_aggregations_core.py        # Core aggregations
├── test_aggregate_drives_minimal.py # Drive aggregations (template)
├── test_validation.py               # Schema validation
└── fixtures/                        # Shared test data
    └── sample_data.parquet
```

---

## Documentation

```
docs/
├── guide.md                     # Documentation hub
│
├── modeling/                    # Modeling docs
│   ├── features.md             # Feature definitions
│   ├── betting_policy.md       # Unit sizing rules
│   ├── baseline.md             # V2 baseline philosophy
│   └── model_registry.md       # Model versioning
│
├── process/                     # Process docs
│   ├── experimentation_workflow.md  # V2 4-phase workflow
│   ├── promotion_framework.md       # 5-gate promotion system
│   └── 12_week_implementation_plan.md
│
├── ops/                         # Operations docs
│   ├── weekly_pipeline.md      # Production workflow
│   ├── monitoring.md           # Dashboard design
│   └── rollback_sop.md         # Rollback procedures
│
└── decisions/                   # Decision logs
    └── decision_log.md         # Historical decisions
```

---

## Session Logs

```
session_logs/
└── YYYY-MM-DD/                  # Daily sessions
    ├── 01-description.md
    ├── 02-description.md
    └── 03-description.md
```

**Convention:** `NN-brief-description.md` where NN is session number for that day.

---

## Artifacts

```
artifacts/
├── mlruns/                      # MLflow tracking
│   ├── 0/                      # Default experiment
│   └── 1/                      # Named experiments
│
├── models/                      # Serialized models
│   └── *.joblib
│
├── hydra_outputs/              # Hydra run outputs
│   └── YYYY-MM-DD/
│       └── HH-MM-SS/
│           └── .hydra/         # Config snapshots
│
└── reports/                    # Generated reports
    └── performance_YYYY_WW.html
```

---

## Data (External Drive/Cloud)

```
$CFB_MODEL_DATA_ROOT/
├── raw/                        # Raw API responses
│   ├── plays/
│   │   └── year=YYYY/
│   │       └── week=WW/
│   │           └── data.parquet
│   ├── games/
│   ├── teams/
│   └── betting_lines/
│
├── aggregated/                 # Aggregated products
│   ├── byplay/
│   ├── drives/
│   ├── team_game/
│   └── team_season/
│
├── features/                   # Feature caches
│   ├── adj_iter_2/
│   ├── adj_iter_4/
│   └── weekly_features/
│
└── models/                     # Production models
    └── home_points_catboost_v1.joblib
```

---

## Key File Locations

### Start Here

| File | Purpose |
|------|---------|
| `AGENTS.md` | Universal entry point for AI assistants |
| `.codex/QUICKSTART.md` | Essential commands |
| `.agent/CONTEXT.md` | Architecture and domain knowledge |
| `README.md` | User-facing project overview |

### Configuration

| File | Purpose |
|------|---------|
| `conf/config.yaml` | Main Hydra config |
| `.env` | Environment variables |
| `pyproject.toml` | Dependencies and tool config |

### Core Code

| File | Purpose |
|------|---------|
| `src/config.py` | Path configuration |
| `src/features/pipeline.py` | Feature engineering pipeline |
| `src/models/train_model.py` | Model training entry point |
| `src/models/betting.py` | Bet generation logic |

### Scripts

| File | Purpose |
|------|---------|
| `scripts/pipeline/train_production_points_for.py` | Train production models |
| `scripts/pipeline/generate_weekly_bets.py` | Generate predictions |
| `scripts/pipeline/score_weekly_bets.py` | Score performance |

### Documentation

| File | Purpose |
|------|---------|
| `docs/process/experimentation_workflow.md` | V2 4-phase workflow |
| `docs/modeling/features.md` | Feature definitions |
| `docs/modeling/betting_policy.md` | Unit sizing rules |

---

## Common File Patterns

### Find by Task

**Adding a new feature:**
- Computation: `src/features/core.py`
- Config: `conf/features/my_feature_v1.yaml`
- Tests: `tests/test_aggregations_core.py`
- Docs: `docs/modeling/features.md`

**Training a model:**
- Entry point: `src/models/train_model.py`
- Model config: `conf/model/catboost.yaml`
- Feature config: `conf/features/standard_v1.yaml`
- Experiment: `conf/experiment/my_experiment.yaml`

**Running production pipeline:**
- Train: `scripts/pipeline/train_production_points_for.py`
- Predict: `scripts/pipeline/generate_weekly_bets.py`
- Score: `scripts/pipeline/score_weekly_bets.py`

**Debugging:**
- Feature pipeline: `scripts/debug/debug_features.py`
- Model inspection: `scripts/debug/inspect_model.py`
- Data columns: `scripts/debug/check_data_columns.py`

**Analysis:**
- Model comparison: `scripts/analysis/compare_models.py`
- SHAP: `scripts/analysis/run_shap_analysis.py`
- Calibration: `scripts/analysis/analyze_calibration.py`

---

## Naming Conventions

### Files

- **Scripts:** `verb_noun.py` (e.g., `train_model.py`, `generate_bets.py`)
- **Tests:** `test_module.py` (e.g., `test_aggregations_core.py`)
- **Configs:** `noun_version.yaml` (e.g., `catboost.yaml`, `standard_v1.yaml`)
- **Docs:** `noun.md` (e.g., `features.md`, `betting_policy.md`)

### Session Logs

```
session_logs/YYYY-MM-DD/NN-brief-description.md
```

Example: `session_logs/2026-02-13/01-refactor-phase-0.md`

### Experiments

```
conf/experiment/{target}_{model}_{variant}.yaml
```

Example: `spread_catboost_baseline_v1.yaml`

---

## Quick Navigation

### From Root, Go To...

**Training:**
```bash
cd src/models/
vim train_model.py
```

**Features:**
```bash
cd src/features/
vim pipeline.py
```

**Configs:**
```bash
cd conf/
vim config.yaml
```

**Tests:**
```bash
cd tests/
vim test_aggregations_core.py
```

**Production Scripts:**
```bash
cd scripts/pipeline/
vim generate_weekly_bets.py
```

**Documentation:**
```bash
cd docs/modeling/
vim features.md
```

---

_Last Updated: 2026-02-13_
_Project file map and navigation guide_
