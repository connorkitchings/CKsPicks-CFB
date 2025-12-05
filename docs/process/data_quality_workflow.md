# Data Quality Validation Workflow

**Status**: Proposed | **Version**: 1.0 | **Date**: 2025-12-05

This document specifies the automated process for validating the quality, correctness, and integrity of the aggregated datasets before they are used for feature engineering or modeling. Its goal is to catch data issues early and prevent corrupted data from silently degrading model performance.

This workflow is a prerequisite for all other processes in the [Experimentation Workflow](./experimentation_workflow.md).

---

## Guiding Principles

1.  **Trust, but Verify**: Never assume upstream data is clean. Always run checks after ingestion and aggregation.
2.  **Fail Fast**: The pipeline should stop immediately if a critical data quality check fails, preventing bad data from propagating.
3.  **Automate Everything**: Data quality checks must be automated and run as a standard part of the data pipeline.
4.  **Report Clearly**: When a check fails, the output report should make it easy to diagnose the root cause.

---

## The Validation Process

This process will be executed by a new script, `scripts/pipeline/validate_data.py`, which will run automatically after the main data aggregation step.

### Step 1: Schema and Structure Validation

This step ensures the dataset's structure is correct.

1.  **Required Columns**: Verify that all expected columns are present in the dataset. The list of required columns will be defined in a configuration file.
2.  **Data Types**: Check that each column has the correct data type (e.g., `float64`, `int64`, `object`).
3.  **Uniqueness**: Ensure the primary key of the dataset (e.g., `game_id` + `team`) is unique.

### Step 2: Data Integrity and Sanity Checks

This step validates the actual values within the dataset. The checks will be configured with sensible, pre-defined thresholds.

1.  **Null Value Checks**:
    *   Fail if critical identifier columns (e.g., `game_id`, `team`, `year`, `week`) contain any null values.
    *   Warn if key feature columns have a percentage of nulls exceeding a defined threshold (e.g., > 5%).

2.  **Range Checks**:
    *   Verify that key metrics fall within realistic ranges. For example:
        *   Success Rate (`sr`): `0.0` to `1.0`
        *   EPA per Play (`epa_pp`): `-10.0` to `10.0`
        *   Yards per Play (`ypp`): `-20.0` to `100.0`
    *   These ranges will be configurable.

3.  **Categorical Value Checks**:
    *   For key categorical columns (e.g., `conference`), verify that the values belong to a predefined set of accepted values. This catches issues like new or misspelled conference names.

4.  **Consistency Checks**:
    *   Verify that for any given game, the stats for the home team and away team are consistent (e.g., `home_team_yards` should have a corresponding `away_team_yards_allowed`).
    *   Ensure the number of games per week and teams per season falls within a normal range, flagging unusual drops or spikes.

### Step 3: Reporting and Alerting

The output of the validation script will determine the next steps in the pipeline.

1.  **On Success**:
    *   The script will log a success message.
    *   It will output a `data_quality_report.json` artifact containing the summary of checks passed.
    *   The main data pipeline will proceed to the next step (feature engineering/modeling).

2.  **On Warning**:
    *   If a non-critical check fails (e.g., a feature has >5% nulls), the script will log a prominent warning message.
    *   The pipeline will be allowed to continue, but the warning should be reviewed by a developer.

3.  **On Failure**:
    *   If a critical check fails (e.g., nulls in `game_id`, a metric outside its valid range), the script will raise an exception and exit with a non-zero status code.
    *   The main data pipeline **must stop immediately**.
    *   The error message will clearly state which check failed and why, providing context to help with debugging (e.g., "Check failed: `off_sr` out of range [0, 1]. Found value: 1.02 in game_id: 12345").

---

## How to Use

The validation workflow is designed to be run from the command line after the data aggregation pipeline has completed.

### Prerequisites

1.  **Environment Variables**: Ensure your `.env` file is configured with the `CFB_MODEL_DATA_ROOT` variable pointing to your data directory. The validation script uses this to find the data.
2.  **Aggregated Data**: You must have already run the aggregation pipeline (e.g., via `uv run python scripts/pipeline/run_pipeline_generic.py --year YYYY`) to generate the `processed` data.
3.  **Consolidated Data File**: The validation script runs on a single data file. You may need to consolidate the partitioned data first using a helper script like `scripts/consolidate_data.py`.

### Running the Validator

To run the validation suite, execute the `validate_data.py` script, providing the path to the configuration file, the dataset you want to test, and the name of the validation suite to use from the config.

**Example:**

```bash
# This command validates the consolidated 2023 team_game data
uv run python scripts/pipeline/validate_data.py \
  --config conf/validation.yaml \
  --dataset team_game_2023.parquet \
  --dataset-name team_game
```

If validation succeeds, the script will exit with a code 0. If it fails, it will print a descriptive error message and exit with a code 1, which can be used to halt an automated pipeline.

