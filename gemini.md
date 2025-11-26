# Gemini-Specific Session Guide

> **Purpose**: Provide Gemini-specific context and critical reminders for working on the cfb_model project. Read this FIRST in every new Gemini session.

---

## Critical Configuration: External Data Root

### 🚨 MOST COMMON MISTAKE 🚨

**The data does NOT live in the project directory!**

All raw and processed data resides on an external hard drive. The path is configured via environment variable:

```bash
CFB_MODEL_DATA_ROOT='/Volumes/CK SSD/Coding Projects/cfb_model/'
```

### Before ANY Data Operation

**ALWAYS verify these three things:**

1. ✅ `CFB_MODEL_DATA_ROOT` environment variable is set
2. ✅ The external drive is mounted and accessible
3. ✅ You're reading from / writing to the external path, NOT `./data/` in project root

### Quick Validation Check

```python
import os
from pathlib import Path

# This should print the external drive path
data_root = os.getenv("CFB_MODEL_DATA_ROOT")
print(f"Data root: {data_root}")

# This should return True
Path(data_root).exists()
```

### Common Paths

Based on `CFB_MODEL_DATA_ROOT='/Volumes/CK SSD/Coding Projects/cfb_model/'`:

- Raw plays: `/Volumes/CK SSD/Coding Projects/cfb_model/raw/plays/year=YYYY/week=WW/`
- Processed features: `/Volumes/CK SSD/Coding Projects/cfb_model/processed/team_week_adj/iteration=N/year=YYYY/week=WW/`
- Games: `/Volumes/CK SSD/Coding Projects/cfb_model/raw/games/year=YYYY/`

### If You See `./data/` Being Created

**STOP IMMEDIATELY!** This is wrong. The script is misconfigured and needs to explicitly load `CFB_MODEL_DATA_ROOT` from the environment.

---

## Session Kickoff Checklist

When starting a new Gemini session:

1. **Read this file first** (`gemini.md`)
2. **Verify data root configuration** as shown above
3. **Load minimal context** per AGENTS.md §2
4. **Review last 3 days of session logs** for recent changes
5. **Propose a plan** before any implementation

### Recommended First Prompt

```
Review gemini.md first, then load the minimal context pack from AGENTS.md.
Review the last 3 session logs to understand recent work.
Then propose a clear plan for [TASK DESCRIPTION] before implementing anything.
```

---

## Key Constraints for Gemini

### Data & Paths

- ✅ Always use `CFB_MODEL_DATA_ROOT` from environment
- ❌ Never create `./data/` in project root
- ✅ Validate paths exist before operations
- ✅ Use `src/config.py` path helpers when available

### Modeling

- Train window: 2019, 2021-2023 (skip 2020)
- Holdout: 2024
- Features: Load from `processed/team_week_adj/iteration=4/` (cached)
- No target leakage: training strictly precedes prediction

### Betting Policy

- Read from `docs/project_org/betting_policy.md`
- **Never modify** unit sizing or exposure rules in code
- Only apply existing rules, return reason codes for violations

### Tooling

- Use `uv run` for all Python commands
- MLflow tracking: `artifacts/mlruns/`
- Hydra configs: `conf/` directory
- Always run lint/format before suggesting commit

---

## Common Gemini Pitfalls

### 1. Creating Local Data Directory

**Problem**: Script creates `./data/` folder in project root  
**Solution**: Load `CFB_MODEL_DATA_ROOT` from env; fail if not set

### 2. Forgetting Cached Features

**Problem**: Regenerating features that are already cached  
**Solution**: Use `processed/team_week_adj/iteration=4/` cache first

### 3. Hardcoded Paths

**Problem**: Using `/Users/...` or `./data/` hardcoded paths  
**Solution**: Always use `os.getenv("CFB_MODEL_DATA_ROOT")` or `src.config`

### 4. Skipping Environment Check

**Problem**: Script fails silently when drive isn't mounted  
**Solution**: Add explicit validation at script start

---

## Session Closing Checklist

Before ending a Gemini session where code changed:

1. ✅ Update session log in `session_logs/YYYY-MM-DD/NN.md`
2. ✅ Run health checks: `uv run ruff format . && uv run ruff check .`
3. ✅ Run tests if relevant: `uv run pytest -q`
4. ✅ Propose commit message for user to execute manually
5. ✅ Document any new patterns in `docs/project_org/kb_overview.md`

---

## Quick Reference: Key Files

### Must Read (Minimal Context)

- `AGENTS.md` - Agent roles and rules
- `README.md` - Project overview and setup
- `docs/project_org/project_charter.md` - Goals and scope
- `docs/operations/weekly_pipeline.md` - Production workflow

### Read on Demand

- `docs/project_org/feature_catalog.md` - Feature definitions
- `docs/project_org/modeling_baseline.md` - Model architecture
- `docs/project_org/betting_policy.md` - Unit sizing rules
- `docs/project_org/kb_overview.md` - Known patterns

### Code Anchors (open when needed)

- `src/config.py` - Path configuration
- `src/features/pipeline.py` - Feature engineering
- `src/models/train_model.py` - Model training
- `scripts/generate_weekly_bets_clean.py` - Prediction generation

---

## Example: Correct Data Path Usage

```python
import os
from pathlib import Path
import pandas as pd

# ✅ CORRECT: Load from environment
data_root = Path(os.getenv("CFB_MODEL_DATA_ROOT"))
if not data_root.exists():
    raise ValueError(f"Data root not found: {data_root}")

# ✅ CORRECT: Build paths from root
plays_path = data_root / "raw/plays/year=2024/week=12/data.csv"
features_path = data_root / "processed/team_week_adj/iteration=4/year=2024/week=12/data.csv"

# ❌ WRONG: Hardcoded or relative paths
plays_path = "./data/raw/plays/2024/12/data.csv"  # NO!
plays_path = "/Volumes/CK SSD/..."  # NO! (hardcoded)
```

---

## Getting Help

If unclear about:

- **Data paths**: Ask user to confirm `CFB_MODEL_DATA_ROOT` value
- **Model architecture**: Reference `docs/project_org/modeling_baseline.md`
- **Feature definitions**: Check `docs/project_org/feature_catalog.md`
- **Betting rules**: Read `docs/project_org/betting_policy.md` (never guess)

**When in doubt**: Ask the user rather than making assumptions.

---

_Last Updated: 2025-01-03_  
_Keep this file under 3,000 words for fast loading in every Gemini session_
