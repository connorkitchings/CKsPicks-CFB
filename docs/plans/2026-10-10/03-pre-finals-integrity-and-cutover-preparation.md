# Pre-finals integrity and cutover preparation

- **Status:** Implemented (2026-10-10; documentation preparation only)
- **Created:** 2026-10-10
- **Planner:** Sol
- **Approval source:** User approved the plan and backfill sequence in this chat, added the Preview approval query and Tuesday pivot refinements, and explicitly requested implementation on 2026-10-10.
- **Planning log:** `session_logs/2026-10-10/08-pre-finals-preparation-planning.md`
- **Implementation log:** `session_logs/2026-10-10/09-pre-finals-preparation-docs.md`
- **Commit policy:** Commit plan with documentation; user controls Git operations.

## Goal and acceptance

Prepare integrity work, Preview rehearsal and Production review using the [repair matrix](../2026-10-08/02-repair-track-certification-and-closure.md#completion-matrix) and [run sheet](01-week7-cutover-run-sheet.md). Each open requirement has an owner, dependency, source, existing evidence, next bounded task, required acceptance evidence and stop condition. Planning establishes readiness only; no certification, rehearsal success or release approval is inferred.

## Baseline and constraints

Clean `dev` at `d22efb1a`. Documentation only: preserve original paths, historical amendments, immutable evidence and separate exact write approvals. Certify the complete 2025 candidate before cutover; publish/verify it after corrected selection; full repair closure follows publication. All other integrity prerequisites stand. No data operation, runtime repair, SQL apply, serving change, deployment or Git operation is included. Physical archival, runbook merger and architecture work remain deferred.

## Ordered changes

1. Persist this approved five-section contract and planning log before implementation.
2. Classify existing repair obligations by available-now, stable-finals and corrected-selection dependencies. Supply bounded tasks, owners, receipts and stop conditions; append the approved backfill-sequencing amendment without rewriting history.
3. Expand Preview preflight: identity, grants, migrations, lease, before-state and exactly one B2 approval row with `first_live_week = 6`. Cover registered exports, certified inputs, prior authorization, staging, apply, freeze, matchup repin, readback, owner-login rollback and re-apply.
4. Expand Production review: exact code/packet/input identity, before/after diff, complete Preview/rollback evidence, gaps, drift and deadlines. At Tuesday October 13 14:00Z, unverified Preview rehearsal bars cutover and triggers the independently approved/certified standalone fallback, frozen by 22:00Z. Production authorization remains separate and exact.
5. Check documented flags against source; keep unknown identities/hashes unresolved. Identify the first bounded pre-finals integrity implementation task.

## Validation

Run unchanged `tests/test_data_first_documentation_authority.py`, strict MkDocs and `git diff --check`. Verify affected local links/anchors, obligation coverage, dependency ordering, CLI references and unchanged historical amendments/evidence. Documentation completion must not mark any execution task complete.

## Handoff/amendments

User explicitly requested documentation implementation in this chat after approval; persist first and execute that scoped request here. Existing session skills and the general Sol/Terra workflow remain unchanged. Material changes require a new decision. Close this documentation contract only after checks pass; retain the parent repair contract In Progress. First execution handoff: read-only exact-key inventory of the 95 adjusted rows, followed by a separately scoped disposition/recertification step.

**Close-out:** Dependency cards, approved sequencing amendment and both checklists delivered. Documentation checks passed; execution boxes remain unchecked and the repair contract remains In Progress.
