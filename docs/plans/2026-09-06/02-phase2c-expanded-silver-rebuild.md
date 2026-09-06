# Phase 2c: Expanded Silver Rebuild

- **Status:** Implemented
- **Created:** 2026-09-06
- **Planner:** Sol
- **Approval source:** User explicitly approved this exact Phase 2c plan and directed implementation on 2026-09-06.
- **Implementation log:** `session_logs/2026-09-06/02-phase2c-expanded-silver-rebuild.md`
- **Commit policy:** Separate implementation and evidence commits

## Goal

Build the Preview-only, ten-season FBS-involved Silver corpus from the sealed
Phase 1 v3 regular captures and completed Phase 2 postseason captures. Publish
an immutable ref set for Phase 2d without altering V4 or production.

## Implementation Tasks

1. Normalize mixed historical capture encodings, constrain all detail datasets
   to the selected schedule, and preserve unsupported detail as explicit
   reconciliation evidence.
2. Add a Preview-only dry-run/apply runner that selects exact source manifests,
   validates provenance/checksums, and materializes per-season Silver and
   reconciliation outputs under a committed code SHA.
3. Publish a checksummed Phase 2c ref set with source lineage, output refs,
   timing classes, coverage, and exclusion reasons.

## Validation

Run focused Silver/Phase 2 tests, full Python coverage, Ruff check and
format-check, contracts check, MkDocs, V4 compatibility checks, and
`git diff --check`. Apply only after the implementation commit; Phase 2c is
complete only after Preview catalog/R2 verification succeeds.

## Amendment 1 — Sealed Phase 1 v3 input state

The corrected Phase 1 v3 resolved manifest is intentionally
`resolved_with_blockers` because it records two unrelated non-canonical
research objects. Phase 2c accepts that sealed state only while selecting its
exact verified regular captures and dataset refs. It still rejects incomplete
or non-complete Phase 2 capture runs and the certified R1 source set.

## Execution Record

Phase 2c completed in Preview on 2026-09-06 under run
`2026-09-06T1437Z-phase2c-expanded-silver-v1` at committed code SHA
`6be713a33ee32c1d661bd536e2db9c9d0fa73ca1`. The complete
`data_first_phase2c_ref_set_v1` is at
`artifacts/research/data-first-football-v1/phase2/silver/runs/2026-09-06T1437Z-phase2c-expanded-silver-v1/ref-set.json`
with manifest SHA-256
`b3023ab5b7a304ddbc81ae2feca56238959520a54b3a75ed9be136f5d8f51df3`.

All ten permitted seasons have verified checkpoints and eight registered,
readable Silver outputs (80 total). The corpus closes at 8,936 games/outcomes
(8,521 regular, 415 postseason; 7,792 FBS–FBS, 1,144 FBS–FCS), has no 2020
rows and zero blocking reconciliation conflicts. A repeated dry-run matched the
published ref set. Phase 2d is unblocked but was not started by this work.
