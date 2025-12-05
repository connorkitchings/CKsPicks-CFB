"""
Data Quality Validation Script

This script implements the checks outlined in the Data Quality Validation Workflow.
It is designed to be run after data aggregation to ensure the integrity of the
datasets before they are used for feature engineering or modeling.
"""

import argparse
import sys
from typing import Any, Dict, List

import pandas as pd
import yaml


class DataValidationError(Exception):
    """Custom exception for data validation errors."""

    pass


def load_config(config_path: str) -> Dict[str, Any]:
    """Loads the validation configuration from a YAML file."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def check_required_columns(df: pd.DataFrame, columns: List[str], dataset_name: str):
    """Checks if all required columns are present in the DataFrame."""
    missing_columns = [col for col in columns if col not in df.columns]
    if missing_columns:
        raise DataValidationError(
            f"[{dataset_name}] Missing required columns: {', '.join(missing_columns)}"
        )
    print(f"  ✅ [{dataset_name}] All required columns are present.")


def check_uniqueness(df: pd.DataFrame, columns: List[str], dataset_name: str):
    """Checks for uniqueness of rows based on a set of columns."""
    if df.duplicated(subset=columns).any():
        raise DataValidationError(
            f"[{dataset_name}] Duplicate rows found based on columns: {', '.join(columns)}"
        )
    print(
        f"  ✅ [{dataset_name}] Uniqueness check passed for columns: {', '.join(columns)}."
    )


def check_null_values(df: pd.DataFrame, config: Dict[str, Any], dataset_name: str):
    """Checks for null values in specified columns."""
    critical_null_checks = config.get("critical_null_checks", [])
    for col in critical_null_checks:
        if col in df.columns and df[col].isnull().any():
            raise DataValidationError(
                f"[{dataset_name}] Found null values in critical column: '{col}'"
            )

    warning_null_checks = config.get("warning_null_checks", {})
    for col, threshold in warning_null_checks.items():
        if col in df.columns:
            null_percentage = df[col].isnull().mean() * 100
            if null_percentage > threshold:
                print(
                    f"  ⚠️  [{dataset_name}] Warning: Column '{col}' has {null_percentage:.2f}% "
                    f"null values, which exceeds the threshold of {threshold}%."
                )
    print(f"  ✅ [{dataset_name}] Null value checks passed.")


def check_range_values(df: pd.DataFrame, config: Dict[str, Any], dataset_name: str):
    """Checks if column values fall within a specified range."""
    for col, ranges in config.items():
        if col in df.columns:
            min_val, max_val = ranges["min"], ranges["max"]
            # Using .between correctly handles numeric types
            if not df[col].dropna().between(min_val, max_val).all():
                offending_values = df[~df[col].between(min_val, max_val)][col]
                raise DataValidationError(
                    f"[{dataset_name}] Column '{col}' has values outside the expected "
                    f"range [{min_val}, {max_val}]. Offending values: {offending_values.tolist()}"
                )
    print(f"  ✅ [{dataset_name}] Range checks passed.")


def check_categorical_values(
    df: pd.DataFrame, config: Dict[str, Any], dataset_name: str
):
    """Checks if categorical column values are in the set of accepted values."""
    if not config:
        print(f"  ✅ [{dataset_name}] No categorical value checks configured.")
        return

    for col, accepted_values in config.items():
        if col in df.columns:
            unique_values = df[col].dropna().unique()
            unknown_values = [v for v in unique_values if v not in accepted_values]
            if unknown_values:
                raise DataValidationError(
                    f"[{dataset_name}] Column '{col}' has unknown categorical values: "
                    f"{', '.join(map(str, unknown_values))}"
                )
    print(f"  ✅ [{dataset_name}] Categorical value checks passed.")


def run_validation_suite(df: pd.DataFrame, config: Dict[str, Any], dataset_name: str):
    """Runs all configured validation checks on a DataFrame."""
    print(f"\nRunning validation suite for '{dataset_name}'...")

    if "required_columns" in config:
        check_required_columns(df, config["required_columns"], dataset_name)
    if "uniqueness_columns" in config:
        check_uniqueness(df, config["uniqueness_columns"], dataset_name)
    if "null_checks" in config:
        check_null_values(df, config["null_checks"], dataset_name)
    if "range_checks" in config:
        check_range_values(df, config["range_checks"], dataset_name)
    if "categorical_checks" in config:
        check_categorical_values(df, config["categorical_checks"], dataset_name)

    print(f"🎉 Successfully validated '{dataset_name}'.")


def main():
    parser = argparse.ArgumentParser(description="Data Quality Validation Script")
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Path to the validation config YAML file.",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        required=True,
        help="Path to the dataset Parquet file to validate.",
    )
    parser.add_argument(
        "--dataset-name",
        type=str,
        required=True,
        help="Name of the dataset for reporting.",
    )
    args = parser.parse_args()

    try:
        print(f"Loading config from {args.config}...")
        config = load_config(args.config)

        print(f"Loading dataset from {args.dataset}...")
        df = pd.read_parquet(args.dataset)

        validation_config = config.get("validation", {}).get(args.dataset_name)
        if not validation_config:
            raise ValueError(
                f"No validation configuration found for '{args.dataset_name}' in {args.config}"
            )

        run_validation_suite(df, validation_config, args.dataset_name)

    except (FileNotFoundError, ValueError, DataValidationError) as e:
        print(f"\n❌ Data validation failed: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
