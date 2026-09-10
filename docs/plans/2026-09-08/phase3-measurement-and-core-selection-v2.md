# Phase 3: Corrected Measurements and Core Selection v2

- **Status:** Superseded
- **Created:** 2026-09-08
- **Last amended:** 2026-09-09
- **Planner:** Astra
- **Approval source:** User approved the expanded execution contract and selected the reconstructed-history six-hour availability buffer on 2026-09-09.
- **Implementation log:** `session_logs/2026-09-09/03-phase3-v2-implementation.md`
- **Superseded by:** `docs/plans/2026-09-09/phase3-measurement-and-core-selection-v2.md` — the streaming replacement retains this contract's modeling decisions while replacing its unsafe materialization design.
- **Commit policy:** User creates a clean, committed checkpoint before Preview execution; user executes all Git operations.

## Goal

Repeat the sealed Phase 3 core-measurement selection against Repair v2's complete
historical population, with replayable pregame state and auditable opponent
adjustments. The outputs must be sufficient input evidence for a separate Phase
4A v2 rating-selection task, without fitting auxiliary priors, selecting game
context, producing live forecasts, or changing production.

Observable success means that the independently verified result contains every
eligible game in the repaired population, applies a leakage-safe historical
cutoff to every pregame value, evaluates the unchanged candidate registry on the
same complete validation population, and either retains one eligible core or
stops with a documented gate failure.

## Current State and Binding Inputs

Repair v2 is the only modeling parent. The implementation accepts its manifest
through `--repair-manifest-uri`, validates its raw-object and canonical checksum
before decoding, and resolves its embedded Phase 2d and Phase 2e references.
The exact verified Repair manifest is:

```text
artifacts/research/data-first-football-v1/repair/v2/runs/
repair-v2-20260909T1417Z/repair-manifest.json
raw SHA-256: b55af0dd7952a4b5e0d663b82182b351ec5496a292246a934a857c354058e0b4
canonical manifest_sha256: 2fefcb95a2e8b4ae27e8fb2bf740328413aa576bcd725ebd9a18378edd50ac48
```

Repair establishes 8,936 scheduled keys across 2015–2019 and 2021–2025; 8,935
are completed, outcome-valid, and forecast-eligible; 8,903 have usable
measurements. The other 32 completed games remain forecast-eligible despite
missing measurement evidence. Incomplete game `401640992` remains in the
population but is forecast-ineligible. 2020 is forbidden everywhere.

The old Phase 3 v1 retained-core manifest is diagnostic comparison evidence
only. It cannot be a v2 feature, training, selection, or rating parent. Its
reduced-population EPA-only result is not a v2 result. V4, Neon, web serving,
production predictions, and Phase 4–6 execution are out of scope.

The common requirements in
`docs/plans/2026-09-08/transformation-review-and-authority-reset.md` apply,
including Preview-only operation, immutable R2 artifacts, exact lineage checks,
the 2,000-replicate paired bootstrap, and no production activation.

## Chosen Historical Availability Policy

Phase 2 historical evidence is reconstructed and lacks trustworthy completed-at
timestamps. Phase 3 v2 therefore records a reconstructed, diagnostic-only
availability classification; it must never claim authentic pregame availability.
For a target `(season, canonical_week)`, admit a source game only when both:

1. its canonical week precedes the target canonical week; and
2. `source_kickoff_utc + 6 hours <= earliest eligible target kickoff_utc` for
   that target week.

The cutoff is the target week's earliest eligible kickoff, not the target game's
individual kickoff. Equality is permitted. The policy, target cutoff, source
kickoff, calculated availability timestamp, and `historically_reconstructed`
timing classification are persisted on every applicable output. A source never
enters the same week, even if its game began much earlier. Live Phase 6 will use
its actual freeze timestamp in a separate contract.

## Scope

### Included

- Versioned Phase 3 v2 reconstruction, tournament, publication, and independent
  verification code.
- Canonical schemas, sealed configuration, focused fixtures, and tests.
- Postgame observations, pregame snapshots, replayable adjusted history,
  terminal state, complete-population candidate predictions, attribution,
  certification, and a retained-core manifest.
- Preview dry run, Preview materialization, independent verification, and
  deterministic rerun after a user-created committed checkpoint.

### Excluded

- Changes to Phase 3 v1, V4, production artifacts, Neon, web interfaces, or
  prediction publication.
- Auxiliary-prior fitting or use, Phase 4A ratings, Phase 4B context, Phase 5
  modeling, Phase 6 operations, betting decisions, and promotion review.
- Recapturing missing play data or altering Repair v2's 33-game ledger.
- Any new candidate, component-weight, threshold, hyperparameter, or grid
  search after results are known.

