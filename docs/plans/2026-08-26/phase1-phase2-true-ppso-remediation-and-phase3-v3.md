# Phase 1/2 True-PPSO Remediation and Phase 3 v3 Tournament

- **Status:** In Progress
- **Created:** 2026-08-26
- **Planner:** Sol (user-approved remediation plan)
- **Approval source:** User explicitly authorized implementation on 2026-08-26.
- **Implementation log:** `session_logs/2026-08-26/01-phase1-phase2-true-ppso-remediation.md`
- **Commit policy:** The user commits each code/configuration contract before its
  Preview materialization. Every external write is Preview-only and immutable.

## Goal

Repair the Phase 1 PPSO unit mismatch in an isolated ratings namespace, rebuild
the dependent Phase 2 state artifacts under unchanged state equations, and only
then run a new sealed Phase 3 v3 linear-versus-NB2 score tournament. Phase 3
v1/v2 remain immutable failed research; V4 stays unchanged and production-only.

## Current State

The v2 measurement observations use a Boolean scoring event as the PPSO
numerator while Phase 2's frozen fallback center is four points. The resulting
2021 offense/defense location shift explains the persistent Phase 3 total bias.
No shared drive dataset, V4 artifact, production R2 path, Neon table, catalog,
market input, public API, or Phase 4 operation is in scope.

## Implementation Tasks

### Task 1 — True-PPSO Phase 1 contract

Create `measurement_baseline_v3` and Preview-only schemas
`rating_measurement_observations_v3`,
`rating_adjusted_measurement_snapshots_v3`, and
`rating_adjusted_measurement_terminal_snapshots_v2`. In the ratings-only
observation path, order plays by game, drive, quarter, and play; reconstruct
the offense score stream; calculate drive points as score after less score
before; and admit only finite integer values in `[0, 8]`. Outcomes validate
final score streams but never calculate or replace a drive numerator.

Quarantine a mismatched offense and its paired defense PPSO observation with
`score_stream_mismatch`. Require at least 94% exact team-score reconciliation
in every historical season, preserve the other six measurements row-for-row,
and require terminal offense/defense PPSO means in `[2, 6]`.

### Task 2 — Phase 2 v2 rebuild

After Task 1 passes a same-stamp immutable rerun, pin its exact refs/checksums
in a separate `team_state_baseline_v2` commit and materialize
`rating_measurement_states_v2` and `rating_team_states_v2`. Retain the four
equal component weights, fallback center/scale, prior exposure, rho `0.60`,
uncertainty algebra, defensive reversal, and point-in-time chronology. Add a
location gate: absolute population means for offense and defense must be at
most `0.35` per historical season and completed-game ordinal with 30+ rows,
including terminal states.

### Task 3 — Phase 3 v3 sealed tournament

After Task 2 passes a same-stamp rerun, pin its exact refs in a separate v3
score configuration and run unchanged bounded linear and NB2 score families.
Use sealed expanding selection (2021→2022, 2021–22→2023, 2021–23→2024),
complete-family selection by average target-wise V4 MAE ratio with the frozen
0.01 linear tie-break, then exactly one unchanged 2025 confirmation. Only a
passing family may be refit on 2021–2025 and write Preview-only
`rating_score_models_v3`, `rating_score_predictions_v3`, evaluation, and
`rating_score_candidate_v3` artifacts. A failed selection or confirmation
writes only its diagnostic evaluation and leaves Phase 3 in progress.

## Validation

- True-score tests cover scoring outcomes, scoreless/one-play drives,
  invalid/regressing scores, symmetric quarantines, outcome non-use, no-future
  evidence, and unchanged non-PPSO measurements.
- Phase 1 requires per-season score reconciliation ≥94%, PPSO `[0,8]`, terminal
  means `[2,6]`, immutable same-stamp rerun, and full lineage/audit checks.
- Phase 2 requires unchanged posterior/carryover/uncertainty behavior plus the
  new location-stability gate and deterministic rerun.
- Phase 3 requires existing symmetry, direction, covariance, interval,
  fold-isolation, V4 pairing, selection, locked-confirmation, and failed-write
  gates under v3 refs.
- Run ratings and full Python suites, scoped Ruff, contracts validation/sync,
  strict MkDocs, and `git diff --check` before final closure.

## Definition of Done

- [ ] Phase 1 v3 artifacts and a byte-identical rerun pass all gates.
- [ ] Phase 2 v2 artifacts and a byte-identical rerun pass all gates.
- [ ] Phase 3 v3 either freezes a passing candidate with rerun evidence, or
  records its immutable diagnostic and remains in progress.
- [ ] Authority docs, measurement catalog, roadmap, requirements, plan index,
  and session logs name exact refs, checksums, metrics, and eligibility.
- [ ] Phase 4 is described as plan-eligible only after a passing v3 candidate.

## Amendments

### Amendment 1 — Cumulative final-score reconciliation (2026-08-26)

The initial committed v3 Preview attempt stopped before publishing refs because
the 2021 reconciliation rate fell below 94%. The failure exposed a mechanical
implementation defect: final score validation used the trailing score marker
rather than the required reconstructed cumulative maximum. The score stream is
now audited against each team's maximum cumulative score; regressions remain
quarantined independently. A focused regression test covers this distinction.
No equation, parent, threshold, selection rule, or candidate identity changed.

### Amendment 2 — Reconciliation audit evidence (2026-08-26)

The first successful corrected v3 run passed the reconciliation gate but its
audit report retained only the boolean result, not the required per-season
rates. The report now serializes the already-computed immutable
`score_reconciliation` evidence. This is a reporting-lineage correction only;
it does not alter measurement values, gating, parents, or selection policy.
