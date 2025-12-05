# Artifacts Directory Structure

**Version**: V2 (2025-12-05)  
**Status**: Active

This document defines the organization of the `artifacts/` directory for V2 workflow.

---

## Overview

The artifacts directory contains all experiment outputs, trained models, production artifacts, and analysis work. It is organized to align with the V2 4-phase experimentation workflow.

**Design Principles**:

1. **Phase-Aligned**: Structure matches Baseline → Features → Models → Deployment
2. **Separation of Concerns**: Experiments ≠ Models ≠ Production
3. **Findability**: Clear paths for common use cases
4. **Git Strategy**: Commit metadata, exclude binaries

---

## Directory Structure

```
artifacts/
│
├── mlruns/                          # MLflow experiment tracking
│   ├── 0/                           # Default experiment
│   ├── 1/                           # V2-001 (Phase 1)
│   └── ...
│
├── models/                          # Trained model artifacts
│   ├── baseline/                    # Phase 1: Ridge baseline
│   │   └── v2-001/
│   ├── candidates/                  # Phase 2-3: Candidate models
│   │   ├── v2-002/
│   │   └── v2-006/
│   └── production/                  # Phase 4: Champion Model
│       ├── champion_current/        # Active (symlink or copy)
│       └── champion_previous/       # Rollback fallback
│
├── experiments/                     # Experiment outputs
│   ├── phase1_baseline/
│   │   └── v2-001/
│   │       ├── metrics.csv
│   │       ├── predictions.csv
│   │       └── plots/
│   ├── phase2_features/
│   │   ├── v2-002/
│   │   └── v2-003/
│   ├── phase3_models/
│   │   ├── v2-006/
│   │   └── v2-007/
│   └── promotion_tests/
│       ├── v2-002_vs_baseline.json
│       └── v2-006_vs_baseline.json
│
├── production/                      # Phase 4 outputs
│   ├── predictions/
│   │   └── 2025/
│   │       ├── week01_bets.csv
│   │       └── week02_bets.csv
│   ├── scored/
│   │   └── 2025/
│   │       ├── week01_scored.csv
│   │       └── week02_scored.csv
│   └── monitoring/
│       ├── performance_log.csv
│       ├── dashboard_data.json
│       └── alerts/
│
├── validation/                      # Validation reports
│   ├── data_quality/
│   │   └── 2025/
│   └── walk_forward/
│       └── 2024_validation.csv
│
├── analysis/                        # Personal workspace (gitignored)
│   ├── feature_exploration/
│   ├── model_diagnostics/
│   └── reports/
│
└── archive/                         # Deprecated experiments
    └── legacy_v1/
```

---

## Directory Purposes

### `mlruns/` - MLflow Tracking

**Purpose**: Experiment tracking database  
**Managed By**: MLflow  
**Contents**: Run metadata, parameters, metrics, artifact pointers

**Usage**:

```python
import mlflow
mlflow.set_tracking_uri("file://./artifacts/mlruns")
mlflow.start_run(run_name="v2-001")
mlflow.log_metric("rmse", 12.5)
```

**Git Strategy**: Exclude large files, keep experiment structure

---

### `models/` - Model Artifacts

**Purpose**: Serialized trained models  
**Organization**: By phase and status

#### Subdirectories

**`baseline/`** - Phase 1 models

- Ridge regression experiments
- Example: `baseline/v2-001/model.joblib`

**`candidates/`** - Phase 2-3 models

- Feature engineering experiments (Phase 2)
- Model selection experiments (Phase 3)
- Example: `candidates/v2-006/model.joblib`

**`production/`** - Phase 4 Champion

- `champion_current/` - Active production model
- `champion_previous/` - Rollback backup

#### Model Directory Contents

Each model directory contains:

```
v2-001/
├── model.joblib           # Trained model
├── metadata.json          # Config, metrics, timestamp
└── feature_importance.csv # (optional) Feature weights
```

**Git Strategy**: Exclude `.joblib`, `.pkl` files; commit metadata

---

### `experiments/` - Experiment Outputs

**Purpose**: Metrics, predictions, diagnostics (separate from models)  
**Organization**: By phase

#### Contents

Each experiment directory contains:

