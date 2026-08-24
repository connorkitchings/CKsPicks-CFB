# Session: Internal Power Rating Optimization (Option 2)

## TL;DR

- **Worked On:** Architecting and tuning a native, point-in-time pure Internal SP+ generation script (`internal_ratings.py`) derived directly from opponent-adjusted EPA and pace.
- **Completed:** Deployed the baseline Option 2 math, yielding a `-2.02%` ROI and `51.3%` Hit Rate (a massive `+1.2%` jump over prior methods). Also conducted Math Tuning (adding Success Rate) and Hyperparameter Optimization via Optuna (`tune_catboost.py`).
- **Blockers:** Both the Math Tuning (blending SR into EPA) and Hyperparameter Optimization (Optuna) heavily degraded ROI back into the `-3.65%` and `-3.41%` range when exposed to Walk-Forward validation, proving the core `EPA * Pace` heuristic is the apex of our internal metrics.
- **Next:** Since Option 2 (Internal SP+) has officially peaked at `-2.02%`, we must pivot to ingesting historical, week-by-week weekly snapshots of true external market metrics (FPI, SP+, FEI) to build a fully profitable framework.

## Changes Made

- **File `src/cks_picks_cfb/features/internal_ratings.py`:** Engineered the `internal_power_rtg`, `internal_off_rtg`, and `internal_def_rtg` using strict `pandas.shift(1)` isolating loops to guarantee zero look-ahead bias.
- **File `src/cks_picks_cfb/features/v2_recency.py`:** Hooked the `add_internal_power_ratings` function into the end of the opponent-adjustment calculation.
- **File `src/cks_picks_cfb/features/selector.py`:** Added `internal_ratings_stats` to the feature configuration map.
- **File `conf/features/internal_power_rating_v1.yaml`:** Built the YAML config layout for the internal metrics alongside the baseline core.
- **File `conf/experiment/v2_catboost_internal_power.yaml`:** Setup the specific 4-fold expanding Walk-Forward pipeline evaluation.
- **File `scripts/tuning/tune_catboost.py`:** Authored a standalone Optuna hyperparameter optimization script tailored explicitly to the `internal_power_rating_v1.yaml` array and `V2CatBoostModel`.

## Testing

- [x] Health checks pass (`ruff` formatting and linting clear)
- [x] Tests pass (173 tests)
- [x] Documentation updated (Implementation Plan and Walkthrough reflect optimization results)

## Technical Details

The Optuna script `scripts/tuning/tune_catboost.py` discovered a minimal configuration (`Iterations=1359, Depth=3, L2=6.44`) that yielded `~0.0%` ROI specifically on the 2024 holdout set. However, 4-Fold Validation proved it overfit to 2024 and collapsed globally across time. Default heuristics (`depth=6, iterations=1000`) are strictly superior.

## Notes for Next Session

**Resume at:** Data Ingestion Pipeline for External Market Metrics
**Context:** Option 2 Internal metrics hit a hard ceiling at `-2.02%`. We cannot beat the CFB spread market natively. We _must_ begin scraping and storing point-in-time valid Weekly SP+, FPI, and FEI ratings to produce true alpha.
**Next steps:**

1. Investigate the `.agent` and existing `data` folders to identify where external ratings are fetched.
2. Ensure we gather historical week-specific ratings going back to 2019 without downloading end-of-season numbers.

**tags:** ["modeling", "features", "pipeline", "optuna", "tuning"]
