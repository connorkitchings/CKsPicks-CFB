# Session: Phase 2c Materialization and Ref-Set Closure

## TL;DR

- **Worked On:** Completed the Phase 2c Preview materialization and ref-set closure.
- **Outcome:** The sealed ten-season corpus, all 80 Silver outputs, ten immutable checkpoints, and the final ref set are complete and independently verified.
- **Plan Contract:** `docs/plans/2026-09-06/03-phase2c-materialization-and-ref-set-closure.md`
- **Approval / Status:** User explicitly authorized the exact contract on 2026-09-06; Phase 2c is `Implemented`, Phase 2d is unblocked but not started, and overall Phase 2 remains `In Progress`.
- **Blockers:** None for Phase 2c.
- **Next:** Begin Phase 2d only in a separate approved task using the sealed Phase 2c ref set.

## Context and Decisions

- Phase 2c remains Preview-only and preserves V4, production, 2020 exclusion, schema versions, provider-call prohibition, and the unrelated `.opencode/` directory.
- The exact Phase 1 v3, Phase 2 postseason, and certified R1 inputs are recorded by URI and raw manifest checksum in the immutable identity.
- A resumed run must have an identical identity and every prior checkpoint must revalidate every output checksum, schema, and Preview catalog row before it can be skipped.

## Work Completed

- Added `src/cks_picks_cfb/data/data_first_phase2c.py` with testable contracts for manifests, exact R1/Phase 1 capture equality, identities, checkpoints, ref sets, omission dispositions, and corpus gates.
- Hardened `scripts/research/build_data_first_phase2c.py` without changing its CLI.
- Added Phase 2c regression coverage.
- Updated the Phase 2c closure contract with the implementation checkpoint and blocker.
- Ran the committed-SHA dry-run, materialized Preview-only R2/Neon outputs,
  independently reread every object/catalog row, and confirmed the published
  ref set with the required repeated dry-run.

## Files Modified

- `src/cks_picks_cfb/data/data_first_phase2c.py` - reusable Phase 2c lineage and immutability contracts.
- `scripts/research/build_data_first_phase2c.py` - source/capture verification, resume verification, and final-ref gating.
- `tests/test_data_first_phase2c.py` - focused contract coverage.
- `docs/plans/2026-09-06/03-phase2c-materialization-and-ref-set-closure.md` - implemented status and immutable execution evidence.
- `docs/plans/2026-09-06/02-phase2c-expanded-silver-rebuild.md` - Phase 2c execution closeout.
- `docs/plans/2026-09-05/02-data-repair-and-recertification.md` - Phase 2c implemented / Phase 2d unblocked evidence.
- `docs/plans/index.md` - Phase 2c lifecycle status.

## Validation

- [x] Focused Phase 2c/Silver/history tests — 47 passed.
- [x] Final full Python suite with warnings as errors — 717 passed, 2 skipped.
- [x] Scoped Ruff format-check and lint; repository Ruff lint.
- [x] `make contracts-check`.
- [x] `uv run mkdocs build --quiet`.
- [x] V4/repository-boundary tests — 14 passed.
- [x] `git diff --check`.
- [x] Committed-SHA dry-run: 10 seasons, 80 outputs, 8,936 games/outcomes
  (8,521 regular, 415 postseason; 7,792 FBS–FBS, 1,144 FBS–FCS), zero blocking
  reconciliation conflicts, and no 2020 rows.
- [x] Preview apply plus independent verification: ten checkpoints, 80 readable
  R2 objects, and 80 matching Preview Neon catalog rows.
- [x] Repeated dry-run matched the complete `data_first_phase2c_ref_set_v1`.

## Amendments and Blockers

- None. The completed work did not change public CLI arguments, Silver schemas,
  production behavior, or Phase 2d scope.

## Handoff Notes

- **Resume at:** Open a separate Phase 2d task only after reviewing its own
  implementation contract. Its sole Phase 2c input is
  `artifacts/research/data-first-football-v1/phase2/silver/runs/2026-09-06T1437Z-phase2c-expanded-silver-v1/ref-set.json`
  (SHA-256 `b3023ab5b7a304ddbc81ae2feca56238959520a54b3a75ed9be136f5d8f51df3`).
- **Watch out for:** Preserve the sealed identity
  `b3a02b56ca0f0c7495ce9bbc8221b38d15ac50be32104a48638e2ffa0e7e41a6`, do
  not admit the two non-canonical Phase 1 research-object blockers, and do not
  start Phase 2d work inside this closed Phase 2c task.

**tags:** ["data-first", "phase2", "silver", "lineage", "research"]
