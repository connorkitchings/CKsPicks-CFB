# AGENTS.md

> **Universal AI Assistant Guide for CFB Model**
>
> This file is the primary entry point for all AI coding assistants (Claude Code, GitHub Copilot, Cursor, etc.) working on this repository.

---

## 🚨 CRITICAL RULES - READ FIRST 🚨

### 1. Data Storage Configuration

**THE MOST COMMON MISTAKE: The data does NOT live in the project directory!**

The durable data store is the Cloudflare R2 immutable lake
(`CFB_STORAGE_BACKEND='r2'`). The local backend
(`CFB_STORAGE_BACKEND='local'`) reads/writes an external drive configured via
environment variable:

```bash
CFB_MODEL_DATA_ROOT='/Volumes/CK SSD/Coding Projects/cfb_model/'
```

**Before ANY data operation, ALWAYS verify (per the backend the task uses):**

1. ✅ `CFB_STORAGE_BACKEND` matches the task's backend (`r2` or `local`)
2. ✅ For `r2`: the relevant `CFB_R2_*` (or `CFB_R2_PREVIEW_*`) credentials are present
3. ✅ For `local`: `CFB_MODEL_DATA_ROOT` is set and the drive is mounted
4. ✅ You're never reading from/writing to `./data/` in project root

**Quick Validation (local backend):**

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
- Durable data store: Cloudflare R2 immutable lake (`CFB_STORAGE_BACKEND='r2'`) — Bronze/Silver/Gold datasets with SHA-256 checksums
- Local dev fallback: external drive at `CFB_MODEL_DATA_ROOT` (`CFB_STORAGE_BACKEND='local'`)
- Never create `./data/` in project root

**Data Leakage Prevention:**
- Training strictly precedes prediction
- No target-aware transforms on full dataset
- Use `load_point_in_time_data()` to avoid future data leakage

**Training Windows:**
- Selection: expanding temporal folds validated in 2022-2024
- Locked test: train 2021-2024, evaluate 2025 once
- Production refit: unchanged design on 2021-2025 for 2026
- V4 retains its sealed 2021–2025 lineage. Successor-v2 research uses
  2015–2019 and 2021–2025; skip 2020 entirely in every boundary.
- Completed games: route 0/1/2/3/4+ separately; 4+ is the established route

**Data-First Forecasting Transition:**
- V4 remains the unchanged 2026 production champion and benchmark
- Approved target flow: repository alignment → data audit/repair → validated measurements → simple team ratings/state → spread/total forecasts → prospective evaluation → timestamped line comparison
- Opponent adjustment stays primarily at the football-measurement layer in the initial design; do not double-count schedule strength in ratings
- Use one continuous season-long rating meaning, with prior/evidence credibility changing smoothly as observations accumulate
- Under `data-first-football-v1`, use 2015–2019 and 2021–2025 for development; future outcomes count as prospective evidence only when predictions were frozen before kickoff
- Complete initial requirements before Week 0. A first promotion review requires six completed, normal-coverage slates with V4 and candidate predictions frozen before kickoff; Week 0 does not count.
- New research stays isolated from production bundles, Neon activation, and public publication until a separate promotion contract is approved; betting decisions are deferred

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
2. Verify only the storage configuration required by the task; never expose secrets
3. Review recent session logs (`session_logs/` last 3 days)
4. Route substantial work through the Sol planning → Terra implementation workflow
5. Use the fast path only for established, localized changes

**Ending a Session:**
1. Create session log in `session_logs/YYYY-MM-DD/NN.md`
2. Run validation scoped to the session and changed components
3. Do not broad-format a dirty worktree without explicit authorization
4. Propose a commit message; the user executes git operations manually
5. Update docs and the implementation contract when behavior changed

### Sol Planning → Terra Implementation

Use the durable contract workflow for architecture, data/model lineage, database
contracts or migrations, production/deployment behavior, security-sensitive work,
or changes spanning multiple subsystems.

1. **Sol:** Use `.agent/skills/plan-session/` to investigate and produce a
   decision-complete plan in Plan Mode.
2. **Persist:** After approval, switch the same Sol task to Code mode only to
   save `docs/plans/YYYY-MM-DD/<descriptive-slug>.md` and the planning session
   log. Sol must not edit implementation files in this step.
3. **Terra:** Open a fresh task and use `.agent/skills/implement-plan/` with
   the exact plan path. Terra executes an `Approved` plan, or a `Draft` plan
   explicitly authorized by the user for that exact path.

`docs/planning/` remains the home of strategic roadmaps. `docs/plans/` holds
task-level execution contracts. See `docs/plans/index.md` for lifecycle,
amendment, and commit-policy rules.

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

- **What:** College football betting model that predicts spreads and over/unders, displayed as weekly leans in a Vercel web app
- **Tech Stack:** Python 3.12 (pipeline) + Next.js 16 / React 19 / Tailwind v4 (web app) + Neon Postgres + Cloudflare R2
- **Data:** V4 artifacts retain 2021–2025; successor-v2 research expands to
  2015–2019 and 2021–2025 in R2 (`CFB_STORAGE_BACKEND='r2'`); 2020 excluded
