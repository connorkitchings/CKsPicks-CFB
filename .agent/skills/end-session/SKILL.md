---
name: end-session
description: Close a CFB Model planning, implementation, or fast-path session with scoped validation, complete session logs, safe worktree review, and a user-controlled commit handoff.
---

# End Session

Close the active session without altering unrelated worktree changes.

## 1. Select validation by session type

### Sol planning session

1. Confirm the implementation contract is saved under `docs/plans/YYYY-MM-DD/` and contains the required lifecycle metadata.
2. Run `git diff --check` and `uv run mkdocs build --quiet`.
3. Do not run data operations or broad formatters for documentation-only persistence.
4. Create a full planning session log that links the plan, approval source, commit policy, validation results, and copy-ready Terra handoff prompt.

### Terra implementation session

1. Run the validation required by the implementation contract plus `git diff --check`.
2. Update the contract to `Implemented` only when its definition of done passes; otherwise leave it `In Progress` and record the blocker.
3. Create a full implementation session log linking the plan, amendments, test results, and next step.

### Fast-path session

1. Run focused tests and checks for the affected components.
2. Use formatting only on files in scope; never run a broad formatter in a dirty worktree without explicit authorization.
3. Create a standard session log with completed work, validation, and handoff details.

## 2. Review and hand off

1. Inspect `git status`, `git diff`, and staged changes if any.
2. Separate intentional session changes from pre-existing user changes.
3. Update documentation when behavior or operational workflow changed.
4. Propose a conventional commit message and exact files to include. The user controls staging, commits, and pushes.

## Session-log minimum

Every session log must include: worked-on outcome, decisions, files changed, validation results, blockers, precise next step, and links to any implementation contract or amendment.