## Affected Components and Contracts

- New `src/cks_picks_cfb/data/data_first_phase3_v2.py`: repair-parent
  validation, population completion, observation/snapshot/history/terminal
  builders, coverage and lineage validation.
- New `src/cks_picks_cfb/ratings/phase3_v2.py`: four-pass adjustments,
  cutoff-specific state construction, fold preparation, candidate evaluation,
  shared bootstrap, and deterministic selection.
- New `scripts/research/run_data_first_phase3_v2.py` and
  `scripts/research/verify_data_first_phase3_v2.py`.
- New `conf/research/data_first_football_v1/phase3_measurement_core_v2.yaml`.
- `src/cks_picks_cfb/data/schema_contracts.py` and matching schema/contract
  tests for the `data_first_phase3_*_v2` interfaces.
- New focused test module `tests/test_data_first_phase3_v2.py`; v1 tests and
  behavior remain untouched.
- This contract, the roadmap's status reference, and the implementation session
  log once work is complete.

## Interface Contract

Artifacts are written only under:

```text
artifacts/research/data-first-football-v1/phase3/v2/runs/<run-id>/
```

All artifacts bind the Repair manifest URI and both checksums, resolved source
DatasetRefs and checksums, code/config identities, timing policy, as-of time,
and `environment=preview`. The runner takes:

```text
--repair-manifest-uri
--run-id
--expected-code-sha
--environment preview
--as-of
--config
[--apply]
```

Dry run is the default and writes nothing. `--apply` requires Preview R2 and
catalog credentials, a clean tracked worktree, a committed SHA matching
`--expected-code-sha`, an exact verified Repair parent, and no unapproved input
substitution.

| Interface | Identity and required contents |
| --- | --- |
| `data_first_phase3_population_v2` | One row per Repair schedule key `(season, game_id)`; eligibility, valid outcome, measurement availability, omission reason, canonical week, and outer-fold role. Exactly 8,936 rows. |
| `data_first_phase3_observation_v2` | Postgame raw football measurements. Every eligible game has its full team/role/measurement grid; missing measurements are null, zero-exposure, and reasoned rather than omitted. |
| `data_first_phase3_pregame_snapshot_v2` | One target-cutoff/team/role/measurement/recency/iteration state record, retaining raw context metrics and adjustment state through iterations 0 and 4. |
| `data_first_phase3_adjusted_history_v2` | One cutoff/source-game/team/role/core-measurement/recency record with raw value, exposure, iteration-three opponent reference, correction, iterations 0/4 values, inclusion, and reason. |
| `data_first_phase3_terminal_v2` | One terminal team-season/role/measurement/recency state with the complete aggregates and provenance needed by Phase 4A v2. |
| `data_first_phase3_prediction_v2` | Unique game/candidate/recency/target prediction, fold identity, trained-only lineage, fallback reason, actual label, and error. |
| `data_first_phase3_attribution_v2` | Candidate-level full metric, fold, gate, common-bootstrap, and selection evidence. |
| `data_first_phase3_certification_v2` | Signed JSON binding inputs, policy, population and output counts/hashes, validation results, and explicit Preview-only status. |
| `data_first_phase3_retained_core_v2` | Signed JSON identifying selected core, components, scaffolds, artifact refs, parent lineage, and `production_activation_authorized=false`. |

All tabular keys are unique and schema-validated. The certification and retained
core documents are not equivalent to production authorization.

## Implementation Tasks

### Task 1 — Seal parent admission and the complete population

**Files:**

- `src/cks_picks_cfb/data/data_first_phase3_v2.py`
- `scripts/research/run_data_first_phase3_v2.py`
- `scripts/research/verify_data_first_phase3_v2.py`
- `conf/research/data_first_football_v1/phase3_measurement_core_v2.yaml`

**Changes:**

- Load Repair only after raw-byte and canonical checksum verification; reject
  wrong stage, role, schema, season set, timing classification, code identity,
  output keys, or population reconciliation.
- Materialize the Phase 3 population directly from Repair's schedule population,
  never by inner joining observations. Include every schedule row, preserve the
  32 measurement-missing completed games and their exact reasons, and exclude
  the incomplete game from forecast eligibility only.
- Assign outer validation seasons 2018, 2019, and 2021–2025. The complete
  evaluation population is 6,318 eligible games (6,314 usable plus four
  measurement-missing games).
- Reject 2020, duplicate keys, modified parent bytes, parent substitutions, or
  a population not exactly reconciling to Repair.

**Acceptance criteria:**

- Population has exactly 8,936 schedule rows, 8,935 eligible rows, and 8,903
  measurement-usable rows.
