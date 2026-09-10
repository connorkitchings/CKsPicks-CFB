# Session: Phase 3 v2 compact tournament state

## TL;DR

- **Worked On:** Replaced the failed global raw-snapshot compact-state design.
- **Plan Contract:** `docs/plans/2026-09-10/phase3-v2-compact-tournament-state.md`
- **Approval / Status:** User explicitly authorized implementation; In Progress.
- **Outcome:** The runner now retains compact tournament features rather than
  raw component snapshots. Local validation passes; Preview execution is
  deliberately pending a user-created committed checkpoint.
- **Next:** Commit only the replacement paths, then run one Preview no-write
  preflight using `phase3-v2-compact-state-20260910`.

## Context

The Preview dry run failed before publication because its 428,880 iteration-four
component rows exceeded the 250,000-row compact limit. The replacement retains
only 142,960 deterministic game/candidate/recency tournament feature rows.

## Work Completed

- Added a season-aware compact feature builder that derives component posteriors
  from one weekly partition at a time, composites eight candidate game features,
  and retains only those compact rows and terminal posterior caches.
- Refactored the sealed Ridge tournament to accept compact game features while
  preserving its folds, fallback, standardization, prediction contract, and
  candidate-comparison checks.
- Bound raw/compact counts, canonical compact digest, partition maxima, and the
  absence of a raw accumulator into dry-run, publication, certification,
  retained-core, and verifier evidence.
- Added equivalence, ordering, missing-terminal, duplicate-key, and compact
  tournament-grid tests, including a high-volume fixture with 250,272 raw
  component rows and 83,424 retained compact rows. The prior streaming
  contract is retained and marked Superseded.

## Validation

- [x] Focused Phase 3/lake tests: 28 passed.
- [x] Full warning-as-error test suite: 822 passed, 2 skipped.
- [x] Ruff format check and lint for changed Python files.
- [x] Contract synchronization, strict MkDocs, both CLI help checks, and
  `git diff --check`.
- [ ] Preview dry run, apply, independent verifier, and idempotent rerun.

## Handoff Notes

- **Resume at:** User commits only the listed Phase 3 replacement paths and
  supplies the resulting SHA for the Preview no-write preflight.
- **Watch out for:** Apply remains blocked until the tracked worktree is clean;
  preserve the unrelated web, operations, plan-index, and `.opencode/` changes.

**tags:** ["phase3", "streaming", "compact-state", "implementation"]