- **2026 Deliverable:** Vercel web app at `web/` showing every FBS game's spread + total lean (display only; auth/tracking is post-MVP)
- **Commands:** See `.codex/QUICKSTART.md` (Python + Nx task runner) and `web/README.md` (Next.js)
- **Architecture:** See `.agent/CONTEXT.md` (modeling) and `docs/ops/weekly_pipeline.md` (data flow to web app)

### Dual-Stack Architecture (2026)

This is a **monorepo with two toolchains**:

| Component | Location | Stack | Test/Build |
|---|---|---|---|
| ML pipeline | root (`src/`, `scripts/`, `conf/`) | Python 3.12, uv, Hydra, MLflow | `npx nx run pipeline:test` or `make test` |
| Web app | `web/` | Next.js 16, TypeScript, npm, Tailwind v4 | `npx nx run web:build` or `make web-build` |
| Shared contracts | `contracts/` | SQL + TypeScript + Python | `make contracts-check` |
| Research | `research/` | Python (analysis, tuning, experiments) | — |
| Task runner | root (`nx.json`, `project.json`) | Nx 20 — cached cross-stack tasks | `npx nx run-many -t lint typecheck test build` |
| Shared storage | Cloudflare R2 | Parquet (pipeline reads) | — |
| Web data | Neon Postgres | `games`, `game_results`, `system_stats`, `current_week` + catalog/ops schemas | `make migrate-db` (append-only migrations 0002–0008) |

**Data flow:** Python pipeline writes a local working CSV (`data/production/...`) and durable R2 artifact (`artifacts/production/...`) → `scripts/pipeline/publish_to_db.py --from-artifact` upserts the durable artifact to Postgres → Vercel app reads via Drizzle ORM with ISR (5-min revalidate). R2 is the source of truth; Neon is the derived web-serving database.

**Conventions:**
- Python stays at root; never move or rename `src/`, `scripts/`, `conf/`, `tests/`.
- Next.js app is fully isolated in `web/` with its own `package.json` and `.gitignore`.
- **Single source of truth:** `contracts/` holds the canonical DB schema (`schema.sql`, `schema.ts`) and team-name mapping (`teams.py`, `teams.ts`). The web app has local copies in `web/src/lib/` that must stay in sync. Run `make contracts-check` to validate sync.
- Production scripts live in `scripts/pipeline/` and `scripts/data/`. Research/exploration scripts live in `research/`.

---

## 🎯 2026 Season Execution Status

**Status:** 🏈 Season live — Week 0 scored; Week 1 frozen (games through Mon Sept 7), close-week due Tuesday Sept 8

The 2026 buildout is complete; its strategic execution record is archived at
`docs/archive/2026-completed-plans/2026_historical_bootstrap_week0_execution.md`.
Production is live at `https://c-ks-picks-cfb.vercel.app` in approval-gated
`predictions` publication mode (revealed 2026-08-21). Active work is the
weekly operating cadence documented in `docs/ops/weekly_pipeline.md` and
`docs/ops/production_runbook.md`.

**Current focus:**
- ✅ Data platform modernization (immutable lake, CFBD hardening, resumable ops)
- ✅ Week 0 regime modeling (5 routes × 2 targets, temporal folds)
- ✅ Phase 1–5: Full bootstrap, Silver/Gold, OOF baselines, V4 tournament complete
  (bundle `week0-2026-v4-strict-20260818-r2`, config `conf/weekly_bets/v4_2026.yaml`)
- ✅ Phase 6: Production deployed 2026-08-18; predictions revealed 2026-08-21;
  Week 0 games played Aug 29–30.
- ✅ **Week 0 closed:** `2026w0-55de0317120d` frozen and `scored` (8/8/8).
- ✅ **Week 1 published and frozen:** `2026w1-b2c739321e5d` frozen 2026-09-04
  (43/43/43, no waiver; Thursday kickoff preceded freeze).
- 🟡 **Week 1 close (Tuesday Sept 8):** `close-week YEAR=2026 WEEK=1 AS_OF=<ts>
  ENV=production` — run Tuesday, not Monday (CFBD finalization lag). Then the
  Week 2 cycle: `prepare-week` → `readiness` in Preview → `publish-week` →
  freeze before kickoff. See `docs/ops/weekly_pipeline.md`.
