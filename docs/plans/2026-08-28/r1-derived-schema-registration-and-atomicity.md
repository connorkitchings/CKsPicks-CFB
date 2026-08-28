# R1 Derived-Schema Registration and Atomicity

- **Status:** In Progress
- **Created:** 2026-08-28
- **Planner:** Sol
- **Approval source:** User approved the exact remediation in Codex on
  2026-08-28 ("Proceed").
- **Implementation log:**
  `session_logs/2026-08-28/03-r1-derived-schema-registration-and-atomicity.md`
- **Commit policy:** Separate plan and implementation commits; user executes
  Git operations.

## Goal

Restore the successor-v2 R1 path by publishing executable contracts for every
derived Silver output and ensuring the derived builder validates all outputs
before it writes any immutable object. Success is a fresh, fully recaptured
Preview R1 run that either reaches passing certification or stops only at an
existing R1 data-quality gate.

## Current State

The failed diagnostic run `r1-full-corpus-20260828-fb9870c` completed all ten
capture sets and closed its exact source manifest. Its corrected 2015
reconciliation passed, including the seven manifest-declared CFBD omissions
(717 of 724 completed games covered), then stopped registering
`byplay/byplay_v1`: the builder emits `byplay`, `drives`,
`reconciled_team_game`, and `source_reconciliation`, while executable schemas
exist only for `reconciled_team_game`.

`build_dataset_version()` writes an immutable object before catalog
registration. Missing derived schemas therefore leave diagnostic orphan
objects. R2 remains blocked until a new R1 coverage report says
`tournaments_permitted: true`.

## Proposed Approach

Add initial executable v1 contracts for the three unregistered derived
datasets, retain the existing reconciled-team-game contract, and preflight all
four resulting frames before the first `build_dataset_version()` call. Keep the
general lake behavior unchanged: this operation-specific atomicity guard avoids
silently changing legacy and research builders that may intentionally lack an
executable schema.

## Scope

### Included

- Derived-Silver schemas, builder preflight, R1 committed-code guard, tests,
  documentation, and a fresh Preview-only full-corpus R1 run.

### Excluded

- Schema migrations, changes to capture data, coverage thresholds, source
  authority, R2–R4 execution, production/V4/candidate-v1 behavior, 2020, and
  2026 outcomes.

## Affected Components and Contracts

- `byplay/byplay_v1`: natural key `(game_id, drive_number, play_number)`.
- `drives/drives_v1`: natural key
  `(game_id, drive_number, offense, defense)`.
- `source_reconciliation/reconciliation_v1`: natural key
  `reconciliation_id`; classifications are `exact_match`, `incomplete_source`,
  or `blocking_conflict`.
- `reconciled_team_game/team_game_v1` remains the existing `(season, game_id,
  team)` contract.
- Schema registration uses the current catalog tables; no DDL change is
  required. The new schema SHA is incorporated into fresh derived dataset
  identities.

## Implementation Tasks

### Task 1 — Publish executable derived contracts

**Files:**

- `src/cks_picks_cfb/data/schema_contracts.py`
- `src/cks_picks_cfb/data/silver/contracts.py`

**Changes:**

- Define the three missing v1 contracts with the identifiers, required fields,
  type checks, non-null keys, and allowed reconciliation values above.
- Require the stable fields consumed by the R1 measurement pipeline; retain
  nullable analytic fields and dynamic football features.
- Ensure `schema_for()` rejects the wrong schema version for these derived
  datasets.

**Acceptance criteria:**

- Each emitted derived output has one executable schema and deterministic
  schema SHA; `reconciled_team_game/team_game_v1` remains compatible.

### Task 2 — Fail before writing a partial derived set

**Files:**

- `scripts/pipeline/build_team_game_dataset.py`
- `src/cks_picks_cfb/ops/__main__.py`

**Changes:**

- Build the four output frames, resolve their schemas, and validate each frame
  before invoking `build_dataset_version()`.
- Add `schema_contracts.py` to the R1 committed-code path guard.

**Acceptance criteria:**

- A contract error produces no derived data object, ref set, or catalog row.
- A valid R1 build registers all four outputs with non-null schema SHAs.

### Task 3 — Validate and recapture R1

**Changes:**

- Commit implementation before the data operation and launch a new Preview
  `prepare-rating-history` run under a fresh run ID.
- Recapture all ten permitted seasons; never reuse either failed source set as
  an authoritative parent and do not use `--skip-capture`.
- Run through derived refs, cross-lineage, measurement/state foundation, and
  certification; rerun the identical invocation for deterministic recovery.

**Acceptance criteria:**

- R1 reports `tournaments_permitted: true` only if every existing gate passes.
  Otherwise it leaves immutable diagnostics and R2 remains blocked.

## Testing Strategy

- Unit-test schema resolution/version rejection, required columns, key
  uniqueness and nulls, integer/boolean fields, and reconciliation values.
- Integration-test all-four schema preflight and prove no immutable write occurs
  when any output fails validation.
- Run focused schema/lake/catalog/reconciliation/ops/ratings tests; then the
  full Python suite, scoped Ruff, contract sync, strict MkDocs, CLI smoke
  checks, and `git diff --check`.

## Risks and Edge Cases

- Existing failed-run objects are immutable diagnostics and must not be deleted
  or used as parents.
- The manifest-declared omission exception remains R1-only and does not affect
  schema permissiveness or certification thresholds.
- Cross-lineage, PPSO, terminal-team, and coverage failures after this fix are
  intentional R1 stop conditions, not reasons to weaken the contract.

## Definition of Done

- [ ] Derived contracts and preflight are implemented and tested.
- [ ] A fresh R1 run reaches certification and its identical recovery rerun is
  verified, or an existing data gate publishes terminal diagnostics.
- [ ] Required validation passes, documentation/session records are complete,
  and the plan status reflects the terminal result.
- [ ] R2 is handed off only after a passing R1 certification.

## Amendments

None.
