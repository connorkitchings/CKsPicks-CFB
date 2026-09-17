# V5-04A: Forecast Offsets, Bridge Registry, and Horizon Tournament

- **Status:** In Progress
- **Created:** 2026-09-17
- **Planner:** Sol planning task
- **Approval source:** User approved this execution decomposition on 2026-09-17, authorizing 04A execution.
- **Implementation log:** `session_logs/2026-09-17/02-v5-forecast-offsets-and-horizons.md`.
- **Commit policy:** Separate code checkpoint; user executes Git before any Preview run identity is selected.

## Goal

Complete Tasks 1–3 of the approved V5-04 contract: build the fixed
translation-only non-offense offsets from the certified R6 scoring ledger, fit
the bounded bridge registry (alpha-10 reference plus inner-selected challenger
per target) under both fitting horizons, and run the expanding-vs-latest-five
tournament on identical 2022–2025 games. Success is a deterministic no-write
preflight whose offset evidence, per-horizon head metrics, selected horizon and
head recipes, and complete partition plans can be reviewed before any
calibration or immutable publication (Contract 04B).

## Current State and Entry Gate

Contract 03 is Implemented. The sole eligible rating parent is the certified
Preview manifest:

- `artifacts/research/data-first-football-v1/possession-v1/ratings/runs/possession-v1-ratings-20260917-d029526-cert/retained-rating-manifest.json`
  (selected `ppp__rho_0_60__exposure`, selection `5bb2e7b6…`)

with the unchanged R6 measurement and Repair v2 parents behind it. No
forecast, calibration, or horizon code exists yet; `bridge_predictions` in
`possession_rating_tournament.py` is the 03 diagnostic reference only. The
R6 scoring ledger (`possession_scoring_event`, 78,418 rows) carries the needed
categories: `eligible_regulation_offense` (66,902), `regulation_non_offense`
(4,475), `excluded_regulation_offense` (3,221), `unresolved` (3,266),
`overtime` (554), with `period_class` regulation/overtime. The runner still
rejects `--apply`; immutable materialization remains exclusively in 04B.

## Proposed Approach

Keep I/O in a new research runner and add producer-owned forecasting code
under a new `src/cks_picks_cfb/forecast/` package. Reuse the sealed 03 replay
machinery (producer may import 03 materializer code; only the 04B verifier
must be independent) with horizon-bounded fitting inputs: learned-prior Ridge
fits, Kalman noise fits and their inner validation, bridge fits, and
calibration inputs each see only their horizon's eligible earlier seasons.
State trajectories stay continuous — no old game is dropped from replay,
preceding-season normalization is preserved, and carryover history is intact;
only fitted parameters vary by horizon. Offsets are computed once per cutoff
and are identical across heads and horizons.

The dry run performs the complete offset/bridge/horizon computation without R2
writes and records ordered partition plans, row counts, canonical digests,
head metrics, and the selected horizon in stdout JSON suitable for 04B's
evidence-bound apply. No local `./data/`, catalog, Neon, V4, or production
write is permitted.

## Scope

### Included

- Exact-parent loading with checksum/schema/consumer-role validation for the
  03 retained manifest, R6, and Repair v2 (verified at consumption time).
- Per-cutoff non-offense offset construction with league-mean prior, zero-
  offset bootstrap, and fold-blocking missing-evidence rules.
- Bounded bridge registry per horizon and target with inner-alpha selection.
- Expanding-vs-latest-five replay, paired-bootstrap comparison, and horizon
  adoption decision on identical 2022–2025 games.
- Bounded partition planning and complete no-write preflight evidence.
- Focused tests and observability for offset/bridge/horizon phases.

### Excluded

- Uncertainty calibration, 2026 refit, frozen candidate serialization, R2
  child-part or final-manifest writes, independent verification, and idempotent
  apply; Contract 04B owns them.
- Contract 05 readiness/prospective work, live 2026 replay, market inputs,
  production, Neon, catalog registration, and public serving.
