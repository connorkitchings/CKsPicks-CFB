# Phase 1 — Rating Measurement Remediation

- **Status:** In Progress
- **Created:** 2026-08-24
- **Planner:** Sol
- **Approval source:** User explicitly authorized implementation of the Phase 2 plan, including this separate prerequisite, on 2026-08-24.
- **Implementation log:** `session_logs/2026-08-24/03-phase1-remediation-and-phase2-implementation.md`
- **Commit policy:** Separate implementation commit required before Preview artifact materialization.

## Goal

Replace the reviewed Phase 1 research interfaces with immutable v2 artifacts
that preserve point-in-time evidence, measurement accuracy, and committed-code
lineage. The v1 artifacts remain immutable historical records and are not
eligible inputs to Phase 2.

## Contract

- Publish `rating_measurement_observations_v2`,
  `rating_adjusted_measurement_snapshots_v2`, and
  `rating_adjusted_measurement_terminal_snapshots_v1` only under the isolated
  Preview research prefix.
- Filter all identities by `(season, game_id)`; retain schedule status through
  filtering; exclude cancelled or postponed snapshot targets.
- Build each pregame snapshot from only the target season's completed evidence.
  Build one terminal adjusted snapshot per completed 2021–2025 season after all
  eligible season evidence.
- Weight schedule-strength deltas by the team-game measurement denominator.
  Omit unavailable opponent values from that calculation and attach an explicit
  quality flag instead of treating them as zero.
- Use only a genuine parent `effective_at`, `captured_at`, `observed_at`, or
  `__captured_at` value as authentic timing. Missing timing yields reconstructed
  status and cannot inform protected 2026 evidence.
- Exclude null PPA from both the EPA numerator and denominator; calculate
  scoring opportunities before field-position filtering; propagate
  measurement/role-specific quality flags and evidence bounds into snapshots.
- Refuse Preview writes unless the ratings source/configuration paths are
  tracked and match the recorded commit SHA. Existing v1 artifacts are never
  overwritten.

## Implementation Tasks

### Task 1 — Versioned contracts and exact observations

- Add v2 schemas and validators, including a terminal snapshot contract.
- Correct identity, status, temporal, PPA, opportunity, and source-lineage
  handling in the observation builder.

### Task 2 — Season-scoped adjustment and terminal snapshots

- Apply denominator-weighted adjustment only within the target season.
- Produce pregame and terminal snapshots with propagated quality and lineage.

### Task 3 — Preview-only artifact gate and audit

- Update the CLI for three v2 refs and committed-code verification.
- Extend the audit with v2 schema, season-isolation, timing, weighting, and
  supersession checks.

## Validation

- Add focused asymmetric tests for every review finding, including a cancelled
  out-of-scope row before an in-scope game, missing PPA, missing field position,
  unavailable opponents, cross-season evidence, and authentic-time exclusion.
- Run ratings tests, full Python tests, Ruff, contracts validation, strict
  MkDocs, and `git diff --check`.
- Do not materialize Preview artifacts until the relevant code is committed.

## Definition of Done

- [ ] Replacement v2 interfaces and tests are complete.
- [ ] A committed-code Preview materialization produces new immutable refs and
  passes the v2 audit.
- [ ] Documentation identifies v1 as superseded for Phase 2 consumption.
- [ ] Phase 2 may consume only the replacement audit's refs/checksums.
