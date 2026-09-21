# V5-04: Forecast Bridge, Fitting Window, and Candidate Freeze

- **Status:** Implemented
- **Created:** 2026-09-13
- **Planner:** Codex planning task
- **Approval source:** User selected bridge-first forecasting, a bounded older-data comparison, optional later arithmetic, and approved the package with "Implement the proposed plan." on 2026-09-13.
- **Implementation log:** `session_logs/2026-09-17/04-v5-04a-hardening-and-preflight.md`, `session_logs/2026-09-17/07-v5-04b-calibration-and-certification.md`, `session_logs/2026-09-17/08-v5-04b-certification-execution.md`.
- **Commit policy:** Separate code and frozen-evidence checkpoints; user executes Git.
- **Resolution (2026-09-21):** Returned to Implemented via umbrella Contract 11 (`docs/plans/2026-09-18/11-v5-forecast-verification-closure.md`), closed through the 11B/11C/11D decomposition on the r9 descendant line. The September 13/17 artifacts remain frozen historical evidence.

## Goal, current state, and entry gate

Freeze one reproducible possession-rating candidate with margin and total means,
non-null calibrated uncertainty, a declared fitting-history policy, and exact
live update rules. Require independently verified parents from
[02](02-v5-possession-measurement-certification.md) and
[03](03-v5-possession-rating-estimation.md). The
[common contract](v5-ratings-successor-roadmap-and-contracts.md) is binding.

Contract 03 selects the structural rating definition/prior/updater on development
history. Do not reselect those choices while testing windows or heads. No current
possession candidate is assumed to exist. Historical NB2 or Phase 4B manifests
cannot substitute for these parents.

## Approach, scope, and interfaces

Keep the small rating-to-target Ridge family. Add a fixed prior-only non-offense
translation offset, chronological uncertainty calibration, and exactly two
parameter-fitting horizons. No possession arithmetic, EPA-to-points formula,
clock tempo, field-position normalization, NB2, residual ML, or additional
context family is in this registry. Volume and scoring-ledger summaries prepare
future challenger research without blocking this bridge release.

Implement possession-specific forecasting/calibration code and schemas alongside
the new ratings modules, research runner/verifier/config, and focused tests.
Parent flags: `--rating-manifest-uri`, `--measurement-manifest-uri`, and
`--repair-manifest-uri`; optional `--v4-benchmark-manifest-uri` is reporting-only.
Stage: `forecasts`. Standard dry-run/apply/manifest constraints apply. No serving
interfaces, DB migrations, catalog registration, or production model changes.

## Implementation tasks

### Task 1 — Freeze target, venue, and non-offense offset semantics

Use target labels `margin = home_points - away_points` and
`total = home_points + away_points`, including overtime and all valid final
scoring. These are forecast targets, not bookmaker lines; document any consumer
spread-sign conversion. Inputs are four role ratings plus the identical
physical-host/unknown-venue indicators from 03. No same-game measurements or
future terminal states are inputs.

Build a separate non-offense expectation from the certified regulation
non-offense ledger. For each team, score-for and score-against means at a cutoff
use only earlier usable finalized team-game observations in that season, with
four equivalent games at the preceding eligible season's league mean:

```text
smoothed_for = (sum_prior_nonoffense_for + 4 * prior_league_mean) / (usable_games + 4)
smoothed_against = (sum_prior_nonoffense_against + 4 * prior_league_mean) / (usable_games + 4)
offset_home = (smoothed_home_for + smoothed_away_against) / 2
offset_away = (smoothed_away_for + smoothed_home_against) / 2
offset_margin = offset_home - offset_away
offset_total = offset_home + offset_away
```

Derive the league mean by pooling valid team-game regulation non-offense totals
over that preceding season, preserving complete paired coverage. Empty current
history uses the preceding league mean. The first corpus season has no earlier
league mean; use an explicitly flagged zero-offset bootstrap for training-only
initialization, not a claim that non-offense scoring was observed to be zero.
Subsequent missing required league evidence blocks that fold rather than using a
future mean. Missing team observations use the declared prior; count only usable
ledger games in the numerator and denominator. OT and excluded offensive points
remain full-game target components, not non-offense offsets.

Train heads on `target - pregame_offset` and add the same pregame offset at
prediction. Do not subtract realized same-game non-offense points as though
known before kickoff. Offsets are identical across candidate heads for the same
cutoff, and their rule is fixed across fitting horizons.

