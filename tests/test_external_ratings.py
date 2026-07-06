"""Tests for external ratings ingester."""

from unittest.mock import MagicMock

import pytest

from cks_picks_cfb.data.external_ratings import (
    ExternalRatingsIngester,
    ingest_external_ratings,
)


class TestExternalRatingsIngester:
    """Verify ExternalRatingsIngester functionality."""

    @pytest.fixture(autouse=True)
    def mock_storage(self, tmp_path, monkeypatch):
        """Mock data root to a temporary directory."""
        monkeypatch.setenv("CFB_MODEL_DATA_ROOT", str(tmp_path))
        (tmp_path / "raw").mkdir(parents=True, exist_ok=True)
        (tmp_path / "interim").mkdir(parents=True, exist_ok=True)
        (tmp_path / "processed").mkdir(parents=True, exist_ok=True)

    def test_init_with_all_rating_type(self):
        """Initialize with rating_type='all'."""
        ingester = ExternalRatingsIngester(year=2024, rating_type="all")
        assert ingester.year == 2024
        assert ingester.rating_type == "all"

    def test_init_with_single_rating_type(self):
        """Initialize with single rating type."""
        ingester = ExternalRatingsIngester(year=2024, rating_type="sp")
        assert ingester.rating_type == "sp"

    def test_init_invalid_rating_type_raises(self):
        """Invalid rating_type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid rating_type"):
            ExternalRatingsIngester(year=2024, rating_type="invalid")

    def test_entity_name(self):
        """Entity name is external_ratings."""
        ingester = ExternalRatingsIngester(year=2024)
        assert ingester.entity_name == "raw/external_ratings"

    def test_partition_keys(self):
        """Partition keys are ['year', 'week']."""
        ingester = ExternalRatingsIngester(year=2024, week=5)
        assert ingester.partition_keys == ["year", "week"]

    @pytest.fixture
    def mock_csv_data(self, tmp_path):
        """Create mock CSV files in the expected directory structure."""
        import pandas as pd

        manual_dir = tmp_path / "raw" / "manual" / "ratings" / "year=2024" / "week=5"
        manual_dir.mkdir(parents=True, exist_ok=True)

        # SP+ Mock Data
        pd.DataFrame(
            [
                {
                    "team": "Alabama",
                    "rating": 30.5,
                    "offense": 40.2,
                    "defense": 10.1,
                    "special_teams": 0.4,
                },
                {
                    "team": "Georgia",
                    "rating": 29.8,
                    "offense": 38.0,
                    "defense": 9.0,
                    "special_teams": 0.8,
                },
            ]
        ).to_csv(manual_dir / "sp.csv", index=False)

        # FPI Mock Data
        pd.DataFrame(
            [
                {
                    "School": "Alabama",
                    "FPI": 28.5,
                    "OFF": 100.0,
                    "DEF": 80.0,
                    "ST": 50.0,
                },
                {
                    "School": "Georgia",
                    "FPI": 27.0,
                    "OFF": 95.0,
                    "DEF": 85.0,
                    "ST": 55.0,
                },
            ]
        ).to_csv(manual_dir / "fpi.csv", index=False)

        # FEI Mock Data
        pd.DataFrame(
            [
                {
                    "Team": "Alabama",
                    "FEI": 1.25,
                    "OFEI": 0.8,
                    "DFEI": 0.25,
                    "SFEI": 0.1,
                },
                {
                    "Team": "Georgia",
                    "FEI": 1.15,
                    "OFEI": 0.7,
                    "DFEI": 0.35,
                    "SFEI": -0.1,
                },
            ]
        ).to_csv(manual_dir / "fei.csv", index=False)

        return manual_dir

    def test_fetch_data_all_ratings(self, mock_csv_data):
        """Fetch all rating types from CSVs."""
        ingester = ExternalRatingsIngester(year=2024, week=5, rating_type="all")
        data = ingester.fetch_data()

        types_fetched = [rt for rt, _ in data]
        assert "sp" in types_fetched
        assert "fpi" in types_fetched
        assert "fei" in types_fetched

        # each should have 2 records
        for _, records in data:
            assert len(records) == 2

    def test_fetch_data_single_rating(self, mock_csv_data):
        """Fetch only SP+ ratings."""
        ingester = ExternalRatingsIngester(year=2024, week=5, rating_type="sp")
        data = ingester.fetch_data()

        types_fetched = [rt for rt, _ in data]
        assert types_fetched == ["sp"]
        assert len(data[0][1]) == 2

    def test_transform_sp_ratings(self, mock_csv_data):
        """Transform SP+ ratings correctly."""
        ingester = ExternalRatingsIngester(year=2024, week=5, rating_type="sp")
        data = ingester.fetch_data()
        records = ingester.transform_data(data)

        assert len(records) == 2
        alabama = next(r for r in records if r["team"] == "Alabama")
        assert alabama["rating_type"] == "sp"
        assert alabama["rating"] == 30.5
        assert alabama["offense_rating"] == 40.2
        assert alabama["defense_rating"] == 10.1
        assert alabama["special_teams_rating"] == 0.4
        assert alabama["season"] == 2024
        assert alabama["week"] == 5

    def test_transform_fpi_ratings(self, mock_csv_data):
        """Transform FPI ratings correctly using alias columns."""
        ingester = ExternalRatingsIngester(year=2024, week=5, rating_type="fpi")
        data = ingester.fetch_data()
        records = ingester.transform_data(data)

        assert len(records) == 2
        alabama = next(r for r in records if r["team"] == "Alabama")
        assert alabama["rating_type"] == "fpi"
        assert alabama["rating"] == 28.5  # Mapped from FPI
        assert alabama["offense_rating"] == 100.0  # Mapped from OFF

    def test_transform_fei_ratings(self, mock_csv_data):
        """Transform FEI ratings correctly using alias columns."""
        ingester = ExternalRatingsIngester(year=2024, week=5, rating_type="fei")
        data = ingester.fetch_data()
        records = ingester.transform_data(data)

        assert len(records) == 2
        alabama = next(r for r in records if r["team"] == "Alabama")
        assert alabama["rating_type"] == "fei"
        assert alabama["rating"] == 1.25  # Mapped from FEI


class TestIngestExternalRatings:
    """Verify convenience function."""

    @pytest.fixture
    def mock_ingester(self):
        """Mock ingester."""
        from unittest.mock import patch

        with patch(
            "cks_picks_cfb.data.external_ratings.ExternalRatingsIngester"
        ) as mock_class:
            mock_instance = MagicMock()
            mock_instance.fetch_data.return_value = []
            # needs to be list of dicts or at least something with truthy len for if block
            mock_instance.transform_data.return_value = [{"a": 1}, {"b": 2}]
            mock_instance.ingest_data.return_value = None
            mock_class.return_value = mock_instance
            yield mock_instance

    def test_calls_ingester_methods(self, mock_ingester):
        """Convenience function calls all ingester methods."""
        count = ingest_external_ratings(year=2024, week=5, rating_type="sp")

        mock_ingester.fetch_data.assert_called_once()
        mock_ingester.transform_data.assert_called_once()
        mock_ingester.ingest_data.assert_called_once()
        assert count == 2
