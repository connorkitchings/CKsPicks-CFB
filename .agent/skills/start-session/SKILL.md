# Skill: Start Session

> **Workflow for initializing a new work session**
>
> Ensures proper context loading and validation before starting work.

---

## Purpose

Systematically prepare for a new coding session by:
- Loading critical project context
- Verifying environment configuration
- Understanding recent work
- Proposing a clear plan before implementation

---

## When to Use

- Beginning a new coding session
- Returning to the project after a break
- Starting work on a new task
- First-time setup with the project

---

## Workflow

### Step 1: Load Critical Context

**Read in order:**

1. **AGENTS.md** - Critical rules and overview
   - Pay special attention to Data Root Configuration
   - Note any V2 workflow status updates

2. **.codex/QUICKSTART.md** - Essential commands reference
   - Skim for commands you'll need

3. **.agent/CONTEXT.md** - Architecture and domain knowledge
   - Read if working on architecture or features
   - Skip if task is isolated

### Step 2: Verify Environment

**Check data root configuration:**

```bash
# Verify environment variable is set
echo $CFB_MODEL_DATA_ROOT

# Check if external drive is mounted (or cloud storage configured)
ls "$CFB_MODEL_DATA_ROOT"

# Expected output: Lists raw/, processed/, features/, etc.
```

**If verification fails:**
- Alert user immediately
- Request they verify drive is mounted
- Confirm `CFB_MODEL_DATA_ROOT` is set in `.env`
- Do NOT proceed with data operations

### Step 3: Review Recent Work

**Read last 3 days of session logs:**

```bash
# List recent session logs
find session_logs/ -name "*.md" -mtime -3 | sort
```

**Look for:**
- Recent changes and decisions
- Blockers or issues
- In-progress work
- Context about current state

**Summarize findings:**
- What was worked on recently?
- Any unresolved issues?
- What's the current focus area?

### Step 4: Check Git Status

```bash
# Check current branch
git branch --show-current

# Check working tree status
git status

# Check recent commits
git log --oneline -n 5
```

**Note:**
- Current branch (should not be `main` for work)
- Uncommitted changes
- Recent commits for context

### Step 5: Understand the Task

**Ask clarifying questions if needed:**
- What is the specific goal?
- Are there constraints or preferences?
- What is the expected outcome?
- Are there related PRs or issues?

### Step 6: Propose a Plan

**Before starting implementation:**

1. **Summarize understanding** of the task
2. **Propose approach** with 3-5 clear steps
3. **Identify files** that will be modified
4. **Estimate complexity** (simple/moderate/complex)
5. **Call out risks** or unknowns
6. **Wait for user approval** before proceeding

**Example plan:**

```markdown
## Proposed Plan for [TASK]

**Understanding:**
[Summarize what user wants]

**Approach:**
1. Read current implementation in `src/features/core.py`
2. Add new function `calculate_explosive_play_rate()`
3. Update tests in `tests/test_aggregations_core.py`
4. Update feature config in `conf/features/standard_v1.yaml`
5. Document in `docs/modeling/features.md`

**Files to modify:**
- `src/features/core.py` (+20 lines)
- `tests/test_aggregations_core.py` (+30 lines)
- `conf/features/standard_v1.yaml` (+1 line)
- `docs/modeling/features.md` (+10 lines)

**Complexity:** Moderate
**Risks:** None identified

**Proceed?**
```

---

## Checklist

- [ ] Read AGENTS.md (critical rules)
- [ ] Skim .codex/QUICKSTART.md (commands)
- [ ] Read .agent/CONTEXT.md (if needed for task)
- [ ] Verify `CFB_MODEL_DATA_ROOT` environment variable
- [ ] Check external drive / cloud storage is accessible
- [ ] Review last 3 days of session logs
- [ ] Check git status and recent commits
- [ ] Understand the task (ask clarifying questions)
- [ ] Propose clear plan with steps
- [ ] Wait for user approval before implementing

---

## Common Mistakes to Avoid

❌ **Starting implementation without plan** - Always propose first
❌ **Skipping environment verification** - This catches most data root errors
❌ **Not reading recent session logs** - Miss important context
❌ **Working directly on `main` branch** - Create feature branch first
❌ **Assuming task understanding** - Ask if unclear

---

## Output Template

```markdown
## Session Start - [TASK]

### Context Loaded
- [x] AGENTS.md reviewed
- [x] Data root verified: $CFB_MODEL_DATA_ROOT
- [x] Recent logs reviewed (last 3 days)
- [x] Git status checked

### Recent Work Summary
[Summary of last 3 session logs]

### Current State
- Branch: [branch name]
- Last commit: [commit message]
- Uncommitted changes: [yes/no]

### Task Understanding
[What you understand the task to be]

### Proposed Plan
1. [Step 1]
2. [Step 2]
3. [Step 3]

### Files to Modify
- [file 1]
- [file 2]

**Waiting for approval to proceed...**
```

---

_Last Updated: 2026-02-13_
_Session initialization workflow_
