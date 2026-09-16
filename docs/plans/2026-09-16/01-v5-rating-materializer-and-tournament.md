# V5-03A: Possession Rating Materializer and Tournament

- **Status:** In Progress
- **Created:** 2026-09-16
- **Planner:** Codex planning task
- **Approval source:** User explicitly approved this exact contract path on 2026-09-16.
- **Implementation log:** `session_logs/2026-09-16/04-v5-rating-materializer-and-tournament.md`.
- **Commit policy:** Separate code checkpoint; user executes Git before any Preview run identity is selected.

## Goal

Complete steps 1–3 of the approved V5-03 contract: load the exact R6 and Repair
v2 evidence, construct every chronological prior and pregame state for the sealed
60-candidate registry, and run the identical rating-to-margin/total bridge and
selection tournament. Success is a deterministic no-write preflight whose full
partition plan, record digests, population evidence, candidate results, and
selected identity can be reviewed before immutable publication.

## Current State

Commit `453ad7c` provides the sealed configuration, schemas, parent validation,
pure prior/update/Kalman primitives, bridge/selection scaffolding, and Preview
CLI boundaries. The in-progress checkpoint adds exact-parent input loading,
chronological state construction, bridge/selection computation, and deterministic
no-write partition planning. The runner still rejects `--apply`; immutable
materialization remains exclusively in Contract 03B.

The only eligible parents are:

- `artifacts/research/data-first-football-v1/possession-v1/measurements/runs/possession-v1-measurements-20260915-18fb0aa-r6/measurement-manifest.json`
- `artifacts/research/data-first-football-v1/repair/v2/runs/repair-v2-20260909T1417Z/repair-manifest.json`

R6 contains 8,936 population rows, 285,952 team-game observations, 142,960
pregame snapshots, 24,223,998 cutoff-specific adjusted-history rows, and 8,580
terminal rows. The adjusted-history size requires streaming by declared
partition; it must never be concatenated in full.

## Proposed Approach

Keep I/O in the research runner and add a producer-owned orchestration layer on
top of the existing pure rating functions. Stream R6 adjusted-history partitions
once in season/week order, derive shared cutoff-specific sufficient statistics,
and reuse them across candidates. Priors and Kalman noise remain candidate-
specific, but schedule population, transforms, completed-game counts, venue
facts, labels, and bridge population are shared and immutable.

The dry run performs the complete computation without R2 writes. It records the
ordered partition membership, row counts, canonical record digests, selection
evidence, and a summary checksum in stdout JSON suitable for Contract 03B's
evidence-bound apply. No local `./data/`, catalog, Neon, V4, or production write
is permitted.

## Scope

### Included

- Exact-parent loading and checksum/schema/consumer-role validation.
- Chronological prior, state, bridge, diagnostic, and selection computation for all 60 candidates.
- Bounded partition planning and complete no-write preflight evidence.
- Focused tests and observability for long source/replay/tournament phases.

### Excluded

- R2 child-part or final-manifest writes, independent verification, and idempotent apply; Contract 03B owns them.
- Contract 04 forecasting-head/window selection, live 2026 replay, market inputs, production, Neon, catalog registration, and public serving.
- Any registry, constant, fold, threshold, feature-family, or population change.

## Affected Components and Interfaces

- Extend `scripts/research/run_data_first_possession_ratings.py` with complete source loading, computation, ordered part planning, progress events, and machine-readable preflight evidence.
- Add producer orchestration in `src/cks_picks_cfb/ratings/possession_rating_materializer.py`; keep mathematical primitives in `possession_ratings.py` and selection in `possession_rating_tournament.py`.
- Reuse the registered V5 schemas and dataset names from `data_first_possession_rating_v1.py`.
- Introduce internal `RatingTournamentInputs`, `RatingTournamentComputation`, and `DatasetPlan` structures. The runner's public CLI remains `--run-id`, `--expected-code-sha`, `--environment preview`, `--as-of`, `--config`, `--measurement-manifest-uri`, and `--repair-manifest-uri`; dry-run remains the default.
- Dry-run stdout adds `source_refs`, `population_sha256`, `candidate_status`, `selected_candidate`, `selection_sha256`, `preflight_plans`, `row_counts`, `output_records_sha256`, and `preflight_sha256`.

## Implementation Tasks

### Task 1 — Load and reconcile exact rating inputs

**Changes:**

- Verify manifest bytes before JSON decoding, then verify R6's signed manifest,
  reviewed certification SHA, output identities, and exact Repair v2 lineage.
- Read compact population, observation, terminal, and Repair auxiliary datasets;
  iterate adjusted-history by its declared `(season, week)` partitions.
- Resolve the exact `game_outcomes` refs through Repair's verified core-eligibility
  lineage and derive labels only from finalized, valid schedule rows.
- Normalize Repair auxiliary rows into the frozen recruiting, returning-
  production, coaching, and roster-continuity blocks. Enforce the admitted
  columns and use explicit carryover fallback for missing/ambiguous rows.
- Derive completed-game counts from finalized schedule history, physical-host
  and unknown-venue indicators from source schedule facts, and the scoreable
  population independently of successful joins.

**Acceptance criteria:**

