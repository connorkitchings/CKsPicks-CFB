# Session: Plan weekly ingestion repair

## TL;DR
- **Worked On:** Trace inventory, capture-ID and cumulative input-refresh gaps.
- **Outcome:** User approved fixture-only checklist repair and an explicitly pending Week8 template.
- **Plan Contract:** docs/plans/2026-10-15/02-weekly-ingestion-repair.md (imported from `codex/weekly-ingestion-repair` `bb2f1fe8`; originally `01-repair-weekly-ingestion-and-w8-template.md`)
- **Approval / Status:** Approved by explicit implementation request.
- **Blockers:** Future operational hashes/readiness remain pending post-Week7 gate; no implementation blocker identified.
- **Next:** Fresh Terra workers implement in isolated worktree.

## Context and Decisions
- Preserve primary checkout's three uncommitted artifacts; copy them into worktree before repair.
- Existing builders supply inventories, captures, Silver and derived inputs; no new orchestration API.
- Existing season loader derives real measurements when optional imported refs are absent.
- Fixture-only scope excludes every live provider request and database/storage write.

## Validation
- CLI signatures, dataflow and manifest/season loader inspected read-only.
- Focused implementation validation recorded in implementation log.

## Handoff Notes
- **Resume at:** Execute approved contract in isolated worktree.
- **Watch out for:** Capture IDs and cumulative lineage must remain explicit; future data cannot be fabricated.

**tags:** ["ops", "planning", "ingestion"]