- No incomplete or measurement-missing record silently disappears.

### Task 2 — Build postgame observations and leakage-safe pregame state

**Files:**

- `src/cks_picks_cfb/data/data_first_phase3_v2.py`
- `src/cks_picks_cfb/ratings/phase3_v2.py`

**Changes:**

- Reuse only the definition-fixed v1 measurement primitives for EPA/PPA,
  success, 20-yard explosiveness, true scoring-opportunity efficiency, field
  position, plays per drive, turnover, and pass/rush measurements. Do not alter
  their semantics while implementing v2.
- Build raw observations from the 8,903 usable games and left-complete the full
  eligible grid. Missing games receive null values, zero usable exposure, and
  an explicit source/measurement reason; no outcomes, scores, or measurements
  are imputed.
- Construct snapshots using the chosen six-hour weekly cutoff policy. Store
  source evidence timing and why each source is admitted or excluded.
- Run exactly four league-centered additive opponent-adjustment iterations.
  Store per-source values using the iteration-three opponent correction, and
  prove exposure-weighted source history reproduces the iteration-four aggregate.
  Keep missing-opponent treatment identical between source and aggregate forms.
- Persist all 17 team-role measurement combinations in snapshots for downstream
  pregame context work. Persist adjusted history only for the six core adjusted
  measurements—`epa_per_play`, `success_rate`, `explosive_rate_20`,
  `points_per_scoring_opportunity`, `epa_pass`, and `epa_rush`—because raw
  snapshots preserve the remaining context measures. This limits history to
  6,777,120 rows rather than duplicating all context metrics.

**Acceptance criteria:**

- 303,790 raw observation rows (8,935 eligible games × 34 observation rows).
- 1,215,160 pregame snapshots (17 combinations × two recency modes × iterations
  0/4) and 6,777,120 core adjusted-history rows under the sealed fixture.
- Same-week, later-week, and late-rescheduled source observations cannot appear
  in a target week state. Equality at the six-hour boundary is admitted.

### Task 3 — Produce terminal state and repeat the frozen tournament

**Files:**

- `src/cks_picks_cfb/ratings/phase3_v2.py`
- `src/cks_picks_cfb/data/data_first_phase3_v2.py`
- `conf/research/data_first_football_v1/phase3_measurement_core_v2.yaml`

**Changes:**

- Create terminal state for all 1,310 team-season keys, each applicable
  measurement-role combination, and both recency modes. Preserve the two-year
  chronology gap (2019 never flows into 2021) and fixed missing/FCS fallbacks.
- Evaluate exactly the unchanged registry: `epa_only`, `quality_core_equal`,
  four named leave-one-outs, `epa_pass_rush`, and
  `quality_core_epa_split`. Use the sealed component directions, weighting,
  annual rho 0.60, exposure updater, fold-local Ridge alpha 10, train-only
  standardization, and fixed recency-half-life-4 sensitivity.
- For a missing eligible game's pregame state, use only fold-local role means
  and maximum uncertainty, record the fallback, and keep the game in every
  candidate comparison. Never derive an imputation from its outcome or future
  state.
- Produce exactly 202,176 prediction rows: 6,318 games × eight candidates × two
  recency modes × margin/total targets.
- Generate one deterministic common bootstrap resample plan for all candidates:
  2,000 draws, seed `20260908`, season then week blocks, paired game targets
  together. Calculate baseline-minus-challenger absolute-error intervals from
  that common plan; do not seed by candidate.
- Retain a challenger only if it meets all frozen gates: at least 0.5% primary
  pooled improvement versus EPA-only, 90% paired lower bound above zero, equal
  population, no target-season MAE regression over 5%, and no sensitivity
  regression over 0.5% against its own EPA-only reference. Among eligible
  candidates within 0.5% of the best MAE, select fewest components then lexical
  ID. If none passes, retain valid EPA-only.

**Acceptance criteria:**

- Every candidate and target has the same complete 6,318-game validation
  population.
- Selection is reproducible bit-for-bit and makes no post-result registry or
  threshold expansion.

### Task 4 — Publish immutable Preview evidence and independently verify it

**Files:**

- `scripts/research/run_data_first_phase3_v2.py`
- `scripts/research/verify_data_first_phase3_v2.py`
- `src/cks_picks_cfb/data/schema_contracts.py`

**Changes:**

- Publish only after all pre-write gates pass. Bind output DatasetRefs/counts,
  parent identity, cutoff policy, population digest, candidate registry,
  fallback counts, bootstrap digest, selected core, and explicit diagnostic
  timing/consumer roles in the two signed JSON artifacts.
