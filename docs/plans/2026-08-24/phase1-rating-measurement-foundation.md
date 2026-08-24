# Phase 1 — Rating Measurement and Opponent-Adjustment Foundation

- **Status:** Superseded
- **Created:** 2026-08-24
- **Planner:** Sol
- **Approval source:** User explicitly approved the Phase 1 documentation finalization and its selected defaults on 2026-08-24.
- **Implementation log:** `session_logs/2026-08-24/02-phase1-rating-measurement-implementation.md` (reserved)
- **Commit policy:** Separate plan commit required before implementation because this establishes model lineage and protected-evidence interfaces.

## Goal

Create the isolated, point-in-time measurement foundation consumed by the
future rating engine without modifying V4. Replace implicit values in a wide
feature row with explicit raw observations and pregame adjusted snapshots whose
exposure, effective-time status, provenance, missingness, and transformation
lineage can be audited.

Phase 1 succeeds when:

- every selected historical team-game has reproducible long-form measurement
  observations built from immutable canonical parents;
- every scheduled historical or inference game can resolve pregame measurement
  snapshots using only previously eligible observations;
- opponent adjustment is performed exactly once in the new measurement layer;
- coverage and redundancy reports establish whether the baseline catalog is fit
  for Phase 2; and
- no rating estimator, candidate prediction, market input, Neon activation, or
  V4 behavior is introduced.

## Current State

`build_team_game_dataset.py` already creates immutable `byplay_v1`, `drives_v1`,
and `team_game_v1` datasets from canonical plays, schedule, weather, corrections,
and source reconciliation. The feature layer then aggregates wide team-season
values and applies iterative opponent adjustment. The point-in-time Gold builder
keeps prior/current blocks and excludes bookmaker fields.

Those foundations are reusable, but the existing wide rows do not consistently
retain the numerator, denominator, exposure basis, per-measurement missing reason,
or adjustment lineage needed by a durable rating-state contract. The established
opponent-adjustment helper is season-aggregate oriented; calling it over a full
season would leak future schedule evidence into a pregame rating workflow.

Phase 1 therefore adds a parallel ratings research package and leaves all
existing V4 aggregations, schemas, configs, callers, and artifacts unchanged.

## Proposed Approach

Create two versioned long-form datasets:

1. `rating_measurement_observations_v1` records one raw team-game observation per
   role and measurement, including exact numerator and denominator.
2. `rating_adjusted_measurement_snapshots_v1` records the strictly pregame raw
   aggregate and measurement-level opponent-adjusted value available to each
   scheduled team before kickoff.

The snapshot builder walks games in kickoff order. For a target game it may use
only observations from completed, non-cancelled games with kickoffs before the
target kickoff and eligible effective-time status. It recomputes adjustment from
that frozen history; it never reads a future row or carries a full-season adjusted
value backward.

All artifacts live under the Preview research prefix
`artifacts/research/rating-successor/measurements/{measurement_design_id}/`.
The CLI rejects `production`, never writes prediction or V4 refs, and may register
immutable dataset metadata only in the Preview catalog.

## Baseline Measurement Catalog

The v1 observation interface contains the following deliberately small catalog.
Offense and defense roles are separate rows where both apply.

| Measurement ID | Roles | Numerator | Denominator | Phase 1 adjustment |
| --- | --- | --- | --- | --- |
| `epa_per_play` | offense, defense | Sum of eligible-play PPA | Eligible scrimmage plays | Iterative additive |
| `success_rate` | offense, defense | Successful eligible plays | Eligible scrimmage plays | Iterative additive |
| `explosive_rate_20` | offense, defense | Eligible plays gaining at least 20 yards | Eligible scrimmage plays | Iterative additive |
| `points_per_scoring_opportunity` | offense, defense | Points on scoring-opportunity drives | Scoring opportunities | Iterative additive |
| `average_start_field_position` | offense, defense | Sum of own-goal distance at drive start | Eligible drives | Context only; not adjusted |
| `plays_per_drive` | offense | Eligible scrimmage plays | Eligible offensive drives | Pace context only; not adjusted |
| `turnover_rate` | offense, defense | Eligible-play turnovers | Eligible scrimmage plays | Reliability context only; not adjusted |

Eligible plays are exactly rows where `is_drive_play == 1` and `garbage == 0`.
`is_drive_play` already excludes special teams, penalties, two-point plays, and
non-counting events. Missing either eligibility flag is a coverage failure, not
an implicit inclusion. Eligible drives contain at least one eligible play and
must be attributable to one offense and defense without cancellation or
duplication.

