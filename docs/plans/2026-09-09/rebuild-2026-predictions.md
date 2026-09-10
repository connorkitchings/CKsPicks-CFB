# Plan: Rebuild 2026 Predictions with Correct Features

**Status:** Draft  
**Created:** 2026-09-09  
**Author:** AI Assistant  
**Priority:** High - Production model performance issue

## Executive Summary

The V4 production model is underperforming in 2026 (36.0% spread win rate) compared to 2025 (50.9% spread win rate). Root cause analysis reveals a **feature mismatch**: the model was trained on features that are not present in the 2026 operational inference pipeline.

This plan documents the root cause, validation methodology, and step-by-step remediation to rebuild 2026 predictions with the correct feature set.

## Problem Statement

The V4 model was trained on `point_in_time_matchups_v5` which includes preseason features (recruiting, returning production, talent composite). The 2025 predictions used the same dataset and achieved 50.9% spread win rate.

The 2026 operational pipeline is using `point_in_time_matchups` (v4) which does NOT include these features, resulting in 36.0% spread win rate.

This is a feature mismatch - the model is being asked to make predictions without the features it was trained on.

## Root Cause Analysis

### Dataset Version Comparison

The operational pipeline (`scripts/pipeline/assemble_model_ready_features.py`) supports `--preseason-features-ref-uri` but it's not being used for 2026 predictions.

**2025 benchmark dataset** (used for training and 2025 predictions):
- Dataset: `point_in_time_matchups_v5`
- Version: `fe55e75884c7665527e740d3`
- Built from:
  - `point_in_time_matchups_core` (base features)
  - `baseline_predictions_oof` (baseline predictions)
  - `v4_preseason_team_features` version `8c47f6d5ccdced2365e4dfdd` (preseason features) ✅

**2026 operational dataset** (used for 2026 predictions):
- Dataset: `point_in_time_matchups`
- Version: `30ac8b5d37719160ff9d751c` (week 1)
- Built from:
  - `point_in_time_matchups_core` (base features)
  - `baseline_predictions_oof` (baseline predictions)
  - ❌ NO preseason features

### Feature Gap Analysis

The V4 model expects 47+ features per route, including:
- `home_shrunk_adj_off_epa_pp` (empirical-Bayes shrunk offensive EPA/play)
- `home_adj_off_epa_pp_current_weight` (shrinkage weight for current vs prior)
- Similar features for defense, rush/pass YPP, success rate, etc.

These features are computed at inference time by `add_ordinal_shrinkage_features()` from base features. However, at week 1, all teams have 0 completed games, so these base features are all NaN.

The model was trained on data where these features had values (weeks 2+), but at week 1 inference, the features are missing or NaN, causing the model to make poor predictions.

### Performance Impact

| Season | Week | Games | Spread Win Rate | Total Win Rate |
|--------|------|-------|-----------------|----------------|
| 2025 | 1 | 48 | 58.3% | N/A |
| 2026 | 0 | 8 | 25.0% | N/A |
| 2026 | 1 | 43 | 38.1% | 37.3% |

The 2026 performance is significantly worse than 2025, particularly in early weeks where preseason features are most critical.

## Root Cause

The operational pipeline (`scripts/pipeline/assemble_model_ready_features.py`) supports `--preseason-features-ref-uri` but it's not being used for 2026 predictions.

The 2025 benchmark dataset was built with:
- `point_in_time_matchups_core` (base features)
- `baseline_predictions_oof` (baseline predictions)
- `v4_preseason_team_features` version `8c47f6d5ccdced2365e4dfdd` (preseason features)

The 2026 operational dataset was built with:
- `point_in_time_matchups_core` (base features)
- `baseline_predictions_oof` (baseline predictions)
- ❌ NO preseason features

## Solution

Rebuild the 2026 predictions using the correct feature dataset that includes preseason features.

### Implementation Steps

#### Step 1: Identify the correct preseason features dataset

The 2025 benchmark used preseason features version `8c47f6d5ccdced2365e4dfdd`:
- URI: `lake/gold/dataset=v4_preseason_team_features/version=8c47f6d5ccdced2365e4dfdd/data.parquet`
- This dataset contains recruiting, returning production, and talent composite features

Verify the dataset exists and is accessible:
```bash
PYTHONPATH=.:src uv run python -c "
from cks_picks_cfb.data.storage import get_storage
storage = get_storage()
uri = 'lake/gold/dataset=v4_preseason_team_features/version=8c47f6d5ccdced2365e4dfdd/data.parquet'
print(f'Dataset exists: {storage.exists(uri)}')
"
```

#### Step 2: Rebuild model-ready features for 2026 weeks 0-2

