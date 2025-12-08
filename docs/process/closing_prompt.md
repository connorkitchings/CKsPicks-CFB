# 🏁 CFB Model — Session Closing Prompt

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
   - If weekly predictions were generated, confirm the `CFB_weekXX_bets.csv` file has **one row per
     game** (use `df['Game'].nunique()` as a quick check). Re-run the generator if duplicates remain.

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
   - Also review `docs/process/first_prompt.md` and `docs/process/last_prompt.md` if workflow guidance changed (e.g., new flows, health checks).
   - Update any relevant documentation based on the changes made during the session.
   - When weekly picks are ready to share, send a **test** email first:
     `uv run python -m scripts.publish_picks --year <YYYY> --week <WW> --mode test`. Once the test
     render looks good, repeat with `--mode prod` to notify the full list.

7. **Commit and Push Changes:**

   - Stage all changes: `git add .`
   - Commit with descriptive message:

     ```bash
     git commit -m "feat(v2): [brief description of session work]

     - [Key outcome 1]
     - [Key outcome 2]
     - [Key outcome 3]"
     ```

   - Push to remote: `git push origin main`

After you have generated the dev log and committed changes, the session is complete.

### Usage Tips

- **Automate**: You can store these snippets in your editor snippets for one-click insertion.
- **Enforce Links**: Always use the linking syntax to keep logs and docs interconnected.
- **Be Concise**: Logs should capture _decisions and results_, not every keystroke.
- **Review Checklist**: Before ending, run `pre-commit run --all-files` to catch linting issues.

---

By following these templates, each AI development session starts with the right context and ends
with a clean, traceable record—ensuring continuity and accountability across the project.