```
v2-001/
├── metrics.csv            # Performance metrics
├── predictions.csv        # Test set predictions
├── plots/                 # Visualizations
│   ├── residuals.png
│   ├── calibration.png
│   └── feature_importance.png
├── config.yaml            # Hydra config snapshot
└── summary.json           # Quick reference
```

#### Promotion Tests

`promotion_tests/` contains bootstrap test results:

- `v2-002_vs_baseline.json` - Phase 2 feature promotion
- `v2-006_vs_baseline.json` - Phase 3 model promotion

Format:

```json
{
  "baseline_roi": 0.05,
  "candidate_roi": 0.062,
  "improvement": 0.012,
  "p_value": 0.03,
  "passed": true,
  "gates": {...}
}
```

**Git Strategy**: Exclude large CSVs/PNGs; commit summaries and configs

---

### `production/` - Phase 4 Outputs

**Purpose**: Production predictions, scoring, monitoring  
**Organization**: By year

#### `predictions/`

Weekly betting recommendations:

```
predictions/2025/week01_bets.csv
```

Columns: `game_id`, `home_team`, `away_team`, `prediction`, `edge`, `bet_type`, `recommended_units`

#### `scored/`

Post-game results:

```
scored/2025/week01_scored.csv
```

Adds: `actual_outcome`, `result` (win/loss), `units_won`

#### `monitoring/`

Dashboard data:

- `performance_log.csv` - Rolling metrics (hit rate, ROI, units)
- `dashboard_data.json` - Streamlit cache
- `alerts/` - Alert history (🟡/🟠/🔴)

**Git Strategy**: Include predictions (reproducibility); exclude scored & monitoring

---

### `validation/` - Validation Reports

**Purpose**: Data quality checks, walk-forward validation

#### `data_quality/`

Week-by-week validation reports (Week 3+):

```
data_quality/2025/week01_validation.json
```

#### `walk_forward/`

Historical validation results:

```
walk_forward/2024_validation.csv
```

**Git Strategy**: Include summaries; exclude large detailed reports

---

### `analysis/` - Personal Workspace

**Purpose**: Ad-hoc exploration, notebooks, investigations

**Organization**: Flexible (user preference)

**Git Strategy**: **Completely excluded** (except this README)

---

### `archive/` - Deprecated Experiments

**Purpose**: Old or superseded experiments (not deleted but inactive)

**Organization**:

- `legacy_v1/` - V1 models (historical reference)
- `deprecated/` - V2 experiments superseded by better versions

**Git Strategy**: Exclude (preserve structure via MANIFEST if needed)

---

## Naming Conventions

### Experiment IDs

**Format**: `v2-XXX` where XXX is zero-padded  
**Examples**: `v2-001`, `v2-002`, `v2-006`, `v2-012`

**Assignment**:

- Sequential across all phases
- Never reuse IDs
- Track in `docs/experiments/index.md`

### File Naming

**Predictions**: `week<WW>_bets.csv` (e.g., `week01_bets.csv`, `week12_bets.csv`)  
**Scored**: `week<WW>_scored.csv`  
**Models**: `model.joblib` (standard name in each experiment dir)

---

## Git Strategy

### What to Commit

✅ **Include**:

- Directory structure (empty directories via `.gitkeep`)
- README files
- Metadata (`.json`, `.yaml`)
- Summary files (`summary.json`, `metrics.csv` if <1MB)
- Production predictions (`predictions/*.csv`)

❌ **Exclude**:

- Model binaries (`.joblib`, `.pkl`, `.h5`, `.pt`)
- Large CSVs (>1MB)
- Plots/images (`.png`, `.jpg`)
- Scored results
- Monitor ing data
- Entire `analysis/` directory

### .gitignore Entries

See `.gitignore` in repo root for full list. Key patterns:

```gitignore
# Models (binaries)
artifacts/models/**/*.joblib
artifacts/models/**/*.pkl

# Experiments (large outputs)
artifacts/experiments/**/*.csv
artifacts/experiments/**/*.png

# Production (scored results)
artifacts/production/scored/
artifacts/production/monitoring/*.csv

# Analysis (personal workspace)
artifacts/analysis/
!artifacts/analysis/README.md

# MLflow (large tracking data)
artifacts/mlruns/*/artifacts/
```

