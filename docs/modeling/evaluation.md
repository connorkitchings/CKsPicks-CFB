# Evaluation Policy

> **Authority note (2026-09-05):** V4 and existing frozen experiments retain
> the policies below. New work under `data-first-football-v1` uses 2015-2019 and
> 2021-2025 as development data and relies on future pre-kickoff freezes for
> independent evidence. See the
> [data-first roadmap](../planning/data-first-football-forecasting-roadmap.md).
> Timestamped lines are comparison evidence after football evaluation; betting
> decisions are outside the current program.

> **Status:** V4 evaluation authority and the protected 2026 policy for the
> approved rating-centric successor.

## Current V5 evaluation contract (2026-09-13)

The [V5 common contract](../plans/2026-09-13/v5-ratings-successor-roadmap-and-contracts.md)
and 02–06 govern current research. V5 ratings successor is distinct from V4
feature schema v5. Repair v2 is verified and Phase 3 v2 is certified. The
possession methodology is specified and amended; possession measurements remain
uncertified. The next ratings task is 02: possession measurement certification;
the [data-first roadmap](../planning/data-first-football-forecasting-roadmap.md)
is the status authority. The original Phase 4B retained manifest remains
prohibited as a forecasting parent. Old reduced-population comparisons retain
historical limits; the September 8 Phase 4A–6 runners are Superseded.

Use complete schedule-derived populations, 2015–2019 and 2021–2025 development
history, and outer seasons 2018, 2019, 2021–2025. Exclude 2020 everywhere and 2026
outcomes from development selection. Inner validation starts in 2017 with at least
two earlier fitting seasons. Every fitted transform, prior, noise parameter, head
and calibration precedes its validation season. Fixed first-generation floor/
fallback and exposure constants are not fit globally on 2015–2019.

Contract 03 evaluates both definitions across six priors and five updaters with
identical alpha-10 Ridge bridges. Within-definition reference is fixed-rho/exposure.
A challenger advances on >=0.5% pooled overall improvement with positive paired
90% lower bound, or the same early-union gain with full-season MAE within 1%.
Require <=5% target-season and pooled completed-game-stage regressions. Invalid
references block advancement; valid simple references may win. Compare the retained
EPA and PPP winners under the same rules, preferring PPP without an admissible
EPA gain. Use 2,000 paired season/week bootstrap replicates, seed 20260908,
common resamples and 5th/95th percentiles. These are development comparisons.

The first forecast release is **bridge-first**. Contract 04 uses fixed pregame
non-offense offsets and bounded Ridge head selection. Full-game labels include
OT and excluded offensive scoring; neither becomes a same-game predictor.
After freezing the structural rating design, compare expanding fitting history
with the latest five eligible seasons at each nested fit on identical 2022–2025
games. Preserve continuous team-state history. Latest-five requires >=0.5% pooled
MAE gain with a positive paired lower bound, each target MAE/CRPS within 1%, and
<=5% season/stage regression. Otherwise retain expanding history. Report earlier
and recent eras separately. No head/window gain establishes independent evidence.

Outcome variance is mean squared earlier nested rolling-origin prediction error
(floor `1e-6`), requiring an eligible prior residual season. Rating posterior
variance is reported separately and is not added again. Use Gaussian marginal
target distributions, analytical CRPS and 50/80/95% intervals. No current-validation
or training-fit residuals may calibrate uncertainty; no second calibration or
mean-bias correction is in this registry. Separate margin/total heads do not
claim a coherent joint team-score distribution. NB2/arithmetic are later challengers.

Prospective evidence requires six qualifying normal-coverage paired slates,
>=40 games, T−2h target/T−1h hard measured freeze, and >=24h after the last included
game's completion for scoring. Week 0 and historical replays do not count. Contract
05 separates tooling completion from authentic live readiness; 06 collects evidence.
Prespecified prior-week state/offset updates do not reset the window; changes to
design/fitting/calibration/source semantics do. Preseason/noise/head/calibration
parameters stay fixed during the prospective season. Markets are comparison-only
after football evaluation; promotion requires a separate contract.

## Ordered evaluation layers

Later evidence cannot rescue a failure at an earlier layer.

1. **Rating quality:** point-in-time correctness, stable meaning, plausible
   responsiveness, uncertainty behavior, measurement attribution, and lineage.
2. **Prediction quality:** margin/total or score accuracy, bias, season and
   early/late stability, paired comparison against V4, and probabilistic
   calibration when distributions are emitted.
3. **Market comparison:** only after football-model quality succeeds, join
   authentic timestamped lines to compare forecast and market margin/total
   errors, cutoff disagreement, and closing information separately.

Market prices and untimestamped legacy quotes are never ratings or
football-prediction inputs and cannot choose a candidate. Betting selection,
staking, bankroll outcomes, and threshold optimization are deferred.

## V4 benchmark

V4 selected its ten routes with sealed 2022–2024 temporal OOF evidence, a
frozen design, one locked-2025 anti-regression evaluation, and an unchanged
2021–2025 refit. Its established metrics include MAE, RMSE, bias, sample count,
paired bootstrap intervals, and season-level results. It remains the production
champion and direct comparator. Historical paired reporting requires valid V4
training/cutoff lineage on the same games; do not imply clean V4 predictions for
every expanded-history season. V4 uncertainty is currently unavailable; mark its
missing CRPS/calibration as unavailable rather than invent variance.

## Protected prospective 2026 policy

The successor-v2 research corpus is 2015–2019 and 2021–2025; 2020 is excluded
from every input, label, prior, and fold. This is historical development and
temporal-validation evidence, not an untouched test set. Candidate v1 remains
an O2 diagnostic baseline; the V5 ratings successor receives a new prospective lane. For
every 2026 candidate:

1. Record immutable candidate identity, code/config lineage, training cutoff,
   data versions, and eligible outcome window before that window is observed.
2. Freeze candidate predictions before the first kickoff in each eligible
   slate.
3. Do not modify a candidate using outcomes that it then claims as protected
   evidence. A revision receives a new identity and later untouched window.
4. Keep all shadow artifacts outside V4 bundles, Neon activation, public
   publication, and weekly rollback authority.
5. Retain candidate and V4 outputs for the identical game set and information
   cutoff to allow paired evaluation.

Historical candidate-v1 Phase 5 implemented a separate immutable policy:
Week 1 or later, at least 40 games, T-2h operating target, T-1h hard measured
freeze lead, 24-hour postgame stabilization, and six eligible slates. See the
[rating shadow operations runbook](../ops/rating_shadow_operations.md). These
are evidence gates only; reported metrics cannot tune or promote the candidate.

## Promotion review

Week 0 is not a full slate. The first review occurs only after six completed
normal-coverage slates with frozen V4 and candidate predictions. A separate
approved contract must show:

- reproducible state and prediction artifacts;
- rating stability, responsiveness, and uncertainty calibration;
- no material predictive regression against V4, with paired and season/slice
  evidence;
- operational rehearsal, fail-closed behavior, and rollback proof; and
- timestamped market comparison only after the previous findings are satisfactory.

No calendar target overrides missing evidence. Exact statistical thresholds are
chosen in the baseline and promotion contracts, not retrofitted after results.