**Acceptance:** Side/venue signs and offsets are independently reproduced.
Same-game or later ledger changes cannot affect a pregame offset. Non-offense
is a translation-only state; it never updates offense/defense ratings.

### Task 2 — Fit the bounded bridge registry chronologically

Per fitting horizon, use a fixed alpha-10 Ridge reference and an inner-selected
Ridge challenger from `{0.1,1,10,100}` separately for margin/total. Use the same
training-only scaling floor 0.05 and deterministic constant-column handling as
03. Inner target MAE selects alpha; within 0.5% prefer larger alpha. No eligible
inner fold means alpha 10 with an explicit fallback. All inner/outer fits precede
their evaluated season. Refit the chosen parameters on the allowed earlier
history, never validation rows.

Within a horizon, retain the inner-selected-alpha challenger only when it is
valid, target MAE/CRPS <=1.01 times that horizon's alpha-10 reference, all target
season/stage MAE regression guards <=5%, and it establishes >=0.5% target MAE gain
with a positive paired 90% lower bound on all outer seasons. Otherwise retain
alpha 10. An alpha choice selected inside a fold is a fitted parameter, not a
new outer candidate. Keep all forecasts/choices for audit.

**Acceptance:** Invalid optimizer/output/reference or population loss blocks
advancement appropriately. All forecast outputs are finite and share the same
scoreable schedule population. Head evaluation cannot change the 03 structural
design.

### Task 3 — Compare expanding and latest-five fitting horizons

Expanding uses all eligible completed seasons before each fit. Latest-five uses
the latest five such seasons, excluding 2020. Apply the policy recursively to
learned prior/noise fits, their inner validation, bridge fits, and calibration.
If fewer than five earlier seasons exist, the two horizons coincide. Preserve
continuous team-state and carryover history and preceding-season normalization;
do not drop old games from the actual state trajectory or pretend a team began
existing at the fitting-window boundary.

Freeze the 03 definition/prior/updater structure and constants. Replay its
chronological fitted parameters under each horizon, retaining all alpha/noise
and fallback histories. Compare the resulting per-horizon retained heads on
identical 2022–2025 games, with the common paired bootstrap. Earlier years remain
reported, including 2018–2019 and the 2021 transition; they are not relabeled as
the recent-window selection period.

Adopt latest-five as one shared policy for both targets only when:

- Equal-weight pooled margin/total MAE improves >=0.5% on 2022–2025 with a
  positive paired 90% lower bound.
- Each target's MAE and Gaussian CRPS are <=1.01 times expanding history on
  that paired period.
- Each target-season and pooled completed-game-stage MAE regression is <=5%
  relative to expanding history; missing required slices cannot pass silently.

Otherwise retain expanding history. Never select separate rating-history policies
for margin and total or reopen structural choices after seeing the window result.
Report this as bounded development evidence on the already-used corpus.

**Acceptance:** Earlier-only parameter-fitting season lists are recorded for
every nested prediction. Full/short policies differ only as declared and retain
identical populations. Independent calculation reproduces the chosen horizon.

### Task 4 — Calibrate uncertainty and freeze serializable forecasts

For each outer season and candidate, generate earlier nested rolling-origin
prediction residuals using the same structural design, horizon, offset rule,
and inner-alpha procedure. Require at least one eligible prior residual season
for uncertainty; no current validation residual or in-sample training error may
substitute. The first eligible residual season is 2017 after two prior fitting
seasons, allowing calibration for outer 2018.

Target variance is the mean squared prior prediction error, floor `1e-6`.
No extra bias correction or second calibration of the same residuals. Keep
posterior rating variance as attribution, not an additional term added to this
empirical outcome variance. Emit explicitly labeled Gaussian marginal target
distributions with analytical CRPS and central 50/80/95% intervals. Independently
fitted margin/total heads do not claim a coherent joint team-score distribution.

Report MAE, RMSE, bias, CRPS, coverage, width, residual counts, season/stage/FCS
coverage, floors/fallbacks, non-offense offsets, and scoring-ledger/possession-volume
diagnostics. Only report V4 comparisons where its predictions have verified,
comparable cutoff and training lineage. Do not extend the V4 evaluation history
to all expanded seasons by running an already trained future model. V4 lacks
non-null uncertainty today; mark unavailable V4 CRPS/calibration as unavailable,
not zero or a reason to fabricate variance.

