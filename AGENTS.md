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

**Historical V4 Training Windows (not the operational V5 design):**
- Selection: expanding temporal folds validated in 2022-2024
- Locked test: train 2021-2024, evaluate 2025 once
- Production refit: unchanged design on 2021-2025 for 2026
- V4 retains its sealed 2021–2025 lineage. Successor-v2 research uses
  2015–2019 and 2021–2025; skip 2020 entirely in every boundary.
- Historical V4 completed-game routes: 0/1/2/3/4+ separately; 4+ is the established route

**Data-First Forecasting Transition:**
- V5 Blitzkrieg is the only operational model; live release IDs and week state are in `docs/status.md`. V4 is documented historical evidence in [the retrospective](docs/modeling/v4_retrospective.md), not an operational rollback path. Rollback reactivates a prior verified V5 season release.
- Approved target flow: repository alignment → data audit/repair → validated measurements → simple team ratings/state → spread/total forecasts → prospective evaluation → timestamped line comparison
- Opponent adjustment stays primarily at the football-measurement layer in the initial design; do not double-count schedule strength in ratings
- Use one continuous season-long rating meaning, with prior/evidence credibility changing smoothly as observations accumulate
- The approved 2026-09-13 V5 package compares two possession definitions, learned preseason priors and one Kalman challenger. The original Phase 4B retained manifest remains prohibited as a forecasting parent. Polls and direct-core models are diagnostic-only.
- Under `data-first-football-v1`, use 2015–2019 and 2021–2025 for development; future outcomes count as prospective evidence only when predictions were frozen before kickoff (the public 2026 V5 record is the unified point-in-time record described in `docs/modeling/record_methodology.md`; "prospective" now names freeze provenance only)
- V5 model development is complete and accepted. Atomic season releases are the serving authority; Production activation requires a separate owner decision and verified Preview rehearsal. The cumulative 2026 record continues as monitoring; six slates are not a prelaunch gate.
- Further model research stays isolated from production bundles, Neon activation, and public publication until a separate promotion contract is approved; betting decisions are deferred

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
1. Read this file (AGENTS.md) first, then `docs/status.md`
2. Verify only the storage configuration required by the task; never expose secrets
3. Review recent session logs (`session_logs/` last 3 days)
4. Route substantial work through the Sol planning → Terra implementation workflow
5. Use the fast path only for established, localized changes
6. For a weekly update, use the full [weekly runbook](docs/ops/weekly_runbook.md), the sole operational authority. Reconcile the complete FBS schedule against fresh spread and total coverage; record capture time, missing game IDs, the next refresh and exact release gates. Prior null lines do not prove the provider still lacks lines.
7. Build the revision, refresh exact per-team-game score exceptions, and commit pinned inputs before preparing from a clean tree. Do not commit between prepare and the last release. Use `run_season.py` for prepare/release/rollback; legacy publish/freeze/close targets refuse execution. Production rollback requires the owner credential; provided wrappers do not support Preview rollback.

**Ending a Session:**
1. Create session log in `session_logs/YYYY-MM-DD/NN-slug.md`
2. Run validation scoped to the session and changed components
3. Do not broad-format a dirty worktree without explicit authorization
4. Propose a commit message; the user executes git operations manually
5. Update docs and the implementation contract when behavior changed; update `docs/status.md` when week state or the selected run changed (never copy run IDs elsewhere)

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
- **2026 Deliverable:** Vercel web app at `web/` featuring a full 4-tab operational interface (Picks, Results, Ratings, Performance) showing every FBS game's spread + total lean against market lines, certified Blitzkrieg V5 team ratings, and transparent performance tracking
- **Commands:** See `.codex/QUICKSTART.md` (Python + Nx task runner) and `web/README.md` (Next.js)
- **Architecture:** See `.agent/CONTEXT.md` (modeling) and `docs/ops/weekly_runbook.md` (data flow to web app)

### Dual-Stack Architecture (2026)

This is a **monorepo with two toolchains**:

