# Session: Phase 2c Materialization and Ref-Set Closure

## TL;DR

- **Worked On:** Implemented the committed-code checkpoint required before Phase 2c Preview materialization.
- **Outcome:** The runner now verifies sealed source lineage, records immutable run identities and per-season checkpoints, supports verified resumption, and cannot publish an incomplete ref set.
- **Plan Contract:** `docs/plans/2026-09-06/03-phase2c-materialization-and-ref-set-closure.md`
- **Approval / Status:** User explicitly authorized the exact contract on 2026-09-06; status remains `In Progress` pending the user-owned implementation commit and Preview execution.
- **Blockers:** Apply must bind its artifacts to the commit containing this code. No R2/Neon materialization has run.
- **Next:** User commits the code checkpoint; rerun the exact committed-SHA dry-run, review the fixed corpus gates, then execute Preview-only apply with the same run ID and `as_of`.

## Context and Decisions

- Phase 2c remains Preview-only and preserves V4, production, 2020 exclusion, schema versions, provider-call prohibition, and the unrelated `.opencode/` directory.
- The exact Phase 1 v3, Phase 2 postseason, and certified R1 inputs are recorded by URI and raw manifest checksum in the immutable identity.
- A resumed run must have an identical identity and every prior checkpoint must revalidate every output checksum, schema, and Preview catalog row before it can be skipped.

## Work Completed

- Added `src/cks_picks_cfb/data/data_first_phase2c.py` with testable contracts for manifests, exact R1/Phase 1 capture equality, identities, checkpoints, ref sets, omission dispositions, and corpus gates.
- Hardened `scripts/research/build_data_first_phase2c.py` without changing its CLI.
- Added Phase 2c regression coverage.
- Updated the Phase 2c closure contract with the implementation checkpoint and blocker.

## Files Modified

- `src/cks_picks_cfb/data/data_first_phase2c.py` - reusable Phase 2c lineage and immutability contracts.
- `scripts/research/build_data_first_phase2c.py` - source/capture verification, resume verification, and final-ref gating.
- `tests/test_data_first_phase2c.py` - focused contract coverage.
- `docs/plans/2026-09-06/03-phase2c-materialization-and-ref-set-closure.md` - approval, in-progress status, and checkpoint record.

## Validation

- [x] Focused Phase 2c/Silver/history tests — 47 passed.
- [x] Full Python suite with warnings as errors — 716 passed, 2 skipped.
- [x] Scoped Ruff format-check and lint; repository Ruff lint.
- [x] `make contracts-check`.
- [x] `uv run mkdocs build --quiet`.
- [x] V4/repository-boundary tests — 14 passed.
- [x] `git diff --check`.

## Amendments and Blockers

- None. The code checkpoint implements the approved contract without changing public CLI arguments, Silver schemas, production behavior, or Phase 2d scope.

## Handoff Notes

- **Resume at:** Commit this exact checkpoint, then run the Preview dry-run with the resulting full `HEAD` SHA. Use a fresh UTC run ID ending `phase2c-expanded-silver-v1` and reuse the same ID and `as_of` for apply.
- **Watch out for:** Do not run apply from an uncommitted worktree, accept a nonzero blocking reconciliation count, create data for 2020, or start Phase 2d before `ref-set.json` is complete and verified.

**tags:** ["data-first", "phase2", "silver", "lineage", "research"]
