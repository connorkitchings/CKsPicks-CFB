# Session: Internal Features Evaluation

## TL;DR

- **Worked On:** Implementing completely new internal metrics (`luck`, `pace`, `turnovers`) from `plays.parquet`, along with `matchup_adv_elo_v1` using point-in-time pure features (CFBD Elo, Recruiting composites).
- **Completed:** Executed Walk-Forward Expanding Cross-Validation (`2021-2024`) on the candidate metrics.
- **Blockers:** Found that off-the-shelf Elo, Recruiting, and basic Internal EPA/Turnover metrics _degraded_ CatBoost performance rather than improved it. Hit a base ceiling of `-3.42%` ROI natively without data leakages.
- **Next:** Moving to Option 2 - designing completely internal, predictive Week-to-Week Power Ratings derived from custom exponentially decayed efficiency margins metrics (an internal SP+ system).

## Changes Made

- **File `conf/features/internal_advanced_v1.yaml`:** Generated 16 experimental, internal base stats focusing on turnover margins, penalty expectations, tempo ratio, and variance models.
- **File `conf/experiment/v2_catboost_internal_adv.yaml`:** Built the expanding Walk-Forward baseline to evaluate against.
- **File `conf/features/matchup_adv_elo_v1.yaml`:** Merged CFBD API `pregame_elo`, `talent_composite`, and explicit EPA Interactions via `selector.py`.
- **File `conf/experiment/v2_catboost_adv_elo.yaml`:** Created test validation structure for the valid Elo variants.
- **File `src/cks_picks_cfb/utils/logging.py`:** Fixed Python 3.12+ `datetime.utcnow()` deprecation warnings in the event logger.

## Testing

- [x] Health checks pass
- [x] Tests pass
- [x] Documentation updated

## Technical Details

`selector.py` dynamically handles string interactions declared under `cfg.features.interactions`. We used this to effectively cross-multiply Home and Away EPAs/SRs cleanly. Sadly, these did not manifest as predictive signals.

## Notes for Next Session

- Resume at: Option 2 implementation (Building a comprehensive custom Point-in-Time ranking algorithm for Offense, Defense, and Team ratings utilizing strictly week-to-week values).
- Remember: CFBD pre-game Elo / Recruiting alone isn't nearly robust enough to drive a betting edge in the CFB Spreads market.
- Watch out for: Ensure any rolled Internal SP+ generation accurately calculates 'snapshot' priors _before_ Wednesday lines are hit, strictly respecting time series validation.

**tags:** ["modeling", "features", "validation", "point-in-time", "elo", "catboost"]