- Any 03 structural reselection (definition/prior/updater/constants), registry
  expansion, possession arithmetic, EPA-to-points conversion, clock tempo,
  field-position normalization, residual ML, or additional context families.

## Affected Components and Interfaces

- New `scripts/research/run_data_first_forecasts.py` with complete source
  loading, offset/bridge/horizon computation, ordered part planning, progress
  events, and machine-readable preflight evidence. Public CLI:
  `--run-id`, `--expected-code-sha`, `--environment preview`, `--as-of`,
  `--config`, `--rating-manifest-uri`, `--measurement-manifest-uri`,
  `--repair-manifest-uri`, optional reporting-only
  `--v4-benchmark-manifest-uri`; dry-run remains the default.
- New producer code under `src/cks_picks_cfb/forecast/` (`offsets.py`,
  `heads.py`, `horizons.py`); keep 03 rating replay reuse behind a
  horizon-parameterized fitting interface. Mathematical primitives stay pure;
  runners own I/O.
- New schema contracts in `src/cks_picks_cfb/data/data_first_forecast_v1.py`
  with registered dataset names (`forecast_registry`, `forecast_model`,
  `forecast_prediction`, `forecast_calibration`, `window_comparison`,
  `forecast_selection`, `candidate_manifest`), identity/manifest schemas,
  parent validation (03 retained + R6 + Repair v2), and column contracts.
- New sealed config `conf/research/data_first_football_v1/forecast_v1.yaml`
  (Preview only): horizons, alpha grids, bootstrap settings, calibration
  inputs, `production_activation_authorized: false`.
- Dry-run stdout adds `offsets_sha256`, `head_metrics`, `selected_horizon`,
  `horizon_sha256`, `preflight_plans`, `row_counts`, `output_records_sha256`.

## Implementation Tasks

### Task 1 — Build fixed non-offense offsets (04 Task 1)

**Changes:**

- Stream R6 scoring events once; keep only `period_class == regulation` and
  `scoring_category == regulation_non_offense` rows. `unresolved`,
  `excluded_regulation_offense`, and `overtime` rows never enter offsets.
- Resolve each event's scoring team from the ledger row and the conceding team
  from the finalized schedule participants; accumulate per-team regulation
  non-offense for/against from earlier usable finalized team-games only.
- Derive the preceding eligible season's pooled league mean over valid
  team-game regulation non-offense totals with complete paired coverage.
  Smooth with four equivalent games at that mean:
  `smoothed = (sum + 4 * league_mean) / (usable_games + 4)`.
- First corpus season (2015) uses an explicitly flagged zero-offset bootstrap
  for training-only initialization. Missing required league evidence blocks
  that fold; missing team observations fall back to the declared prior.
- Offsets are fixed across fitting horizons and candidate heads for the same
  cutoff. Train heads on `target − pregame_offset`; add the same offset at
  prediction. OT and excluded offensive points stay full-game target
  components.

**Acceptance criteria:**

- Side/venue signs and offsets are independently reproduced from the ledger.
- Same-game or later ledger changes cannot alter a pregame offset.
- Non-offense never updates offense/defense ratings; offsets are
  translation-only state with explicit fallback flags.

### Task 2 — Fit the bounded bridge registry per horizon (04 Task 2)

**Changes:**

- Freeze the 03 `ppp__rho_0_60__exposure` structure, constants, and venue
  indicators. Replay chronological fitted parameters (learned priors, Kalman
  noise, bridge alphas) under each horizon's eligible earlier seasons.
- Per horizon and target (margin/total): fixed alpha-10 Ridge reference plus
  one inner-selected challenger from `{0.1, 1, 10, 100}`. Same training-only
  scaling floor 0.05 and deterministic constant-column handling as 03. Inner
  target MAE selects alpha; within 0.5% prefer larger alpha; no eligible inner
  fold means alpha 10 with an explicit fallback flag.
- Refit chosen parameters on allowed earlier history only, never validation
  rows. Retain the challenger only when valid, target MAE/CRPS ≤ 1.01× the
  horizon reference, all target season/stage regressions ≤ 5%, and ≥ 0.5%
  target MAE gain with positive paired 90% lower bound on all outer seasons.
