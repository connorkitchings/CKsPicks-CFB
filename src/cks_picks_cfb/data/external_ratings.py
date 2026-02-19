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

    def fetch_data(self) -> list[tuple[str, Any]]:
        """Fetch ratings data from the CFBD API.

        Returns:
            List of (rating_type, rating_object) tuples from CFBD API
        """
        ratings_api = cfbd.RatingsApi(cfbd.ApiClient(self.cfbd_config))
        all_ratings: list[tuple[str, Any]] = []

        if self.rating_type in ("sp", "all"):
            sp_ratings = ratings_api.get_sp(year=self.year)
            for rating in sp_ratings:
                all_ratings.append(("sp", rating))
            print(f"Found {len(sp_ratings)} SP+ ratings for {self.year}")

        if self.rating_type in ("fpi", "all"):
            fpi_ratings = ratings_api.get_fpi(year=self.year)
            for rating in fpi_ratings:
                all_ratings.append(("fpi", rating))
            print(f"Found {len(fpi_ratings)} FPI ratings for {self.year}")

        if self.rating_type in ("srs", "all"):
            srs_ratings = ratings_api.get_srs(year=self.year)
            for rating in srs_ratings:
                all_ratings.append(("srs", rating))
            print(f"Found {len(srs_ratings)} SRS ratings for {self.year}")

        return all_ratings

    def transform_data(self, data: list[tuple[str, Any]]) -> list[dict[str, Any]]:
        """Transform ratings data into storage format.

        Args:
            data: List of (rating_type, rating_object) tuples from CFBD API

        Returns:
            List of dictionaries ready for storage
        """
        # Define unified schema with all possible columns
        # This ensures PyArrow doesn't drop columns when combining record types
        base_columns = {
            "season": None,
            "year": None,
            "rating_type": None,
            "team": None,
            "conference": None,
            "rating": None,
            "ranking": None,
            "offense_rating": None,
            "defense_rating": None,
            "special_teams_rating": None,
            "second_order_wins": None,
            "sos": None,
            "fpi": None,
            "fpi_rk": None,
            "resume_ranks": None,
            "mean_win_total": None,
            "trend": None,
            "srs": None,
        }

        records = []

        for rating_type, rating in data:
            # Use Pydantic's dict() method to flatten nested models
            if hasattr(rating, "dict"):
                rating_dict = rating.dict()
            else:
                rating_dict = vars(rating)

            # Start with base schema
            record = dict(base_columns)

            # Set base fields
            record.update(
                {
                    "season": self.year,
                    "year": self.year,
                    "rating_type": rating_type,
                    "team": rating_dict.get("team"),
                    "conference": rating_dict.get("conference"),
                }
            )

            if rating_type == "sp":
                # Flatten nested offense/defense/special_teams
                offense = rating_dict.get("offense") or {}
                defense = rating_dict.get("defense") or {}
                special_teams = rating_dict.get("special_teams") or {}

                record.update(
                    {
                        "rating": rating_dict.get("rating"),
                        "ranking": rating_dict.get("ranking"),
                        "offense_rating": offense.get("rating")
                        if isinstance(offense, dict)
                        else getattr(offense, "rating", None),
                        "defense_rating": defense.get("rating")
                        if isinstance(defense, dict)
                        else getattr(defense, "rating", None),
                        "special_teams_rating": special_teams.get("rating")
                        if isinstance(special_teams, dict)
                        else getattr(special_teams, "rating", None),
                        "second_order_wins": rating_dict.get("second_order_wins"),
                        "sos": rating_dict.get("sos"),
                    }
                )
            elif rating_type == "fpi":
                # FPI stores offense/defense in 'efficiencies' object
                efficiencies = rating_dict.get("efficiencies") or {}

                record.update(
                    {
                        "rating": rating_dict.get(
                            "fpi"
                        ),  # Use fpi as rating for consistency
                        "fpi": rating_dict.get("fpi"),
                        "fpi_rk": rating_dict.get("fpi_rk"),
                        "resume_ranks": rating_dict.get("resume_ranks"),
                        "mean_win_total": rating_dict.get("mean_win_total"),
                        "trend": rating_dict.get("trend"),
                        "offense_rating": efficiencies.get("offense"),
                        "defense_rating": efficiencies.get("defense"),
                        "special_teams_rating": efficiencies.get("special_teams"),
                    }
                )
            elif rating_type == "srs":
                record.update(
                    {
                        "rating": rating_dict.get("rating"),
                        "ranking": rating_dict.get("ranking"),
                        "srs": rating_dict.get("rating"),
                    }
                )

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
