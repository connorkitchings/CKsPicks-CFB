# Session: Phase 2 Planning and Sub-phase 2a Preparation

## TL;DR

- **Worked On:** Start-session review; verified Phases 0 and 1 completion;
  planned Phase 2 implementation; performed pre-Phase-2 doc cleanup and
  read-only investigation for Sub-phase 2a.
- **Outcome:** Phase 2 plan amended to
  `docs/plans/2026-09-05/02-data-repair-and-recertification.md` with four
  ordered sub-phases. The 52 catalog-missing lineage parents are classified as
  unavailable historical evidence, reducing 2a scope. Doc cleanup edits are
  uncommitted.
- **Plan Contract:** `docs/plans/2026-09-05/02-data-repair-and-recertification.md`
  (Approved, Amendment 1 added)
- **Approval / Status:** User approved full Phase 2 scope (split sub-phases,
  ingest 2015-2019, include FBS-FCS) and directed implementation.
- **Blockers:** None.
- **Next:** User commits the doc/contract changes; then implement Sub-phase 2a.

## Context and Decisions

- The session started from the end-session of Phase 1. Phase 0 is fully
  implemented; Phase 1 is functionally implemented with a sealed audit in R2
  (`2026-09-05T1510Z-phase1-evidence-audit-v2/`) and 57 issues.
- Two small documentation drifts were found:
  - `docs/plans/index.md` still listed Phase 1 as "Approved".
  - `AGENTS.md` "2026 Season Execution Status" said Phase 1 was "next".
- Phase 2 scope decisions:
  - Split into four ordered sub-phases (2a repairs → 2b recapture → 2c Silver
    rebuild → 2d recertification).
  - Ingest 2015-2019 corpus now.
  - Include FBS-FCS games now (full FBS-involved population).
- Read-only investigation of the 52 catalog-missing lineage parents:
  - They originate from historical research root manifests (candidate_v1,
    measurement_v3, state_v2, R1/R2 coverage, early-week context, V4 replay).
  - **0 of 52 are referenced as parents in `catalog.dataset_dependencies`.**
  - **0 of 52 have objects in the current R2 lake structure**
    (`lake/silver/...`, `lake/gold/...`, `artifacts/preview/...`).
  - Conclusion: they are unavailable historical evidence, not repairable
    defects. Correct Phase 2a action is quarantine + disposition, not
    registration.

## Work Completed

- Verified Phase 0/1 completeness and closed documentation drifts:
  - Updated `docs/plans/index.md` Phase 1 status to Implemented with sealed
    audit artifact reference.
  - Updated `AGENTS.md` "2026 Season Execution Status" to reflect Phase 0/1
    completion and Phase 2 next.
- Amended `docs/plans/2026-09-05/02-data-repair-and-recertification.md` with
  detailed Amendment 1 covering:
  - Phase 1 findings table
  - Sub-phases 2a–2d with tasks, acceptance, risks, and definition of done
  - Mapping to the original six implementation tasks
  - Handoff instructions
- Queried Preview Neon catalog and R2 to classify the 52 missing lineage
  parents as unavailable historical evidence.

## Files Modified

- `docs/plans/index.md` — Phase 1 status update.
- `AGENTS.md` — 2026 execution status update.
- `docs/plans/2026-09-05/02-data-repair-and-recertification.md` — Amendment 1
  with detailed Phase 2 sub-phase plan.
- `session_logs/2026-09-05/04-phase2-planning-and-2a-prep.md` — this log.

## Validation

- [x] `git diff --check` passed.
- [x] `uv run mkdocs build --quiet` passed.
- [x] Read-only catalog/R2 investigation completed without mutations.

## Amendments and Blockers

- Amendment 1 added to the Phase 2 contract with explicit sub-phases and scope.
- No blockers.

## Handoff Notes

- **Resume at:** User commits the current worktree changes, then implement
  Sub-phase 2a (deterministic repairs): quarantine 52 lineage parents, repair
  `preseason_team_inputs` duplicate keys under `preseason_inputs_v2`, and
  clarify downstream-game-outside-denominator.
- **Watch out for:** The 52 lineage parents are not repairable; quarantine them
  rather than attempting registration. Preserve original datasets as historical
  evidence. Never mutate production; all Phase 2 work stays in Preview/research
  namespace.

**tags:** ["data-first", "phase2", "planning", "repair", "lineage"]
