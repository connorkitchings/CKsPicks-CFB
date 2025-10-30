# Gemini CLI Run Rules (Slim)

> **Purpose:** Keep operational IQ while holding prompt size low. This file is the **single source of truth** for read‑order, budgets, and pointers. It must remain ≤ **5,000 tokens**.

---

## ⚠️ Context Budget & Read Rules

### Hard limits

- **gemini.md max:** 3–5k tokens
- **Total context budget:** ≤ 50k tokens **before** reading source code
- **Read order:** `README.md` → `mkdocs.yml` → `pyproject.toml` → **Minimal Context Pack** (pointers only) → last **3 days** session logs (**TL;DR only**)
- **Stop conditions:** budget reached **or** required section found

### Denylist (never read unless explicitly asked)

- `artifacts/**`, `.venv/**`, `.git/**`, `__pycache__/`
- `notebooks/**` (exploratory only)
- `session_logs/` older than 3 days
- Any file **> 200 KB**

### Recency gate

- Only pull extra context from files changed in the last **30 days**: `git diff --name-only --since=30.days`
- If unchanged, the pointer index is sufficient; do **not** open the file.

### Section gating

- Read **only** the named headings/sections below. Never scan entire files or directories.

---

## Minimal Context Pack (Pointer Index)

Read **only these sections** (skip everything else) and only if needed for the current task:

### Core docs

1. `README.md` → **Getting Started**, **Project Structure**, **Development Workflow**
2. `mkdocs.yml` → nav structure only
3. `pyproject.toml` → **[project.dependencies]**, **[tool.ruff]** (skip metadata/build-system)
4. `docs/project_org/project_charter.md` → **Project Scope**, **Success Criteria**
5. `docs/planning/roadmap.md` → **Current Sprint** (top section only)
6. `docs/decisions/decision_log.md` → **last 3 entries only**

### Task‑specific

- **Modeling** → `docs/project_org/modeling_baseline.md` → **Ensemble Configuration**
- **Weekly ops** → `docs/operations/weekly_pipeline.md` → **Schedule**, **Steps**
- **Features** → `docs/project_org/feature_catalog.md` → **Conventions**, **Opponent‑adjusted features** _(skip tables unless debugging)_
- **Betting** → `docs/project_org/betting_policy.md` → **Unit Sizing Methodology (Option A only)** _(read only when sizing)_

### Session logs

- Latest `session_logs/<date>/<nn>.md` → **TL;DR (≤5 lines)** and **tags** only
- Open full log **only if** tags match the current task

### Code anchors (open **on demand**, not preloaded)

- `src/config.py` — data paths/constants
- `src/utils/local_storage.py` — storage patterns
- `src/features/pipeline.py` — feature engineering
- `src/models/train_model.py` — training loop
- `scripts/generate_weekly_bets_clean.py` — prediction output
- `scripts/cli.py` — CLI commands
- `tests/test_*.py` — usage examples

---

## Ten‑line Command Cache (use README for everything else)

```bash
uv sync --extra dev && source .venv/bin/activate
uv run ruff format . && uv run ruff check .
uv run pytest
uv run mkdocs serve
mlflow ui --backend-store-uri file:///$(pwd)/artifacts/mlruns
python -c 'from cfb_model.flows.preaggregations import preaggregations_flow as f; f(year=2024)'
PYTHONPATH=src uv run python -m models.train_model --train-years 2019,2021,2022,2023 --test-year 2024
uv run python scripts/cli.py aggregate preagg --year 2024
uv run python scripts/ingest_cli.py games --year 2024 --season-type regular
uv run python scripts/run_ingestion_year.py --year 2024 --data-root "$CFB_DATA_ROOT"
```

> If you need additional commands, **open README.md** (do not expand this cache here).

---

## Session Initialization Flow

```text
Base files (section‑gated) → Minimal Context Pack (pointers only) → latest session log TL;DR → open code anchors on demand
```

**Stop reading** when you have enough context, you hit the budget, or the file hasn’t changed in 30 days.

---

## Session Log Micro‑Summary Template

> Each new log must start with a TL;DR and tags. Read **only** this block by default; open the full log **only if** tags match the task.

```md
# TL;DR (≤5 lines)

- What was attempted
- Key outcome(s)
- Blockers/bugs (IDs or files)
- Next action(s)
- Owner/date

**tags:** ["ingestion", "features", "modeling", "sweeps", "mlflow", "hydra", "infra", "docs"]
```

---

## Call‑When‑Needed Stubs

Use **what → where** pointers instead of inlining long how‑to’s.

- To run weekly bets: call `scripts/generate_weekly_bets_clean.py` — see **README ▸ Operations ▸ Weekly bets**.
- If MLflow fails to log artifacts: open **docs/decisions/decision_log.md** (latest entry) for known issue + workaround.
- To sweep hyperparameters: see **conf/hydra/sweeper/** and **README ▸ Hydra ▸ Multirun**.
- Environment variables: see **.env.example** at repo root (do not inline here).

---

## Data & Modeling Rules (micro form)

- **No data leakage:** training strictly precedes prediction
- **Lines/odds:** never as model features; only for edge calculation
- **Eligibility:** min 4 games before betting
- **Window:** train 2014–2023 (skip 2020); holdout 2024
- **Columns:** `off_*`, `def_*`, `adj_*`; always include `season`, `week`, `game_id`

> For details, open the pointer sections in **feature catalog**, **modeling baseline**, and **weekly pipeline**.

---

## MLflow & Hydra (pointers only)

- **MLflow:** open `README.md` → _Monitoring_ section for launch commands; compare runs via UI
- **Hydra configs:** `conf/config.yaml` and `conf/model/*` for overrides; use CLI overrides (e.g., `model=spread_xgboost`) and multirun `-m` when needed

Note: Do not paste configs or long CLI examples into prompts — follow pointers.

---

## PR & Docs Discipline (thin)

- Run format/lint/tests before PR
- Update impacted docs and **append** to `docs/decisions/decision_log.md` for material changes
- PR description: summary, linked issues, validation results, screenshots/logs (if UI)

---

## Do / Don’t

### Do

- Cite exact _file + heading_ before reading
- Prefer files touched in last 30 days
- Summarize newly read context in **≤200 tokens** before acting

### Don’t

- Inline large tables, policies, or long command blocks
- Scan entire directories
- Read from denylisted paths or files > 200 KB

---

## Maintenance

- This file must stay ≤ **5,000 tokens**; if it grows, remove examples first (keep pointers)
- Re‑audit the pointer list monthly; prefer fewer, sharper pointers over breadth
