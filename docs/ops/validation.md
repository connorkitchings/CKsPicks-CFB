# Data Validation Service

## Overview

The `DataValidationService` provides configuration-driven data quality validation for the CFB model pipeline. It combines schema validation (fast, config-driven checks) with deep semantic validation (slower, comprehensive checks).

## Quick Start

### Using the CLI

**Note:** Run the validation module using Python's `-m` flag to avoid import conflicts:

```bash
# Basic validation for a season
PYTHONPATH=. uv run python -m src.utils.validation --year 2024 --data-type processed

# Schema-only validation (fast)
PYTHONPATH=. uv run python -m src.utils.validation --year 2024 --data-type processed --schema-only

# Deep validation (includes semantic checks)
PYTHONPATH=. uv run python -m src.utils.validation --year 2024 --data-type processed --deep

# Validate raw data
PYTHONPATH=. uv run python -m src.utils.validation --year 2024 --data-type raw
```

### Using the Service in Code

```python
from src.utils.validation import get_validation_service

# Create service instance
service = get_validation_service(data_type="processed")

# Validate a specific entity
issues = service.validate_entity(
    year=2024,
    entity="team_game",
    key_columns=["game_id", "team"],
    schema_only=False  # Set to True for schema-only validation
)

# Validate entire season
issues = service.validate_processed_season(year=2024)

# Check for errors
errors = [iss for iss in issues if iss.level == "ERROR"]
if errors:
    for err in errors:
        print(f"[{err.entity}] {err.message}")
```

## Validation Layers

The validation service uses a **layered approach** for optimal performance:

### Layer 1: Schema Validation (Fast)
- **Purpose:** Catch basic data quality issues quickly
- **Speed:** <1s for typical dataset
- **Checks:**
  - Required columns presence
  - Critical null checks (0% nulls allowed)
  - Warning null checks (threshold-based)
  - Range validation (min/max bounds)
  - Uniqueness constraints

### Layer 2: Manifest/Duplicate Checks
- **Purpose:** Verify data integrity across partitions
- **Speed:** Medium (reads manifests, samples data)
- **Checks:**
  - Manifest row counts match CSV rows
  - Duplicate detection on key columns

### Layer 3: Deep Semantic Validation (Slow)
- **Purpose:** Comprehensive cross-entity consistency checks
- **Speed:** Slow (full data reads, complex aggregations)
- **Checks:**
  - Drives consistency (plays aggregate to drives)
  - Team-game consistency (drives aggregate to team-game)
  - Team-season consistency (team-game aggregates to team-season)
  - Opponent adjustment consistency
  - Box score comparison (if raw data available)

## Configuration Reference

### validation.yaml Structure

Validation rules are defined in `conf/validation.yaml`:

```yaml
validation:
  entity_name:
    required_columns:
      - column1
      - column2

    uniqueness_columns:
      - key_column1
      - key_column2

    null_checks:
      critical_null_checks:
        - column_with_no_nulls_allowed
      warning_null_checks:
        column_name: 5.0  # Max null percentage threshold

    range_checks:
      numeric_column:
        min: 0.0
        max: 100.0
```

### Example: team_game Validation

```yaml
validation:
  team_game:
    required_columns:
      - season
      - week
      - game_id
      - team
      - n_off_plays
      - off_sr
      - off_ypp

    uniqueness_columns:
      - season
      - week
      - game_id
      - team

    null_checks:
      critical_null_checks:
        - season
        - week
        - game_id
        - team
      warning_null_checks:
        off_epa_pp: 5.0  # Allow up to 5% nulls
        temperature: 10.0  # Weather can be missing

    range_checks:
      off_sr: {min: 0.0, max: 1.0}
      off_ypp: {min: -20.0, max: 100.0}
      n_off_plays: {min: 10, max: 150}
```

## Extending Validation Rules

### Adding a New Entity

1. **Define validation rules** in `conf/validation.yaml`:

```yaml
validation:
  my_entity:
    required_columns:
      - id
      - name
    uniqueness_columns:
      - id
    null_checks:
      critical_null_checks:
        - id
    range_checks:
      score: {min: 0, max: 100}
```

2. **Test the configuration:**

```python
from src.utils.validation import get_validation_service
import pandas as pd

service = get_validation_service()

# Create test data
df = pd.DataFrame({
    "id": [1, 2, 3],
    "name": ["A", "B", "C"],
    "score": [85, 92, 105]  # 105 exceeds max
})

# Validate
issues = service.validate_schema(df, "my_entity")
print(f"Found {len(issues)} issues")
```

3. **Add to entity validation** in `validate_processed_season()` or CLI.

### Custom Validation Rules

For validation logic beyond YAML configuration, add methods to `DataValidationService`:

```python
class DataValidationService:
    # ...existing methods...

    def validate_custom_logic(self, df: pd.DataFrame) -> list[ValidationIssue]:
        """Custom validation logic beyond schema checks."""
        issues = []

        # Example: Check that offense != defense
        if (df["offense"] == df["defense"]).any():
            issues.append(ValidationIssue(
                "ERROR",
                "Found rows where offense == defense",
                entity="drives"
            ))

        return issues
```

## ValidationIssue Levels

Issues are categorized by severity:

