# Data Quality Framework

**Purpose**: Ensure data integrity throughout the pipeline  
**Timeline**: Weeks 3-4 of V2 implementation  
**Status**: To be implemented

---

## Overview

**Philosophy**: "Garbage in, garbage out." We must validate data at every stage before trusting experiment results.

**Approach**: 3-layer validation system

1. **Ingestion**: Validate raw data from CFBD API
2. **Aggregation**: Validate processed data (team_game, team_season)
3. **Features**: Validate feature distributions before modeling

---

## Layer 1: Ingestion Validation

**Script**: `scripts/validation/validate_ingestion.py`  
**When**: After `scripts/ingestion/ingest_XXXX.py`  
**Goal**: Catch API changes or data corruption early

### Checks

#### 1. Schema Validation

**Requirement**: All expected columns present with correct types

```python
def validate_schema(df, expected_schema):
    """Check that dataframe matches expected schema."""
    missing_cols = set(expected_schema.keys()) - set(df.columns)
    if missing_cols:
        raise ValueError(f"Missing columns: {missing_cols}")

    for col, expected_type in expected_schema.items():
        if df[col].dtype != expected_type:
            raise TypeError(f"Column {col}: expected {expected_type}, got {df[col].dtype}")
```

**Expected Schemas**:

- `raw/plays`: See `docs/data/schema/raw_plays.md`
- `raw/games`: See `docs/data/schema/raw_games.md`

#### 2. Null Checks

**Requirement**: Critical fields must be non-null

```python
CRITICAL_FIELDS = [
   'game_id', 'season', 'week', 'home_team', 'away_team',
    'play_number', 'offense', 'defense', 'yards_gained'
]

def validate_nulls(df):
    """Check critical fields for nulls."""
    for field in CRITICAL_FIELDS:
        null_count = df[field].isnull().sum()
        if null_count > 0:
            raise ValueError(f"{field} has {null_count} null values")
```

#### 3. Range Checks

**Requirement**: Numeric fields within plausible bounds

```python
RANGE_CHECKS = {
    'yards_gained': (-50, 100),
    'down': (1, 4),
    'distance': (0, 100),
    'ppa': (-10, 10),  # EPA per play
}

def validate_ranges(df):
    """Check numeric fields are in valid ranges."""
    for field, (min_val, max_val) in RANGE_CHECKS.items():
        if field in df.columns:
            invalid = df[(df[field] < min_val) | (df[field] > max_val)]
            if len(invalid) > 0:
                print(f"WARNING: {len(invalid)} rows with {field} out of range")
```

---

## Layer 2: Aggregation Validation

**Script**: `scripts/validation/validate_aggregation.py`  
**When**: After `scripts/pipeline/run_pipeline_generic.py`  
**Goal**: Ensure aggregation logic is correct

### Checks

#### 1. Distribution Checks

**Requirement**: Aggregated stats within historical ranges

```python
# Historical means from 2019-2023 data
HISTORICAL_MEANS = {
    'off_epa_pp': 0.1,  # Mean ~0.1, σ ~0.3
    'off_sr': 0.45,     # Mean ~0.45, σ ~0.05
    'off_ypp': 5.5,     # Mean ~5.5, σ ~0.8
}

def validate_distributions(team_season_df):
    """Check team_season stats are within 3σ of historical mean."""
    for col, historical_mean in HISTORICAL_MEANS.items():
        if col in team_season_df.columns:
            actual_mean = team_season_df[col].mean()
            if abs(actual_mean - historical_mean) > 1.0:  # Rough check
                print(f"WARNING: {col} mean is {actual_mean} (expected ~{historical_mean})")
```

#### 2. Completeness Checks

**Requirement**: All expected teams present

```python
def validate_completeness(team_season_df, year):
    """Check that all FBS teams are present."""
    expected_teams = 130  # FBS has ~130 teams
    actual_teams = team_season_df['team'].nunique()

    if actual_teams < expected_teams * 0.9:  # Allow 10% margin
        print(f"WARNING: Only {actual_teams} teams found (expected ~{expected_teams})")
```

#### 3. Outlier Detection

**Requirement**: Flag extreme values for manual review

```python
def detect_outliers(team_season_df, cols=['off_epa_pp', 'def_epa_pp']):
    """Find teams with stats >3σ from mean."""
    for col in cols:
        if col in team_season_df.columns:
            mean = team_season_df[col].mean()
            std = team_season_df[col].std()
            outliers = team_season_df[
                (team_season_df[col] < mean - 3*std) |
                (team_season_df[col] > mean + 3*std)
            ]
            if len(outliers) > 0:
                print(f"OUTLIERS in {col}:")
                print(outliers[['team', col]])
```

---

## Layer 3: Feature Validation

**Script**: `scripts/validation/validate_features.py`  
**When**: Before running experiments  
**Goal**: Detect feature drift that could break models

### Checks

#### 1. Feature Drift (KS Test)