Use `scripts/pipeline/assemble_model_ready_features.py` with the `--preseason-features-ref-uri` parameter.

For each week (0, 1, 2), run:
```bash
PYTHONPATH=.:src uv run python scripts/pipeline/assemble_model_ready_features.py \
  --core-ref-uri <core_ref_uri_for_week_N> \
  --baselines-ref-uri <baselines_ref_uri> \
  --preseason-features-ref-uri lake/gold/dataset=v4_preseason_team_features/version=8c47f6d5ccdced2365e4dfdd/manifest.json \
  --feature-track strict \
  --as-of <as_of_timestamp> \
  --output-ref-uri <output_uri> \
  --environment preview
```

This will create `point_in_time_matchups_v5` datasets for each week, matching the schema used in 2025.

**Note:** The `--core-ref-uri` and `--baselines-ref-uri` must be the correct refs for each week. Check the existing 2026 prediction runs to find the correct refs.

#### Step 3: Regenerate predictions for 2026 weeks 0-2

Use `scripts/pipeline/generate_weekly_bets.py` with the new model-ready datasets.

For each week, run:
```bash
PYTHONPATH=.:src uv run python scripts/pipeline/generate_weekly_bets.py \
  --config conf/weekly_bets/v4_2026.yaml \
  --year 2026 --week N \
  --dataset-refs-uri <new_dataset_refs_uri> \
  --as-of <as_of_timestamp> \
  --environment preview
```

This will create new prediction runs with the correct features.

#### Step 4: Score the new predictions

Use `scripts/pipeline/score_weekly_bets.py` to score the new predictions against actual outcomes:
```bash
PYTHONPATH=.:src uv run python scripts/pipeline/score_weekly_bets.py \
  --year 2026 --week N \
  --run-id <new_run_id>
```

Compare win rates to 2025:
```bash
PYTHONPATH=.:src uv run python -c "
import psycopg
from dotenv import load_dotenv
import os

load_dotenv('.env')
conn_url = os.environ['DATABASE_URL']

with psycopg.connect(conn_url) as conn:
    with conn.cursor() as cur:
        cur.execute('''
            SELECT 
                g.week,
                COUNT(*) as games,
                SUM(CASE WHEN pg_spread.result = 'win' THEN 1 ELSE 0 END) as spread_wins,
                SUM(CASE WHEN pg_spread.result = 'loss' THEN 1 ELSE 0 END) as spread_losses
            FROM predictions p
            JOIN prediction_runs pr ON p.run_id = pr.run_id
            JOIN games g ON p.game_id = g.game_id
            LEFT JOIN prediction_grades pg_spread ON p.run_id = pg_spread.run_id 
                AND p.game_id = pg_spread.game_id AND pg_spread.target = 'spread'
            WHERE pr.season = 2026
              AND pr.model_id = 'week0-2026-v4-strict-20260818-r2'
              AND g.home_points IS NOT NULL
            GROUP BY g.week
            ORDER BY g.week
        ''')
        for row in cur.fetchall():
            week, games, wins, losses = row
            win_pct = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
            print(f'Week {week}: {wins}-{losses} ({win_pct:.1f}%)')
"
```

#### Step 5: Update the database

Replace the old 2026 predictions with the new ones:

1. Deactivate the old prediction runs:
```sql
UPDATE prediction_runs
SET state = 'superseded'
WHERE season = 2026
  AND model_id = 'week0-2026-v4-strict-20260818-r2'
  AND run_id IN ('2026w0-79ec2aebcb00', '2026w0-55de0317120d', '2026w1-b2c739321e5d', '2026w2-43b25511a100');
```

2. Activate the new prediction runs:
```sql
UPDATE current_week
SET active_run_id = <new_run_id>
WHERE season = 2026 AND week = N;
```

3. Update the web app to show the corrected predictions (automatic via `current_week` table).

#### Step 6: Validate and monitor

After rebuilding, monitor the win rates:
- 2026 week 0: Should improve from 25% (8 games)
- 2026 week 1: Should improve from 38.1% (43 games)
- 2026 week 2: Should improve from current (49 games)

If the rebuilt predictions show similar performance to 2025 (around 50%+), the issue was the missing features. If they're still low, we need to investigate further (model overfitting, season differences, etc.).

### Expected Outcome

With the correct features, the 2026 predictions should perform similarly to 2025 (around 50%+ win rate), assuming the model is still valid.

If the win rate is still low, then the issue is not features but rather:
- The model is overfit to 2025
- The 2026 season is fundamentally different
- There's a bug in the model or inference code

## Validation

### Success Criteria

