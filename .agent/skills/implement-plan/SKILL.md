---
name: implement-plan
description: Execute an approved Sol-to-Terra implementation contract from docs/plans. Use when a fresh implementation session must follow a durable repository plan while preserving its architecture, validation, and amendment rules.
---

# Implement Plan

Use this skill only for a plan at `docs/plans/YYYY-MM-DD/<descriptive-slug>.md`.

## 1. Authorize and reconcile the contract

1. Read the entire plan and its linked current-state documents before editing code.
2. Confirm the plan is `Approved`, or that the user has explicitly authorized implementation of this exact plan path.
3. If an explicit user handoff authorizes a Draft plan, update its metadata to `Approved` and record the approval source before implementation.
4. Inspect the branch and worktree. Preserve unrelated changes; do not broad-format, stage, discard, or commit them.
5. Compare repository state with the contract. If a material assumption is false, stop before code changes and report: expected state, actual state, why it conflicts, and the smallest proposed amendment.

## 2. Execute in order

1. Mark the plan `In Progress` and record the implementation session log path.
2. Perform implementation tasks sequentially and preserve all stated interfaces, constraints, and acceptance criteria.
3. Run each task's required validation as its logical stage completes.
4. Use normal implementation judgment for mechanical details only.

## 3. Amend safely

Append an amendment and continue only when the discovery does not change architecture, public interfaces, scope, or acceptance criteria.

For a material deviation, stop and request a revised Sol plan. Do not silently redesign the solution.

## 4. Close the implementation

1. Run the plan's final validation and `git diff --check`.
2. Update the plan to `Implemented` only after every definition-of-done item passes; otherwise leave it `In Progress` and document the blocker.
3. Create a full implementation session log linking the plan, amendments, validation, and precise next step.
4. Propose a commit consistent with the plan's commit policy. Git operations remain user-controlled.
