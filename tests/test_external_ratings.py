"""Tests for external ratings ingester."""

from unittest.mock import MagicMock, Mock

import pytest

from cks_picks_cfb.data.external_ratings import (
    ExternalRatingsIngester,
    ingest_external_ratings,
)


class TestExternalRatingsIngester:
    """Verify ExternalRatingsIngester functionality."""

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
        assert ingester.entity_name == "external_ratings"

    def test_partition_keys(self):
        """Partition keys are ['year']."""
        ingester = ExternalRatingsIngester(year=2024)
        assert ingester.partition_keys == ["year"]

    @pytest.fixture
    def mock_api(self):
        """Mock CFBD API client."""
        with pytest.mock.patch("cks_picks_cfb.data.external_ratings.cfbd") as mock_cfbd:
            mock_api = MagicMock()
            mock_cfbd.RatingsApi.return_value.ApiClient.return_value = mock_api
            mock_cfbd.ApiClient.return_value = MagicMock()
            yield mock_api

    def test_fetch_data_all_ratings(self, mock_api):
        """Fetch all rating types."""
        mock_sp = MagicMock()
        mock_sp.__iter__ = Mock(return_value=iter([]))
        mock_api.get_sp.return_value = mock_sp

        mock_fpi = MagicMock()
        mock_fpi.__iter__ = Mock(return_value=iter([]))
        mock_api.get_fpi.return_value = mock_fpi

        mock_srs = MagicMock()
        mock_srs.__iter__ = Mock(return_value=iter([]))
        mock_api.get_srs.return_value = mock_srs

        ingester = ExternalRatingsIngester(year=2024, rating_type="all")
        data = ingester.fetch_data()

        assert mock_api.get_sp.called
        assert mock_api.get_fpi.called
        assert mock_api.get_srs.called

    def test_fetch_data_single_rating(self, mock_api):
        """Fetch only SP+ ratings."""
        mock_sp = MagicMock()
        mock_sp.__iter__ = Mock(return_value=iter([]))
        mock_api.get_sp.return_value = mock_sp

        ingester = ExternalRatingsIngester(year=2024, rating_type="sp")
        data = ingester.fetch_data()

        assert mock_api.get_sp.called
        assert not mock_api.get_fpi.called
        assert not mock_api.get_srs.called

    def test_transform_sp_ratings(self, mock_api):
        """Transform SP+ ratings correctly."""
        mock_rating = MagicMock()
        mock_rating.team = "Test Team"
        mock_rating.conference = "Test Conf"
        mock_rating.rating = 25.5
        mock_rating.offense = 30.0
        mock_rating.defense = 20.0
        mock_rating.special_teams = 22.0
        mock_rating.second_order_wins = 5.0
        mock_rating.srs = 24.0
        mock_rating.sp_overall = 26.0
        mock_rating.sp_offense = 28.0
        mock_rating.sp_defense = 24.0
        mock_rating.sp_special_teams = 25.0

        ingester = ExternalRatingsIngester(year=2024)
        mock_rating._rating_type = "sp"
        records = ingester.transform_data([mock_rating])

        assert len(records) == 1
        record = records[0]
        assert record["rating_type"] == "sp"
        assert record["team"] == "Test Team"
        assert record["rating"] == 25.5
        assert record["offense_rating"] == 30.0
        assert record["defense_rating"] == 20.0
        assert record["special_teams_rating"] == 22.0
        assert record["second_order_wins"] == 5.0

    def test_transform_fpi_ratings(self, mock_api):
        """Transform FPI ratings correctly."""
        mock_rating = MagicMock()
        mock_rating.team = "Test Team"
        mock_rating.conference = "Test Conf"
        mock_rating.fpi = 18.5
        mock_rating.resume_ranks = 15
        mock_rating.mean_win_total = 8.2
        mock_rating.offense = 20.0
        mock_rating.defense = 18.0
        mock_rating.fpi_rk = 25
        mock_rating.trend = "+1.2"

        ingester = ExternalRatingsIngester(year=2024)
        mock_rating._rating_type = "fpi"
        records = ingester.transform_data([mock_rating])

        assert len(records) == 1
        record = records[0]
        assert record["rating_type"] == "fpi"
        assert record["rating"] == 18.5
        assert record["fpi"] == 18.5
        assert record["resume_ranks"] == 15
        assert record["offense_rating"] == 20.0
        assert record["defense_rating"] == 18.0
        assert record["fpi_rk"] == 25

    def test_transform_srs_ratings(self, mock_api):
        """Transform SRS ratings correctly."""
        mock_rating = MagicMock()
        mock_rating.team = "Test Team"
        mock_rating.conference = "Test Conf"
        mock_rating.rating = 10.5

        ingester = ExternalRatingsIngester(year=2024)
        mock_rating._rating_type = "srs"
        records = ingester.transform_data([mock_rating])

        assert len(records) == 1
        record = records[0]
        assert record["rating_type"] == "srs"
        assert record["rating"] == 10.5
        assert record["srs"] == 10.5


class TestIngestExternalRatings:
    """Verify convenience function."""

    @pytest.fixture
    def mock_ingester(self):
        """Mock ingester."""
        with pytest.mock.patch(
            "cks_picks_cfb.data.external_ratings.ExternalRatingsIngester"
        ) as mock_class:
            mock_instance = MagicMock()
            mock_instance.fetch_data.return_value = []
            mock_instance.transform_data.return_value = []
            mock_instance.ingest_data.return_value = 5
            mock_class.return_value = mock_instance
            yield mock_instance

    def test_calls_ingester_methods(self, mock_ingester):
        """Convenience function calls all ingester methods."""
        count = ingest_external_ratings(year=2024, rating_type="sp")

        mock_ingester.fetch_data.assert_called_once()
        mock_ingester.transform_data.assert_called_once()
        mock_ingester.ingest_data.assert_called_once()
        assert count == 5
