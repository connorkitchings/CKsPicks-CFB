# Project Context

> **Domain Knowledge and Architecture for CFB Model**
>
> This file contains project-specific context that AI assistants should understand when working on this codebase.

---

## Project Overview

This is a college football betting model system that predicts point spreads and over/unders using machine learning.

**Domain:** Sports betting / predictive analytics
**Sport:** NCAA Division I FBS College Football
**Prediction Targets:** Point spreads, over/under totals
**Data Source:** CollegeFootballData.com API
**Time Period:** 2019-2025 seasons (excluding 2020 COVID year)

---

## Architecture Overview

### Data Pipeline Flow

The system follows a hierarchical aggregation pipeline:

```
Raw API Data
    ↓
1. Raw Ingestion (src/data/)
    ├── plays.py → Play-by-play data
    ├── games.py → Game results
    ├── teams.py → Team metadata
    └── betting_lines.py → Market lines
    ↓
2. Aggregation (src/features/pipeline.py)
    ├── byplay → Play-level features
    ├── drives → Drive-level aggregations
    ├── team_game → Game-level team stats
    └── team_season → Season-level metrics
    ↓
3. Feature Engineering (src/features/)
    ├── core.py → Aggregation functions
    ├── byplay.py → Play-level transforms
    ├── weather.py → Weather integration
    └── selector.py → Feature selection
    ↓
4. Modeling (src/models/)
    ├── train_model.py → Training pipeline
    ├── features.py → Point-in-time data loading
    └── betting.py → Bet generation
    ↓
Production Predictions
```

### Points-For Modeling Approach

**Unlike traditional spread models**, this system predicts:

1. **Home team points** (e.g., 28.5)
2. **Away team points** (e.g., 24.3)

Then derives betting targets:
- `predicted_spread = home_points - away_points` (e.g., +4.2)
- `predicted_total = home_points + away_points` (e.g., 52.8)

**Why this approach?**
- Better captures asymmetric matchups
- Provides more flexibility for ensemble strategies
- Allows separate optimization for offense/defense

**Current Production Models (as of Nov 2024):**
- Spreads: CatBoost with recency features
- Totals: XGBoost optimized via Optuna

---

## Data Storage

### Directory Structure

```
$CFB_MODEL_DATA_ROOT/  (external drive or cloud)
├── raw/                    # Raw API responses
│   ├── plays/             # Play-by-play data
│   ├── games/             # Game results
│   ├── teams/             # Team metadata
│   └── betting_lines/     # Market lines
├── aggregated/            # Aggregated products
│   ├── byplay/            # Play-level features
│   ├── drives/            # Drive-level stats
│   ├── team_game/         # Game-level stats
│   └── team_season/       # Season-level metrics
├── features/              # Feature caches
│   ├── adj_iter_2/        # Adjusted features (2 iterations)
│   ├── adj_iter_4/        # Adjusted features (4 iterations)
│   └── weekly_features/   # Running season features
└── models/                # Serialized models
```

### Data Format

All data stored as **Parquet files** with partitioning:
- `year=YYYY/week=WW/data.parquet` - For time-series data
- `data.parquet` - For static data (teams, venues)

**Key columns:**
- `season` (int) - Year (e.g., 2024)
- `week` (int) - Week number (1-15, conference championship, bowls)
- `game_id` (int) - Unique game identifier
- `team` (str) - Team name
- `opponent` (str) - Opponent team name

---

## Feature Engineering Principles

### Opponent Adjustment

The system uses **iterative opponent adjustment** to normalize raw stats against opponent quality.