After rebuilding, compare:
- 2025 week 1: 58.3% spread win rate (48 games) - baseline
- 2026 week 0: Currently 25% (8 games), should improve to ~50%+
- 2026 week 1: Currently 38.1% (43 games), should improve to ~50%+
- 2026 week 2: Currently TBD (49 games), should be ~50%+

If the rebuilt predictions show similar performance to 2025, the issue was the missing features. If they're still low, we need to investigate further.

### Validation Checklist

- [ ] Preseason features dataset exists and is accessible
- [ ] Model-ready features rebuilt for weeks 0-2 with `point_in_time_matchups_v5` schema
- [ ] New predictions generated with correct features
- [ ] Predictions scored against actual outcomes
- [ ] Win rates improved to ~50%+ for weeks 0-2
- [ ] Database updated with new prediction runs
- [ ] Web app displaying corrected predictions
- [ ] No regression in 2025 predictions (unchanged)

### Monitoring

After deployment, monitor:
- Daily win rates for weeks 0-2
- User feedback on prediction quality
- Model performance as season progresses (weeks 3+ should be less affected)

## Rollback Plan

If the rebuilt predictions are worse, we can revert to the old predictions:

1. The old prediction runs are still in the database (marked as `superseded`)
2. To rollback, update `current_week.active_run_id` to point to the old runs:
```sql
UPDATE current_week
SET active_run_id = '2026w0-55de0317120d'
WHERE season = 2026 AND week = 0;
```

3. The web app will automatically display the old predictions

## Documentation Updates

This plan requires updates to the following documentation:

1. **docs/ops/weekly_pipeline.md** - Add section on preseason features requirement
2. **docs/ops/production_runbook.md** - Add troubleshooting section for feature mismatches
3. **AGENTS.md** - Add note about V4 feature requirements
4. **Session log** - Document this investigation and fix

## Lessons Learned

1. **Feature consistency is critical** - The training and inference pipelines must use identical feature sets
2. **Schema versioning matters** - `point_in_time_matchups_v5` vs `point_in_time_matchups` (v4) have different features
3. **Early season performance is sensitive** - Week 0-1 predictions rely heavily on preseason features
4. **Validation gaps** - The operational pipeline should have validated that the feature set matches the training set

## Future Improvements

1. **Automated feature validation** - Add a check in the pipeline to verify that inference features match training features
2. **Feature schema enforcement** - Use strict schema validation to prevent mismatches
3. **Early season monitoring** - Add alerts for unusual performance drops in weeks 0-2
4. **Documentation** - Clearly document the requirement for `--preseason-features-ref-uri` in the operational pipeline

## Appendix: Technical Details

### Dataset References

**2025 benchmark dataset:**
- Dataset: `point_in_time_matchups_v5`
- Version: `fe55e75884c7665527e740d3`
- URI: `lake/gold/dataset=point_in_time_matchups_v5/version=fe55e75884c7665527e740d3/data.parquet`
- Parent versions: `['02cd3a9f47f780de0871f947', 'cf356b202a1c45e48854a8c9', '8c47f6d5ccdced2365e4dfdd']`
  - `02cd3a9f47f780de0871f947`: `point_in_time_matchups_core`
  - `cf356b202a1c45e48854a8c9`: `baseline_predictions_oof`
  - `8c47f6d5ccdced2365e4dfdd`: `v4_preseason_team_features`

**2026 operational dataset (week 1):**
- Dataset: `point_in_time_matchups`
- Version: `30ac8b5d37719160ff9d751c`
- URI: `lake/gold/dataset=point_in_time_matchups/version=30ac8b5d37719160ff9d751c/data.parquet`
- Missing: preseason features

### Model Bundle Details

- Bundle ID: `week0-2026-v4-strict-20260818-r2`
- Training years: `[2021, 2022, 2023, 2024, 2025]`
- Feature track: `strict`
- Feature dataset refs: `point_in_time_matchups_v5` version `fe55e75884c7665527e740d3`

### Key Features

The V4 model expects 47+ features per route, including:
- `home_shrunk_adj_off_epa_pp` - Empirical-Bayes shrunk offensive EPA/play
- `home_adj_off_epa_pp_current_weight` - Shrinkage weight for current vs prior
- `home_shrunk_adj_def_epa_pp` - Empirical-Bayes shrunk defensive EPA/play
- `home_adj_def_epa_pp_current_weight` - Shrinkage weight for current vs prior
- Similar features for rush/pass YPP, success rate, etc.

These features are computed at inference time by `add_ordinal_shrinkage_features()` from base features. At week 1, all teams have 0 completed games, so these base features are all NaN, causing the model to make poor predictions.
