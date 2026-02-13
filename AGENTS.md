# AGENTS.md

> **Universal AI Assistant Guide for CFB Model**
>
> This file is the primary entry point for all AI coding assistants (Claude Code, GitHub Copilot, Cursor, etc.) working on this repository.

---

## 🚨 CRITICAL RULES - READ FIRST 🚨

### 1. External Data Root Configuration

**THE MOST COMMON MISTAKE: The data does NOT live in the project directory!**

All raw and processed data resides on an external hard drive (or cloud storage after Phase 2 migration). The path is configured via environment variable:

```bash
CFB_MODEL_DATA_ROOT='/Volumes/CK SSD/Coding Projects/cfb_model/'
```

**Before ANY data operation, ALWAYS verify:**

1. ✅ `CFB_MODEL_DATA_ROOT` environment variable is set
2. ✅ The external drive is mounted and accessible (or cloud storage configured)
3. ✅ You're reading from/writing to the external path, NOT `./data/` in project root

**Quick Validation:**

```python
import os
from pathlib import Path

# This should print the external drive path
data_root = os.getenv("CFB_MODEL_DATA_ROOT")
if not data_root or not Path(data_root).exists():
    raise ValueError(f"Data root not accessible: {data_root}")
print(f"✅ Data root verified: {data_root}")
```

**If you see `./data/` being created in project root:**

**STOP IMMEDIATELY!** The script is misconfigured. Always load `CFB_MODEL_DATA_ROOT` from environment and fail loudly if not set.

### 2. Data & Modeling Guardrails

**Storage Location:**
- All raw and processed data resides on external drive at `CFB_MODEL_DATA_ROOT`
- Validate this path exists before any I/O operation
- Never create `./data/` in project root

**Data Leakage Prevention:**
- Training strictly precedes prediction
- No target-aware transforms on full dataset
- Use `load_point_in_time_data()` to avoid future data leakage

**Training Windows:**
- Train: 2019, 2021-2023 (skip 2020 COVID year)
- Holdout: 2024
- Minimum games: 4 games required for adjusted stats & betting eligibility

**Column Conventions:**
- Maintain: `season`, `week`, `game_id`, `team` keys
- Prefix: `off_*`, `def_*`, `adj_*` consistently
- No bookmaker-derived features in model inputs (only in post-model edge calc)

**Correct Data Path Usage:**

```python
# ✅ CORRECT: Load from environment
data_root = Path(os.getenv("CFB_MODEL_DATA_ROOT"))
if not data_root.exists():
    raise ValueError(f"Data root not found: {data_root}")

# ✅ CORRECT: Build paths from root
plays_path = data_root / "raw/plays/year=2024/week=12/data.parquet"

# ❌ WRONG: Hardcoded or relative paths
plays_path = "./data/raw/plays/2024/12/data.parquet"  # NO!
plays_path = "/Volumes/CK SSD/..."  # NO! (hardcoded)
```

### 3. Session Protocol

**Starting a Session:**
1. Read this file (AGENTS.md) first
2. Verify data root configuration
3. Review recent session logs (`session_logs/` last 3 days)
4. Propose a plan before implementation
5. Wait for user approval before executing

**Ending a Session:**
1. Create session log in `session_logs/YYYY-MM-DD/NN.md`
2. Run health checks: `uv run ruff format . && uv run ruff check .`
3. Run tests: `uv run pytest -q`
4. Propose commit message (user executes manually)
5. Update docs if behavior changed

---

## 📚 Getting Started

### Quick Onboarding

**First-time setup? Read in order:**
1. This file (AGENTS.md) - Critical rules and overview
2. `.codex/QUICKSTART.md` - Essential commands
3. `.agent/CONTEXT.md` - Project architecture and domain knowledge
4. `README.md` - User-facing project overview
5. Last 3 session logs - Recent work context

**Estimated onboarding time:** <30 minutes