- 🧭 **Historical ratings evidence:** R1 is certified at
  `r1-full-corpus-20260831-5f2a384`; its immutable coverage report has
  `tournaments_permitted: true`. The fresh, code-bound Preview admission at
  `early-week-context-20260904-786580ec-r2` admits reconstructed returning
  production, recruiting, and coaching; transfers and talent remain rejected.
  The direct selection report is sealed, and the R2 between-season prior
  tournament completed 2026-09-04 at `r2-prior-20260904-4c6e610` (winner
  `continuity_ridge_alpha_0_1`, all gates passed) — see
  `docs/research/2026-09-04-early-week-context-cross-report.md`. All evidence
  is reconstructed and activation-ineligible. The pending R3/R4 sequence is
  superseded; **Phase 0 and Phase 1 are implemented** (Phase 1 sealed audit at
  `artifacts/research/data-first-football-v1/phase1/2026-09-05T1510Z-phase1-evidence-audit-v2/`;
  57 issues feeding Phase 2). **Phase 2 data repair and recertification is next.**
  O2 candidate-v1 at `ac1fba1` is diagnostic-only. See
  `docs/planning/data-first-football-forecasting-roadmap.md`.

**Roadmap (2026 transition):** `docs/planning/roadmap.md` ·
**Weekly ops:** `docs/ops/weekly_pipeline.md` ·
**Production runbook:** `docs/ops/production_runbook.md`

**Historical reference:** V2 workflow and prior rating research are retained in
`docs/archive/`; they are evidence, not current operating authority.

---

## 🔄 Key Workflows

### Development Cycle

1. **Create feature branch:** `git checkout -b feature/your-feature`
2. **Make changes:** Edit code, add tests
3. **Run scoped quality gates:** follow the active implementation contract or affected components
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
PYTHONPATH=src uv run python -m cks_picks_cfb.train

# Run specific experiment
PYTHONPATH=src uv run python -m cks_picks_cfb.train experiment=week0_regimes

# Hyperparameter optimization
PYTHONPATH=src uv run python -m cks_picks_cfb.train mode=optimize

# Debug configuration
PYTHONPATH=src uv run python -m cks_picks_cfb.train --cfg job --resolve
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
- Debug with: `PYTHONPATH=src uv run python -m cks_picks_cfb.train --cfg job --resolve`
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
- ✅ Solution: use the versioned `conf/training/week0_2026.yaml` chronology

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
- `research/**` (only when actively debugging or experimenting)
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
- **Contracts:** `contracts/` - DB schema and team mappings (single source of truth)
- **Session Skills:** `.agent/skills/` - Start/end session workflows

### Documentation

- **User Guide:** `README.md` - Project overview and setup
- **Documentation home:** `docs/index.md` - Current authority map
- **Rating requirements:** `docs/modeling/rating_system_requirements.md` - Approved successor requirements
- **Measurement catalog:** `docs/modeling/measurement_catalog.md` - Football measurements and provenance
- **Betting Policy:** `docs/modeling/betting_policy.md` - Unit sizing rules
- **Decision Log:** `docs/decisions/decision_log.md` - Historical decisions

### Configuration

- **Main Config:** `conf/config.yaml` - Hydra entry point
- **Models:** `conf/model/` - Model configurations
- **Features:** `conf/features/` - Feature set definitions
- **Experiments:** `conf/experiment/` - Pre-configured experiments

### Core Code

- **Config:** `src/cks_picks_cfb/config/` - Path configuration
- **Features:** `src/cks_picks_cfb/features/pipeline.py` - Feature engineering
- **Training:** `src/cks_picks_cfb/train.py` - Canonical model training
- **Ops state machine:** `src/cks_picks_cfb/ops/` - Publish/freeze/close/replay orchestration
- **Inference:** `scripts/pipeline/generate_weekly_bets.py` - Predictions
- **Contracts:** `contracts/` - DB schema and team mappings (single source of truth)
- **Research:** `research/` - Analysis, tuning, debugging, experiments

---

## 📝 Session Log Template

Create logs in `session_logs/YYYY-MM-DD/NN.md`:

```markdown
# Session: [Brief Description]

## TL;DR
- **Worked On:** [what was done]
- **Outcome:** [what changed or was decided]
- **Plan Contract:** [plan path or `N/A (fast path)`]
- **Approval / Status:** [approval source and contract lifecycle state, if applicable]
- **Blockers:** [any issues or `None`]
- **Next:** [what's next]

## Context and Decisions
- [important context or decision]

## Work Completed
- [completed task]

## Files Modified
- `path/to/file` - [description]

## Validation
- [ ] [required focused checks]
- [ ] `git diff --check`

## Amendments and Blockers
- [amendment, material conflict, or `None`]

## Handoff Notes
- **Resume at:** [precise next action]
- **Watch out for:** [important constraint]

**tags:** ["modeling", "features", "pipeline", etc.]
```

---

## 🛠️ Skills Available

Skills are workflows for common tasks. Invoke via `.agent/skills/` directory:

- **start-session** - Session initialization workflow
- **plan-session** - Sol investigation and implementation-contract workflow
- **implement-plan** - Terra contract execution workflow
- **end-session** - Session cleanup and documentation

See `.agent/skills/CATALOG.md` for full list.

---

_Last Updated: 2026-08-23_
_Universal entry point for all AI coding assistants_
