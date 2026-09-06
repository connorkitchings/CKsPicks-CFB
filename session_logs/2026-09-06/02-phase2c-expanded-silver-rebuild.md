# Session: Phase 2c Expanded Silver Rebuild — Code Checkpoint

## TL;DR

- **Worked On:** Implemented the Preview-only Phase 2c source-selection and
  materialization runner, plus the remaining mixed-capture Silver normalizers.
- **Outcome:** The code checkpoint is ready for a user-executed commit. No
  Preview materialization was run because apply mode correctly requires that
  commit's exact SHA and a clean tracked worktree.
- **Plan Contract:** `docs/plans/2026-09-06/02-phase2c-expanded-silver-rebuild.md`
- **Approval / Status:** User explicitly authorized implementation on
  2026-09-06; contract remains In Progress pending committed-SHA execution.
- **Blockers:** User must commit the implementation checkpoint before apply.
- **Next:** Run the committed-SHA dry-run, review the exact corpus plan, then
  execute Preview-only apply with a fresh immutable run ID.

## Work Completed

- Added `scripts/research/build_data_first_phase2c.py`, a Preview-only
  `dry-run`/`apply` runner that pins Phase 1 v3, both completed Phase 2 capture
  manifests, and the certified R1 source set.
- The runner validates source state, capture registration, allowed seasons,
  postseason request shape, exact per-season coverage, and R1-declared regular
  play omissions. It emits the checksummed `data_first_phase2c_ref_set_v1` only
  after an apply run completes.
- Added mixed timestamp parsing, serialized team-stat decoding, selected-game
  constraints, and conflicting season/week guards to Silver normalization.
- Added regression coverage for mixed timestamps, serialized team statistics,
  malformed serialized input, filtered non-target outcomes, and conflicting
  game identities.

## Validation

- [x] Focused Phase 2/Silver tests: 35 passed.
- [x] Full Python suite: 710 passed, 2 skipped.
- [x] Contracts validation.
- [x] MkDocs build.
- [x] Scoped Ruff format-check and lint.
- [x] Repository Ruff lint.
- [x] `git diff --check`.
- [ ] Repository-wide Ruff format-check: blocked by 24 unrelated pre-existing
  files; deliberately not reformatted in this dirty-worktree-safe checkpoint.

## Amendment

The sealed Phase 1 v3 manifest remains `resolved_with_blockers` due to two
unrelated non-canonical research objects. Phase 2c accepts that documented,
sealed state only for its exact verified selections; Phase 2 capture runs and
the R1 source set still require `complete`.

## Handoff Notes

- **Commit first:** apply mode requires `--expected-code-sha` to equal HEAD and
  refuses tracked changes.
- **Do not change:** V4, production, 2020 exclusion, capture automation, and
  `.opencode/`.

**tags:** ["data-first", "phase2", "silver", "lineage"]
