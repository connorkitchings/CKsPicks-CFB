# Phase 0: Repository Architecture and Documentation Alignment

- **Status:** Approved
- **Created:** 2026-09-05
- **Planner:** Sol
- **Approval source:** User approved the full data-first plan and explicitly targeted Phase 0 on 2026-09-05.
- **Implementation log:** `session_logs/2026-09-05/02-phase0-repository-alignment.md`
- **Commit policy:** Separate plan commit required before implementation

## Goal

Make the repository understandable and ready for the data-first forecasting
program while proving that V4 production, weekly operations, publication,
artifact loading, rollback, and named research benchmarks retain their current
behavior.

## Current State

The repository already has sound top-level boundaries, but current authority
still describes the R1-R4 successor sequence as active. Research entry points
share `scripts/pipeline/` with production commands, and legacy modules, configs,
and documents require dependency classification before removal. The current
worktree was clean at planning time on `main` at `de54a7a`.

## Proposed Approach

Align documentation first, establish compatibility evidence, then perform
staged structural cleanup. Preserve existing public production interfaces and
use wrappers for relocated named research commands. Delete only items proven
unreferenced by production, named benchmarks, configs, tests, and artifact
readers. Defer data-dependent shared-code redesign to later phases.

## Scope

### Included

- Production and research dependency maps, baseline validation, documentation
  authority, active research layout, safe archival/removal, and compatibility
  wrappers.
- Named benchmarks: certified R1, fixed rating baseline, frozen candidate v1,
  completed R2 prior, and sealed direct early-game research.

### Excluded

- Data repair, new measurements/models, production behavior changes, live
  publish/freeze/close, deployment, database migrations, and artifact rewrites.

## Affected Components and Contracts

- Current architecture/docs authority, research scripts/config organization,
  supported command inventory, and compatibility validation.
- Preserve Python at root, `web/`, `contracts/`, `src/cks_picks_cfb/ratings/`,
  production `scripts/pipeline/`, and all existing production interfaces.

## Implementation Tasks

### Task 1 - Record the operating baseline

- Map production commands, imports, configs, schemas, bundle readers, R2/Neon
  boundaries, and named-benchmark dependencies.
- Record V4 identity and representative immutable inputs without exposing
  credentials. Capture scoped test, contract, web, prediction, and replay
  results; label pre-existing failures.

**Acceptance:** Each supported path has an owner, entry point, dependencies,
and baseline check. Volatile timestamps/logs may be excluded from comparisons;
predictions may not.

### Task 2 - Align current and target documentation

- Make current operations, target architecture, active contracts, and
  historical evidence distinct in the docs index, roadmap, project/assistant
  guides, modeling authority, file map, and runbooks.
- Scope the new 2025 development policy and $15/month budget only to this
  program. Link rather than duplicate policy authority.

**Acceptance:** Documentation search finds no statement that pending R3/R4 is
active or that the new program has a locked-2025 test or betting-policy scope.

### Task 3 - Establish active research structure

- Create `scripts/research/` for new and migrated active research commands.
- Keep production commands in `scripts/pipeline/`. Production code may not
  import from `research/` or `scripts/research/`.
- Relocate research commands incrementally and retain thin wrappers at named
  historical paths when production or benchmark reproduction requires them.
- Separate new-program configs from production and historical configs without
  changing existing config paths consumed by artifacts.

**Acceptance:** Named commands and readers pass smoke tests; dependency checks
show no production-to-exploratory import.

### Task 4 - Archive or remove proven obsolete material

- Classify candidates as current, compatibility, historical, or removable.
- Archive stale documents/configs with replacement pointers. Delete code only
  after static reference, config, test, CLI, and artifact-reader checks pass.
- Record every move/removal and its pinned-commit recovery path.

**Acceptance:** No unexplained removal; repository map and links match the tree.

### Task 5 - Prove compatibility and close Phase 0

- Re-run baseline checks and compare deterministic outputs.
- Publish the architecture/dependency map, cleanup disposition, validation
  results, and exact Phase 1 entry conditions.

**Acceptance:** Required checks pass or the plan remains In Progress with an
explicit blocker. No production activation occurs.

## Testing Strategy

Run focused production and named-benchmark tests first, then contract sync,
Python test suite/coverage, scoped Ruff, strict MkDocs, web lint/typecheck/build,
research CLI smoke tests, artifact-reader checks, and `git diff --check`.
Use fixtures or Preview read-only/replay paths; never mutate production merely
to test structure.

## Risks and Edge Cases

- Dynamic imports and saved artifact paths may evade static search; verify with
  smoke tests and manifest/config inspection.
- A pre-existing failure is recorded and preserved, never silently waived.
- Shared behavior that could change V4 is versioned into research instead.
- Dirty-worktree changes remain outside scope.

## Definition of Done

- [ ] Operating baseline and dependency map are published.
- [ ] Authority docs consistently describe current and target systems.
- [ ] Research entry points are separated with required compatibility preserved.
- [ ] Every removal has evidence and a recovery path.
- [ ] Required validation passes and Phase 1 entry conditions are explicit.
- [ ] Session log is complete and status is `Implemented`.

## Amendments

A change to production behavior, public interfaces, top-level boundaries,
compatibility scope, or deletion criteria requires a revised Sol plan.