### Project Quick Facts

- **What:** College football betting model predicting spreads and over/unders
- **Tech Stack:** Python 3.12, Hydra, MLflow, Optuna, CatBoost/XGBoost
- **Data:** 2019-2025 CFB data on external drive (50-100GB)
- **Workflow:** V2 4-phase experimentation (currently PAUSED for infrastructure refactoring)
- **Commands:** See `.codex/QUICKSTART.md`
- **Architecture:** See `.agent/CONTEXT.md`

---

## 🎯 V2 Modeling Workflow Status

**Status:** 🛑 PAUSED for Infrastructure Refactoring

The V2 4-phase experimentation workflow (detailed in `docs/process/experimentation_workflow.md`) is temporarily suspended while we modernize infrastructure:

**Phase 1:** Baseline Establishment
**Phase 2:** Feature Engineering & Selection
**Phase 3:** Model Selection
**Phase 4:** Deployment & Monitoring

**Modeling will resume after:**
- ✅ Cloud storage migration complete (Phase 2)
- ✅ AI tooling modernization complete (Phase 1)
- ✅ Integration validation complete (Phase 6)

**Next modeling milestone:** Post-refactoring baseline validation

**Reference:** `docs/process/experimentation_workflow.md`, `docs/process/promotion_framework.md`

---

## 🔄 Key Workflows

### Development Cycle

1. **Create feature branch:** `git checkout -b feature/your-feature`
2. **Make changes:** Edit code, add tests
3. **Run quality gates:** `uv run ruff format . && uv run ruff check . && uv run pytest -q`
4. **Create session log:** Document work in `session_logs/`
5. **Commit:** User executes proposed commit
6. **Create PR:** When ready for review

### Testing & Validation

```bash
# Run all tests
uv run pytest

# Run tests quietly
uv run pytest -q

# Run specific test file
uv run pytest tests/test_aggregations_core.py

# Format and lint together
uv run ruff format . && uv run ruff check .
```

### Model Training

```bash
# Basic training with defaults
PYTHONPATH=. uv run python src/models/train_model.py

# Run specific experiment
PYTHONPATH=. uv run python src/models/train_model.py experiment=spread_catboost_baseline_v1

# Hyperparameter optimization
PYTHONPATH=. uv run python src/models/train_model.py mode=optimize

# Debug configuration
PYTHONPATH=. uv run python src/models/train_model.py --cfg job --resolve
```

**See `.codex/QUICKSTART.md` for complete command reference.**

---

## 🚨 Troubleshooting

### Common Issues

**Import Errors:**
- Run scripts with `PYTHONPATH=.` from repo root
- Or activate venv: `source .venv/bin/activate`

**Missing Data / Path Errors:**
1. Check `CFB_MODEL_DATA_ROOT` environment variable is set
2. Verify external drive is mounted: `ls /Volumes/`
3. Confirm path exists: `ls "$CFB_MODEL_DATA_ROOT"`
4. Check script uses environment variable, not hardcoded paths

**Hydra Config Errors:**
- Debug with: `PYTHONPATH=. uv run python src/models/train_model.py --cfg job --resolve`
- Check `conf/config.yaml` and experiment configs

**MLflow Tracking Issues:**
1. Ensure `artifacts/mlruns/` directory exists and is writable
2. Start MLflow UI: `MLFLOW_PORT=5050 docker compose -f docker/mlops/docker-compose.yml up mlflow`
3. Check `MLFLOW_TRACKING_URI` if using custom location

**Test Failures:**
- Run verbose: `uv run pytest -v`
- Check fixtures match expected schemas
- Verify test data is valid

**External Drive Not Accessible:**
1. Verify drive is mounted: `ls /Volumes/`
2. Check drive name matches `CFB_MODEL_DATA_ROOT`
3. Remount if necessary
4. Update `.env` if drive path changed

