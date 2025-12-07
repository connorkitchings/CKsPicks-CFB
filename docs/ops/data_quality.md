# Data Quality Framework

**Status**: Active (Week 3 Implementation)  
**Owners**: Ops Team

The Data Quality Framework ensures that all data feeding into the V2 modeling pipeline is valid, complete, and reliable. It consists of a 3-layer validation system implemented in Python scripts.

---

## 🏗️ 3-Layer Validation

### 1. Ingestion Validation (`validate_ingestion.py`)

Checks the raw data fetched from CFBD.

- **Scope**: `raw/games` and `raw/betting_lines` artifacts.
- **Checks**:
  - Schema: Required columns (`game_id`, `home_team`, `scores`) present.
  - Completeness: No missing games or massive gaps.
  - Validity: Scores >= 0, Spreads within reasonable range (-70 to 70).
  - Uniqueness: No duplicate `game_id`s.

### 2. Aggregation Validation (`validate_aggregation.py`)

Checks the processed team statistics before they are merged into games.

- **Scope**: `processed/team_week_adj` artifacts.
- **Checks**:
  - Schema: EPA and Success Rate columns present.
  - Completeness: All teams have stats for all weeks played.
  - Outliers: EPA per play within [-1.5, 1.5].
  - Uniqueness: No duplicate `team-season-week` entries.

### 3. Feature Validation (`validate_features.py`)

Checks the final merged dataset ready for training.

- **Scope**: Output of `load_v1_data()`.
- **Checks**:
  - Integrity: `spread_target` matches score diffs.
  - NaN/Inf: No invalid values in feature columns.
  - Alignment: Game dates match stat weeks.
  - Correlation: Sanity check that features correlate with targets.

---

## 🏃 Usage

Run validation manually for a specific year:

```bash
# Validate Raw Ingestion
PYTHONPATH=. uv run python scripts/validation/validate_ingestion.py --year 2024

# Validate Aggregation
PYTHONPATH=. uv run python scripts/validation/validate_aggregation.py --year 2024

# Validate Features
PYTHONPATH=. uv run python scripts/validation/validate_features.py --year 2024
```

---

## 🚨 Troubleshooting

| Error                              | Common Cause                | Fix                                                |
| :--------------------------------- | :-------------------------- | :------------------------------------------------- |
| `[Games] Negative scores detected` | Bad CFBD data               | Check specific game ID, exclude or patch data.     |
| `[Aggregation] Missing columns`    | Pipeline aggregation failed | Re-run `scripts/pipeline/run_pipeline_generic.py`. |
| `[Features] NaN or Infinite`       | Division by zero in stats   | Check play-by-play data for empty drives.          |