Freeze the selected design/horizon and target-alpha fitting recipes, then refit
unchanged on eligible history through 2025 for the 2026 candidate. Preseason
priors, noise, heads, alpha choices and calibration remain fixed during the live
season. Only declared prior-game state and offset updates are allowed. Future
source availability is a separate readiness gate in 05; historical admission
does not make the refit live-ready.

**Acceptance:** Complete serialized parameters reproduce means/variances and
intervals from exact states, and calibration chronology is independently verified.

### Task 5 — Publish a verified candidate handoff

Output `forecast_registry`, `forecast_model`, `forecast_prediction`,
`forecast_calibration`, `window_comparison`, `forecast_selection`, and
`candidate_manifest` records. Predictions bind target, mean/variance, intervals,
distribution label, offset, model/state/source refs, cutoff, horizon, quality and
fallback. Manifest pins both target models, rating design, constants, fitting
season lists, calibration residual refs, source policy, allowed updates, and
activation=false.

The verifier independently reconstructs inputs/offsets, nested fits, predictions,
bootstrap selection, uncertainty, and serializable round trips. Preserve full and
short history evidence even when the simpler reference wins. Verify immutable
apply and idempotent rerun before 05 consumes the candidate.

## Testing strategy

Common computational gates plus window-membership tests (including 2020 exclusion),
nested residual chronology, variable inner-alpha histories, zero-history offset,
missing team/league evidence, source-score accounting, venue/side signs, variance
and Gaussian CRPS/intervals, identical comparison populations, invalid references,
unavailable historical V4 coverage, and model serialization. Same-game/future
perturbations must cover every offset, parameter and calibration path.

## Risks, definition of done, and amendments

A shorter window may help recently without being a new independent test. The
simple bridge may remain best. Do not add arithmetic/NB2/context experiments to
rescue a failed candidate or tune intervals on protected 2026 outcomes.

- [x] Forecast registry and both fitting horizons evaluated as declared.
- [x] Candidate parameters, uncertainty, source policy and update recipe frozen.
- [x] Independent verifier and idempotent Preview apply pass.
- [x] Required checks, report, docs, plan status and implementation log complete.

Use the common amendment process. This freeze establishes a research candidate,
not a qualifying prospective slate or authority to activate production.

## Execution decomposition (2026-09-17)

The remaining implementation is split into two dependency-ordered contracts
without changing this umbrella contract's architecture, interfaces, registry,
mathematics, gates, or definition of done:

1. [V5-04A: offsets, bridge, and horizons](../2026-09-17/01-v5-forecast-offsets-bridge-and-horizons.md)
   completes exact-parent loading, fixed non-offense offsets, the bounded
   bridge registry under both horizons, the window tournament, and
   deterministic no-write preflight evidence.
2. [V5-04B: calibration and certification](../2026-09-17/02-v5-forecast-calibration-and-certification.md)
   performs uncertainty calibration, candidate freeze and serialization,
   evidence-bound immutable materialization, independent reconstruction,
   idempotency, and final Contract 05 eligibility.

Both were Draft pending this decomposition's approval. The user approved the
decomposition on 2026-09-17, authorizing 04A execution; 04B remains Draft
until 04A has a clean committed SHA and reviewed deterministic preflight
evidence. V5-04 remains Approved and is not complete until 04B certifies.

**04A closure (2026-09-17):** 04A is Implemented with a reviewed,
deterministic, byte-equivalent no-write Preview preflight
(`forecast-v1-20260917-19ca44b-04a`; selected shared `expanding` horizon,
alpha-10 reference head on both targets; equal 3,659-game populations).
04B is rebased onto the implemented 04A interfaces and remains Draft
pending a separate explicit user approval.

## Historical-first correction (2026-09-18)

04A remains implemented and its historical preflight record is retained. The
umbrella is reopened as **In Progress** because 04B's implemented verifier does
not yet meet this contract's required independent reconstruction standard. It
checks the forecast manifest and labels/references, but does not reconstruct the
stored offsets, feature frames, bridge fits, calibration, horizon selection, or
forecast records. The artifact remains inspectable historical evidence and
`production_activation_authorized: false`; it is not an eligible forecast parent
for downstream readiness or prospective collection.

Contract [11](../2026-09-18/11-v5-forecast-verification-closure.md) must close
the computational-verification gap after the full [10](../2026-09-18/10-v5-historical-foundation-audit.md).
Only then may this umbrella return to `Implemented`. This correction preserves
the September 17 record rather than changing it retroactively.
