# Phase 5: Rating-Based Forecast Selection v2

- **Status:** Superseded
- **Created:** 2026-09-08
- **Planner:** Astra
- **Approval source:** User approved the full replacement plan on 2026-09-08, retaining the Ridge/NB2 tournament and ratings as mandatory foundation.
- **Implementation log:** Pending repaired Phase 4B and separate Phase 5 task
- **Commit policy:** Separate code/evidence checkpoints; user executes Git.

> **Superseded (2026-09-13):** Execution authority is [04: forecast bridge and fitting-window selection](../../archive/v5-contracts/2026-09-13/04-v5-forecast-bridge-and-fitting-window.md).
> Preserve the original approval, historical hold notice, and mathematical record
> below. Only sections explicitly inherited by the
> [V5 common contract](../../archive/v5-contracts/2026-09-13/v5-ratings-successor-roadmap-and-contracts.md)
> carry forward. This does not authorize executing old runners or consuming the
> original Phase 4B retained manifest as a forecasting parent.

> **Execution hold (2026-09-10):** This remains an Approved historical record
> with its original approval source. Do not execute it until a replacement
> forecasting design or explicit reaffirmation follows methodology review.

## Goal, scope and parents

Freeze one rating-based margin and one total forecast with non-null uncertainty.
The [common contract](transformation-review-and-authority-reset.md) applies.
Inputs: `--phase4-rating-uri`, `--phase4b-context-uri`, and
`--phase3-retained-uri` for diagnostic direct-core comparison; require repaired
v2 roles and matching populations. Optional `--market-reference-uri` is loaded
only after selection. Original Phase 4B and historical NB2 outputs confer no
eligibility. Production, promotion, betting and context reselection are excluded.

## Frozen candidate registry

Eligible families: direct rating-to-target Ridge, shared team-score Ridge,
and rebuilt NB2 team scores. Select margin and total separately. Direct-core
Ridge uses identical admitted core/context information only as a diagnostic of
rating compression; it is never a retention candidate.

Target Ridge uses the exact corrected Phase 4B rating/context/venue feature list.
Ridge alphas `{0.1,1,10,100}` are selected by earlier-season inner target MAE;
prefer larger alpha within 0.5% of best. Fewer than one eligible inner fold means
alpha 10, explicitly recorded. Refit on all preceding training seasons.

Score models use shared coefficients across home/away team rows: intercept,
own offense, opponent defense, physical-host indicator (zero for both at neutral
sites), and own/opponent versions of the frozen target-context features and
missingness indicators. Unknown venue status follows the fixed Phase 4A policy.
Standardization is training-only, scale floor 0.05. No home/away-specific
coefficient split. Fit separate target-specific score variants if margin and
total retained different contexts; select score-model Ridge alpha using the
derived target error, not individual-score error.

Score Ridge means must be strictly positive and finite across the full forecast
population; no post hoc clipping. Failure disqualifies the candidate. NB2 uses
log-link `mu=exp(X beta)`, variance `mu + dispersion*mu^2`, and shared positive
dispersion. Fit current-lineage integer nonnegative score labels. No rows may be
dropped by legacy complete-case helpers.

NB2 deterministic likelihood fitting: L-BFGS-B, dispersion `[1e-6,100]`, maxiter
1000, ftol `1e-9`; initialize beta from least-squares log(score+0.5) on the
training standardized design and dispersion 0.25. Constrain own-offense beta
positive (lower `1e-8`), opponent-defense beta negative (upper `-1e-8`), hosting
beta nonnegative; other coefficients unconstrained. Nonconvergence, singular
unidentifiable design after deterministic constant-column removal, nonfinite
means, or invalid dispersion disqualifies NB2 before performance comparison.
Do not silently clip the linear predictor to rescue an invalid candidate.

## Forecast distribution and calibration

Use moment-based Gaussian margin/total distributions for every candidate and
the corrected Phase 4B simple reference. State variance is reported separately;
do not equate rating uncertainty with outcome uncertainty or add it twice to
empirical forecast errors.

For each outer validation season, generate nested rolling-origin prediction
residuals on preceding seasons (inner hyperparameter fitting also precedes each
residual's season). At least one eligible prior residual season is required to
issue an uncertainty-bearing candidate; otherwise block that fold/candidate.
Never calibrate from training-fit errors or the current validation outcomes.

- Target Ridge variance: mean squared prior prediction error (floor `1e-6`);
  no mean/bias correction in this registry.
- Score Ridge covariance: paired prior home/away residual second-moment matrix,
  symmetrized, eigenvalues floored at `1e-6`; persist the correction magnitude.
- NB2 marginal variances: `vH=muH+a*muH^2`, `vA=muA+a*muA^2`. Estimate residual
  home/away correlation from earlier paired residuals, bound it to `[-0.99,0.99]`,
  and use `c=rho*sqrt(vH*vA)`; undefined correlation uses zero with a reason.
- Derive `margin=muH-muA`, `total=muH+muA`,
  `vMargin=vH+vA-2*c`, `vTotal=vH+vA+2*c`.
- For score models calibrate each target variance by the mean of preceding
  squared standardized errors from nested rolling predictions; scale must be
  finite and positive (floor `1e-6`). Apply the fixed fitted scale prospectively.
  Target Ridge's empirical variance already supplies this calibration; do not
  calibrate it a second time from the same residuals.

Compute Gaussian CRPS analytically and central 50/80/95% intervals. Report MAE,
RMSE, bias, CRPS, coverage, width, covariance corrections and calibration sample
counts. Label NB2 target uncertainty as a Gaussian approximation, not an exact
discrete distribution. Independently selected target forecasts need not define
one coherent joint home/away score distribution; do not claim they do.

## Selection, outputs, and failure

Reference is corrected Phase 4B alpha-10 target Ridge with the same uncertainty
protocol. Candidate eligibility requires target MAE and CRPS <=1.01 times
reference, equal population, finite outputs and no season MAE regression >5%.
Claim gain only for >=0.5% MAE improvement and paired 90% lower bound >0.
Among passing models within 0.5% of best target MAE, order target Ridge, shared
score Ridge, NB2, then larger alpha. Retain reference when no challenger passes.
An invalid reference blocks advancement rather than producing a null-uncertainty
fallback. Registry expansion after inspection is prohibited.

Stage `phase5/v2`; schemas: `phase5_registry`, `phase5_model`,
`phase5_prediction`, `phase5_calibration`, `phase5_selection`,
`phase5_retained_forecast`, `phase5_market_diagnostic`. Predictive rows include
target, mean/variance, interval bounds, distribution label, exact target model,
rating/context parents, cutoff, coverage and fallback. Persist serializable
model parameters, transforms, inner fits, residual refs and update/refit policy.
Bundle both selected target manifests in one candidate manifest for Phase 6.

Only after retention, load reconstructed market refs for sign checks, quote
coverage, line-implied error and disagreement. They cannot change fitting,
selection, promotion, CLV claims or prospective counts.

## Tests and done

Test side/host swapping and neutral games, shared score design, target-specific
context, integer NB2 labels, failed optimizer/positive means, missing feature
fallback, no complete-case population loss, nested residual chronology, PSD and
variance propagation, Gaussian CRPS/intervals, reference parity, selection
thresholds and market non-use. Independently reproduce retained models and
predictions. Common gates apply. Done: complete verified target candidate or
reference, uncertainty, lineage, diagnostics, documentation and log. Changes
to distributions, calibration, families or grids require common amendments.
