# Skill: End Session

> **Workflow for cleanly ending a work session**
>
> Ensures proper cleanup, documentation, and handoff for next session.

---

## Purpose

Systematically wrap up a coding session by:
- Running quality gates
- Documenting work performed
- Proposing commits
- Preparing handoff for next session

---

## When to Use

- Finishing a work session
- Before taking a break
- After completing a task
- Before switching to different work

---

## Workflow

### Step 1: Run Health Checks

**Format code:**

```bash
# Auto-format all code
uv run ruff format .
```

**Check linting:**

```bash
# Check for linting issues
uv run ruff check .

# Auto-fix fixable issues
uv run ruff check . --fix
```

**Run tests:**

```bash
# Run all tests quietly
uv run pytest -q

# If failures, run verbose to debug
uv run pytest -v
```

**Record results:**
- ✅ All checks pass → Proceed
- ❌ Any failures → Fix or document why (technical debt)

### Step 2: Create Session Log

**Determine session number:**

```bash
# Check today's session logs
ls session_logs/$(date +%Y-%m-%d)/

# Next available number
```

**Create log file:**

```bash
# Create directory if needed
mkdir -p session_logs/$(date +%Y-%m-%d)

# File name format
session_logs/YYYY-MM-DD/NN-brief-description.md
```

**Use this template:**

```markdown
# Session: [Brief Description]

## TL;DR
- **Worked On:** [what was done]
- **Completed:** [what was finished]
- **Blockers:** [any issues encountered]
- **Next:** [what's next / what to resume]

## Changes Made
- **File 1:** [description of changes]
- **File 2:** [description of changes]
- **File 3:** [description of changes]

## Testing
- [x] Health checks pass
- [x] Tests pass (52 tests)
- [x] Documentation updated

## Technical Details
[Optional: Any technical notes for future reference]

## Notes for Next Session
[Critical context to carry forward]
- Resume at: [specific location or task]
- Remember: [important context]
- Watch out for: [any gotchas or considerations]

**tags:** ["modeling", "features", "pipeline", "refactoring", etc.]
```

### Step 3: Review Changes

**List modified files:**

```bash
# Check what changed
git status

# Review diffs
git diff

# Review staged changes
git diff --cached
```

**Verify:**
- All intended changes are present
- No unintended changes
- No debug code or print statements
- No commented-out code (unless intentional)

### Step 4: Propose Commit

**Analyze changes and propose commit message:**

**Format:**

```
type(scope): brief description

- Detailed change 1
- Detailed change 2
- Detailed change 3

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

**Types:**
- `feat:` - New feature
- `fix:` - Bug fix
- `refactor:` - Code restructuring
- `docs:` - Documentation only
- `test:` - Test additions/fixes
- `chore:` - Maintenance tasks

**Example:**

```bash
git add -A
git commit -m "$(cat <<'EOF'
feat(features): Add explosive play rate feature

- Implemented calculate_explosive_play_rate() in core.py
- Added unit tests with edge case coverage
- Updated feature config to include new feature
- Documented in features.md

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
EOF
)"
```

**Present to user:**
- Show proposed commit message
- List files to be committed
- Ask for approval
- User executes the commit command

### Step 5: Update Documentation (If Needed)

**Check if docs need updates:**

- [ ] Added new feature? → Update `docs/modeling/features.md`
- [ ] Changed API? → Update relevant docs
- [ ] New workflow? → Update process docs
- [ ] Config changes? → Update `.codex/HYDRA.md` or AGENTS.md

**Make minimal, targeted updates:**
- Focus on what changed
- Don't add aspirational content
- Keep it factual and current

### Step 6: Prepare Handoff

**Create handoff summary in session log:**

```markdown
## Notes for Next Session

**Resume at:**
[Specific file, function, or task to continue]

**Context:**
- [Important decision made]
- [Key insight discovered]
- [Pattern to follow]

**Watch out for:**
- [Gotcha or consideration]
- [Known issue or limitation]

**Next steps:**
1. [Specific next action]
2. [Subsequent action]
3. [Follow-up task]
```

---

## Checklist

### Quality Gates
- [ ] Run `uv run ruff format .` (code formatting)
- [ ] Run `uv run ruff check .` (linting)
- [ ] Run `uv run pytest -q` (all tests pass)
- [ ] Review diffs for unintended changes

### Documentation
- [ ] Create session log in `session_logs/YYYY-MM-DD/NN-description.md`
- [ ] Document what was done (TL;DR section)
- [ ] Document next steps (handoff section)
- [ ] Add relevant tags

### Commit Preparation
- [ ] Review all changed files
- [ ] Propose commit message (conventional commit format)
- [ ] Stage files: `git add -A`
- [ ] Present commit for user to execute

### Handoff
- [ ] Notes for next session are clear
- [ ] Resume point is specific
- [ ] Context is captured
- [ ] Blockers are documented

---

## Common Mistakes to Avoid

❌ **Skipping tests** - Always run tests before ending
❌ **Vague session logs** - Be specific about what was done
❌ **Committing without review** - Always review diffs first
❌ **No handoff notes** - Future you will thank past you
❌ **Forgetting Co-Authored-By** - Give credit to AI assistant

---

## Output Template

```markdown
## Session End Summary

### Health Checks
✅ Formatting: PASSED
✅ Linting: PASSED
✅ Tests: 52 PASSED

### Session Log Created
Location: `session_logs/2026-02-13/01-description.md`

### Changes Summary
- Modified: 3 files
- Added: 1 file
- Deleted: 0 files

Files:
- src/features/core.py (+20 lines)
- tests/test_aggregations_core.py (+30 lines)
- conf/features/standard_v1.yaml (+1 line)
- docs/modeling/features.md (+10 lines)

### Proposed Commit

\`\`\`bash
git add -A
git commit -m "$(cat <<'EOF'
feat(features): Add explosive play rate feature

- Implemented calculate_explosive_play_rate() in core.py
- Added unit tests with edge case coverage
- Updated feature config to include new feature
- Documented in features.md

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
EOF
)"
\`\`\`

**Please execute the above commit command.**

### Handoff for Next Session
**Resume at:** Testing the new feature in production pipeline
**Key context:** Feature calculates plays ≥10 yards as % of total plays
**Next step:** Run full pipeline with new feature included
```

---

_Last Updated: 2026-02-13_
_Session cleanup and documentation workflow_