**Example:** Team A averages 7.0 yards/play, but played weak defenses. After adjustment:
- Iteration 1: 6.8 yards/play (adjusted for opponent avg)
- Iteration 2: 6.7 yards/play (adjusted for opponent's adjusted avg)
- Iteration 3: 6.65 yards/play (convergence)

**Parameter:** `adjustment_iteration` (typically 2-4)

### Feature Categories

1. **Offensive Efficiency**
   - Yards per play
   - Success rate (gaining ≥50% of yards needed)
   - Explosiveness (plays ≥10 yards)
   - Red zone scoring rate

2. **Defensive Efficiency**
   - Same metrics, from defense perspective
   - "Allowed" versions (e.g., `yards_per_play_allowed`)

3. **Situational Performance**
   - Third down conversion rate
   - Red zone efficiency
   - Turnover margin

4. **Pace Metrics**
   - Plays per game
   - Seconds per play
   - Tempo adjustments

5. **Recency Features**
   - Last 3-4 games weighted higher
   - Exponential decay weighting

6. **Weather Features** (outdoor games only)
   - Temperature
   - Wind speed
   - Precipitation

7. **Mismatch Features**
   - Offense vs defense interactions
   - Calculated as offense_metric × defense_metric_allowed

### Feature Naming Convention

```
{home|away}_{off|def}_{metric}[_adj{N}][_last{M}]
```

Examples:
- `home_off_yards_per_play` - Home offense yards/play (raw)
- `home_off_yards_per_play_adj2` - Adjusted (2 iterations)
- `away_def_success_rate_last3` - Away defense success rate (last 3 games)

**See `docs/modeling/features.md` for complete feature catalog.**

---

## Configuration System (Hydra)

### Structure

```
conf/
├── config.yaml              # Top-level defaults
├── model/                   # Model configs (catboost, xgboost, ridge)
├── features/                # Feature set definitions
├── experiment/              # Pre-packaged experiments
├── tuning/                  # Optuna search spaces
├── paths/                   # Data path overrides
└── weekly_bets/            # Betting policy configs
```

### Composition

Hydra composes configs hierarchically:

```yaml
# conf/config.yaml
defaults:
  - model: catboost           # Use conf/model/catboost.yaml
  - features: standard_v1     # Use conf/features/standard_v1.yaml
  - experiment: null          # Optional experiment override

data:
  adjustment_iteration: 2
  train_years: [2019, 2021, 2022, 2023]
  test_year: 2024
```

### Override Patterns

```bash
# Switch model type
model=xgboost

# Change test year
data.test_year=2025

# Load experiment (overrides all)
experiment=spread_catboost_baseline_v1

# Add new parameter
+new_param=value

# Delete parameter
~old_param

# Override nested parameter
model.params.depth=8
```

**See `.codex/HYDRA.md` for detailed guide.**

---

## Model Training Workflow

### Standard Training

```bash
PYTHONPATH=. uv run python src/models/train_model.py \
    model=catboost \
    data.test_year=2024 \
    experiment=null
```

### Hyperparameter Optimization

```bash
PYTHONPATH=. uv run python src/models/train_model.py \
    mode=optimize \
    model=catboost \
    tuning=catboost_optuna
```

### Walk-Forward Validation

Train on multiple holdout years sequentially:

```python
test_years = [2021, 2022, 2023, 2024]
for year in test_years:
    train(test_year=year)
```

---

## MLflow Integration

### Tracking

All training runs automatically logged to MLflow:

**Tracked:**
- **Metrics:** RMSE, MAE, calibration error, betting ROI
- **Parameters:** All Hydra config values
- **Artifacts:** Trained models, feature lists, predictions
- **Tags:** git_sha, model_type, feature_set, experiment

**Location:** `artifacts/mlruns/` (file-based backend)

### Model Registry

Production models promoted through stages:

1. `None` → `Development`
2. `Development` → `Staging`
3. `Staging` → `Production`

**Model ID Convention:**
```
{target}_{model_type}_{feature_set}_{tuning}_{data_version}
```

Example: `home_points_catboost_standard_v1_optuna_2024_adj2`

---

## Testing Philosophy

### Test Patterns

1. **Minimal Fixtures** - Small, focused test data
2. **Edge Cases** - Empty DataFrames, single rows, missing columns
3. **Aggregation Validation** - Verify calculations match expected values
4. **Schema Validation** - Check column presence and types

### Test Organization

```
tests/
├── test_aggregations_core.py        # Core aggregation functions
├── test_aggregate_drives_minimal.py # Drive-level aggregations
├── test_validation.py               # Schema validation
└── fixtures/                        # Shared test data
```

**Pattern:** Use `tests/test_aggregate_drives_minimal.py` as template for new tests.

---

## Betting Policy

**Location:** `docs/modeling/betting_policy.md`

### Key Rules

1. **Kelly Criterion** for bet sizing
2. **Minimum edge threshold:** 2.5% for spreads, 3% for totals
3. **Maximum bet size:** 5% of bankroll
4. **Game minimums:** Teams must have ≥4 games for adjusted stats
5. **No betting on:** Teams without sufficient data, games with missing lines

**IMPORTANT:** Policy is defined in documentation, NOT in code. Scripts only **apply** policy rules, never modify them.

---

## Project-Specific Details

### Year 2020 Exclusion

**COVID-affected 2020 season is excluded from training** due to:
- Schedule disruptions
- Roster changes (opt-outs, transfers)
- Limited/no fans (home field advantage distorted)
- Inconsistent COVID protocols

**Use:** `train_years: [2019, 2021, 2022, 2023]`

### Adjustment Iterations

Different depths for offense/defense:

```yaml
adjustment_iteration: 2              # Default for both
adjustment_iteration_offense: 3      # Override for offense
adjustment_iteration_defense: 2      # Override for defense
```

**Typical values:** 2-4 iterations (more iterations = more convergence, but diminishing returns)

### Feature Set IDs

- `standard_v1` - Core efficiency metrics
- `recency_v1` - Standard + recency-weighted features
- `pace_v1` - Standard + tempo/pace features
- `spread_shap_pruned` - Pruned via SHAP analysis (best for spreads)

---

## Development Standards

### Code Style

- **Formatter:** ruff format
- **Linter:** ruff check
- **Line length:** 88 characters (Black-compatible)
- **Type hints:** Encouraged but not required
- **Docstrings:** Required for public functions

### Testing Requirements

- All aggregation functions must have unit tests
- Test edge cases (empty data, single row, missing columns)
- Minimum 80% coverage on critical paths

### Feature Development

1. Add feature computation to `src/features/core.py` or `byplay.py`
2. Create feature config in `conf/features/new_feature_v1.yaml`
3. Add unit tests
4. Run ablation study to validate impact
5. Update `docs/modeling/features.md`

---

## Common Workflows

### Adding a New Feature

1. **Define computation** in `src/features/core.py`
2. **Add to config** in `conf/features/`
3. **Test** with minimal fixture
4. **Validate impact** with ablation study
5. **Document** in `docs/modeling/features.md`

### Training a New Model

1. **Create config** in `conf/model/new_model.yaml`
2. **Create Optuna space** in `conf/tuning/new_model_optuna.yaml`
3. **Run optimization** with `mode=optimize`
4. **Evaluate** on walk-forward validation
5. **Document** findings in decision log

### Production Deployment

1. **Train production models:**
   ```bash
   PYTHONPATH=. uv run python scripts/pipeline/train_production_points_for.py
   ```

2. **Generate weekly predictions:**
   ```bash
   PYTHONPATH=. uv run python scripts/pipeline/generate_weekly_bets.py
   ```

3. **Review predictions** (manual step)

4. **Place bets** (manual step)

5. **Score performance:**
   ```bash
   PYTHONPATH=. uv run python scripts/pipeline/score_weekly_bets.py
   ```

---

## Key Concepts

### Point-in-Time Data

**Problem:** When training on historical data, only use information that was available at prediction time.

**Solution:** `load_point_in_time_data()` ensures:
- Training data precedes test data
- No future information leaks into features
- Strict temporal separation

### Opponent-Adjusted Stats

**Raw stats are misleading** - a team averaging 35 points/game against weak defenses is different from 35 points/game against strong defenses.

**Adjustment process:**
1. Calculate team averages (raw)
2. Calculate opponent averages (what they typically allow)
3. Adjust team stats based on opponent quality
4. Iterate 2-4 times until convergence

### Kelly Criterion

**Bet sizing formula:**
```
fraction = (edge × odds) / (odds - 1)
```

Where:
- `edge` = model probability - implied market probability
- `odds` = decimal odds

**Example:**
- Model: 55% win probability
- Line: -110 (52.38% implied probability)
- Edge: 2.62%
- Kelly: ~2.6% of bankroll

---

_Last Updated: 2026-02-13_
_Domain knowledge and architecture reference_