---

## Workflow Integration

### Phase 1: Training Ridge Baseline

```bash
# Train
PYTHONPATH=. uv run python src/train.py experiment=v2-001

# Creates:
# - artifacts/mlruns/1/                        (MLflow run)
# - artifacts/experiments/phase1_baseline/v2-001/ (metrics, plots)
# - artifacts/models/baseline/v2-001/          (model artifact)
```

### Phase 2: Feature Experiments

```bash
# Train with new features
PYTHONPATH=. uv run python src/train.py experiment=v2-002 features=opponent_adjusted

# Creates:
# - artifacts/experiments/phase2_features/v2-002/
# - artifacts/models/candidates/v2-002/

# Run promotion test
uv run python scripts/test_promotion.py \
    --baseline v2-001 \
    --candidate v2-002 \
    --output artifacts/experiments/promotion_tests/v2-002_vs_baseline.json
```

### Phase 3: Model Selection

```bash
# Train CatBoost
PYTHONPATH=. uv run python src/train.py experiment=v2-006 model=catboost

# Creates:
# - artifacts/experiments/phase3_models/v2-006/
# - artifacts/models/candidates/v2-006/

# Promotion test
uv run python scripts/test_promotion.py \
    --baseline v2-001 \
    --candidate v2-006 \
    --output artifacts/experiments/promotion_tests/v2-006_vs_baseline.json
```

### Phase 4: Production Deployment

```bash
# Promote to Champion (symlink)
ln -sf ../../candidates/v2-006 artifacts/models/production/champion_current

# Weekly prediction
uv run python scripts/prediction/generate_weekly_bets.py --week 10
# → artifacts/production/predictions/2025/week10_bets.csv

# Score results
uv run python scripts/scoring/score_weekly_bets.py --week 10
# → artifacts/production/scored/2025/week10_scored.csv

# Update monitoring
uv run python scripts/monitoring/update_dashboard.py
# → artifacts/production/monitoring/performance_log.csv
```

---

## Finding Artifacts

### "Where is the current Champion Model?"

```bash
ls -la artifacts/models/production/champion_current
# If symlink: shows target (e.g., -> ../../candidates/v2-006)
```

### "Where are the metrics for experiment v2-003?"

```bash
cat artifacts/experiments/phase2_features/v2-003/summary.json
```

### "What are this week's predictions?"

```bash
cat artifacts/production/predictions/2025/week10_bets.csv
```

### "What's the current ROI?"

```bash
tail artifacts/production/monitoring/performance_log.csv
```

---

## Maintenance

### Weekly Cleanup

**What to keep**:

- All MLflow metadata
- All model metadata files
- Final experiment summaries
- Production predictions

**What to delete** (after 30 days):

- Large experiment CSVs (keep summaries)
- Diagnostic plots (regenerate if needed)
- Scored results older than 1 season

### Archiving Old Experiments

When an experiment is superseded:

```bash
mv artifacts/models/candidates/v2-002 artifacts/archive/deprecated/v2-002
mv artifacts/experiments/phase2_features/v2-002 artifacts/archive/deprecated/v2-002_outputs
```

Update `artifacts/archive/MANIFEST.md` with reason and date.

---

## Troubleshooting

### "Directory not found" errors

Ensure structure is created:

```bash
# From repo root
mkdir -p artifacts/{models/{baseline,candidates,production},experiments/{phase1_baseline,phase2_features,phase3_models},production/{predictions/2025,scored/2025,monitoring}}
```

### Symlink issues

If symlinks don't work (Windows):

- Use hard copy instead of `ln -s`
- Update scripts to copy rather than symlink

### MLflow can't find artifacts

Check tracking URI:

```python
import mlflow
print(mlflow.get_tracking_uri())
# Should be: file://./artifacts/mlruns
```

---

## Related Documentation

- [V2 Workflow](../process/experimentation_workflow.md) - Overall 4-phase process
- [Weekly Pipeline](./weekly_pipeline.md) - Production workflow
- [Promotion Framework](../process/promotion_framework.md) - Gate system
- [Experiments Index](../experiments/index.md) - Experiment registry

---

**Last Updated**: 2025-12-05  
**Version**: V2 Initial Structure