| Component | Location | Stack | Test/Build |
|---|---|---|---|
| ML pipeline | root (`src/`, `scripts/`, `conf/`) | Python 3.12, uv (legacy Hydra/MLflow retained pending cleanup) | `npx nx run pipeline:test` or `make test` |
| Web app | `web/` | Next.js 16, TypeScript, npm, Tailwind v4 | `npx nx run web:build` or `make web-build` |
| Shared contracts | `contracts/` | SQL + TypeScript + Python | `make contracts-check` |
| Research | `scripts/research/` | Python (data-first runners and verifiers; see contract 2026-10-01/04) | — |
| Task runner | root (`nx.json`, `project.json`) | Nx 20 — cached cross-stack tasks | `npx nx run-many -t lint typecheck test build` |
| Shared storage | Cloudflare R2 | Parquet (pipeline reads) | — |
| Web data | Neon Postgres | `season_releases`, `season_release_*` + legacy compatibility and catalog/ops schemas | `scripts/pipeline/migrate_db.py --database-url` (verified target; append-only migrations through 0025; optional tables `game_venues`, `team_season_stats`) |

**Data flow:** Immutable R2 captures and reconciled Silver inputs → hash-pinned revision manifest → `run_season.py prepare` computes V5 measurements, ratings, predictions, grades and verified serving projections → Preview rehearsal → owner-approved atomic Production release in Neon → Vercel reads the active release through Drizzle with ISR. R2 is the durable source of truth; Neon is derived serving state. Legacy `publish_to_db.py` and direct `current_week` mutation are not the operational path.

**Web flags:** Matchup pages (`/matchup/[gameId]`) are a full-time site feature (emergency killswitch `CFB_MATCHUP_ENABLED=0`); `CFB_UI_TEST_MODE=1` serves fixture data for local runs and Playwright. See `web/README.md`.

**Conventions:**
- Python stays at root; never move or rename `src/`, `scripts/`, `conf/`, `tests/`.
- Next.js app is fully isolated in `web/` with its own `package.json` and `.gitignore`.
- **Single source of truth:** `contracts/` holds the canonical DB schema (`schema.sql`, `schema.ts`) and team-name mapping (`teams.py`, `teams.ts`; web logos are keyed by CFBD team id via `web/src/lib/team-logos.generated.ts`, built by `npm run logos:build`). The web app has local copies in `web/src/lib/` that must stay in sync. Run `make contracts-check` to validate sync.
- Production scripts live in `scripts/pipeline/` and `scripts/data/`. Active data-first research and V5 stage runners live in `scripts/research/`; the old top-level `research/` exploration folder was removed on 2026-10-01 (recoverable from git history).

---

## 🎯 2026 Season Execution Status

**Current status:** see [`docs/status.md`](docs/status.md) — the single source for live run IDs, week state and the scoreboard. Primary success metric: cumulative 2026 V5 ATS win % from Week 0 onward vs the 52.4% break-even at -110, spreads and totals reported separately, with strictly point-in-time inputs ([record methodology](docs/modeling/record_methodology.md)).

The 2026 buildout is complete; its strategic execution record is archived at
`docs/archive/2026-completed-plans/2026_historical_bootstrap_week0_execution.md`.
Production is live at `https://c-ks-picks-cfb.vercel.app` in approval-gated
`predictions` publication mode (revealed 2026-08-21). Active work is the
weekly operating cadence documented in `docs/ops/weekly_runbook.md`.

Dated checkpoints (Weeks 0-3, the Phase 1-6 buildout, the September V5 acceptance record and
the 2026-10-04 "current focus") now live in [`docs/status_history.md`](docs/status_history.md). They are
history, not current authority; use [`docs/status.md`](docs/status.md) for live state. The accepted
V5 model, its lineage and historical V4 are summarized in the
[V5 status guide](docs/modeling/v5_status.md). The 2026 record is one continuous V5 record from Week 0 (Week 4 and earlier were generated
retrospectively from point-in-time inputs; Week 5 was the first slate frozen before kickoff).

**Roadmap (2026 transition):** `docs/planning/roadmap.md` ·
**Weekly operations and release/rollback:** `docs/ops/weekly_runbook.md`

**Historical reference:** V2 workflow and prior rating research are retained in
`docs/archive/`; they are evidence, not current operating authority.

---

## 🔄 Key Workflows

### Branching (two long-lived branches)

- **`main`** — production. Vercel deploys from it; keep it releasable.
- **`dev`** — working branch. Day-to-day changes land here first.
- Optional short-lived branches (`feature/…`, `fix/…`) come off `dev`, merge back into `dev`, and are deleted after merging.
- Release by merging `dev` into `main` (fast-forward when possible). Do not commit to `main` directly except for an urgent production fix, and then merge it back into `dev`.
- No other long-lived branches. Delete merged branches, locally and on GitHub.

### Development Cycle

