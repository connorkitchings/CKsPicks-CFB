# AI Development Session Templates

This document provides **copy-paste templates** for starting and ending an AI-assisted development
session. Each template ensures the assistant gathers the right context, operates within project
standards, and records its work correctly.

---

## 🟢 Session Kickoff Prompt

This is a template prompt to start a new AI session for the cfb_model project. Copy, paste, and fill
in the bracketed information to bring the AI up to speed quickly.

Hello. We are continuing our work on the 'cfb_model' project. Your role is my AI co-pilot, and we
will be following the Vibe Coding System.

To get up to speed, please perform the following steps:

1. **Load the Minimal Context Pack (token-efficient):**
    - `docs/project_org/project_charter.md` — Charter, scope, and standards.
    - `docs/planning/roadmap.md` — Current sprint goal, tasks, and acceptance criteria.
    - `docs/decisions/decision_log.md` — Planning-level decisions made so far.
    - `docs/project_org/modeling_baseline.md` — MVP modeling approach and betting policy.
    - `docs/operations/weekly_pipeline.md` — Manual weekly runbook and outputs.
    - Optional quick refs: `docs/index.md`, `README.md`, `pyproject.toml` (only if needed).
    - Keep context small: skim headings and bullet summaries; capture 6–10 concise bullets.

2. **Confirm the Sprint Focus:**
    - From `docs/planning/roadmap.md`, extract the sprint goal and top 3 active tasks.
    - Note acceptance criteria relevant to today's objective.

3. **Quick Health Check (fast, optional):**
    - `uv run ruff check .` — ensure linter is clean or note issues to fix.
    - `uv run pytest -q` — run unit tests (synthetic tests exist; no external data needed).
    - `uv run mkdocs build --strict` — catch doc reference issues if docs are in scope.

3. **Review the Last Session's Handoff:**
    - Search `/session_logs/` for all `.md` files matching today's date (e.g., `2025-08-03.md`,
      `2025-08-03_02.md`, etc.).
    - Review the most recent session log entry to understand exactly where we left off, focusing on
      the 'Session Handoff' section.
    - If there are multiple logs for today, always use the highest-numbered log (e.g., `_02`, `_03`
      etc.) as the most recent handoff.
    - If no log exists for today, check the latest `.md` file with the most recent date.

4. **Prepare for Today's Task:**
    - **Our focus today is:** `[Describe the concrete task to execute this session]`
    - Note: Data paths resolve via `CFB_MODEL_DATA_ROOT` or default `./data` (see `src/cfb_model/config.py`).
    - Prefect flows available: `preaggregations_flow(year, data_root=None, verbose=True)` in `cfb_model.flows.preaggregations`.

Once you have completed this review, please confirm you are ready, and we will begin.

## 🔴 Session Closing Prompt

This is a template prompt to end a development session cleanly. Copy, paste, and fill in the
bracketed information.

We are now ending our development session for today. To ensure we maintain our project context and
prepare for a smooth handoff, please perform the following wrap-up tasks:

1. **Summarize Session Accomplishments:**
    - **Task Completed:** `[IMPL-task:ID] - [Brief description of the task]`
    - **Key Outcomes:** `[List the 1-3 main achievements of the session, e.g., 'Successfully
      connected to the CollegeFootballData API to ingest play-by-play data.']`

2. **Identify Blockers and Learnings:**
    - **Blockers Encountered:** `[Describe any issues that are preventing progress, e.g., 'The API
      is rate-limiting our requests.']`
    - **New Learnings/Patterns:** `[Mention any new solutions or patterns discovered that should be
      added to the knowledge_base.md, e.g., 'Found a more efficient way to parse JSON responses.']`

3. **Define Next Steps:**
    - **Immediate Next Task:** `[What is the very next thing to do? e.g., 'Refactor the data
      ingestion pipeline to handle rate-limiting.']`

4. **Final Health Check:**
    - Run `uv run ruff check .` and `uv run ruff format .` to ensure code quality
    - Run `uv run pytest tests/ -v --tb=short` to verify all tests pass
    - Run `uv run mkdocs build --quiet` to verify documentation builds correctly
    - Include health check results in the dev log

5. **Generate the Dev Log:**
    - Based on the information above, please generate a complete dev log entry for today.
    - Use the template from `session_logs/_template.md`.
    - **Important:** Create a new directory for today's date `[YYYY-MM-DD]` inside `/session_logs/`
      if it doesn't exist.

- Create the new log with a sequential, zero-padded filename (e.g., `01.md`, `02.md`) inside the
    date directory.

6. **Update Documentation:**
    - Review `README.md`,`docs/index.md`, `pyproject.toml`, `docs/decisions/README.md`,
      `mkdocs.yml`, `docs/project_org/project_charter.md`, and `docs/project_org/kb_overview.md`.
    - Also review `docs/guides/ai_session_templates.md` if workflow guidance changed (e.g., new flows, health checks).
    - Update any relevant documentation based on the changes made during the session.

After you have generated the dev log, I will review it and make any final edits. All version control
(committing, pushing, etc.) is handled manually and outside the AI workflow.

### Usage Tips

- **Automate**: You can store these snippets in your editor snippets for one-click insertion.
- **Enforce Links**: Always use the linking syntax to keep logs and docs interconnected.
- **Be Concise**: Logs should capture *decisions and results*, not every keystroke.
- **Review Checklist**: Before ending, run `pre-commit run --all-files` to catch linting issues.
- **Manual Version Control**: All actions related to git (committing, pushing, branching, etc.)
  must be performed manually by the user. The AI will never perform these actions or prompt you to
  do so automatically.

---

By following these templates, each AI development session starts with the right context and ends
with a clean, traceable record—ensuring continuity and accountability across the project.