This catalog is the Phase 1 interface, not a declaration that every measurement
will enter the Phase 2 estimator. The redundancy report must treat
`success_rate` as the first diagnostic challenger to `epa_per_play`; field
position, pace, and turnovers remain contextual unless a later contract promotes
them into team quality.

## Interfaces and Contracts

### Raw observation row

Required fields:

- Identity: `season`, `week`, `game_id`, `kickoff_utc`, `team`, `opponent`,
  `side`, `measurement_id`, `unit_role`.
- Value: `numerator`, `denominator`, `raw_value`, `exposure_unit`.
- Time: nullable `effective_at`, `temporal_status`, `eligible_after`.
- Quality: `coverage_status`, `missing_reason`, `quality_flags`.
- Lineage: `measurement_schema_version`, `measurement_design_id`, source dataset
  refs/checksums, code SHA, and config SHA.

`raw_value` is null when the denominator is zero or required source evidence is
missing. The builder must never replace a zero denominator with one.
Historical 2021–2025 rows may have `temporal_status = reconstructed` and a null
`effective_at`; they are eligible only for kickoff-ordered historical
development. Protected 2026 rows require authentic source timing before their
target kickoff.

### Pregame adjusted snapshot row

Required fields:

- Target identity: `season`, `week`, `as_of_game_id`, `as_of_kickoff_utc`,
  `team`, `measurement_id`, `unit_role`.
- Evidence: `raw_aggregate`, `adjusted_value`, `games_exposure`,
  `primary_exposure`, and included-observation count.
- Adjustment: `adjustment_method`, `adjustment_iteration`, league center, and
  `schedule_strength_component`.
- Quality and lineage fields inherited from the observation set plus the exact
  parent observation dataset ref.

The baseline adjustment method is the existing additive, league-centered
concept evaluated over the strictly prior observation graph. Four iterations
are fixed in `measurement_baseline_v1`; iteration zero and iteration four are
retained for audit. Context-only measurements must have
`adjustment_method = none` and `adjusted_value = raw_aggregate`.

### Coverage and redundancy report

The immutable report contains, by season and measurement/role:

- expected and observed team-games, non-null numerator/denominator/value counts,
  zero-exposure and missing-reason counts;
- temporal-status distribution and the number of rows eligible for historical
  development versus protected 2026 use;
- min/median/max exposure and value quantiles;
- pairwise Spearman correlations on common pregame snapshots; and
- explicit pass/fail results for uniqueness, two-team symmetry, source
  reconciliation, 2020 exclusion, 2019 restrictions, and future-row checks.

The report is descriptive and lineage-focused. It must not inspect betting
markets, optimize prediction error, or select a rating estimator.

## Scope

### Included

- A new isolated `cks_picks_cfb.ratings` measurement/contracts namespace.
- Versioned config for the catalog, eligibility filters, and four-iteration
  adjustment.
- A Preview-only CLI that reads immutable schedule/outcomes/byplay/drives/
  reconciled-team-game refs and writes immutable research datasets and reports.
- Executable schema validation plus focused unit and integration tests.
- Updates to the measurement catalog and rating requirements with exact Phase 1
  interface and audit results.

### Excluded

- Rating estimation, priors, team-state snapshots, margin/total predictions,
  uncertainty estimation, candidate freezing, or shadow scoring.
- Market data, betting metrics, residual ML, rating-assisted adjustment, or
  special-teams rating components.
- Modifications to V4 features, bundles, configs, ops commands, Neon serving
  tables, web publication, or production artifacts.
- Silent fallback to local `./data/` or execution against the production target.

## Affected Components and Contracts

- Add `src/cks_picks_cfb/ratings/` for pure observation, snapshot-adjustment,
  schema, and audit behavior; do not import it from V4 paths.
- Add `conf/ratings/measurement_baseline_v1.yaml` as the canonical catalog and
  adjustment configuration.
- Add `scripts/pipeline/build_rating_measurements.py` as the Preview-only,
  immutable artifact entry point.
- Extend executable dataset-schema validation for the two measurement datasets;
  no SQL or public TypeScript contract changes.
- Add focused tests under `tests/ratings/` and CLI tests using in-memory storage.

## Implementation Tasks

### Task 1 — Encode the measurement contracts

**Changes:**

- Define frozen measurement specifications, roles, exposure units, adjustment
  posture, and required source columns.
- Implement raw and snapshot schema validators with uniqueness, finite-value,
  nonnegative-exposure, null-reason, temporal-status, and forbidden-market-field
  rules.
