---
name: start-session
description: Initialize a CFB Model work session, verify the relevant environment safely, review recent work, and route substantial changes to planning contracts or localized changes to the fast path.
---

# Start Session

Prepare a work session before editing implementation files.

## 1. Load context

1. Read `AGENTS.md` and `.codex/QUICKSTART.md`.
2. Read `.agent/CONTEXT.md` when the work involves architecture, data, modeling, or features.
3. Review session logs from the last three days and inspect branch, worktree, and recent commits.
4. Preserve all pre-existing worktree changes unless the user explicitly places them in scope.

## 2. Verify only the environment the task needs

Read `.env` without printing secrets.

- For `CFB_STORAGE_BACKEND=local`, confirm that `CFB_MODEL_DATA_ROOT` is set and accessible before any data I/O.
- For `CFB_STORAGE_BACKEND=r2`, confirm that the relevant source or preview R2 bucket, account ID, access key, and secret key variables are present before cloud data I/O. Use the `CFB_R2_SOURCE_*` or `CFB_R2_PREVIEW_*` set selected by the task.
- For documentation-only work, record unavailable data storage but continue; never create a local `./data/` fallback.

## 3. Choose the session path

Use `plan-session` when the request affects architecture, data/model lineage, schemas or migrations, production/deployment behavior, security, or multiple subsystems. Sol performs investigation in Plan Mode; after approval, Sol switches to Code mode solely to save the contract and planning log before the user opens a fresh Terra task.

Use `implement-plan` only when the user provides an exact contract path under `docs/plans/YYYY-MM-DD/` and the plan is Approved or explicitly authorized.

Use the fast path for a localized fix, test, or documentation edit with an established implementation pattern. Still state the intended change, validation, and worktree constraints before editing.

## Checklist

- [ ] Critical project context and recent logs reviewed.
- [ ] Git branch, status, and recent commits inspected.
- [ ] Required storage configuration checked without exposing secrets.
- [ ] Session routed to `plan-session`, `implement-plan`, or fast path.
- [ ] Validation and approval expectations stated before implementation.
