"""Unit tests for DataValidationService and schema validation.

Tests follow the minimal fixture pattern from test_aggregate_drives_minimal.py.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd
import pytest
import yaml

from src.utils.local_storage import LocalStorage
from src.utils.validation import (
    DataValidationService,
    ValidationIssue,
    get_validation_service,
)


@pytest.fixture
def temp_data_root():
    """Create a temporary data root directory with required subdirectories."""
    with TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        # Create subdirectories that LocalStorage expects
        (root / "processed").mkdir(parents=True, exist_ok=True)
        (root / "raw").mkdir(parents=True, exist_ok=True)
        yield root


@pytest.fixture
def temp_config_file(temp_data_root):
    """Create a temporary validation config file."""
    config_path = temp_data_root / "validation.yaml"
    config = {
        "validation": {
            "test_entity": {
                "required_columns": ["id", "name", "value"],
                "uniqueness_columns": ["id"],
                "null_checks": {
                    "critical_null_checks": ["id", "name"],
                    "warning_null_checks": {"value": 5.0},
                },
                "range_checks": {
                    "value": {"min": 0.0, "max": 100.0},
                    "score": {"min": -10.0, "max": 10.0},
                },
            }
        }
    }
    with config_path.open("w") as f:
        yaml.dump(config, f)
    return config_path


@pytest.fixture
def mock_storage(temp_data_root):
    """Create a mock LocalStorage instance."""
    return LocalStorage(
        data_root=temp_data_root, file_format="csv", data_type="processed"
    )


@pytest.fixture
def validation_service(mock_storage, temp_config_file):
    """Create a DataValidationService instance with test config."""
    return DataValidationService(storage=mock_storage, config_path=temp_config_file)


class TestDataValidationService:
    """Tests for DataValidationService initialization and configuration."""

    def test_service_initialization(self, validation_service):
        """Test that service initializes correctly with config."""
        assert validation_service.config is not None
        assert "validation" in validation_service.config
        assert "test_entity" in validation_service.config["validation"]

    def test_service_without_config(self, mock_storage, temp_data_root):
        """Test service initialization without config file."""
        nonexistent_config = temp_data_root / "nonexistent.yaml"
        service = DataValidationService(
            storage=mock_storage, config_path=nonexistent_config
        )
        assert service.config == {}

    def test_get_validation_service_factory(self, temp_data_root):
        """Test convenience factory function."""
        service = get_validation_service(
            data_root=temp_data_root, data_type="processed"
        )
        assert isinstance(service, DataValidationService)
        assert service.storage is not None


class TestSchemaValidation:
    """Tests for schema validation rules."""

    def test_required_columns_present(self, validation_service):
        """Test validation passes when all required columns present."""
        df = pd.DataFrame({"id": [1, 2], "name": ["A", "B"], "value": [10.0, 20.0]})
        issues = validation_service.validate_schema(df, "test_entity")
        errors = [iss for iss in issues if iss.level == "ERROR"]
        assert len(errors) == 0

    def test_required_columns_missing(self, validation_service):
        """Test validation fails when required columns missing."""
        df = pd.DataFrame({"id": [1, 2]})  # Missing 'name' and 'value'
        issues = validation_service.validate_schema(df, "test_entity")
        errors = [iss for iss in issues if iss.level == "ERROR"]
        assert len(errors) == 1
        assert "Missing required columns" in errors[0].message
        assert "name" in errors[0].message
        assert "value" in errors[0].message

    def test_critical_null_check_error(self, validation_service):
        """Test critical null check raises ERROR when nulls present."""
        df = pd.DataFrame(
            {"id": [1, None, 3], "name": ["A", "B", None], "value": [10.0, 20.0, 30.0]}
        )
        issues = validation_service.validate_schema(df, "test_entity")
        errors = [iss for iss in issues if iss.level == "ERROR"]

        # Should have errors for both 'id' and 'name' having nulls
        assert len(errors) == 2
        error_messages = [err.message for err in errors]
        assert any("id" in msg for msg in error_messages)
        assert any("name" in msg for msg in error_messages)

    def test_warning_null_check_threshold(self, validation_service):
        """Test warning null check raises WARN when threshold exceeded."""
        # Create dataframe with 10% nulls (threshold is 5%)
        df = pd.DataFrame(
            {
                "id": range(1, 21),
                "name": ["A"] * 20,
                "value": [10.0] * 18 + [None, None],  # 10% nulls
            }
        )
        issues = validation_service.validate_schema(df, "test_entity")
        warnings = [iss for iss in issues if iss.level == "WARN"]

        assert len(warnings) == 1
        assert "value" in warnings[0].message
        assert "10.0%" in warnings[0].message
        assert "threshold" in warnings[0].message

    def test_warning_null_check_below_threshold(self, validation_service):
        """Test warning null check passes when below threshold."""
        # Create dataframe with 2% nulls (threshold is 5%)
        df = pd.DataFrame(
            {
                "id": range(1, 101),
                "name": ["A"] * 100,
                "value": [10.0] * 98 + [None, None],  # 2% nulls
            }
        )
        issues = validation_service.validate_schema(df, "test_entity")
        warnings = [iss for iss in issues if iss.level == "WARN"]
        value_warnings = [w for w in warnings if "value" in w.message]

        assert len(value_warnings) == 0

    def test_range_check_below_minimum(self, validation_service):
        """Test range check detects values below minimum."""
        df = pd.DataFrame(
            {"id": [1, 2, 3], "name": ["A", "B", "C"], "value": [-5.0, 10.0, 20.0]}
        )
        issues = validation_service.validate_schema(df, "test_entity")
        errors = [iss for iss in issues if iss.level == "ERROR"]

        assert len(errors) == 1
        assert "value" in errors[0].message
        assert "below minimum" in errors[0].message
        assert "0.0" in errors[0].message

    def test_range_check_above_maximum(self, validation_service):
        """Test range check detects values above maximum."""
        df = pd.DataFrame(
            {"id": [1, 2, 3], "name": ["A", "B", "C"], "value": [10.0, 20.0, 150.0]}
        )
        issues = validation_service.validate_schema(df, "test_entity")
        errors = [iss for iss in issues if iss.level == "ERROR"]

        assert len(errors) == 1
        assert "value" in errors[0].message
        assert "above maximum" in errors[0].message
        assert "100.0" in errors[0].message

    def test_range_check_within_bounds(self, validation_service):
        """Test range check passes for values within bounds."""
        df = pd.DataFrame(
            {
                "id": [1, 2, 3],
                "name": ["A", "B", "C"],
                "value": [0.0, 50.0, 100.0],  # All within [0, 100]
            }
        )
        issues = validation_service.validate_schema(df, "test_entity")
        errors = [iss for iss in issues if iss.level == "ERROR"]
        range_errors = [e for e in errors if "value" in e.message]

        assert len(range_errors) == 0

    def test_uniqueness_check_duplicates(self, validation_service):
        """Test uniqueness check detects duplicate keys."""
        df = pd.DataFrame(
            {
                "id": [1, 2, 2, 3],  # Duplicate id=2
                "name": ["A", "B", "C", "D"],
                "value": [10.0, 20.0, 30.0, 40.0],
            }
        )
        issues = validation_service.validate_schema(df, "test_entity")
        errors = [iss for iss in issues if iss.level == "ERROR"]

        assert len(errors) == 1
        assert "duplicate" in errors[0].message.lower()
        assert "2 duplicate rows" in errors[0].message  # 2 rows with id=2

    def test_uniqueness_check_no_duplicates(self, validation_service):
        """Test uniqueness check passes with unique keys."""
        df = pd.DataFrame(
            {
                "id": [1, 2, 3, 4],
                "name": ["A", "B", "C", "D"],
                "value": [10.0, 20.0, 30.0, 40.0],
            }
        )
        issues = validation_service.validate_schema(df, "test_entity")
        errors = [iss for iss in issues if iss.level == "ERROR"]
        uniqueness_errors = [e for e in errors if "duplicate" in e.message.lower()]

        assert len(uniqueness_errors) == 0

    def test_entity_not_in_config(self, validation_service):
        """Test validation warns when entity not in config."""
        df = pd.DataFrame({"col1": [1, 2], "col2": ["A", "B"]})
        issues = validation_service.validate_schema(df, "nonexistent_entity")

        assert len(issues) == 1
        assert issues[0].level == "WARN"
        assert "No validation config" in issues[0].message

    def test_multiple_validation_errors(self, validation_service):
        """Test multiple validation errors are detected together."""
        df = pd.DataFrame(
            {
                "id": [None, 2, 2],  # Null in critical column + duplicates
                "name": ["A", "B", "C"],
                "value": [-10.0, 150.0, 50.0],  # Below min and above max
            }
        )
        issues = validation_service.validate_schema(df, "test_entity")
        errors = [iss for iss in issues if iss.level == "ERROR"]

        # Should have: 1 critical null, 1 duplicate, 1 below min, 1 above max = 4 errors
        assert len(errors) == 4


class TestValidationIssue:
    """Tests for ValidationIssue dataclass."""

    def test_validation_issue_creation(self):
        """Test ValidationIssue can be created correctly."""
        issue = ValidationIssue(
            level="ERROR", message="Test error", entity="test", path=Path("/tmp/test")
        )
        assert issue.level == "ERROR"
        assert issue.message == "Test error"
        assert issue.entity == "test"
        assert issue.path == Path("/tmp/test")

    def test_validation_issue_without_path(self):
        """Test ValidationIssue works without path."""
        issue = ValidationIssue(level="WARN", message="Test warning", entity="test")
        assert issue.level == "WARN"
        assert issue.path is None

    def test_validation_issue_levels(self):
        """Test different validation issue levels."""
        levels = ["ERROR", "WARN", "INFO"]
        for level in levels:
            issue = ValidationIssue(level=level, message="Test", entity="test")
            assert issue.level == level


class TestIntegration:
    """Integration tests for validation service."""

    def test_validate_entity_with_schema(self, validation_service, temp_data_root):
        """Test validate_entity integrates schema validation."""
        # Create test data file - LocalStorage expects data under processed/ subdirectory
        entity_dir = (
            temp_data_root / "processed" / "test_entity" / "year=2024" / "week=1"
        )
        entity_dir.mkdir(parents=True, exist_ok=True)

        df = pd.DataFrame(
            {
                "id": [1, 2, 3],
                "name": ["A", "B", "C"],
                "value": [10.0, 150.0, 30.0],  # value=150 exceeds max
            }
        )
        df.to_csv(entity_dir / "data.csv", index=False)

        issues = validation_service.validate_entity(
            year=2024, entity="test_entity", key_columns=["id"], schema_only=True
        )

        errors = [iss for iss in issues if iss.level == "ERROR"]
        # Should have 1 range error
        assert len(errors) >= 1
        assert any("above maximum" in e.message for e in errors)

    def test_schema_only_flag(self, validation_service, temp_data_root):
        """Test schema_only flag stops after schema validation."""
        # Create test data - LocalStorage expects data under processed/ subdirectory
        entity_dir = (
            temp_data_root / "processed" / "test_entity" / "year=2024" / "week=1"
        )
        entity_dir.mkdir(parents=True, exist_ok=True)

        df = pd.DataFrame({"id": [1, 2], "name": ["A", "B"], "value": [10.0, 20.0]})
        df.to_csv(entity_dir / "data.csv", index=False)

        # Schema-only should not check manifests/duplicates
        issues_schema_only = validation_service.validate_entity(
            year=2024, entity="test_entity", key_columns=["id"], schema_only=True
        )

        # With good schema, should have no errors
        errors = [iss for iss in issues_schema_only if iss.level == "ERROR"]
        assert len(errors) == 0
