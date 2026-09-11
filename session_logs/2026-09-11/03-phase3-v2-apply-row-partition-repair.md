# Session: Phase 3 v2 Apply Attempt — Row-Partition Repair

## TL;DR

- **Worked On:** Executed the authorized Phase 3 v2 Preview apply after the
  passing no-write preflight; diagnosed and repaired the apply-only writer
  failure it exposed; recorded the approved retry contract.
- **Plan Contract:** `docs/plans/2026-09-10/phase3-v2-compact-tournament-state.md`
- **Approval / Status:** The user authorized the apply and then explicitly
  authorized Amendment 2 (retry run ID `phase3-v2-compact-state-20260910-r2`)
  on 2026-09-11. The contract remains `In Progress`.
- **Outcome:** The passing preflight at `513dec0` is recorded; the apply failed
  inside `PartitionedDatasetWriter` before publishing anything consumable; the
  defect is fixed with regression coverage and full validation is green.
- **Blockers:** The retry is blocked on the user-controlled commit checkpoint
  (apply requires a clean tracked worktree at the fixed SHA).
- **Next:** Commit, then rerun the no-write preflight with the new SHA and run
  ID `phase3-v2-compact-state-20260910-r2`, apply, verify, and rerun.

## Evidence

The no-write Preview preflight at committed SHA `513dec0` passed every gate:
adjusted history 3,067,048 (Amendment 1 value), compact features 142,960,
transient iteration-four components 428,880, predictions 202,176, population
8,936, observations 303,790, pregame snapshots 1,215,160, all partition
maxima within bounds, selection `quality_core_epa_split`, certification SHA
`8961d85b…`.

The authorized apply then failed at the `attribution` dataset with
`StorageError: phase3_attribution partition column is absent: scope`.
`PARTITIONS` declares attribution as `(("scope",), ())` — a logical-only
partition whose rows carry no `scope` column — but
`PartitionedDatasetWriter.__init__` used
`tuple(row_partition_keys or partition_keys)`, so the explicit empty sequence
fell back to `("scope",)` and `add()` demanded the column. The reader
(`iter_partitioned_dataset`) had the identical `or` fallback. No-write
preflights attach no writers, and no test covered logical-only partitions, so
only materialization could expose the defect.

Preview state after the failed apply (verified read-only): the run prefix
contains only the stale `publication-plan.json` bound to the old identity;
orphaned content-addressed children exist for population (10), observations
(10), pregame snapshots (152), adjusted history (142 nonempty of 152),
terminal (10), and predictions (7) partitions; `phase3_attribution` has zero
children. Nothing consumable was published — `finish()` never ran, and no
storage backend implements delete, so the stale publication plan makes the
original run ID permanently unusable.

## Work Completed

- Fixed `src/cks_picks_cfb/data/lake.py` so an explicit empty
  `row_partition_keys` sequence is honored as "no row-level partition
  binding" in both the writer and the reader; an absent declaration still
  defaults to the partition keys (back-compatible with existing manifests).
- Added regression coverage in `tests/test_data_lake.py`: an
  attribution-shaped logical-only partition round trip (the exact failed
  path, including manifest `row_partition_keys: []` and idempotent rewrite)
  and a guard that declared row keys still bind rows to partitions.
- Recorded Amendment 2 (retry run ID `phase3-v2-compact-state-20260910-r2`,
  same as-of) in the plan contract and updated `docs/plans/index.md`.

## Files Modified

- `src/cks_picks_cfb/data/lake.py` - honor explicit empty row partition keys
  in writer and reader.
- `tests/test_data_lake.py` - logical-only partition regression and binding
  guard.
- `docs/plans/2026-09-10/phase3-v2-compact-tournament-state.md` - Amendment 2.
- `docs/plans/index.md` - current Phase 3 status.
- `session_logs/2026-09-11/03-phase3-v2-apply-row-partition-repair.md` - this
  log.

## Validation

- [x] No-write Preview preflight passed at `513dec0` (see Evidence).
- [x] `uv run pytest -q -W error tests/test_data_lake.py tests/test_data_first_phase3_v2.py tests/test_data_first_documentation_authority.py` — 38 passed.
- [x] `uv run pytest -q -W error` — 836 passed, 2 skipped.
- [x] Ruff format and lint for changed paths.
- [x] `uv run mkdocs build --strict --quiet`.
- [x] `git diff --check`.
- [ ] Post-commit: preflight, apply, independent verifier, and idempotent
  rerun under `phase3-v2-compact-state-20260910-r2`.

## Amendments and Blockers

- Amendment 2 (user-authorized 2026-09-11): apply-path row-partition repair
  and retry run ID `phase3-v2-compact-state-20260910-r2`, same as-of
  `2026-09-10T00:00:00Z`. All rollout gates still apply.
- Blocker: user-controlled commit checkpoint required before Preview apply.

## Handoff Notes

- **Resume at:** Commit the five modified files
  (`fix(lake): honor explicit empty row partition keys`), capture
  `git rev-parse HEAD`, then run the no-write preflight with run ID
  `phase3-v2-compact-state-20260910-r2` and `--expected-code-sha "$(git
  rev-parse HEAD)"`, inspect, and only then apply.
- **Watch out for:** Do not reuse run ID `phase3-v2-compact-state-20260910` —
  its stale `publication-plan.json` immutable-collides with any new identity.
  sklearn matmul RuntimeWarnings on degenerate Ridge folds are pre-existing
  and handled by tournament fallback; certification ignores them.

**tags:** ["phase3", "preview", "apply", "lake", "amendment", "research"]
