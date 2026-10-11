# Cutover-safe documentation consolidation

- **Status:** Implemented (2026-10-10; scoped validation passed)
- **Created:** 2026-10-10
- **Planner:** Sol
- **Approval source:** User approved the narrowed plan and explicitly requested implementation in this chat on 2026-10-10.
- **Planning log:** `session_logs/2026-10-10/06-cutover-safe-docs-planning.md`
- **Implementation log:** `session_logs/2026-10-10/07-cutover-safe-docs-consolidation.md`
- **Commit policy:** Commit plan with implementation; user controls Git operations.

## Goal and acceptance

Simplify the active reading path while preserving every existing plan path, approval, evidence file and unfinished obligation. The index distinguishes current execution, supporting contracts, deferred backlog and historical records. Every unfinished supporting requirement has an explicit owner; no repair or release is declared complete by documentation cleanup.

## Baseline and constraints

Clean `dev` at `7ed767fd`. Edit only the plan index, repair completion matrix, compact contract template and required plan/session logs. No relocation, runtime change, database write, deployment, release-gate change or modification of existing documentation tests. Preserve immutable inputs, receipts, backups, historical amendments and `stash@{0}`. Physical archival and weekly-runbook consolidation are deferred to Week 8 steady-state.

## Ordered changes

1. Put repair closure and the Week 7 run sheet under Current Execution. Keep active supporting contracts separate; put artifact archival and production-boundary work in Deferred Backlog. Replace historical narrative with a compact linked table without changing file paths. Retain `v5_status.md`, "V5 Product Transformation", "V5 contract archive", "six slates are not a launch prerequisite", and "Week 4 refresh awaits stabilized finals" (as a satisfied historical checkpoint).
2. Reconcile supporting contracts and amendments against the repair completion matrix. Add missing obligations with originating links, evidence, state and next gate. Retain independent monitoring, artifact preservation and architecture obligations with their own owners. Preserve historical decisions and acceptance criteria.
3. Keep template lifecycle/approval metadata and use exactly five sections: Goal and acceptance; Baseline and constraints; Ordered changes; Validation; Handoff/amendments. Retain prompts for acceptance, interfaces, exclusions, failure gates and material amendments. Existing session skills and Sol/Terra workflow remain unchanged.
4. Confirm no active test process uses root `.coverage.*` or `.pytest_cache`, then remove those disposable files. Remove temporary logs only with positive proof of disposability; record exact paths. Preserve `data_pipeline.log` and uncertain files.

## Validation

- `uv run pytest tests/test_data_first_documentation_authority.py`
- `uv run mkdocs build --strict`
- `git diff --check`
- Check all retained index links, template section count, obligation ownership, unchanged evidence/test hashes, existing tracked paths and stash identity.

## Handoff/amendments

The user explicitly requested implementation of the approved plan in this chat; persist the contract and planning log before implementation here. This session-specific instruction supersedes the fresh-task handoff for this documentation cleanup only; session skills remain unchanged. A material scope or acceptance change requires a new user decision. Close this contract only after scoped validation passes; propose a user-run commit without staging, committing, merging or pushing.

**Close-out:** All ordered changes and scoped checks passed; see the implementation log. No existing tracked file moved, no historical amendment changed and no repair/release contract was closed.
