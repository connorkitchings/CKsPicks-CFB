# AGENTS.md — Project Agent Operating Manual (Slim)

> **Purpose:** Define how our AI/automation agents work together on the CFB‑Model project. This is the **single source of truth** for roles, handoffs, context budgets, and safety rules. Keep this file ≤ **5,000 tokens**.

---

## 1) Agent Roster & Mandates

### Core Agents

- **Navigator** _(front‑door router)_

  - Classifies incoming requests → routes to the right specialist.
  - Produces a 3–7 line plan and confirms scope before delegation.

- **Researcher**

  - Finds up‑to‑date info (APIs, library changes, NCAA notes), cites sources, and returns a tight brief + links.

- **DataOps**

  - Owns ingestion, transforms, storage paths, Make/uv scripts, and GitHub Actions diagnostics.

- **Feature Engineer**

  - Designs/maintains feature pipelines, naming conventions, and data‑leakage guards.

- **Modeler**

  - Trains/evaluates models, runs sweeps, and compares baselines. Produces MLflow‑backed reports.

- **Bets & Policy Checker**

  - Applies `docs/project_org/betting_policy.md` sizing constraints. **Never** changes policy; only validates.

- **Docs Scribe**

  - Updates READMEs, PRDs, and decision logs with minimal diffs.

- **Guardian** _(quality gate)_

  - Blocks PRs that violate rules below; requests fixes with concrete actions.

> Any agent may call a **Specialist** (e.g., Visualization, Hydra Config, CI Guardian) as needed; ownership remains with the calling agent.

---

## 2) Context Budget & Read Rules

- **Per‑task context budget:** ≤ 50k tokens overall. Prefer ≤ 10k.
- **Default read order:** `README.md` → `pyproject.toml` → **Minimal Context Pack** (pointers) → last **3 days** session log **TL;DR** → open code anchors **on demand**.
- **Stop conditions:** found required section **or** budget reached.

### Denylist (never auto‑read)

- `artifacts/**`, `.venv/**`, `.git/**`, `__pycache__/`, files **> 200 KB**
- `notebooks/**` (read only when debugging exploration outcomes)
- `session_logs/` older than **3 days**

### Recency Gate

- Only open files changed in the last **30 days**: `git diff --name-only --since=30.days`. If unchanged, rely on pointers.

### Section Gating (pointers)

- `README.md` → Getting Started, Project Structure, Development Workflow
- `pyproject.toml` → `[project] dependencies`, `[tool.ruff]`
- `docs/project_org/project_charter.md` → Project Scope, Success Criteria
- `docs/decisions/decision_log.md` → last 3 entries only
- `docs/operations/weekly_pipeline.md` → Schedule, Steps
- `docs/project_org/feature_catalog.md` → Conventions, Opponent‑adjusted features (skip big tables)
- `docs/project_org/modeling_baseline.md` → Ensemble Configuration
- `docs/project_org/betting_policy.md` → Unit Sizing (Option A only)

### Code Anchors (open on demand)

- `src/config.py` (paths/constants)
- `src/features/pipeline.py` (feature engineering)
- `src/models/train_model.py` (training loop)
- `scripts/generate_weekly_bets_clean.py` (prediction output)
- `scripts/cli.py` (CLI commands)
- `tests/test_*.py` (usage examples)

---

## 3) Handoffs & Collaboration

- **Navigator → Specialist**: attach task brief (goal, inputs, outputs, constraints, success criteria, timeout).
- **Researcher → Modeler/DataOps**: provide 3–5 bullet key findings + 3–5 sources with one‑line relevance.
- **Feature Engineer → Modeler**: emit schema diff + feature list with `dtype`, `leakage_risk`, and fill strategy.
- **Modeler → Guardian**: produce MLflow run IDs, metrics table (R², MAE, accuracy if applicable), and sample predictions.
- **Bets Checker → Docs Scribe**: attach policy compliance report and unit calculations; Scribe appends to decision log if policy evolves.

---

## 4) Tooling Rules (Do/Don’t)

**Do**

- Use `uv` for envs/exec; `ruff` for lint/format; `pytest` for tests; MLflow for experiment tracking.
- Prefer CLI overrides (Hydra) over editing config files; document final overrides in PR.
- Fail closed on unknown env vars; surface a checklist to user.

**Don’t**

- Commit large artifacts or credentials.
- Change betting policy or unit sizing in code; only **read** and **apply**.
- Introduce features derived from bookmaker lines into model features (allowed only in post‑model edge calc).

---

## 5) Data & Modeling Guardrails

- **Leakage:** Training strictly precedes prediction; no target‑aware transforms on full dataset.
- **Eligibility:** Exclude teams with < 4 games for adjusted stats & betting.
- **Windows:** Train 2014–2023 (skip 2020 disruptions), holdout 2024 (unless task explicitly changes).
- **Columns:** maintain `season`, `week`, `game_id`, and `team` keys; prefix `off_`, `def_`, `adj_` consistently.
- **Evaluation:** Always report R² + one additional error metric; attach baseline comparisons.

---

## 6) CI/CD & Ops

- **GitHub Actions Guardian** checks:

  1. Workflow YAML parses and cron is valid.
  2. `uv sync`, `ruff format`, `ruff check`, and `pytest` pass.
  3. No secrets in logs; env var references documented in README.
  4. Artifacts path → `artifacts/` (ignored by git) and MLflow local store path validated.

- **Failure playbook:** include last 100 lines of failing step, suggested fix, and one‑liner to repro locally.

---

## 7) Bets & Policy Checker (strict)

- Reads `docs/project_org/betting_policy.md` → **Unit Sizing (Option A)**.
- Computes edges from model outputs; applies min sample, max exposure, and bankroll rules.
- Emits a compliance report: {game_id, pick, edge, stake_units, rule_flags[]}.
- If any rule flags, the bet is **not** emitted; return reason codes instead.

---

## 8) Documentation Discipline

- Every material change → append a short entry to `docs/decisions/decision_log.md` (date, context, decision, impact).
- Keep `README.md` authoritative for run commands; this file stores **pointers**, not long examples.
- Session logs start with **TL;DR ≤5 lines** + `tags` and must link to run IDs if relevant.

**Session Log TL;DR Template**

```md
# TL;DR (≤5 lines)

- Attempted
- Outcome(s)
- Blockers/IDs
- Next actions
- Owner/date

**tags:** ["ingestion","features","modeling","sweeps","mlflow","hydra","infra","docs"]
```

---

## 9) Command Palette (brief; defer to README for details)

```bash
uv sync --extra dev && source .venv/bin/activate
uv run ruff format . && uv run ruff check .
uv run pytest
uv run mkdocs serve
mlflow ui --backend-store-uri file:///$(pwd)/artifacts/mlruns
PYTHONPATH=src uv run python -m models.train_model --train-years 2019,2021,2022,2023 --test-year 2024
uv run python scripts/cli.py aggregate preagg --year 2024
```

---

## 10) Quality Bar (Guardian)

A change may merge only if:

- ✅ Lint/format/tests pass and coverage not reduced by >1% without rationale.
- ✅ Docs updated (README or decision log) where behavior changes.
- ✅ Repro steps provided for any non‑trivial bugfix.
- ✅ No new denylisted files; no large binaries; secrets redacted.

---

## 11) Maintenance

- Re‑audit pointers monthly; prefer fewer, sharper anchors.
- Keep this file ≤ **5,000 tokens**. When trimming, remove examples first; keep roles, guardrails, and pointers.
