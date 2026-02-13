# Skills Catalog

> **Workflow automation for common tasks**
>
> Skills are pre-defined workflows that AI assistants can follow for consistent task execution.

---

## Available Skills

### Session Management

#### start-session
**Location:** `.agent/skills/start-session/SKILL.md`

**Purpose:** Initialize a new work session with proper context loading and validation.

**When to use:**
- Beginning a new coding session
- Returning after a break
- Starting work on a new task

**What it does:**
1. Verifies data root configuration
2. Reviews recent session logs (last 3 days)
3. Checks git status
4. Proposes plan before implementation

---

#### end-session
**Location:** `.agent/skills/end-session/SKILL.md`

**Purpose:** Clean up and document work at end of session.

**When to use:**
- Finishing a work session
- Before taking a break
- After completing a task

**What it does:**
1. Runs health checks (format, lint, tests)
2. Creates session log
3. Proposes commit message
4. Updates relevant documentation

---

## How to Use Skills

### For AI Assistants

1. **Identify the skill needed** - Check this catalog
2. **Read the skill file** - Navigate to `.agent/skills/{skill-name}/SKILL.md`
3. **Follow the workflow** - Execute steps in order
4. **Adapt as needed** - Skills are templates, not rigid scripts

### For Users

Skills are primarily for AI assistants to follow. Users can reference them to understand what the assistant should be doing.

---

## Future Skills (Planned)

- **train-model** - Complete model training workflow
- **add-feature** - Add new feature with tests and docs
- **create-experiment** - Set up new experiment config
- **debug-pipeline** - Systematic pipeline debugging
- **review-pr** - Code review checklist

---

_Last Updated: 2026-02-13_
_Skills catalog for CFB Model_
