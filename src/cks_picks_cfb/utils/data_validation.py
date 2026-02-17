"""Data validation utilities for statistical quality checks.

Provides multi-layer validation for ingested and processed data:
1. Schema validation (required columns, data types)
2. Completeness validation (expected years/weeks present)
3. Statistical validation (outlier detection with thresholds)
4. Integrity validation (referential integrity)
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class ValidationResult:
    """Result of a validation check."""

    check_name: str
    passed: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    severity: str = "warning"  # info, warning, error


@dataclass
class ValidationReport:
    """Complete validation report for an entity."""

    entity: str
    results: list[ValidationResult] = field(default_factory=list)
    total_checks: int = 0
    passed: int = 0
    warnings: int = 0
    errors: int = 0

    def add_result(self, result: ValidationResult) -> None:
        """Add a validation result."""
        self.results.append(result)
        self.total_checks += 1
        if result.passed:
            self.passed += 1
        elif result.severity == "error":
            self.errors += 1
        else:
            self.warnings += 1

    def summary(self) -> str:
        """Return summary string."""
        return (
            f"{self.entity}: {self.passed}/{self.total_checks} passed, "
            f"{self.warnings} warnings, {self.errors} errors"
        )


def detect_outliers_iqr(
    df: pd.DataFrame, column: str, threshold_multiplier: float = 3.0
) -> pd.Series:
    """Detect outliers using IQR method with configurable threshold.

    Args:
        df: DataFrame to check
        column: Column name to check
        threshold_multiplier: IQR multiplier for outlier threshold (default 3.0)

    Returns:
        Boolean Series where True indicates an outlier
    """
    if column not in df.columns:
        return pd.Series([False] * len(df), index=df.index)

    values = df[column].dropna()
    if len(values) < 4:
        return pd.Series([False] * len(df), index=df.index)

    q1 = values.quantile(0.25)
    q3 = values.quantile(0.75)
    iqr = q3 - q1
    lower_bound = q1 - (threshold_multiplier * iqr)
    upper_bound = q3 + (threshold_multiplier * iqr)

    outliers = (df[column] < lower_bound) | (df[column] > upper_bound)
    return outliers.fillna(False)


def validate_schema(
    df: pd.DataFrame,
    required_columns: list[str],
    optional_columns: list[str] | None = None,
) -> ValidationResult:
    """Validate DataFrame has required columns.

    Args:
        df: DataFrame to validate
        required_columns: Columns that must be present
        optional_columns: Columns that should ideally be present

    Returns:
        ValidationResult object
    """
    missing = [c for c in required_columns if c not in df.columns]
    missing_optional = (
        [c for c in (optional_columns or []) if c not in df.columns]
        if optional_columns
        else []
    )

    passed = len(missing) == 0
    message = f"Missing {len(missing)} required columns: {missing}"
    if missing_optional:
        message += f"; missing {len(missing_optional)} optional: {missing_optional}"

    if not passed:
        severity = "error"
    elif missing_optional:
        severity = "warning"
    else:
        message = "All required columns present"
        severity = "info"

    return ValidationResult(
        check_name="schema_validation",
        passed=passed,
        message=message,
        details={
            "missing_required": missing,
            "missing_optional": missing_optional,
            "actual_columns": list(df.columns),
        },
        severity=severity,
    )


def validate_completeness(
    df: pd.DataFrame,
    year_column: str = "year",
    week_column: str | None = None,
    expected_years: list[int] | None = None,
    expected_weeks: dict[int, list[int]] | None = None,
    allow_missing: bool = True,
) -> ValidationResult:
    """Validate data completeness across expected years/weeks.

    Args:
        df: DataFrame to validate
        year_column: Name of year column
        week_column: Name of week column (optional)
        expected_years: Expected years in data
        expected_weeks: Expected weeks per year as {year: [weeks]}
        allow_missing: Whether missing data is acceptable

    Returns:
        ValidationResult object
    """
    issues = []

    if expected_years is not None:
        present_years = sorted(df[year_column].unique().tolist())
        missing_years = set(expected_years) - set(present_years)
        extra_years = set(present_years) - set(expected_years)

        if missing_years:
            issues.append(f"Missing years: {sorted(missing_years)}")
        if extra_years:
            issues.append(f"Extra years: {sorted(extra_years)}")

    if week_column is not None and expected_weeks is not None:
        for year, expected_week_list in expected_weeks.items():
            year_df = df[df[year_column] == year]
            present_weeks = sorted(year_df[week_column].unique().tolist())

            missing_weeks = set(expected_week_list) - set(present_weeks)
            extra_weeks = set(present_weeks) - set(expected_week_list)

            if missing_weeks:
                issues.append(f"{year}: Missing weeks: {sorted(missing_weeks)}")
            if extra_weeks:
                issues.append(f"{year}: Extra weeks: {sorted(extra_weeks)}")

    passed = len(issues) == 0
    message = "; ".join(issues) if issues else "Data completeness validated"

    return ValidationResult(
        check_name="completeness_validation",
        passed=passed,
        message=message,
        details={
            "present_years": sorted(df[year_column].unique().tolist()),
            "present_weeks": (
                sorted(df[week_column].unique().tolist()) if week_column else None
            ),
        },
        severity="warning" if (passed or allow_missing) else "error",
    )


def validate_statistical(
    df: pd.DataFrame,
    numeric_checks: dict[str, dict[str, Any]] | None = None,
    outlier_threshold_multiplier: float = 3.0,
) -> ValidationResult:
    """Validate statistical properties and detect outliers.

    Args:
        df: DataFrame to validate
        numeric_checks: Dict of {column: {min, max, allow_negative, outlier_check}}
        outlier_threshold_multiplier: IQR multiplier for outlier detection

    Returns:
        ValidationResult object
    """
    issues = []
    outlier_counts = {}

    numeric_checks = numeric_checks or {}

    for column, config in numeric_checks.items():
        if column not in df.columns:
            issues.append(f"Column {column} not found")
            continue

        values = df[column].dropna()
        if len(values) == 0:
            issues.append(f"Column {column} has no valid values")
            continue

        min_val = values.min()
        max_val = values.max()
        mean_val = values.mean()
        std_val = values.std()

        if "min" in config and min_val < config["min"]:
            issues.append(f"{column}: min {min_val} < expected {config['min']}")
        if "max" in config and max_val > config["max"]:
            issues.append(f"{column}: max {max_val} > expected {config['max']}")

        if config.get("allow_negative", True) is False:
            neg_count = (values < 0).sum()
            if neg_count > 0:
                issues.append(f"{column}: {neg_count} negative values (not allowed)")

        if config.get("outlier_check", True) and outlier_threshold_multiplier > 0:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                outliers = detect_outliers_iqr(df, column, outlier_threshold_multiplier)
            outlier_count = outliers.sum()
            if outlier_count > 0:
                outlier_counts[column] = {
                    "count": int(outlier_count),
                    "percentage": float(outlier_count / len(df) * 100),
                    "threshold": outlier_threshold_multiplier,
                }

    passed = len(issues) == 0
    message = "; ".join(issues) if issues else "Statistical validation passed"

    return ValidationResult(
        check_name="statistical_validation",
        passed=passed,
        message=message,
        details={
            "issues": issues,
            "outliers": outlier_counts,
        },
        severity="warning",
    )


def validate_integrity(
    df: pd.DataFrame,
    integrity_checks: dict[str, Any] | None = None,
) -> ValidationResult:
    """Validate referential integrity and logical consistency.

    Args:
        df: DataFrame to validate
        integrity_checks: Dict of integrity rules to check

    Returns:
        ValidationResult object
    """
    issues = []

    integrity_checks = integrity_checks or {}

    for check_name, check_config in integrity_checks.items():
        check_type = check_config.get("type")

        if check_type == "unique":
            column = check_config["column"]
            if column not in df.columns:
                continue
            duplicates = df[column].duplicated().sum()
            if duplicates > 0:
                issues.append(f"{check_name}: {duplicates} duplicate {column}")

        elif check_type == "range":
            column = check_config["column"]
            min_val = check_config["min"]
            max_val = check_config["max"]
            if column not in df.columns:
                continue
            out_of_range = ((df[column] < min_val) | (df[column] > max_val)).sum()
            if out_of_range > 0:
                issues.append(
                    f"{check_name}: {out_of_range} values outside [{min_val}, {max_val}]"
                )

        elif check_type == "nonnull":
            columns = check_config["columns"]
            missing_cols = [c for c in columns if c not in df.columns]
            if missing_cols:
                issues.append(f"{check_name}: columns not found: {missing_cols}")
                continue

            for column in columns:
                if column in df.columns:
                    null_count = df[column].isna().sum()
                    if null_count > 0:
                        issues.append(f"{check_name}: {column} has {null_count} nulls")

    passed = len(issues) == 0
    message = "; ".join(issues) if issues else "Integrity validation passed"

    return ValidationResult(
        check_name="integrity_validation",
        passed=passed,
        message=message,
        details={"issues": issues},
        severity="error" if not passed else "info",
    )


def validate_entity(
    df: pd.DataFrame,
    entity_name: str,
    schema_checks: dict[str, Any] | None = None,
    completeness_checks: dict[str, Any] | None = None,
    statistical_checks: dict[str, dict[str, Any]] | None = None,
    integrity_checks: dict[str, Any] | None = None,
    outlier_threshold_multiplier: float = 3.0,
) -> ValidationReport:
    """Run all validations on an entity.

    Args:
        df: DataFrame to validate
        entity_name: Name of the entity being validated
        schema_checks: Configuration for schema validation
        completeness_checks: Configuration for completeness validation
        statistical_checks: Configuration for statistical validation
        integrity_checks: Configuration for integrity validation
        outlier_threshold_multiplier: IQR multiplier for outlier detection

    Returns:
        ValidationReport object with all results
    """
    report = ValidationReport(entity=entity_name)

    if schema_checks:
        result = validate_schema(df, **schema_checks)
        report.add_result(result)

    if completeness_checks:
        result = validate_completeness(df, **completeness_checks)
        report.add_result(result)

    if statistical_checks:
        result = validate_statistical(
            df, statistical_checks, outlier_threshold_multiplier
        )
        report.add_result(result)

    if integrity_checks:
        result = validate_integrity(df, integrity_checks)
        report.add_result(result)

    return report


def print_validation_report(report: ValidationReport) -> None:
    """Print validation report to console.

    Args:
        report: ValidationReport to print
    """
    print(f"\n{'=' * 60}")
    print(f"Validation Report: {report.entity}")
    print(f"{'=' * 60}")
    print(report.summary())

    for result in report.results:
        status_icon = "✓" if result.passed else "!"
        severity_tag = f"[{result.severity.upper()}]" if not result.passed else ""
        print(f"\n{status_icon} {result.check_name} {severity_tag}")
        print(f"  {result.message}")
        if result.details:
            for key, value in result.details.items():
                print(f"  - {key}: {value}")

    print(f"\n{'=' * 60}\n")