- Exact counts/refs/checksums are reported; 2020, markets, polls, transfers,
  talent, R4/R5, Phase 4A, and Phase 4B inputs fail closed.
- Every forecast-eligible game remains in the population with a disposition;
  missing measurements do not silently remove games.
- Adjusted history is processed with bounded memory and each source-game row is
  associated only with a strictly later cutoff.

### Task 2 — Construct all chronological priors and pregame states

**Changes:**

- Build preceding-season team-equal center/scale per definition/role, preserving
  native values, fixed floors/fallbacks, defense reversal, and the 2019→2021 gap.
- Fit the four learned prior families separately by definition and role using
  earlier-only residual targets and inner-season alpha selection. Persist chosen
  alpha, removed constant columns, fitting/calibration seasons, variance, and
  fallback reason for every target season.
- Compute analytic exposure and half-life 2/4/8 states from shared weighted
  numerator/denominator sufficient statistics. Fit Kalman q/r on earlier seasons
  only and replay each adjusted source-game observation once, advancing through
  missing observations and byes.
- Emit states before the target game's observation. Preserve prior/evidence/
  process contributions, native/z means, positive variance, exposure, completed
  games, source refs, and named FCS/no-observation fallbacks.
- Cache only with complete parent/config/code/definition/role/prior/updater/fold
  keys. A cache mismatch or unexplained missing non-FCS state is fatal.

**Acceptance criteria:**

- All 60 candidates yield the declared state population or an explicit validity
  failure; both fixed-rho/exposure references must remain valid.
- Same-game or future perturbations cannot change a pregame state. Analytic
  states never receive Kalman process noise; Kalman cold starts use the matching
  exposure state with an explicit flag.
- No observation is assimilated twice from cumulative snapshots/history.

### Task 3 — Run the shared bridge, diagnostics, and sealed selection

**Changes:**

- Fit margin and total Ridge alpha 10 separately in each outer fold using only
  earlier seasons and the identical four role ratings plus physical-host and
  unknown-venue indicators. Fit transforms on training rows with floor 0.05.
- Produce complete target/season, 0/1/2/3/4+, early-union, asymmetric-experience,
  fallback, responsiveness, and uncertainty diagnostics.
- Apply the exact hierarchical 2,000-replicate bootstrap, overall/early
  advancement routes, 5% target-season/stage guards, equal target weighting,
  simplicity order, and PPP-preferred cross-definition comparison.
- Plan outputs as: compact `rating_registry` and `rating_attribution`; `prior`
  and `noise_fit` by season; `rating_state`, `team_state`, and
  `bridge_prediction` by season/week. Record ordered part membership and canonical
  digests without writing R2.

**Acceptance criteria:**

- Candidate-varying inputs are limited to the sealed rating design and fitted
  parameters; bridge population and policy are identical.
- Every candidate has results or an explicit validity failure, both references
  pass, and exactly one retained candidate is selected reproducibly.
- Repeating the full dry run produces identical part plans, record digests,
  metrics, and selected identity.

## Testing Strategy

- Unit tests: source/ref rejection, auxiliary normalization, predecessor scales,
  learned-prior chronology/constant fallback, exposure and recency denominators,
  Kalman q/r/cold-start/day advancement, FCS fallback, venue policy, stage counts,
  bootstrap/gates/ties, and partition-plan determinism.
- Leakage tests: perturb same-game/future outcomes, measurements, terminal rows,
  context, scales, and venue facts and assert earlier outputs are unchanged.
- Integration fixture: two definitions × six priors × five updaters over multiple
  seasons, including 2019→2021, byes, missing observations, FCS, and unknown venue;
  assert complete equal bridge populations and deterministic selection.
- Validation: focused tests with warnings as errors, full warning-as-error suite
  and configured coverage, scoped Ruff, CLI help/compile, contract validation,
  production-boundary regression, strict MkDocs, and `git diff --check`.

## Risks and Edge Cases

- The 24.2M-row adjusted history can exceed memory if concatenated or replayed
  separately for every candidate; partition streaming and shared sufficient
  statistics are mandatory.
- Candidate-specific missingness can accidentally alter the bridge population;
  preserve the schedule population and encode fallbacks/validity failures.
- Learned priors and q/r fits are nested chronological fits; persist their exact
  histories so Contract 03B and Contract 04 do not infer them from final states.
- A simple reference may win. Results cannot trigger threshold, registry, or
  population changes without a user-approved amendment.

## Definition of Done

- [ ] Exact R6/Repair/source inputs reconcile and all prohibited inputs fail closed.
- [ ] All 60 candidates have complete results or explicit validity failures; both references are valid.
- [ ] The complete bridge/diagnostic/selection result is deterministic and selects exactly one candidate.
- [ ] Full no-write preflight evidence includes ordered plans/counts/digests for every output.
- [ ] Required validation passes and the implementation log records the code checkpoint.
- [ ] The user commits the checkpoint before Contract 03B chooses a run identity.

## Amendments

Mechanical performance or observability changes may be logged here if they
preserve parents, mathematical meaning, registry, folds, gates, output schemas,
and population. Any semantic or interface change requires user-approved replanning.
