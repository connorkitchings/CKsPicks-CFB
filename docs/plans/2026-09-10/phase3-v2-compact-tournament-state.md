# Phase 3 v2 Compact Tournament-State Replacement

- **Status:** In Progress
- **Created:** 2026-09-10
- **Planner:** Astra
- **Approval source:** User explicitly authorized this exact replacement on 2026-09-10.
- **Implementation log:** `session_logs/2026-09-10/03-phase3-v2-compact-state.md`
- **Supersedes:** `docs/plans/2026-09-09/phase3-measurement-and-core-selection-v2.md`
- **Commit policy:** User-controlled, separate checkpoint before Preview apply.

## Goal

Replace the failed raw snapshot accumulator with a bounded, deterministic
tournament-feature representation while preserving every sealed Phase 3 v2
mathematical, lineage, timing, and Preview-only decision.

## Binding Constraints

- Repair v2 remains the sole parent, with its sealed raw and canonical checksums.
- 2020 is forbidden. The six-hour reconstructed cutoff, four-pass adjustment,
  two recency modes, eight candidates, Ridge alpha 10, 2,000 bootstrap draws,
  folds, gates, and output artifact set remain unchanged.
- The 428,880 iteration-four adjusted component rows are an input stream, never
  a retained compact table. Every raw partition and transient component-state
  partition is at most 100,000 rows.
- The retained tournament feature table is exactly 142,960 rows, keyed by
  `(season, game_id, candidate, recency_mode)`; predictions remain 202,176
  rows. Each is bounded by 250,000 rows.
- No V4, web, Neon, production, Phase 4–6, or new published Phase 3 dataset is
  in scope.

## Implementation

1. Add a reusable stateful compact-feature builder. It consumes one weekly
   snapshot partition at a time, derives iteration-four adjusted component
   posterior states using existing scale, prior-decay, and exposure formulas,
   immediately composites candidate game features, and drops the component
   frame. It advances small terminal posterior caches only after each season.
2. Refactor the tournament entry point to fit the existing folds from compact
   game features directly. Preserve feature fallback, standardization, Ridge
   metadata, prediction schema, ordering, population equality checks, and
   selection behavior.
3. Replace the runner's global compact-snapshot concatenation with the compact
   feature builder. Bind compact count, digest, row ceilings, and observed
   maxima into dry-run output, publication plan, certification, and retained
   core. Apply requires a matching compact digest on replay.
4. Update the independent verifier to reconstruct compact features from raw
   parents via the reusable builder, compare their evidence with the retained
   manifest, and then recompute tournament and selection evidence.

## Validation

- Prove the 428,880 / 142,960 / 6,318 / 202,176 count invariants.
- Compare streaming features and predictions against the existing batch state
  and tournament paths on multi-season fixtures, including 2019→2021 decay,
  missing measurements, both recency modes, uncertainty, and fallback behavior.
- Add high-partition, duplicate-key, out-of-order, forbidden-season, missing
  terminal, digest-drift, and ceiling-rejection tests.
- Run focused and full warning-as-error pytest, coverage, Ruff format/lint,
  schema checks, V4/boundary regressions, strict MkDocs, CLI help, and
  `git diff --check`.

## Amendment 1 — Adjusted-history count correction (2026-09-11)

**Approval:** The user explicitly authorized this amendment on 2026-09-11.
**Implementation log:** `session_logs/2026-09-11/02-phase3-v2-adjusted-history-amendment.md`

The first completed no-write Preview preflight reached every compact-state and
tournament headline invariant, but rejected `expected_replay_counts` because
the inherited adjusted-history expectation was 6,777,120. A read-only
reconstruction proved the retained replay output is 3,067,048 rows. The replay
has always retained history only for `ADJUSTED_COMPONENTS`: the six measures
that receive a four-pass opponent adjustment. It does not retain diagnostic
measurements in this dataset.

Replace only the adjusted-history invariant with **3,067,048**. Preserve the
population, observation, snapshot, compact-component, compact-feature,
validation-game, prediction, candidate, recency, timing, and selection gates
unchanged. This is a correction to an unverified inherited denominator, not a
change to the replay scope or tournament mathematics.

Implementation must pin the corrected value in the runner and add regression
coverage proving that adjusted-history rows contain only adjusted components.
The independent verifier continues to reconstruct the complete preflight and
compare its output, selection, certification, and compact evidence before any
result is accepted. Repeat the no-write Preview preflight after a clean
committed checkpoint; Preview apply remains prohibited until it passes.

## Amendment 2 — Apply-path row-partition repair and retry run ID (2026-09-11)

**Approval:** The user explicitly authorized this amendment on 2026-09-11.
**Implementation log:** `session_logs/2026-09-11/03-phase3-v2-apply-row-partition-repair.md`

The first Preview apply, authorized after the passing no-write preflight at
commit `513dec0`, failed inside the apply-only writer path.
`PartitionedDatasetWriter` treated an explicitly empty `row_partition_keys`
sequence as unspecified and fell back to the logical partition keys, so the
deliberately logical-only `attribution` partition (`scope`) demanded a `scope`
column its rows do not carry. The no-write preflight attaches no writers and no
coverage existed for logical-only partitions, so only materialization could
expose it. The writer and reader now honor an explicit empty sequence while an
absent declaration still defaults to the partition keys, with lake regression
coverage for both the attribution-shaped round trip and row binding. No Phase
3 v2 mathematics, counts, digests, gates, timing, or selection rule changed.

The failed apply published nothing consumable: it left only orphaned
content-addressed children and a stale `publication-plan.json` bound to the
prior code SHA under run ID `phase3-v2-compact-state-20260910`. Because
immutable artifacts can be neither rewritten nor deleted through the storage
contract, the certified retry uses run ID
`phase3-v2-compact-state-20260910-r2` with the same as-of
`2026-09-10T00:00:00Z` and the amended invariants. Every remaining rollout
gate — a passing no-write preflight at the committed SHA, apply from a clean
tracked worktree, the independent verifier, and an idempotent rerun — still
applies in full before this contract can be marked Implemented.

## Rollout

After local validation, the user creates a committed checkpoint. Run one
no-write Preview preflight using run ID `phase3-v2-compact-state-20260910` and
as-of `2026-09-10T00:00:00Z`, inspect counts/digests/selection, then apply only
from a clean tracked worktree. Finish with the independent verifier and an
idempotent rerun. Mark this contract Implemented only when every Preview gate
passes; otherwise retain it In Progress with the blocker recorded.
