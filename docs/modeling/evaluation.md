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

## Current V5 evaluation contract (2026-09-22)

[V5 model development is complete and accepted](v5_status.md). The historical scorecard supports prospective use but offers no like-for-like point-in-time V4 backtest. Current live forecasts require refreshed Week 4 07/08 parents and independent verification. A Preview serving rehearsal and rollback proof govern site cutover; six slates remain a monitoring window, not a prelaunch gate. No 2026 outcome may refit this V5 identity.

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