**Requirement**: Feature distributions shouldn't change dramatically year-to-year

```python
from scipy.stats import ks_2samp

def test_feature_drift(baseline_df, current_df, features):
    """KS test for feature distribution drift."""
    drift_report = []

    for feature in features:
        if feature in baseline_df.columns and feature in current_df.columns:
            statistic, p_value = ks_2samp(
                baseline_df[feature].dropna(),
                current_df[feature].dropna()
            )
            drift_report.append({
                'feature': feature,
                'ks_statistic': statistic,
                'p_value': p_value,
                'drifted': p_value < 0.05  # Significant drift
            })

    return pd.DataFrame(drift_report)
```

**Baseline**: Use 2024 data as reference  
**Threshold**: p < 0.05 indicates significant drift

#### 2. Correlation Checks

**Requirement**: Features shouldn't be perfectly correlated

```python
def check_correlations(df, features, threshold=0.95):
    """Find highly correlated feature pairs."""
    corr_matrix = df[features].corr()
    high_corr = []

    for i in range(len(features)):
        for j in range(i+1, len(features)):
            if abs(corr_matrix.iloc[i, j]) > threshold:
                high_corr.append({
                    'feature_1': features[i],
                    'feature_2': features[j],
                    'correlation': corr_matrix.iloc[i, j]
                })

    if len(high_corr) > 0:
        print(f"WARNING: {len(high_corr)} feature pairs with r > {threshold}")
        return pd.DataFrame(high_corr)
```

#### 3. Missing Value Report

**Requirement**: Document missingness patterns

```python
def missing_value_report(df):
    """Report % missing for each column."""
    missing = df.isnull().sum() / len(df) * 100
    missing = missing[missing > 0].sort_values(ascending=False)

    if len(missing) > 0:
        print("Missing Value Report:")
        for col, pct in missing.items():
            print(f"  {col}: {pct:.1f}%")
```

---

## Integration into Pipeline

### Updated Pipeline Flow

```bash
# Week 3-4: Add validation calls

# 1. Ingest raw data
uv run python scripts/ingestion/ingest_plays.py --year 2024

# 2. VALIDATE ingestion
uv run python scripts/validation/validate_ingestion.py --year 2024
# ✅ Schema, nulls, ranges checked

# 3. Run aggregation
uv run python scripts/pipeline/run_pipeline_generic.py --year 2024

# 4. VALIDATE aggregation
uv run python scripts/validation/validate_aggregation.py --year 2024
# ✅ Distributions, completeness, outliers checked

# 5. Before training, VALIDATE features
uv run python scripts/validation/validate_features.py \
    --baseline 2024 --current 2025 --features minimal_unadjusted_v1
# ✅ Drift, correlations, missingness checked
```

---

## Validation Report Template

**Output**: `artifacts/validation/validation_report_YYYY-MM-DD.txt`

```
=== Data Quality Validation Report ===
Date: 2025-12-15
Year: 2024

Layer 1: Ingestion
  ✅ Schema valid (all 45 columns present)
  ✅ No nulls in critical fields
  ⚠️  3 plays with yards_gained out of range [-50, 100]

Layer 2: Aggregation
  ✅ 128 teams found (expected ~130)
  ✅ off_epa_pp mean = 0.11 (within range)
  ⚠️  Outlier: Georgia off_epa_pp = 0.95 (+3.2σ)

Layer 3: Features
  ✅ No significant feature drift (all p > 0.05)
  ✅ No perfect correlations (max r = 0.82)
  ✅ Missing values: off_avg_net_punt_yards 2.3%

Overall: ✅ PASS (minor warnings, safe to proceed)
```

---

## Implementation Timeline

### Week 3: Build Validation Scripts

- [ ] Create `scripts/validation/validate_ingestion.py`
- [ ] Create `scripts/validation/validate_aggregation.py`
- [ ] Create `scripts/validation/validate_features.py`
- [ ] Test on 2024 data

### Week 4: Integrate into Pipeline

- [ ] Add validation calls to `run_pipeline_generic.py`
- [ ] Re-run pipeline for all years (2019, 2021-2024)
- [ ] Fix any data quality issues discovered
- [ ] Generate validation reports for all years

---

## Future Enhancements

- [ ] Automated daily data quality checks (cron job)
- [ ] Email alerts for failed validations
- [ ] Historical trend tracking (drift over multiple years)
- [ ] Schema evolution tracking (API changes)

---

## Note on docs/data/ Audit

**Deferred**: Full audit of `docs/data/` directory (17 files) is deferred until data ingestion pipeline work.

**Current Status**: Contains guides, pipeline overview, API info, and schemas.

**Future Work**: During Week 3-4, review and consolidate:

- Merge redundant ingestion guides
- Update pipeline_overview.md with validation steps
- Ensure schemas match current CFBD API

---

**Last Updated**: 2025-12-05  
**Status**: Design complete, implementation pending Weeks 3-4
