"""Tests for data validation utilities."""

import pandas as pd

from cks_picks_cfb.utils.data_validation import (
    ValidationReport,
    ValidationResult,
    detect_outliers_iqr,
    validate_completeness,
    validate_entity,
    validate_integrity,
    validate_schema,
    validate_statistical,
)


class TestDetectOutliersIQR:
    """Verify IQR-based outlier detection."""

    def test_no_outliers_normal_distribution(self):
        df = pd.DataFrame({"value": [1, 2, 3, 4, 5]})
        outliers = detect_outliers_iqr(df, "value", threshold_multiplier=3.0)
        assert outliers.sum() == 0

    def test_detects_extreme_outliers(self):
        df = pd.DataFrame({"value": [1, 2, 3, 4, 100]})
        outliers = detect_outliers_iqr(df, "value", threshold_multiplier=3.0)
        assert outliers.sum() == 1
        assert outliers.iloc[-1] is True

    def test_handles_missing_column(self):
        df = pd.DataFrame({"other": [1, 2, 3]})
        outliers = detect_outliers_iqr(df, "value")
        assert not outliers.any()

    def test_handles_nans(self):
        df = pd.DataFrame({"value": [1, 2, 3, pd.NA, 5]})
        outliers = detect_outliers_iqr(df, "value", threshold_multiplier=3.0)
        assert len(outliers) == 5


class TestValidateSchema:
    """Verify schema validation."""

    def test_all_required_columns_present(self):
        df = pd.DataFrame({"col1": [1], "col2": [2], "col3": [3]})
        result = validate_schema(df, required_columns=["col1", "col2"])
        assert result.passed
        assert result.severity == "info"

    def test_missing_required_columns(self):
        df = pd.DataFrame({"col1": [1], "col2": [2]})
        result = validate_schema(df, required_columns=["col1", "col2", "col3"])
        assert not result.passed
        assert "col3" in result.details["missing_required"]
        assert result.severity == "error"

    def test_missing_optional_columns(self):
        df = pd.DataFrame({"col1": [1], "col2": [2]})
        result = validate_schema(
            df, required_columns=["col1", "col2"], optional_columns=["col3"]
        )
        assert result.passed
        assert result.severity == "warning"
        assert "col3" in result.details["missing_optional"]


class TestValidateCompleteness:
    """Verify completeness validation."""

    def test_complete_years_and_weeks(self):
        df = pd.DataFrame(
            {"year": [2019, 2019, 2019, 2021, 2021, 2021], "week": [1, 2, 3, 1, 2, 3]}
        )
        result = validate_completeness(
            df,
            year_column="year",
            week_column="week",
            expected_years=[2019, 2021],
            expected_weeks={
                2019: [1, 2, 3],
                2021: [1, 2, 3],
            },
        )
        assert result.passed

    def test_missing_years(self):
        df = pd.DataFrame({"year": [2019, 2021]})
        result = validate_completeness(
            df,
            year_column="year",
            expected_years=[2019, 2021, 2022],
            allow_missing=False,
        )
        assert not result.passed
        assert 2022 not in result.details.get("present_years", [])
        assert result.severity == "error"

    def test_missing_weeks(self):
        df = pd.DataFrame({"year": [2019, 2019], "week": [1, 2]})
        result = validate_completeness(
            df,
            year_column="year",
            week_column="week",
            expected_weeks={2019: [1, 2, 3]},
        )
        assert not result.passed
        assert result.severity == "warning"


class TestValidateStatistical:
    """Verify statistical validation."""

    def test_passes_all_checks(self):
        df = pd.DataFrame(
            {
                "value": [1, 2, 3, 4, 5],
                "positive_only": [1, 2, 3, 4, 5],
            }
        )
        result = validate_statistical(
            df,
            numeric_checks={
                "value": {"min": 0, "max": 10, "allow_negative": True},
                "positive_only": {"allow_negative": False, "outlier_check": False},
            },
        )
        assert result.passed
        assert result.severity == "warning"

    def test_detects_out_of_range(self):
        df = pd.DataFrame({"value": [1, 2, 3, 100]})
        result = validate_statistical(
            df,
            numeric_checks={"value": {"min": 0, "max": 10}},
        )
        assert not result.passed
        assert "max" in result.message

    def test_detects_negative_values(self):
        df = pd.DataFrame({"value": [-5, 1, 2, 3]})
        result = validate_statistical(
            df,
            numeric_checks={"value": {"allow_negative": False}},
        )
        assert not result.passed
        assert "negative" in result.message

    def test_detects_outliers_with_count(self):
        df = pd.DataFrame({"value": [1, 2, 3, 4, 100]})
        result = validate_statistical(
            df,
            numeric_checks={"value": {"outlier_check": True}},
            outlier_threshold_multiplier=2.0,
        )
        outlier_info = result.details.get("outliers", {})
        assert "value" in outlier_info
        assert outlier_info["value"]["count"] >= 1


