AGENTS.md — Project Agent Operating Manual (Slim)

Purpose: Define how our AI/automation agents work together on the CFB-Model project. This is the single source of truth for roles, handoffs, context budgets, and safety rules. Keep this file ≤ 5,000 tokens.

0. Session Lifecycle & Default Prompts
   0.1 What is a "session"?

A session is a single AI coding run in Gemini, Codex, ChatGPT, LM Studio, etc.
A new session starts every time you open the repo in an AI tool.
A session ends when:

The session closing template in docs/guides/ai_session_templates.md has been run, and
A new session_logs/YYYY-MM-DD/NN.md entry has been created and updated.

All agents (Navigator, Researcher, etc.) operate inside this session envelope.
0.2 Default Session Kickoff (first prompt)
At the start of every AI coding session, the first user message should always do three things:

Tell the AI to load only the minimal required context.
Tell the AI to review recent session logs.
Force the AI to propose a plan before implementation.

Canonical first prompt (you can copy/paste and lightly edit per session):

Review the required codebase and documentation to get up to speed on the project. Then, review the last 3 days of session logs to gain an understanding of recent developments. Finally, develop a clear, thorough, and high-level plan for the next steps of this project. Do not begin implementing the plan before I review and approve the plan.

Agents must respond to this kickoff by:

Following the context rules in §2.
Producing a 3–7 line plan (Navigator role) with:

Goal
Key steps
Expected outputs
Risks / open questions

Explicitly asking for approval:
"Ready to proceed with Step 1 once you approve this plan."

Implementation only starts after the human confirms the plan.

For more detailed kickoff steps (Minimal Context Pack, health checks), see docs/guides/ai_session_templates.md and gemini.md.

0.3 Standard Session Closing Ritual (includes git)
At the end of any session where code or docs changed and the closing template is invoked, the AI must drive this flow:

Summarize the session

Use the TL;DR pattern in §8 and session_logs/\_template.md.
Call out: tasks attempted, outcomes, blockers, next steps, and relevant run IDs.

Generate / update the dev log

Create or update session_logs/YYYY-MM-DD/NN.md with:

TL;DR + tags
Body sections from the closing template in docs/guides/ai_session_templates.md.

Update docs

If behavior, interfaces, or workflows changed, propose small diffs for:

README.md
Relevant docs in docs/project_org/ and docs/operations/

Keep changes minimal and clearly scoped.

Health checks

Recommend running (or report results if already run during the session):

uv run ruff format . && uv run ruff check .
uv run pytest -q
uv run mkdocs build --quiet (if docs were touched)

Commit to GitHub after every session (manual git, AI-assisted messaging)
If any code or docs changed in this session and a dev log was created:

AI must:

Show a proposed commit message, e.g.
chore: update session log and docs for <task slug>
Remind you to run:

bash git status
git add <changed files>
git commit -m "<proposed message>"
git push origin <branch-name>

Git operations remain manual:

The AI never executes git, but it must prompt for a commit/push as the final step of the closing ritual when changes occurred.

If nothing changed (pure planning / reading), step 5 becomes:
"No code/docs changes detected; no commit needed this session."

1. Agent Roster & Mandates
   Core Agents

Navigator (front-door router)

First responder for new sessions and new tasks.
Classifies incoming requests → routes to the right specialist.
Produces a 3–7 line plan and confirms scope before delegation.
Keeps track of which roles have been "activated" this session and ensures a clean handoff back to the user.

Researcher

Finds up-to-date info (APIs, library changes, NCAA notes), cites sources, and returns a tight brief + links.
Flags uncertainty explicitly instead of guessing; suggests experiments or measurements when docs are unclear.

DataOps

Owns ingestion, transforms, storage paths, Make/uv scripts, and GitHub Actions diagnostics.
CRITICAL: All raw and processed data MUST reside on the external drive specified by CFB_MODEL_DATA_ROOT environment variable (NOT in project root). This is a hard constraint.
Ensures local vs. CI paths, env vars, and data volumes are consistent with src/config.py and docs.
Always validates data root path exists before any read/write operations.

Feature Engineer

Designs/maintains feature pipelines, naming conventions, and data-leakage guards.
Keeps docs/project_org/feature_catalog.md aligned with actual feature columns.

Modeler

Trains/evaluates models, runs sweeps, and compares baselines. Produces MLflow-backed reports.
Always reports metrics vs. baseline and documents any change in modeling assumptions.

Bets & Policy Checker

Applies docs/project_org/betting_policy.md sizing constraints. Never changes policy; only validates.
Returns reason codes when a candidate bet violates any rule (bankroll, exposure, eligibility, etc.).

Docs Scribe

Updates READMEs, PRDs, and decision logs with minimal diffs.
Keeps docs consistent with the actual code and pipelines—no aspirational sections.

Guardian (quality gate)

Enforces the rules in this file and in development_standards.md.
Blocks PRs / changes that violate guardrails and requests fixes with concrete, actionable changes.
Can stop a task mid-session if it detects scope creep, data leakage, or betting-policy violations.

Any agent may call a Specialist (e.g., Visualization, Hydra Config, CI Guardian) as needed; ownership remains with the calling agent.

2. Context Budget & Read Rules
   🚨 CRITICAL: External Data Root Configuration 🚨
   Before any data operation, verify:

