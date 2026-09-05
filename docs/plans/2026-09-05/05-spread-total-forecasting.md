# Phase 5: Spread and Total Forecasting

- **Status:** Approved
- **Created:** 2026-09-05
- **Planner:** Sol
- **Approval source:** User approved the full data-first plan on 2026-09-05.
- **Implementation log:** Pending Phase 4
- **Commit policy:** Separate plan commit required

## Goal

Improve spread and total forecasts and test whether rating compression retains
the useful information available to a direct football-only benchmark.

## Dependencies and Candidates

Consume the frozen Phase 4 benchmark. Compare rating-based Ridge margin/total,
Ridge team scores, the existing NB2 score model when its corrected lineage is
eligible, and direct Ridge using identical admitted information. Ridge alpha is
`{0.1,1,10,100}` with fold-local standardization. Boosted residuals are deferred.

## Interfaces and Evaluation

Emit one row per candidate, season, game, target, and cutoff with home-minus-away
sign convention, mean, uncertainty, coverage/fallback, and parents. Use expanding
folds through 2025 with training strictly preceding validation; report 2021 as a
gap stress season. Select margin and total separately. Evaluate MAE, RMSE, bias,
CRPS, interval coverage, and width; fit calibration from preceding data only.

## Implementation Tasks

1. Generate identical fold inputs and all bounded candidates; reject duplicate,
   missing, non-finite, future, market, or outcome-derived prediction inputs.
2. Compare on common populations and report unique games separately from target
   and candidate rows. Pair with V4 where valid and identify reconstructed replay.
3. Rank each target by MAE; prefer simplicity within 0.5% of best. Advancement
   requires pooled MAE and CRPS within 1% of the simple reference and no seasonal
   MAE regression above 5%. Claim improvement only at >=0.5% MAE gain.
4. Report 2,000 fixed-seed hierarchical bootstrap replicates, resampling seasons
   then week blocks and keeping each game's paired predictions together.
5. Freeze the selected candidate or the valid simple reference with full lineage.

## Acceptance and Validation

Temporal, population, finite-output, sign, uncertainty, calibration, and
deterministic-reproduction checks pass. All 2015-2019 and 2021-2025 results are
development evidence, including 2025.

## Failure Behavior and Done

Do not broaden the search after failure. Freeze the valid simple reference for
prospective evaluation. Complete candidate registry, evidence, validation,
session log, and status update.

## Amendments

New model families, grids, selection metrics, thresholds, resampling units, or
use of market data require a revised plan.