class TestValidateIntegrity:
    """Verify integrity validation."""

    def test_unique_constraint_passed(self):
        df = pd.DataFrame({"id": [1, 2, 3]})
        result = validate_integrity(
            df,
            integrity_checks={"unique_id": {"type": "unique", "column": "id"}},
        )
        assert result.passed

    def test_detects_duplicates(self):
        df = pd.DataFrame({"id": [1, 2, 2, 3]})
        result = validate_integrity(
            df,
            integrity_checks={"unique_id": {"type": "unique", "column": "id"}},
        )
        assert not result.passed
        assert "duplicate" in result.message

    def test_range_constraint_passed(self):
        df = pd.DataFrame({"week": [1, 2, 3, 4]})
        result = validate_integrity(
            df,
            integrity_checks={
                "week_range": {"type": "range", "column": "week", "min": 1, "max": 15}
            },
        )
        assert result.passed

    def test_detects_out_of_range(self):
        df = pd.DataFrame({"week": [1, 2, 20, 4]})
        result = validate_integrity(
            df,
            integrity_checks={
                "week_range": {"type": "range", "column": "week", "min": 1, "max": 15}
            },
        )
        assert not result.passed
        assert "outside" in result.message

    def test_nonnull_constraint_passed(self):
        df = pd.DataFrame({"id": [1, 2], "name": ["A", "B"]})
        result = validate_integrity(
            df,
            integrity_checks={
                "required_cols": {"type": "nonnull", "columns": ["id", "name"]}
            },
        )
        assert result.passed

    def test_detects_null_values(self):
        df = pd.DataFrame({"id": [1, pd.NA], "name": ["A", "B"]})
        result = validate_integrity(
            df,
            integrity_checks={
                "required_cols": {"type": "nonnull", "columns": ["id", "name"]}
            },
        )
        assert not result.passed
        assert "nulls" in result.message


class TestValidationReport:
    """Verify ValidationReport aggregation."""

    def test_aggregates_results_correctly(self):
        report = ValidationReport(entity="test_entity")

        report.add_result(ValidationResult("check1", True, "OK"))
        report.add_result(ValidationResult("check2", True, "OK"))
        report.add_result(ValidationResult("check3", False, "FAIL", severity="warning"))
        report.add_result(ValidationResult("check4", False, "FAIL", severity="error"))

        assert report.total_checks == 4
        assert report.passed == 2
        assert report.warnings == 1
        assert report.errors == 1

    def test_summary_generates_correct_string(self):
        report = ValidationReport(entity="test_entity")
        report.add_result(ValidationResult("check1", True, "OK"))
        report.add_result(ValidationResult("check2", False, "FAIL", severity="warning"))

        summary = report.summary()
        assert "test_entity" in summary
        assert "1/2 passed" in summary
        assert "1 warnings" in summary


class TestValidateEntity:
    """Verify full entity validation."""

    def test_runs_all_validations(self):
        df = pd.DataFrame(
            {
                "year": [2019, 2021],
                "week": [1, 1],
                "value": [1.0, 2.0],
                "id": [1, 2],
            }
        )

        report = validate_entity(
            df,
            entity_name="test_entity",
            schema_checks={"required_columns": ["year", "week", "value"]},
            completeness_checks={
                "year_column": "year",
                "expected_years": [2019, 2021],
            },
            statistical_checks={"value": {"min": 0, "max": 10, "allow_negative": True}},
            integrity_checks={"unique_id": {"type": "unique", "column": "id"}},
        )

        assert report.entity == "test_entity"
        assert report.total_checks == 4
        assert report.passed >= 3
