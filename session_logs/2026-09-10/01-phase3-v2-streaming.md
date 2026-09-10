# Session: Phase 3 v2 streaming materialization

## TL;DR

- **Worked On:** Replaced the incomplete in-memory Phase 3 v2 materialization
  path with bounded partitioned immutable artifacts.
- **Outcome:** Local implementation and validation pass. Preview execution is
  deliberately pending the required clean committed checkpoint.
- **Plan Contract:**
  `docs/plans/2026-09-09/phase3-measurement-and-core-selection-v2.md`
- **Approval / Status:** Explicit user authorization on 2026-09-10; contract
  remains In Progress until Preview dry run, apply, verifier, and rerun pass.
- **Blockers:** Preview apply is prohibited while the tracked worktree is dirty
  and code is not committed. Unrelated user changes remain preserved.
- **Next:** User creates a clean checkpoint, then runs the Preview dry run with
  the sealed Repair v2 manifest and reviews the emitted partition plan.

## Context and Decisions

- The prior 2026-09-08 Phase 3 v2 contract is retained as a historical record
  and marked Superseded; its measurement, cutoff, candidate, and selection
  decisions remain binding.
- Added additive `partitioned_dataset_v1` support to the immutable lake. Child
  parts are content-addressed; a final root manifest is the only consumable
  logical artifact, preventing interrupted applies from publishing evidence.
- Snapshots and adjusted history stream one `(season, week)` partition at a
  time. Only the iteration-four adjusted core state and terminal state remain
  in memory for the sealed tournament.
- No V4, production, Neon, web, Phase 4–6, or repository-local data behavior
  changed.

## Work Completed

- Created the approved replacement contract at
  `docs/plans/2026-09-09/phase3-measurement-and-core-selection-v2.md`.
- Added partitioned root references, streaming reads, per-part validation,
  logical content digests, immutable collision handling, and idempotent child
  reuse to the lake.
- Refactored Phase 3 replay emission by season/week and replaced the runner's
  global snapshot/history DataFrames with a streaming preflight/materialization
  path.
- Added no-write dry-run summaries, publication-plan binding, partitioned output
  refs, and a streaming independent verifier.
- Added lake and replay tests for ordered immutable partitions, checksum failure,
  config materialization sealing, and incremental week-before-terminal emission.

## Validation

- [x] `uv run pytest -q -W error tests/test_data_lake.py tests/test_data_first_phase3_v2.py` — 23 passed.
- [x] `uv run pytest -q -W error` — 814 passed, 2 skipped.
- [x] `uv run pytest -q -W error tests/test_data_first_phase3.py tests/test_data_first_phase3_v2.py` — 23 passed.
- [x] Ruff format check and lint for all changed Phase 3/lake files.
- [x] Both Phase 3 v2 CLI help checks.
- [x] `make contracts-check`.
- [x] `uv run mkdocs build --strict --quiet`.
- [x] `git diff --check`.
- [ ] Preview dry run, apply, independent verifier, and idempotent rerun —
  require the user-created clean committed checkpoint.

## Amendments and Blockers

- The replacement plan's required `docs/plans/2026-09-09/...` contract did not
  exist when implementation began because the preceding planning pass had not
  persisted it. It was created directly from the user-approved contract; this
  is administrative and does not change architecture or scope.
- A directly selected Repair-v2 pytest invocation has an existing import-path
  collection issue for `scripts.research`; the repository-wide warning-as-error
  run, which includes the complete supported suite, passes.

## Handoff Notes

- **Resume at:** Commit only the Phase 3/lake/plan/log paths, then run the
  Preview dry run. Do not include the unrelated web, operations, plan-index, or
  `.opencode/` changes.
- **Watch out for:** Apply writes only after preflight and requires clean tracked
  state. If the exact snapshot/history invariants do not reconcile, stop before
  any root manifest is published.

**tags:** ["implementation", "data-first", "phase3", "streaming", "lake"]