- Hash the normalized configuration to create `measurement_design_id`; reject a
  caller-supplied ID that does not match.

**Acceptance criteria:**

- Every row conforms to exactly one catalog specification.
- Zero exposure produces a null value with a reason.
- Bookmaker or market-derived columns are rejected anywhere in inputs, outputs,
  configuration, or lineage metadata.

### Task 2 — Build long-form raw observations

**Changes:**

- Derive exact numerators and denominators from immutable byplay and drive parents;
  use reconciled team-game rows only for coverage and symmetry checks.
- Join canonical schedule/outcome identity and encode authentic versus
  reconstructed temporal status without claiming historical capture times that
  do not exist.
- Produce deterministic row ordering and immutable parent/checksum lineage.

**Acceptance criteria:**

- Each eligible completed game yields two team sides for every applicable
  measurement/role or an explicit missing row.
- Cancelled, duplicate, 2020, post-cutoff, and unreconciled games fail closed.
- Re-running identical parents and config produces byte-equivalent logical rows
  and the same design ID.

### Task 3 — Build strictly pregame adjusted snapshots

**Changes:**

- Walk scheduled games by `(kickoff_utc, game_id)` and form each evidence graph
  exclusively from earlier eligible observations.
- Compute exposure-weighted raw aggregates, then four iterations of additive,
  league-centered opponent adjustment for adjustment-eligible measurements.
- Retain iteration-zero and final values plus the schedule-strength component;
  pass context-only measurements through unchanged.

**Acceptance criteria:**

- Changing a future observation cannot alter an earlier snapshot.
- Same-kickoff and later games cannot inform one another; deterministic game ID
  ordering is for output only, never evidence eligibility.
- Sparse and first-game teams remain explicit missing/prior-free measurement
  states for Phase 2; Phase 1 must not invent priors.
- No adjusted measurement receives schedule-strength treatment twice.

### Task 4 — Add the immutable Preview research workflow

**Changes:**

- Implement a CLI requiring explicit parent ref URIs, `--as-of`, output ref URI,
  and measurement config.
- Reject production runtime targets and any output outside the research prefix.
- Write observation, snapshot, and audit artifacts immutably with checksums;
  allow idempotent reuse only when the existing ref bytes match.

**Acceptance criteria:**

- Partial writes activate nothing and immutable collisions fail loudly.
- No prediction, V4 bundle, web-serving, or production ops reference is created.
- In-memory integration tests exercise success, idempotency, collision, and
  validation failure without external I/O.

### Task 5 — Run the historical/2026 coverage audit and close Phase 1

**Changes:**

- In Preview, build 2021–2025 historical development artifacts plus the
  available pregame 2026 snapshot using exact immutable refs.
- Record coverage, temporal status, missingness, exposure, correlations, and
  every excluded row in the audit report.
- Update the active measurement catalog and rating requirements with the final
  Phase 1 disposition of each metric.

**Acceptance criteria:**

- All Phase 1 validation gates pass or the contract remains In Progress with a
  documented blocker; no threshold may be waived to meet Week 1.
- The final report names the exact observation, snapshot, and configuration
  refs/checksums that Phase 2 must consume.
- The report contains no market or prospective-outcome tuning.

## Testing Strategy

- Unit tests for eligibility filtering, numerator/denominator calculation,
  zero exposure, missing flags, symmetry, schema validation, and config hashing.
- Point-in-time tests that mutate future, same-kickoff, cancelled, and late-
  captured observations and prove earlier snapshots are unchanged.
- Opponent-adjustment tests for centering, four-iteration determinism, exposure
  weighting, disconnected schedules, and no-adjustment pass-through metrics.
- Artifact tests for checksum verification, immutable collision, Preview-only
  enforcement, and identical-input idempotency.
- Regression tests proving V4 imports, configs, point-in-time Gold output, and
  weekly publication remain unchanged.
- Required gates: focused tests, full branch-aware coverage floor, Ruff check
  and format check, Python contract validation, MkDocs strict build, and
  `git diff --check`.

## Risks and Edge Cases

- Historical artifacts may have reconstructed rather than authentic retrieval
  times. Encode that status explicitly; never upgrade it silently to protected
  prospective evidence.
- Current wide aggregations sometimes divide by a substituted denominator of
  one. The ratings contract must recompute exact exposures and preserve nulls
  for zero opportunity.
- Multiple games can share kickoff times. Neither game may inform the other.
- Small or disconnected early-season schedules can make adjustment unstable.
  Retain raw values and quality flags; Phase 1 must not solve this by inventing
  a rating prior.