1. **Start from `dev`:** `git checkout dev && git pull` (use a short-lived branch off `dev` for larger work)
2. **Make changes:** Edit code, add tests
3. **Run scoped quality gates:** follow the active implementation contract or affected components
4. **Create session log:** Document work in `session_logs/`
5. **Commit:** User executes proposed commit
6. **Release:** merge `dev` into `main` when ready to deploy

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

### Weekly V5 Operations and Research

Use `make season-revision`, `season-prepare`, `season-release` and `season-rollback` under the [weekly runbook](docs/ops/weekly_runbook.md). Exact cutoff, environment, checksum, clean-tree and owner-approval requirements are mandatory. Started/reconstructed games remain visible because forecasts use only pre-cutoff observations; grading uses eligible pre-kickoff quotes under the [record methodology](docs/modeling/record_methodology.md).

Research lives in `scripts/research/` and requires an approved contract before changing the selected model or serving behavior. V4 training/Hydra/MLflow and Nx code remain pending deferred Phase 3 cleanup; their presence does not authorize operating V4. See `.codex/QUICKSTART.md` for current commands.

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

**Season Prepare / Release Refusal:**
- Confirm the revision URIs and SHA-256s, the intended wrapper and exact score-reconciliation exceptions.
- Prepare requires a clean tree; release requires the same commit as prepare.
- Check `season_verification_v2` failures and follow the weekly runbook rather than bypassing gates.

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
- ✅ Solution: exclude 2020 from all V5/research inputs and boundaries; preserve historical V4 chronology only for historical reproduction.

**Future Data Leakage:**
- ❌ Problem: Using future data in historical analysis
- ✅ Solution: Use `load_point_in_time_data()` for strict temporal splits

**Production-mode screenshots of gated pages:**
- ❌ Problem: `next start` returns the 404 page for gated routes (e.g. `/matchup`), so screenshots look "fine" but show nothing
- ✅ Solution: open gated routes with their flag (e.g. `CFB_MATCHUP_ENABLED=1`) plus `CFB_UI_TEST_MODE=1`, and look at the image before sending it

**Raw `db.execute()` in the web app:**
- ❌ Problem: the Neon HTTP driver returns `{ rows }`, not an array; code reading `res[0]` silently sees nothing (the `to_regclass` guards hid venues, selections and team stats this way)
- ✅ Solution: use `existsFrom`/`rowsOf` from `web/src/lib/db-result.ts`; fixture mode (`CFB_UI_TEST_MODE=1`) bypasses the database, so check optional-table features once against a real Preview database

**Correlated subqueries in drizzle selects:**
- ❌ Problem: in a single-table select drizzle renders `${table.col}` unqualified, so inside a subquery it binds to the inner alias (a row compared with itself; `EXISTS` always false)
- ✅ Solution: write the outer references with the table name (see `web/src/lib/tie-sql.ts`) and verify against real data; unit tests and fixtures cannot see this

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
- `scripts/research/**` (only when actively debugging or experimenting)
- `session_logs/` older than 3 days
- Files > 200 KB
- Files unchanged in last 30 days

**Load code on demand.** Only open source files when actively working on them.

---

## 🔗 Quick Links

### Essential Files

- **Commands:** `.codex/QUICKSTART.md` - All essential commands
- **Architecture:** `.agent/CONTEXT.md` - Project structure and domain knowledge
- **Season operations:** `docs/ops/weekly_runbook.md` - Revision, prepare, release and rollback
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

- **Operational config:** `conf/season/2026/` - Sealed model, revision manifests and exact score exceptions
- **Research:** `conf/research/` - Isolated candidate configurations
- **Historical configs:** `conf/model/`, `conf/features/`, `conf/experiment/` - Retained V4/Hydra compatibility, not operational authority


### Core Code

- **Config:** `src/cks_picks_cfb/config/` - Path configuration
- **Features:** `src/cks_picks_cfb/features/pipeline.py` - Feature engineering
- **Season engine:** `src/cks_picks_cfb/season/` - Chronological forecasts, verification, grading and atomic releases
- **Revision builder:** `scripts/pipeline/build_season_revision.py` - Controller inputs and cumulative registered market quotes
- **Operational CLI:** `scripts/pipeline/run_season.py` - Prepare, status, release and rollback
- **Contracts:** `contracts/` - DB schema and team mappings (single source of truth)
- **Research:** `scripts/research/` - Data-first research runners and verifiers

---

## 📝 Session Log Template

Create logs in `session_logs/YYYY-MM-DD/NN-slug.md`:

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

_Last Updated: 2026-10-15_
_Universal entry point for all AI coding assistants_