- The verifier rereads raw parent and Bronze bytes, validates checksums before
  decoding, reconstructs the population, observations, cutoff state, adjustment
  aggregates, predictions, metrics, bootstrap plan, and selection without
  trusting stored flags or selected IDs.
- Make reruns idempotent: identical inputs/config/code/run id yield the same
  hashes or a collision error; a different run id can produce equivalent,
  separately identified artifacts.

**Acceptance criteria:**

- Verified artifacts are Preview-only and contain no production activation,
  model-promotion, Neon, or web-serving role.
- Independent verification and deterministic rerun agree on all counts, hashes,
  metrics, common-resample digest, and retained-core decision.

## Testing and Validation

Unit and fixture coverage must include:

- Parent role/checksum/schema/provenance/season rejection; raw-byte corruption;
  Repair-parent substitution; and forbidden 2020 data.
- Exact 8,936/8,935/8,903 reconciliation, the 32 completed missing-measurement
  grid, incomplete `401640992`, duplicate keys, and no outcome/measurement
  imputation.
- Measurement-definition compatibility, pass/rush accounting, score stream,
  symmetric offense/defense treatment, missing/FCS fallback, and two-year-gap
  handling.
- Six-hour cutoff behavior before, at, and after boundary; same/future-week and
  same-game perturbation invariance; reconstructed-only timing labels.
- Iteration-four reconstruction from adjusted source history, including missing
  opponents and exposure denominators; raw snapshot retention for later Phase
  4B work.
- Complete 6,318-game candidate population and exact 202,176 prediction rows;
  train-only standardization; fold-local fallback; candidate gates and EPA-only
  fallback.
- Identical common 2,000-draw bootstrap plans across candidates, paired targets,
  determinism, and verifier recomputation.
- Publication idempotency, schema uniqueness, prohibition on touching V4 or
  production state, and full independent reconstruction.

Required local gates are focused and full warning-as-error pytest, coverage,
Ruff format check/lint, schema/contract synchronization, V4 and boundary
regressions, strict MkDocs, CLI help checks, and `git diff --check`. The exact
commands and thresholds are set in the implementation configuration and must be
recorded in its session log.

## Rollout and Handoff

1. Implement only the versioned code, schemas, configuration, tests, and docs;
   preserve `.opencode/` and unrelated user changes.
2. Complete local validation and update the Phase 3 v2 implementation log.
3. Ask the user to make the required clean committed code checkpoint.
4. Run Preview dry run. Review exact population, omission preservation, cutoff
   counts, source exclusions, fallback counts, and output plan before writing.
5. Run Preview apply, then the independent verifier and a deterministic rerun.
6. Record final artifact identities and update this plan to `Implemented` only
   when every core admission and verification gate passes.
7. Hand the verified retained-core manifest to a separate Phase 4A v2 planning
   or implementation task. Do not start Phase 4A from this task.

## Risks and Stop Conditions

- A Repair parent whose checksums, population, timing, or consumer roles do not
  match this contract blocks execution.
- Missing measurements cannot justify shrinking the schedule/outcome population.
- A semantic defect in a frozen measurement definition, adjustment rule, or
  candidate registry requires an explicit amendment; do not silently fix or
  broaden it during this run.
- If terminal state cannot represent the required complete keys, the shared
  bootstrap differs across candidates, a cutoff admits future/same-week data,
  or independent reconstruction differs, stop before Phase 4A.
- Artifact scale is material; implementations must stream/chunk deterministically
  and must not use a repository-local data directory.

## Definition of Done

- [ ] All versioned Phase 3 v2 code, schema contracts, config, fixtures, and
  tests are implemented without modifying v1 behavior.
- [ ] The complete repaired population, leakage-safe state, frozen tournament,
  and Preview-only artifacts satisfy every acceptance count and key constraint.
- [ ] Independent verification and deterministic rerun pass.
- [ ] Required local and Preview validation is recorded in the implementation log.
- [ ] Final immutable artifacts and retained-core decision are recorded here.
- [ ] This plan is updated to `Implemented`; no Phase 4A or production change is
  included.

## Amendments

### Amendment 1 — Reconstructed availability policy

**Reason:** The approved 2026-09-08 contract required verified availability
before each weekly cutoff, but Repair's historically reconstructed captures do
not supply trustworthy game-completion timestamps.

**Original approach:** Require an unspecified verified availability timestamp.

**Revised approach:** For historical diagnostic replay, use the selected six-hour
buffer after a source kickoff and before the next target week's earliest eligible
kickoff. Persist this as reconstructed-only, not authentic pregame availability.

**Impact:** The precise rule makes historical state deterministic and testable
without backdating evidence. It applies only to Phase 3 v2 historical research;
live freeze semantics remain a later Phase 6 concern.
