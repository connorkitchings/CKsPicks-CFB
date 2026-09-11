# Plan: Generate V4 Predictions for 2025 Season

**Status:** Draft  
**Created:** 2026-09-09  
**Scope:** Data pipeline and prediction generation

---

## Objective

Generate proper V4 model predictions for all 2025 games using:
1. CFBD games API for schedules and results
2. CFBD betting lines API for market spreads/totals
3. V4 model trained on 2021-2024 data
4. Point-in-time correct features (only data available before each week's kickoff)

---

## Current State

### What Exists
- **2025 schedule data:** In R2 at `artifacts/preview/refs/history/games-2025.json`
- **2025 game results:** 745 of 746 games have results in database
- **V4 model bundle:** `week0-2026-v4-strict-20260818-r2` in R2
- **V4 baseline predictions:** 761 predictions exist in locked test dataset (but these are Ridge baselines, not full V4)
- **Week 1 games:** 48 games exist in schedule but NOT in database

### What's Missing
- **Betting lines for 2025:** Need to verify CFBD has historical lines
- **Silver/Gold datasets for 2025:** Need to build week-by-week
- **Full V4 predictions:** Need to run inference pipeline for each week
- **Week 1 games in database:** Need to add from schedule

---

## Implementation Plan

### Phase 1: Verify and Ingest 2025 CFBD Data

**Goal:** Ensure all 2025 games and betting lines are captured in Bronze storage.

#### Step 1.1: Check existing 2025 Bronze data

```bash
# Check if 2025 games exist in Bronze
PYTHONPATH=. uv run python -c "
from cks_picks_cfb.data.storage import get_storage
storage = get_storage()
games_files = storage.list_files('raw/games/year=2025/')
print(f'Games files: {games_files}')
lines_files = storage.list_files('raw/betting_lines/year=2025/')
print(f'Betting lines files: {lines_files}')
"
```

#### Step 1.2: Ingest 2025 games if missing

```bash
# Ingest full 2025 season games
PYTHONPATH=. uv run python scripts/cli.py ingest-year 2025 \
  --entities games \
  --season-type regular
```

Or for specific weeks:
```bash
PYTHONPATH=. uv run python scripts/data/ingest_week.py \
  --year 2025 --week 1 --entities games
```

#### Step 1.3: Ingest 2025 betting lines

```bash
# Ingest betting lines for full 2025 season
PYTHONPATH=. uv run python scripts/cli.py ingest-year 2025 \
  --entities betting_lines \
  --season-type regular
```

Or week-by-week:
```bash
for week in {1..16}; do
  PYTHONPATH=. uv run python scripts/data/ingest_week.py \
    --year 2025 --week $week \
    --entities betting_lines
done
```

**Validation:**
- All 762 FBS games have Bronze captures
- Betting lines exist for each week
- No missing games or lines

---

### Phase 2: Build Silver/Gold Datasets for 2025

**Goal:** Create point-in-time correct feature datasets for each week.

#### Step 2.1: Build Silver datasets

```bash
# Build Silver for 2025 (games, plays, betting lines)
PYTHONPATH=. uv run python scripts/data/build_silver.py \
  --year 2025 \
  --entities games,plays,betting_lines
```

This creates:
- `silver/games/year=2025/` - normalized game data
- `silver/plays/year=2025/` - normalized play data
- `silver/market_quotes/year=2025/` - normalized betting lines

#### Step 2.2: Build Gold point-in-time matchups

For each week, build the feature dataset using only data available before that week's kickoff:

```bash
# Build Gold for week 1 (only 2021-2024 data + week 1 schedule)
PYTHONPATH=. uv run python scripts/pipeline/assemble_model_ready_features.py \
  --year 2025 --week 1 \
  --as-of <week1_kickoff_timestamp>

# Build Gold for week 2 (2021-2024 + week 1 results + week 2 schedule)
PYTHONPATH=. uv run python scripts/pipeline/assemble_model_ready_features.py \
  --year 2025 --week 2 \
  --as-of <week2_kickoff_timestamp>

# ... repeat for each week
```

**Key:** The `--as-of` timestamp ensures point-in-time correctness by only including data available before each week's first kickoff.

#### Step 2.3: Register dataset refs

Each Gold dataset gets an immutable `DatasetRef` with SHA-256 checksum:

```python
from cks_picks_cfb.data.catalog import register_dataset_version
from cks_picks_cfb.data.lake import DatasetRef

# Register each week's dataset
for week in range(1, 17):
    ref = DatasetRef(
        dataset="point_in_time_matchups",
        version_id=f"2025w{week}-<hash>",
        schema_version="v1",
        content_sha="<sha256>",
        uri="lake/gold/dataset=point_in_time_matchups/version=<hash>/data.parquet"
    )
    register_dataset_version(ref)
```

---

### Phase 3: Generate V4 Predictions Week-by-Week

**Goal:** Run V4 inference for each 2025 week using the trained model.

#### Step 3.1: Create 2025 config

Create `conf/weekly_bets/v4_2025_locked_test.yaml`:

```yaml
system_name: "Trench Warfare V4"
model_id: "week0-2026-v4-strict-20260818-r2"

model_bundle_v3:
  artifact_uri: artifacts/preview/models/week0-2026-v4-strict-20260818-r2/manifest.json
  sha256: 72429375bfa8c434c7d6fcb455bb9e22333af8c929c0cc3e832f0b80787bf25c

year: 2025
week: 1  # Will be overridden per week

spread_edge_threshold: 0.0
spread_edge_threshold_high_conf: 8.0
total_edge_threshold: 1.5

features:
  type: recency
  alpha: 0.3

training:
  train_years: [2021, 2022, 2023, 2024]
  test_year: 2025
  deploy_year: 2026
```

#### Step 3.2: Generate predictions for each week

```bash
# Week 1
PYTHONPATH=. uv run python scripts/pipeline/generate_weekly_bets.py \
  --config conf/weekly_bets/v4_2025_locked_test.yaml \
  --year 2025 --week 1 \
  --as-of <week1_kickoff> \
  --dataset-refs-uri <week1_refs_uri> \
  --upload-artifact \
  --run-state preview

# Week 2
PYTHONPATH=. uv run python scripts/pipeline/generate_weekly_bets.py \
  --config conf/weekly_bets/v4_2025_locked_test.yaml \
  --year 2025 --week 2 \
  --as-of <week2_kickoff> \
  --dataset-refs-uri <week2_refs_uri> \
  --upload-artifact \
  --run-state preview

# ... repeat for all weeks
```

**Output:** Immutable prediction artifacts in R2 at `artifacts/preview/predictions/year=2025/week=N/run_id=<id>/`

#### Step 3.3: Score predictions against results

After all weeks are predicted, score each week:

```bash
for week in {1..16}; do
  PYTHONPATH=. uv run python scripts/pipeline/score_weekly_bets.py \
    --year 2025 --week $week \
    --run-id <run_id_for_week>
done
```

---

### Phase 4: Publish to Database

**Goal:** Publish V4 predictions and results to Neon for web app display.

#### Step 4.1: Add missing week 1 games

```bash
# Insert week 1 games from schedule
PYTHONPATH=. uv run python << 'EOF'
# Script to add week 1 games to database
# (similar to what we did earlier but properly)
EOF
```

#### Step 4.2: Publish predictions

```bash
for week in {1..16}; do
  PYTHONPATH=. uv run python scripts/pipeline/publish_to_db.py \
    --year 2025 --week $week \
    --from-artifact \
    --run-id <run_id_for_week> \
    --no-update-current \
    --state scored
done
```

#### Step 4.3: Publish results

```bash
PYTHONPATH=. uv run python scripts/pipeline/score_to_db.py \
  --year 2025 \
  --backfill-season \
  --from-artifact
```

---

## Validation

### Data Validation
- [ ] All 762 2025 games in Bronze storage
- [ ] Betting lines for all weeks
- [ ] Silver datasets for all weeks
- [ ] Gold point-in-time features for all weeks
- [ ] V4 predictions for all weeks
- [ ] Scored results for all games

### Model Validation
- [ ] Predictions use only pre-2025 training data
- [ ] Point-in-time correctness verified (no future leakage)
- [ ] Regime routing matches V4 spec (game_1 through established)
- [ ] Model bundle SHA-256 verified

### Web App Validation
- [ ] 2025 season shows all weeks (1-16)
- [ ] Week selector works for 2025
- [ ] Predictions display correctly
- [ ] Win/loss records calculate correctly
- [ ] No regression in 2026 functionality

---

## Key Challenges

1. **Betting lines availability:** CFBD may not have complete historical lines for 2025. Need to verify.
2. **Point-in-time correctness:** Must ensure each week's features only use data available before kickoff.
3. **Week 1 cold start:** Week 1 has no 2025 data, only 2021-2024 training data.
4. **Computational cost:** Building Gold features for 16 weeks is expensive.

---

## Rollback Plan

If something goes wrong:
1. Delete V4 prediction runs from database
2. Restore original V2 predictions if needed
3. Web app can toggle between seasons

---

## Success Criteria

- ✅ V4 predictions generated for all 2025 weeks
- ✅ Point-in-time correctness verified
- ✅ Predictions published to database
- ✅ Web app displays 2025 V4 predictions
- ✅ Win rate calculated correctly

---

## Next Steps

1. **Verify CFBD data:** Check if 2025 games and lines exist in Bronze
2. **Ingest missing data:** Fetch from CFBD if needed
3. **Build Silver/Gold:** Create feature datasets week-by-week
4. **Generate predictions:** Run V4 inference for each week
5. **Publish to DB:** Make predictions available to web app
6. **Validate:** Verify correctness and web app display

---

## Open Questions

1. **Does CFBD have 2025 betting lines?** Need to verify before proceeding.
2. **What's the exact `--as-of` timestamp for each week?** Need to determine from schedule.
3. **Should we use Preview or Production storage?** Preview for testing, Production for final.
4. **How to handle weeks with missing lines?** Fail closed or use fallback?

---

## Estimated Effort

- Phase 1 (Data ingestion): 1-2 hours
- Phase 2 (Silver/Gold): 2-4 hours (computational)
- Phase 3 (Predictions): 2-4 hours (computational)
- Phase 4 (Publishing): 1 hour
- Validation: 1-2 hours

**Total:** 7-13 hours

---

## Dependencies

- CFBD API key (`CFBD_API_KEY`)
- R2 storage credentials (`CFB_R2_*`)
- Database URL (`DATABASE_URL`)
- V4 model bundle in R2
- Sufficient compute for feature engineering