- Keep every forecast, alpha choice, and fallback for audit. An inner alpha
  choice is a fitted parameter, not a new outer candidate.

**Acceptance criteria:**

- Invalid optimizer/output/reference or population loss blocks advancement.
- All forecast outputs are finite and share the identical scoreable schedule
  population. Head evaluation cannot change the 03 structural design.

### Task 3 — Run the horizon tournament and select the policy (04 Task 3)

**Changes:**

- Expanding horizon uses all eligible completed seasons before each fit;
  latest-five uses the latest five such seasons, excluding 2020. Fewer than
  five earlier seasons means the horizons coincide for that fit.
- Apply each policy recursively to learned-prior fits, noise fits, inner
  validation, bridge fits, and calibration inputs. Record earlier-only
  fitting-season lists for every nested prediction.
- Compare per-horizon retained heads on identical 2022–2025 games with the
  common paired bootstrap; report 2018–2019 and 2021 separately without
  relabeling them as the selection period.
- Adopt latest-five for both targets only on ≥ 0.5% equal-weight pooled
  margin/total MAE improvement with positive paired 90% lower bound, per-target
  MAE and Gaussian CRPS ≤ 1.01× expanding, and ≤ 5% target-season/stage
  regressions with no silent missing slices. Otherwise retain expanding.
  Never split horizon policy by target or reopen structural choices.

**Acceptance criteria:**

- Full/short policies differ only as declared and retain identical populations.
- Repeating the full dry run produces identical plans, digests, metrics, and
  selected horizon. An independent calculation reproduces the chosen horizon.

## Testing Strategy

- Unit tests: ledger category filtering, for/against attribution, league-mean
  pooling with paired coverage, four-game smoothing, zero-offset bootstrap,
  fold-blocking on missing league evidence, same-game invariance, 2020
  exclusion in every horizon list, horizon coincidence with < 5 seasons,
  inner-alpha histories and fallback, head retention gates, identical
  comparison populations, invalid references.
- Leakage tests: perturb same-game/future ledger rows, outcomes, terminal
  rows, and scales; assert earlier offsets, parameters, and predictions are
  unchanged.
- Integration fixture: multi-season schedule with byes, FCS, OT games,
  unresolved events, and missing context; assert complete equal populations
  across horizons and deterministic horizon selection.
- Validation: focused tests with warnings as errors, full warning-as-error
  suite and configured coverage, scoped Ruff, CLI help/compile, contract
  validation, production-boundary regression, strict MkDocs, `git diff --check`.

## Risks and Edge Cases

- The 24.2M-row R6 adjusted history plus the full 03 replay under two horizons
  is the costliest computation in the program; reuse 03's fitted-parameter
  replay inputs and stream by partition — never concatenate histories or rerun
  unchanged parents.
- Unresolved ledger events (3,266) and OT scoring must never leak into
  regulation offsets; category filtering is load-bearing and needs explicit
  negative tests.
- A shorter window may help recently without being an independent test; the
  adoption gates and the reported-but-not-selected earlier years guard this.
- The simple alpha-10 bridge may remain best under both horizons; results
  cannot trigger registry, threshold, or population changes without a
  user-approved amendment.

## Definition of Done

- [ ] Exact 03/R6/Repair parents reconcile and all prohibited inputs fail closed.
- [ ] Offsets, both horizon registries, and the window comparison are complete and deterministic.
- [ ] Exactly one horizon policy and one head recipe per target are selected reproducibly.
- [ ] Full no-write preflight evidence includes ordered plans/counts/digests for every output.
- [ ] Required validation passes and the implementation log records the code checkpoint.
- [ ] The user commits the checkpoint before Contract 04B chooses a run identity.

## Amendments

Mechanical performance or observability changes may be logged here if they
preserve parents, mathematical meaning, registry, folds, gates, output schemas,
and population. Any semantic or interface change requires user-approved replanning.
