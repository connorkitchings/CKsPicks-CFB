---
name: plan-session
description: Investigate substantial repository changes and create a durable Sol-to-Terra implementation contract. Use for architecture, data/model, schema, production, security, or multi-component work that needs an approved plan before implementation.
---

# Plan Session

Use this skill for the planning half of a substantial change. Do not implement product code in this session.

## 1. Establish the planning baseline

1. Read `AGENTS.md`, `.codex/QUICKSTART.md`, and relevant architecture or domain documents.
2. Inspect the current branch, worktree, related code, tests, contracts, and the last three days of `session_logs/`.
3. Verify environment configuration only when the investigation needs it. Never expose secret values. Do not require the external data drive for documentation-only work.
4. Identify assumptions that must be confirmed before an implementation decision is safe.

## 2. Produce an implementation contract

In Plan Mode, investigate and present a decision-complete plan for review. After user approval, switch the same Sol task to Code mode only to persist the plan and planning session log; do not edit implementation files.

Create `docs/plans/YYYY-MM-DD/<descriptive-slug>.md` from [the contract template](assets/implementation-contract-template.md). Use a date folder for chronological ordering and add a numeric prefix only when ordering among same-day plans matters.

Set `Status: Draft` until either the user approves the plan or explicitly authorizes the exact plan path for implementation. Record the approval source, commit policy, and intended implementation log path.

## 3. Validate and hand off

1. Run `git diff --check` and `uv run mkdocs build --quiet` for the documentation-only persistence step.
2. Create the full planning session log at `session_logs/YYYY-MM-DD/NN-<description>.md`; link the contract instead of duplicating it.
3. Recommend a separate plan commit for multi-session, asynchronous-review, migration, production, or difficult-to-reverse work. For contained work, record that the plan may be committed with implementation. Never commit automatically.
4. End with a copy-ready prompt for a fresh Terra task:

```text
Use the repository-local implement-plan skill and implement the approved contract at:

docs/plans/YYYY-MM-DD/<descriptive-slug>.md

Treat it as authoritative. Preserve its architectural decisions, run its validation,
and stop for any material conflict. This request explicitly authorizes implementation.
```

## Contract quality bar

The contract must state the goal, observable success criteria, current constraints, chosen approach, scope boundaries, affected interfaces, ordered tasks, validation, risks, definition of done, and amendment process. It must leave Terra no architectural decisions to rediscover.

Use the full workflow when the change affects architecture, data/model lineage, schemas or migrations, production/deployment behavior, security, or multiple subsystems. Use the normal fast path for an established, localized fix, test, or documentation edit.
