# Models Directory

This directory contains all trained model artifacts organized by phase and status.

## Structure

- `baseline/` - Phase 1 baseline models (Ridge regression)
- `candidates/` - Phase 2-3 candidate models (features & model selection)
- `production/` - Phase 4 production Champion Models
  - `champion_current/` - Active production model
  - `champion_previous/` - Rollback fallback

## Naming Convention

**Experiment ID**: `v2-XXX` (e.g., `v2-001`, `v2-006`)

**Directory**: `<phase>/<experiment_id>/`

- Example: `baseline/v2-001/`
- Example: `candidates/v2-006/`

## Contents

Each model directory contains:

- `model.joblib` - Serialized model artifact
- `metadata.json` - Training config, metrics, timestamp
- `feature_importance.csv` - Feature weights (if applicable)

## Production Promotion

When a model is promoted to Champion:

```bash
# Create symlink (recommended)
ln -sf ../../candidates/v2-006 production/champion_current

# Or copy (if symlinks not supported)
cp -r candidates/v2-006/* production/champion_current/
```

## .gitignore

Model binaries (`.joblib`, `.pkl`) are excluded from git.
Only metadata files are committed.

---

**Related**: [V2 Workflow](../docs/process/experimentation_workflow.md) | [Promotion Framework](../docs/process/promotion_framework.md)