- Measurement correlations are diagnostic. Do not select metrics using known
  2026 outcomes or market performance.
- Week 0 production work always takes precedence over the conditional Week 1
  target.

## Definition of Done

- [ ] Both v1 measurement datasets and the audit report are versioned,
  checksummed, immutable, and reproducible from named parents.
- [ ] Point-in-time, lineage, coverage, redundancy, and no-double-counting gates
  pass for the Phase 2 input set.
- [ ] V4 and all production/publication behavior remain unchanged.
- [ ] Required validation passes and the coverage floor does not regress.
- [ ] Documentation and the Phase 1 implementation session log are updated.
- [ ] This plan is approved before implementation and marked `Implemented` only
  after every exit criterion passes.

## Approved Defaults

1. The seven-measurement v1 catalog is frozen; field position, pace, and
   turnovers remain contextual rather than Phase 2 quality inputs.
2. The baseline uses four fixed additive-adjustment iterations and retains
   iteration zero plus iteration four for audit.
3. Reconstructed temporal status is valid for 2021–2025 development only;
   protected 2026 claims require authentic source timing.
4. Preview catalog metadata registration is permitted, while all payloads remain
   under the isolated research prefix.

This approval finalizes documentation and planning only. It does not authorize
implementation, cloud access, catalog registration, artifact creation, or an
advance to Phase 2 without a fresh Terra task using this exact contract.

## Amendments

Any change to eligible-play definitions, measurement catalog, adjustment
posture, temporal-status policy, artifact prefix, or production isolation is
material and requires Sol review plus explicit user approval before Terra
continues.

Implementation amendments (mechanical, recorded by Terra on 2026-08-24; none
change architecture, interfaces, scope, or acceptance criteria):

1. **`success_rate` exposure basis.** Canonical eligible plays include ~2%
   rows with null `success` (dead-ball markers such as End of Half/Game and
   some return/completion plays). The exact-exposure rule divides by eligible
   plays with computable success (matching the existing team-game `off_sr`
   mean behavior); affected games carry the `success_missing_on_eligible_plays`
   quality flag. The frozen config and design ID are unchanged; the precise
   rule is documented in the measurement catalog.
2. **Run-stamped artifact URIs.** Dataset identity includes `as_of`, so
   rebuilt content can legitimately differ under one design ID. Output
   refs/report therefore use `{prefix}/runs/{run-stamp}/…` leaf paths; the
   research-prefix enforcement in the CLI is unchanged and an early
   un-stamped verification build correctly failed closed on collision.
3. **Lake-registered timestamp columns.** `effective_at`/`eligible_after`
   (observations) and evidence-bound timestamps (snapshots) are nullable by
   contract, so they are excluded from the non-nullable lake
   `timestamp_columns`; their semantics are enforced by the ratings frame
   validators instead.

## Implementation Record

**Supersession:** The original v1 artifacts remain immutable research history,
but the 2026-08-24 review found material lineage, season-boundary, weighting,
and source-timing defects. They are superseded for Phase 2 by
`phase1-rating-measurement-remediation.md`; no v1 ref may be used as a
successor-state input.

Executed by Terra on 2026-08-24 (`session_logs/2026-08-24/02-phase1-rating-measurement-implementation.md`).

- Code: `src/cks_picks_cfb/ratings/` (`contracts.py`, `observations.py`,
  `snapshots.py`, `audit.py`), `conf/ratings/measurement_baseline_v1.yaml`,
  `scripts/pipeline/build_rating_measurements.py`, executable schemas in
  `src/cks_picks_cfb/data/schema_contracts.py`, tests in `tests/ratings/`
  (49 tests).
- Preview artifacts (design ID
  `5c4d5cc4d6a46d4b3d830b50607f7fa0f8984cc63ab6ee64b6a7e626b415f95f`):
  observations version `b1da5e85a0438fab109937bf`, snapshots version
  `312917237b7b60cb10d61150`, audit report SHA-256
  `05fe64f101773aff2f6ad46c40e9afaceb516e633d89ac226ab9a2bdc5a542de` under
  `runs/2026-08-24T1830Z/`. All audit checks pass; rebuild is
  byte-idempotent. No catalog registration performed (optional default).
- Exit criteria: all Definition-of-Done items verified — datasets immutable
  and reproducible; point-in-time/lineage/coverage/redundancy/no-double-
  counting gates pass; V4 and publication behavior unchanged (full suite
  462 passed + 49 new, no regressions); coverage floor and quality gates
  pass; docs and session log updated.