- **ERROR**: Data quality problem that must be fixed
  - Missing required columns
  - Null in critical column
  - Values out of range
  - Duplicate key violations

- **WARN**: Data quality concern that should be reviewed
  - Null percentage exceeds threshold
  - Unexpected but not invalid values

- **INFO**: Informational message
  - No data found (expected for some entities/years)
  - Validation skipped due to missing dependencies

## Structured Logging

The service logs all validation events to `data_pipeline.log` in JSON format:

```json
{
  "timestamp": "2024-12-10T10:30:45.123456",
  "level": "INFO",
  "event_type": "validation_entity_start",
  "metadata": {
    "year": 2024,
    "entity": "team_game",
    "key_columns": ["game_id", "team"]
  }
}
```

### Log Event Types

- `validation_service_initialized`: Service created
- `validation_entity_start`: Entity validation started
- `validation_entity_partitions`: Partition discovery
- `validation_entity_complete`: Entity validation finished
- `validation_season_start`: Season validation started
- `validation_season_complete`: Season validation finished
- `schema_validation_failed`: Schema validation error
- `validation_config_missing`: Config file not found
- `validation_config_load_failed`: Config parsing error

### Querying Logs

```bash
# Find all validation errors for team_game
cat data_pipeline.log | jq 'select(.event_type | contains("validation")) | select(.metadata.entity == "team_game")'

# Count validation events by type
cat data_pipeline.log | jq -r '.event_type' | sort | uniq -c
```

## Performance Optimization

### Use Schema-Only for Quick Checks

For rapid validation during development:

```bash
# Fast: Schema validation only (~1s)
PYTHONPATH=. uv run python -m src.utils.validation --year 2024 --schema-only

# Slow: Full deep validation (~30s)
PYTHONPATH=. uv run python -m src.utils.validation --year 2024 --deep
```

### Validate Incrementally

```python
# Validate only specific entities
service = get_validation_service()

# Just validate team_game
issues = service.validate_entity(
    year=2024,
    entity="team_game",
    key_columns=["game_id", "team"]
)
```

### Sample Data for Schema Checks

Schema validation only reads first 1000 rows per partition for speed:

```python
# In validate_schema()
df = pd.read_csv(csv_path, nrows=1000)  # Sample for schema check
```

## Common Validation Patterns

### After Data Ingestion

```bash
# Validate newly ingested raw data
PYTHONPATH=. uv run python -m src.utils.validation --year 2024 --data-type raw

# Validate processed aggregations
PYTHONPATH=. uv run python -m src.utils.validation --year 2024 --data-type processed --schema-only
```

### Before Model Training

```python
from src.utils.validation import get_validation_service

# Validate training data
service = get_validation_service(data_type="processed")
issues = service.validate_processed_season(year=2024)

errors = [iss for iss in issues if iss.level == "ERROR"]
if errors:
    raise ValueError(f"Validation failed with {len(errors)} errors")

# Proceed with training
```

### CI/CD Integration

```bash
#!/bin/bash
# validate_data.sh - Run as part of CI/CD pipeline

set -e

YEAR=${1:-2024}

echo "Running schema validation for year $YEAR..."
PYTHONPATH=. uv run python -m src.utils.validation \
    --year $YEAR \
    --data-type processed \
    --schema-only

if [ $? -ne 0 ]; then
    echo "ERROR: Schema validation failed"
    exit 1
fi

echo "✅ Validation passed"
```

## Troubleshooting

### Config Not Found

**Problem:** `Config file not found: /path/to/conf/validation.yaml`

**Solution:**
```python
from pathlib import Path
from src.utils.validation import DataValidationService

# Provide explicit config path
config_path = Path("/custom/path/to/validation.yaml")
service = DataValidationService(storage, config_path=config_path)
```

### High Null Percentages

**Problem:** Warning null checks failing frequently

**Solution:** Adjust thresholds in `validation.yaml`:

```yaml
warning_null_checks:
  temperature: 15.0  # Increase from 10.0 to 15.0
```

### Range Check False Positives

**Problem:** Valid values flagged as out-of-range

**Solution:** Widen range bounds:

```yaml
range_checks:
  off_ypp: {min: -30.0, max: 120.0}  # Wider bounds
```

### Missing Entities in Config

**Problem:** `No validation config found for entity 'custom_entity'`

**Solution:** Add entity to `conf/validation.yaml` or handle the warning:

```python
issues = service.validate_schema(df, "custom_entity")
# Filter out "No validation config" warnings if expected
issues = [iss for iss in issues if "No validation config" not in iss.message]
```

## Best Practices

1. **Run schema validation first** - Catch basic issues before expensive deep checks
2. **Update config with data evolution** - Add new entities/columns as pipeline grows
3. **Monitor validation logs** - Track validation failures over time
4. **Set appropriate thresholds** - Balance strictness with real-world data quality
5. **Automate validation** - Include in CI/CD pipeline and data refresh workflows
6. **Document exceptions** - If widening ranges, document why in config comments

## Related Documentation

- `src/utils/validation.py` - Implementation
- `conf/validation.yaml` - Configuration
- `tests/test_validation.py` - Test examples
- [Data Pipeline Overview](../data/pipeline_overview.md) - Upstream data flow
- [Monitoring Dashboard](./monitoring.md) - Operational observability

---

_Last Updated: 2026-02-10_
