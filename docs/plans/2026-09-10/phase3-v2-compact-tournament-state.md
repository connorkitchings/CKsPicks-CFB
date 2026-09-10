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

## Rollout

After local validation, the user creates a committed checkpoint. Run one
no-write Preview preflight using run ID `phase3-v2-compact-state-20260910` and
as-of `2026-09-10T00:00:00Z`, inspect counts/digests/selection, then apply only
from a clean tracked worktree. Finish with the independent verifier and an
idempotent rerun. Mark this contract Implemented only when every Preview gate
passes; otherwise retain it In Progress with the blocker recorded.
