# Implementation Contracts

`docs/plans/` holds task-level implementation contracts prepared by Sol and executed by a fresh Terra task. It is distinct from `docs/planning/`, which holds strategic roadmaps and long-lived initiatives.

## Location and naming

Store each contract at:

```text
docs/plans/YYYY-MM-DD/<descriptive-slug>.md
```

The date folder is the chronological ordering. Prefix a same-day filename with `01-`, `02-`, and so on only when implementation order matters.

Copy the template from `.agent/skills/plan-session/assets/implementation-contract-template.md`. A contract records status, approval source, implementation log, and commit policy as well as the goal, current state, tasks, validation, risks, definition of done, and amendments.

## Lifecycle

| Status | Meaning |
| --- | --- |
| `Draft` | Sol is investigating or the user has not approved the contract. |
| `Approved` | The contract is ready for Terra, either by recorded approval or an explicit user handoff for the exact path. |
| `In Progress` | Terra is implementing the contract. |
| `Implemented` | All definition-of-done items and required validation have passed. |
| `Superseded` | A later contract replaces this one. |

Terra must not execute a Draft contract without an explicit user instruction naming that exact path. In that case, Terra records the instruction as the approval source and changes the status to `Approved` before code changes.

## Current rating-transition contract

- [Phase 3 v2 sealed team-score tournament](2026-08-25/phase3-score-model-tournament-v2.md)
  — In Progress. It supersedes neither the Phase 3 v1 diagnostic nor its failed
  research history; a passing v2 candidate freeze is required before Phase 4.

## When to use a contract

Use the Sol-to-Terra workflow for architecture, data/model lineage, schemas or migrations, production/deployment behavior, security-sensitive work, or changes that span multiple subsystems. Use the normal fast path for a small, localized change that follows an established pattern.

## Amendments and commits

Terra may append a minor amendment and continue only when it preserves architecture, public interfaces, scope, and acceptance criteria. A material conflict requires stopping and returning to Sol for a revised contract.

Record whether the plan should receive a separate commit. A separate plan commit is recommended for multi-session work, asynchronous review, migrations, production changes, or difficult-to-reverse decisions. Git operations remain user-controlled.
