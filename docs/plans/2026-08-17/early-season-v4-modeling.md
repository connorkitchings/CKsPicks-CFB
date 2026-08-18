# Early-Season V4 Modeling and Game-4 Handoff

- **Status:** In Progress
- **Created:** 2026-08-17
- **Planner:** Sol
- **Approval source:** User explicitly authorized implementation in this Codex task on 2026-08-17.
- **Implementation log:** `session_logs/2026-08-17/01-early-season-v4-modeling.md`
- **Commit policy:** Separate plan commit; implementation commits remain user-controlled.

## Goal

Redesign the first-four-games methodology around predictive accuracy while
retaining the established model as the late-early-season anchor.  Success means
a reproducible, result-only V4 bundle selects each early route without future
leakage, validates its Game-4 handoff against the established model, and can be
rehearsed end-to-end in Preview.

## Current State

- V3 supplies `game_1` through `game_3` plus `established` routes.  Only Game
  1 spread passed its result-only selection gate; multiple early routes retain
  their baseline.
- The active V2 Preview run and untracked `artifacts/preview/` are user-owned
  operational state and must remain preserved.
- Recruiting, coaches, rosters, returning production, and preseason rankings
  are usable preseason inputs.  CFBD talent remains unavailable and must be
  optional rather than a launch prerequisite.
- The established model is the comparison anchor and is not retournamented.

## Proposed Approach

Add a canonical `game_4` route and run a sealed V4 tournament.  Candidate
features combine point-in-time prior performance with complete preseason source
families; Games 2-4 additionally use team-specific empirical-Bayes current
season features.  Each target-route chooses a result-only winner on 2022-2024
OOF data, validates once on sealed 2025 data, then refits unchanged on
2021-2025.  Historical market data is excluded from feature selection,
promotion, and activation.

## Scope

### Included

- A `game_4` route across model bundles, prediction contracts, storage schemas,
  web labels, and legacy compatibility mappings.
- Point-in-time V4 preseason feature variants from prior performance,
  recruiting, coaches, rosters, returning production, and rankings; talent is
  included only when complete and reproducible for every required season.
- Game-4-versus-established result-only evaluation, sealed tournament/refit,
  finite-output enforcement, V2-V3-V4 comparison, and Preview rehearsal.

### Excluded

- Retournamenting the established model.
- Bookmaker-derived model features, historical market-dependent promotion, and
  paid historical odds acquisition.
- Automatic production deployment, Pick'em submission, Git staging, commits,
  or pushes.

## Affected Components and Contracts

- Point-in-time routing, early-season feature assembly, tournament evaluation,
  and V4 model-bundle refit/loading.
- Prediction regime database constraint and TypeScript/web compatibility for
  `game_4`; historic route values remain readable.
- Preview operational scripts, comparison output, and release documentation.

## Implementation Tasks

### Task 1 — Extend canonical routing and contracts

**Changes:**

- Route a matchup by its least-experienced team through `game_1` to `game_4`,
  with `established` applying only after both teams have completed four games.
- Add an append-only migration and contract/type/web support for `game_4`.
- Preserve parsing of stored legacy labels and model bundles.

**Acceptance criteria:**

- Byes, uneven completed-game counts, cancellations, and historic rows route
  deterministically; no existing prediction row is relabeled in storage.

### Task 2 — Build V4 point-in-time features and candidates

**Changes:**

- Construct V4 candidate variants from prior performance plus reproducible
  preseason source families.  A source family is excluded from a candidate when
  its point-in-time coverage is incomplete; talent never triggers row-level
  inference or partial imputation.
- Extend team-side empirical-Bayes shrinkage and candidate generation through
  Game 4, retaining baseline, direct Ridge/CatBoost, points-derived
  Ridge/CatBoost, and frozen blend candidates.

**Acceptance criteria:**

- Candidates are kickoff-point-in-time reproducible, contain no bookmaker
  inputs or 2020 lineage, and preserve each team's independent exposure.

### Task 3 — Select and refit the V4 methodology

**Changes:**

- Run 2022-2024 OOF selection with MAE as the winner criterion and RMSE/bias,
  sample, season-stability, and paired-bootstrap gates.
- Evaluate Game 4 alternatives against the unchanged established model,
  independently by target.  Freeze the design before one locked 2025 check,
  then refit the selected ten-cell bundle on 2021-2025.
- Reject non-finite predictions and numerical runtime warnings during candidate,
  locked, refit, and inference stages.

**Acceptance criteria:**

- Failed challengers revert to explicit baselines; the immutable report records
  source variants, V2/V3 baselines, selection SHA, locked result, and route
  decision.

### Task 4 — Rehearse and document V4

**Changes:**

- Generate a private V4 Week 0 prediction artifact from the frozen V2 input
  references and emit a V2-V3-V4 comparison.
- Run Preview readiness, publication/freeze, row-level coverage checks, and
  update modeling/operations documentation.

**Acceptance criteria:**

- A selected result-only V4 bundle may be activated only after finite outputs
  and a complete Preview rehearsal.  V2 remains the fallback if that gate is
  not reached.

## Testing Strategy

- Unit-test Game-4 routing, source-availability policy, talent omission,
  shrinkage, numerical failure handling, legacy compatibility, and all stated
  scheduling edge cases.
- Test sealed selection/locked/refit stages, deterministic report/bundle hashes,
  target-specific Game-4 handoff, and explicit baseline fallback.
- Run full Python tests, Ruff, contracts and migration integration checks, web
  lint/typecheck/build, MkDocs, Preview cycle checks, and `git diff --check`.

## Risks and Edge Cases

- Optional sources must be complete within a candidate's historical folds and
  2026 snapshot; otherwise that candidate is unavailable rather than degraded.
- Result-only activation does not represent a betting or profitability claim.
- Preview data artifacts are user-owned; no cleanup, regeneration, or staging
  occurs outside an explicitly authorized rehearsal.

## Definition of Done

- [ ] All implementation tasks and acceptance criteria are complete.
- [ ] Required validation passes.
- [ ] Documentation and implementation session log are updated.
- [ ] Plan status is updated to `Implemented`.

## Amendments

### Amendment 1 — Immutable point-in-time reference and research isolation (2026-08-17)

The historical `preseason_team_inputs` artifacts have 2026 capture timestamps
and end-of-season fields, so they cannot serve as historical preseason inputs.
V4 therefore uses two immutable feature-reference tracks:

- **Strict:** activation-eligible prior performance and current-season
  shrinkage now, with each additive preseason family admitted only when every
  required 2021-2026 team-season has source-specific pre-kickoff effective-time
  evidence.
- **Reconstructed:** subsequently backfilled provider data, explicitly marked
  non-point-in-time and limited to research reports. It cannot select routes,
  refit a bundle, pass readiness, or publish predictions.

The strict core tournament proceeds without waiting for an added source family.
The detailed approved implementation specification is the user-authorized
"V4 Immutable Point-in-Time Feature Reference" plan from this session.

### Amendment 2 — Preview materialization execution gate (2026-08-17)

The strict V4 team reference was successfully materialized in Preview:

- Dataset version: `8c47f6d5ccdced2365e4dfdd`
- Reference SHA: `efa3271d7d64aea60072ab43425e36f44a3c103ef80ee90064357d80df4d4c9b`

The next safe operation, assembling the strict V5 selection Gold reference,
was blocked by the Codex environment usage limit before it ran. The remaining
selection → locked 2025 → refit → private Preview rehearsal is therefore
explicitly incomplete. The active V2 Preview run is unchanged.
