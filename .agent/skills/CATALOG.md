---
# Skills Catalog
# Index of all available skills for AI assistants working on CFB Model

**Last Updated:** 2026-02-13

---

## What Are Skills?

Skills are reusable, documented workflows for common tasks. Each skill lives in `.agent/skills/<skill-name>/SKILL.md` and provides:

- Clear purpose and scope
- Step-by-step workflow
- Checklist for verification
- Common mistakes to avoid

---

## Available Skills

### Core Skills

#### start-session
**Purpose:** Initialize a new work session  
**Location:** `.agent/skills/start-session/SKILL.md`  
**Use When:**
- Beginning a new coding session
- Returning to project after a break
- Starting work on a new task

**Key Steps:**
1. Load critical context (AGENTS.md, .codex/QUICKSTART.md)
2. Verify environment (CFB_MODEL_DATA_ROOT)
3. Review recent work (last 3 days of session logs)
4. Check git status
5. Propose plan before implementation
6. Wait for user approval

---

#### end-session
**Purpose:** Close a work session properly  
**Location:** `.agent/skills/end-session/SKILL.md`  
**Use When:**
- Finishing work for the day
- Completing a task
- Handing off to another AI assistant

**Key Steps:**
1. Create session log
2. Run health checks
3. Update documentation
4. Prepare commit message
5. Document handoff notes

---

## Planned Skills

*The following skills will be added as they are developed:*

- `add-feature` - Add a new feature to the model
- `train-model` - Train a new model with proper tracking
- `run-experiment` - Execute a V2 workflow experiment
- `validate-data` - Run data validation checks
- `generate-bets` - Generate weekly betting predictions

---

## How to Use Skills

### As an AI Assistant

1. **Check this catalog** to see available skills
2. **Read the skill file** before starting work
3. **Follow the workflow** step-by-step
4. **Complete the checklist** to ensure nothing is missed

### Creating New Skills

When creating a new skill:

1. Create directory: `.agent/skills/<skill-name>/`
2. Create file: `SKILL.md`
3. Follow the template structure
4. Add to this catalog
5. Include:
   - Purpose and scope
   - When to use
   - Step-by-step workflow
   - Checklist
   - Common mistakes

---

## Skill Template

```markdown
# Skill: [Name]

> Brief description

---

## Purpose

What this skill accomplishes

## When to Use

- Situation 1
- Situation 2

## Workflow

### Step 1: [Name]
Details...

### Step 2: [Name]
Details...

## Checklist

- [ ] Item 1
- [ ] Item 2

## Common Mistakes

❌ Don't do this
✅ Do this instead
```

---

**Questions?** See `.agent/skills/start-session/SKILL.md` for the complete pattern.
