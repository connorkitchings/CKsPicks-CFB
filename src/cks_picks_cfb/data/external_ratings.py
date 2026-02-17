"""External ratings data ingestion from CFBD API.

Fetches SP+, FPI, and SRS ratings - predictive team strength metrics.
"""

from typing import Any

import cfbd

from .base import BaseIngester


class ExternalRatingsIngester(BaseIngester):
    """Ingester for external rating systems (SP+, FPI, SRS).

    These ratings provide predictive team strength metrics that are valuable
    features for game outcome prediction models.

    SP+ (Bill Connelly): Efficiency-based rating with offense/defense/ST splits
    FPI (ESPN): Predictive model incorporating recruiting, returning production
    SRS (Simple Rating System): Margin-of-victory based rating
    """

    def __init__(
        self,
        year: int = 2024,
        rating_type: str = "all",
        *,
        data_root: str | None = None,
        storage=None,
    ):
        """Initialize the external ratings ingester.

        Args:
            year: The year to ingest data for (default: 2024)
            rating_type: Which ratings to fetch - "sp", "fpi", "srs", or "all" (default)
            data_root: Root path for local data storage
            storage: Custom storage backend
        """
        super().__init__(year, data_root=data_root, storage=storage)
        self.rating_type = rating_type.lower()

        if self.rating_type not in ("sp", "fpi", "srs", "all"):
            raise ValueError(
                f"Invalid rating_type: {rating_type}. Must be sp, fpi, srs, or all"
            )

    @property
    def entity_name(self) -> str:
        """The logical entity name for storage."""
        return "external_ratings"

    @property
    def partition_keys(self) -> list[str]:
        """Partition keys for ratings data."""
        return ["year"]

    def fetch_data(self) -> list[Any]:
        """Fetch ratings data from the CFBD API.

        Returns:
            List of rating objects from CFBD API (combined if fetching all types)
        """
        ratings_api = cfbd.RatingsApi(cfbd.ApiClient(self.cfbd_config))
        all_ratings = []

        if self.rating_type in ("sp", "all"):
            sp_ratings = ratings_api.get_sp(year=self.year)
            for rating in sp_ratings:
                rating._rating_type = "sp"
            all_ratings.extend(sp_ratings)
            print(f"Found {len(sp_ratings)} SP+ ratings for {self.year}")

        if self.rating_type in ("fpi", "all"):
            fpi_ratings = ratings_api.get_fpi(year=self.year)
            for rating in fpi_ratings:
                rating._rating_type = "fpi"
            all_ratings.extend(fpi_ratings)
            print(f"Found {len(fpi_ratings)} FPI ratings for {self.year}")

        if self.rating_type in ("srs", "all"):
            srs_ratings = ratings_api.get_srs(year=self.year)
            for rating in srs_ratings:
                rating._rating_type = "srs"
            all_ratings.extend(srs_ratings)
            print(f"Found {len(srs_ratings)} SRS ratings for {self.year}")

        return all_ratings

    def transform_data(self, data: list[Any]) -> list[dict[str, Any]]:
        """Transform ratings data into storage format.

        Args:
            data: List of rating objects from CFBD API

        Returns:
            List of dictionaries ready for storage
        """
        records = []

        for rating in data:
            rating_type = getattr(rating, "_rating_type", "unknown")

            base_record = {
                "season": self.year,
                "year": self.year,
                "rating_type": rating_type,
                "team": self.safe_getattr(rating, "team", None),
                "conference": self.safe_getattr(rating, "conference", None),
            }

            if rating_type == "sp":
                record = {
                    **base_record,
                    "rating": self.safe_getattr(rating, "rating", None),
                    "offense_rating": self.safe_getattr(rating, "offense", None),
                    "defense_rating": self.safe_getattr(rating, "defense", None),
                    "special_teams_rating": self.safe_getattr(
                        rating, "special_teams", None
                    ),
                    "second_order_wins": self.safe_getattr(
                        rating, "second_order_wins", None
                    ),
                    "srs": self.safe_getattr(rating, "srs", None),
                    "sp_overall": self.safe_getattr(rating, "sp_overall", None),
                    "sp_offense": self.safe_getattr(rating, "sp_offense", None),
                    "sp_defense": self.safe_getattr(rating, "sp_defense", None),
                    "sp_special_teams": self.safe_getattr(
                        rating, "sp_special_teams", None
                    ),
                }
            elif rating_type == "fpi":
                record = {
                    **base_record,
                    "rating": self.safe_getattr(rating, "fpi", None),
                    "fpi": self.safe_getattr(rating, "fpi", None),
                    "resume_ranks": self.safe_getattr(rating, "resume_ranks", None),
                    "mean_win_total": self.safe_getattr(rating, "mean_win_total", None),
                    "offense_rating": self.safe_getattr(rating, "offense", None),
                    "defense_rating": self.safe_getattr(rating, "defense", None),
                    "fpi_rk": self.safe_getattr(rating, "fpi_rk", None),
                    "trend": self.safe_getattr(rating, "trend", None),
                }
            elif rating_type == "srs":
                record = {
                    **base_record,
                    "rating": self.safe_getattr(rating, "rating", None),
                    "srs": self.safe_getattr(rating, "rating", None),
                }
            else:
                record = base_record

            records.append(record)

        return records


def ingest_external_ratings(
    year: int, rating_type: str = "all", data_root: str | None = None
) -> int:
    """Convenience function to ingest external ratings data.

    Args:
        year: Year to ingest
        rating_type: Which ratings - "sp", "fpi", "srs", or "all"
        data_root: Root path for data storage

    Returns:
        Number of records written
    """
    ingester = ExternalRatingsIngester(
        year=year, rating_type=rating_type, data_root=data_root
    )
    data = ingester.fetch_data()
    transformed = ingester.transform_data(data)
    ingester.ingest_data(transformed)
    return len(transformed)