CFB_MODEL_DATA_ROOT environment variable is set (e.g., '/Volumes/CK SSD/Coding Projects/cfb_model/')
The path exists and is accessible
All raw and processed data paths resolve to this external root, NOT to the project directory

Common mistake: Creating a local data/ folder in project root. This is WRONG. All data operations must use the external drive path from the environment variable.
Validation check: Any script that reads/writes data should fail loudly if CFB_MODEL_DATA_ROOT is not set or the path doesn't exist.
Standard Context Rules

Per-task context budget: ≤ 50k tokens overall. Prefer ≤ 10k.
Default read order: README.md → pyproject.toml → Minimal Context Pack (pointers) → last 3 days session log TL;DR → open code anchors on demand.
Stop conditions: found required section or budget reached.

Denylist (never auto-read)

artifacts/**, .venv/**, .git/**, **pycache**/, files > 200 KB
notebooks/** (read only when debugging exploration outcomes)
session_logs/ older than 3 days

Recency Gate

Only open files changed in the last 30 days: git diff --name-only --since=30.days. If unchanged, rely on pointers.

Section Gating (pointers)

README.md → Getting Started, Project Structure, Development Workflow
pyproject.toml → [project] dependencies, [tool.ruff]
docs/project_org/project_charter.md → Project Scope, Success Criteria
docs/decisions/decision_log.md → last 3 entries only
docs/operations/weekly_pipeline.md → Schedule, Steps
docs/project_org/feature_catalog.md → Conventions, Opponent-adjusted features (skip big tables)
docs/project_org/modeling_baseline.md → Ensemble Configuration
docs/project_org/betting_policy.md → Unit Sizing (Option A only)

Code Anchors (open on demand)

src/config.py (paths/constants)
src/features/pipeline.py (feature engineering)
src/models/train*model.py (training loop)
scripts/generate_weekly_bets_clean.py (prediction output)
scripts/cli.py (CLI commands)
tests/test*\*.py (usage examples)

3. Handoffs & Collaboration

Navigator → Specialist: attach task brief (goal, inputs, outputs, constraints, success criteria, timeout).
Researcher → Modeler/DataOps: provide 3–5 bullet key findings + 3–5 sources with one-line relevance.
Feature Engineer → Modeler: emit schema diff + feature list with dtype, leakage_risk, and fill strategy.
Modeler → Guardian: produce MLflow run IDs, metrics table (R², MAE, accuracy if applicable), and sample predictions.
Bets Checker → Docs Scribe: attach policy compliance report and unit calculations; Scribe appends to decision log if policy evolves.

4. Tooling Rules (Do/Don't)
   Do

Use uv for envs/exec; ruff for lint/format; pytest for tests; MLflow for experiment tracking.
ALWAYS verify CFB_MODEL_DATA_ROOT is set before any data operation and that it points to the external drive (not project root).
Prefer CLI overrides (Hydra) over editing config files; document final overrides in PR.
Fail closed on unknown env vars; surface a checklist to user.

Don't

NEVER create a data/ directory in the project root - all data must live on the external drive.
Commit large artifacts or credentials.
Change betting policy or unit sizing in code; only read and apply.
Introduce features derived from bookmaker lines into model features (allowed only in post-model edge calc).

5. Data & Modeling Guardrails

Storage Location: All raw and processed data resides on external drive at CFB*MODEL_DATA_ROOT. Validate this path exists before any I/O.
Leakage: Training strictly precedes prediction; no target-aware transforms on full dataset.
Eligibility: Exclude teams with < 4 games for adjusted stats & betting.
Windows: Train 2014–2023 (skip 2020 disruptions), holdout 2024 (unless task explicitly changes).
Columns: maintain season, week, game_id, and team keys; prefix off*, def*, adj* consistently.
Evaluation: Always report R² + one additional error metric; attach baseline comparisons.

6. CI/CD & Ops

GitHub Actions Guardian checks:

Workflow YAML parses and cron is valid.
uv sync, ruff format, ruff check, and pytest pass.
No secrets in logs; env var references documented in README.
Artifacts path → artifacts/ (ignored by git) and MLflow local store path validated.

Failure playbook: include last 100 lines of failing step, suggested fix, and one-liner to repro locally.

7. Bets & Policy Checker (strict)

Reads docs/project_org/betting_policy.md → Unit Sizing (Option A).
Computes edges from model outputs; applies min sample, max exposure, and bankroll rules.
Emits a compliance report: {game_id, pick, edge, stake_units, rule_flags[]}.
If any rule flags, the bet is not emitted; return reason codes instead.

8. Documentation Discipline

Every material change → append a short entry to docs/decisions/decision_log.md (date, context, decision, impact).
Keep README.md authoritative for run commands; this file stores pointers, not long examples.
Session logs start with TL;DR ≤5 lines + tags and must link to run IDs if relevant.

Session Log TL;DR Template
md# TL;DR (≤5 lines)

- Attempted
- Outcome(s)
- Blockers/IDs
- Next actions
- Owner/date

**tags:** ["ingestion","features","modeling","sweeps","mlflow","hydra","infra","docs"]

Last Updated: 2025-01-03
Keep this file under 5,000 tokens for fast agent loading
