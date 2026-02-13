"""Tests for storage abstraction layer."""

import os
from pathlib import Path

import pandas as pd
import pytest

from src.data.storage import LocalStorage, get_storage


class TestLocalStorage:
    """Test local filesystem storage."""

    @pytest.fixture
    def temp_storage(self, tmp_path):
        """Create temporary local storage."""
        return LocalStorage(str(tmp_path))

    def test_init_valid_path(self, tmp_path):
        """Test initialization with valid path."""
        storage = LocalStorage(str(tmp_path))
        assert storage.root_path == tmp_path

    def test_init_invalid_path(self):
        """Test initialization with invalid path raises error."""
        with pytest.raises(ValueError, match="Data root does not exist"):
            LocalStorage("/nonexistent/path")

    def test_write_read_parquet(self, temp_storage):
        """Test writing and reading parquet files."""
        df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        temp_storage.write_parquet(df, "test.parquet")

        df_read = temp_storage.read_parquet("test.parquet")
        pd.testing.assert_frame_equal(df, df_read)

    def test_write_read_csv(self, temp_storage):
        """Test writing and reading CSV files."""
        df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        temp_storage.write_csv(df, "test.csv", index=False)

        df_read = temp_storage.read_csv("test.csv")
        pd.testing.assert_frame_equal(df, df_read)

    def test_exists(self, temp_storage):
        """Test file existence check."""
        assert not temp_storage.exists("nonexistent.parquet")

        df = pd.DataFrame({"a": [1]})
        temp_storage.write_parquet(df, "exists.parquet")
        assert temp_storage.exists("exists.parquet")

    def test_list_files(self, temp_storage):
        """Test listing files."""
        # Create some test files
        df = pd.DataFrame({"a": [1]})
        temp_storage.write_parquet(df, "dir1/file1.parquet")
        temp_storage.write_parquet(df, "dir1/file2.parquet")
        temp_storage.write_parquet(df, "dir2/file3.parquet")

        # List all files
        files = temp_storage.list_files("")
        assert len(files) == 3
        assert "dir1/file1.parquet" in files
        assert "dir1/file2.parquet" in files
        assert "dir2/file3.parquet" in files

        # List files in subdirectory
        files_dir1 = temp_storage.list_files("dir1")
        assert len(files_dir1) == 2

    def test_get_full_path(self, temp_storage):
        """Test getting full path."""
        full_path = temp_storage.get_full_path("test.parquet")
        assert "test.parquet" in full_path


class TestGetStorage:
    """Test storage factory function."""

    def test_get_local_storage(self, monkeypatch, tmp_path):
        """Test getting local storage from environment."""
        monkeypatch.setenv("CFB_STORAGE_BACKEND", "local")
        monkeypatch.setenv("CFB_MODEL_DATA_ROOT", str(tmp_path))

        storage = get_storage()
        assert isinstance(storage, LocalStorage)
        assert storage.root_path == tmp_path

    def test_get_storage_missing_data_root(self, monkeypatch):
        """Test error when data root is missing for local storage."""
        monkeypatch.setenv("CFB_STORAGE_BACKEND", "local")
        monkeypatch.delenv("CFB_MODEL_DATA_ROOT", raising=False)

        with pytest.raises(ValueError, match="CFB_MODEL_DATA_ROOT must be set"):
            get_storage()

    def test_get_storage_invalid_backend(self, monkeypatch, tmp_path):
        """Test error for invalid storage backend."""
        monkeypatch.setenv("CFB_STORAGE_BACKEND", "invalid")
        monkeypatch.setenv("CFB_MODEL_DATA_ROOT", str(tmp_path))

        with pytest.raises(ValueError, match="Invalid storage backend"):
            get_storage()

    def test_get_storage_defaults_to_local(self, monkeypatch, tmp_path):
        """Test that storage defaults to local when not specified."""
        monkeypatch.delenv("CFB_STORAGE_BACKEND", raising=False)
        monkeypatch.setenv("CFB_MODEL_DATA_ROOT", str(tmp_path))

        storage = get_storage()
        assert isinstance(storage, LocalStorage)


# R2/S3 tests would require mocking boto3 or integration tests with actual cloud resources
# For now, we test the local storage implementation which serves as the baseline