**Ruff Formatting Issues:**
- Ensure using version in `pyproject.toml`
- Update dependencies: `uv sync`

### Common Pitfalls

**Creating Local Data Directory:**
- ❌ Problem: Script creates `./data/` in project root
- ✅ Solution: Load `CFB_MODEL_DATA_ROOT` from env, fail loudly if not set

**Training on 2020 Data:**
- ❌ Problem: Including COVID-disrupted 2020 season
- ✅ Solution: Use `train_years: [2019, 2021, 2022, 2023]`

**Future Data Leakage:**
- ❌ Problem: Using future data in historical analysis
- ✅ Solution: Use `load_point_in_time_data()` for strict temporal splits

**Hardcoded Paths:**
- ❌ Problem: Using `/Users/...` or `./data/` paths
- ✅ Solution: Always use `os.getenv("CFB_MODEL_DATA_ROOT")`

---

## 🧠 Context Management

### Reading Strategy

**Default read order for new tasks:**
1. AGENTS.md (this file) - Critical rules
2. `.codex/QUICKSTART.md` - Commands needed
3. `.agent/CONTEXT.md` - Project architecture (if needed)
4. Last 3 session logs - Recent context
5. Code files - Only when actively working on them

**Context budget:** ≤50k tokens per task, prefer ≤10k

### What NOT to Read Automatically

- `artifacts/**`, `.venv/**`, `.git/**`, `**__pycache__/`
- `notebooks/**` (only when debugging)
- `session_logs/` older than 3 days
- Files > 200 KB
- Files unchanged in last 30 days

**Load code on demand.** Only open source files when actively working on them.

---

## 🔗 Quick Links

### Essential Files

- **Commands:** `.codex/QUICKSTART.md` - All essential commands
- **Architecture:** `.agent/CONTEXT.md` - Project structure and domain knowledge
- **Config Guide:** `.codex/HYDRA.md` - Hydra configuration system
- **File Map:** `.codex/MAP.md` - Project file locations
- **Session Skills:** `.agent/skills/` - Start/end session workflows

### Documentation

- **User Guide:** `README.md` - Project overview and setup
- **V2 Workflow:** `docs/process/experimentation_workflow.md` - Modeling process (paused)
- **Features:** `docs/modeling/features.md` - Feature definitions
- **Betting Policy:** `docs/modeling/betting_policy.md` - Unit sizing rules
- **Decision Log:** `docs/decisions/decision_log.md` - Historical decisions

### Configuration

- **Main Config:** `conf/config.yaml` - Hydra entry point
- **Models:** `conf/model/` - Model configurations
- **Features:** `conf/features/` - Feature set definitions
- **Experiments:** `conf/experiment/` - Pre-configured experiments

### Core Code

- **Config:** `src/config.py` - Path configuration
- **Features:** `src/features/pipeline.py` - Feature engineering
- **Training:** `src/models/train_model.py` - Model training
- **Inference:** `scripts/pipeline/generate_weekly_bets.py` - Predictions

---

## 📝 Session Log Template

Create logs in `session_logs/YYYY-MM-DD/NN.md`:

```markdown
# Session: [Brief Description]

## TL;DR
- **Worked On:** [what was done]
- **Completed:** [what was finished]
- **Blockers:** [any issues]
- **Next:** [what's next]

## Changes Made
- File 1: [description]
- File 2: [description]

## Testing
- [ ] Health checks pass
- [ ] Tests pass
- [ ] Documentation updated

## Notes for Next Session
[Context to carry forward]

**tags:** ["modeling", "features", "pipeline", etc.]
```

---

## 🛠️ Skills Available

Skills are workflows for common tasks. Invoke via `.agent/skills/` directory:

- **start-session** - Session initialization workflow
- **end-session** - Session cleanup and documentation

See `.agent/skills/CATALOG.md` for full list.

---

_Last Updated: 2026-02-13_
_Universal entry point for all AI coding assistants_
