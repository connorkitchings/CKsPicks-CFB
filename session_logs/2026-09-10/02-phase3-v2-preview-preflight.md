# Session: Phase 3 v2 Preview preflight correction

## TL;DR

- **Worked On:** First no-write Preview preflight for the Phase 3 v2 streaming
  replacement.
- **Outcome:** The preflight stopped before any R2 write because canonical JSON
  identity ordering sorted week `10` before week `2`. The lake now keeps JSON
  identity stable while using typed natural ordering for partition streams.
- **Plan Contract:**
  `docs/plans/2026-09-09/phase3-measurement-and-core-selection-v2.md`
- **Approval / Status:** Implementation is explicitly authorized; the contract
  remains In Progress pending a rerun of the Preview dry run, Preview apply,
  independent verification, and deterministic rerun.
- **Blockers:** The correction must be committed before its code SHA can bind a
  valid Preview preflight. The existing unrelated tracked changes also prevent
  any apply until the user supplies a clean tracked worktree.
- **Next:** Commit only the correction paths, rerun the no-write Preview
  preflight against that exact SHA, and inspect its count and partition evidence.

## Context and Decisions

- The failed preflight was read-only and stopped during local plan construction;
  it did not write Preview R2 artifacts or modify V4, production, Neon, web, or
  any downstream phase.
- `partition_key()` remains a canonical JSON identity for manifest lookup and
  root digests. A separate typed `partition_order_key()` now orders partitions,
  so numeric week values remain chronological without changing identity.
- The writer, dry-run planner, and partitioned-dataset reader all enforce the
  same natural ordering. This is a mechanical materialization correction, not a
  change to replay, timing, features, candidates, or selection math.

## Work Completed

- Reproduced the error from the no-write Preview preflight:
  `pregame_snapshots partitions are not strictly ordered`.
- Added natural typed partition ordering and applied it to shared lake writes,
  shared streaming reads, and Phase 3 preflight planning.
- Added a regression test showing `(season=2025, week=1)`, week 2, and week 10
  are accepted and published in natural order.

## Validation

- [x] `uv run pytest -q -W error tests/test_data_lake.py tests/test_data_first_phase3_v2.py` — 24 passed.
- [x] Ruff format check and lint for the modified lake, runner, and test files.
- [x] `git diff --check`.
- [ ] Rerun no-write Preview preflight — requires the new correction commit.
- [ ] Preview apply, independent verifier, and idempotent rerun — remain gated
  on preflight parity and a clean tracked worktree.

## Amendments and Blockers

- No contract amendment is needed: the contract already requires deterministic
  ordered partitions. The initial implementation incorrectly conflated JSON
  identity ordering with numeric stream ordering.

## Handoff Notes

- **Resume at:** Commit only the files listed below, pass that new SHA as
  `--expected-code-sha`, and rerun the exact Preview dry-run command.
- **Watch out for:** Do not apply while the unrelated tracked changes exist;
  apply is intentionally rejected by the contract's clean-worktree gate.

## Files Modified

- `src/cks_picks_cfb/data/lake.py` — typed logical partition ordering.
- `scripts/research/run_data_first_phase3_v2.py` — shared ordering in preflight.
- `tests/test_data_lake.py` — numeric-week ordering regression.
- `docs/plans/2026-09-09/phase3-measurement-and-core-selection-v2.md` — log link.

**tags:** ["phase3", "preview", "streaming", "lake", "preflight"]
