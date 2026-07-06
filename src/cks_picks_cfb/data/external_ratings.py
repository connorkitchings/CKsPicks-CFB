"""External ratings data ingestion from CFBD API.

Fetches SP+, FPI, and SRS ratings - predictive team strength metrics.
"""

from pathlib import Path
from typing import Any

import pandas as pd

from .base import BaseIngester


class ExternalRatingsIngester(BaseIngester):
    """Ingester for external rating systems (SP+, FPI, FEI).

    These ratings provide predictive team strength metrics that are valuable
    features for game outcome prediction models.

    Because historical weekly data is NOT available via the CFBD API,
    this ingester expects to find manually downloaded CSVs in:
    $CFB_MODEL_DATA_ROOT/raw/manual/ratings/year={year}/week={week}/{rating_type}.csv

    SP+ (Bill Connelly): Efficiency-based rating with offense/defense/ST splits
    FPI (ESPN): Predictive model incorporating recruiting, returning production
    FEI (Fremeau): Possession-based efficiency index
    """

    def __init__(
        self,
        year: int = 2024,
        week: int = 1,
        rating_type: str = "all",
        *,
        data_root: str | None = None,
        storage=None,
    ):
        """Initialize the external ratings ingester.

        Args:
            year: The year to ingest data for (default: 2024)
            week: The week to ingest data for (default: 1)
            rating_type: Which ratings to fetch - "sp", "fpi", "fei", or "all" (default)
            data_root: Root path for local data storage
            storage: Custom storage backend
        """
        super().__init__(year, data_root=data_root, storage=storage)
        self.week = week
        self.rating_type = rating_type.lower()

        if self.rating_type not in ("sp", "fpi", "fei", "all"):
            raise ValueError(
                f"Invalid rating_type: {rating_type}. Must be sp, fpi, fei, or all"
            )

    @property
    def entity_name(self) -> str:
        """The logical entity name for storage."""
        return "raw/external_ratings"

    @property
    def partition_keys(self) -> list[str]:
        """Partition keys for ratings data."""
        return ["year", "week"]

    def _get_manual_dir(self) -> Path:
        """Get the directory containing manual CSV dumps.

        Looks for {storage_root}/raw/manual/ratings/year={Y}/week={W}/.
        For cloud backends, Path(str) produces a meaningless path but
        manual_dir.exists() returns False and fetch_data() handles it gracefully.
        """
        root = self.storage.root()
        return (
            Path(root)
            / "raw"
            / "manual"
            / "ratings"
            / f"year={self.year}"
            / f"week={self.week}"
        )

    def fetch_data(self) -> list[tuple[str, list[dict[str, Any]]]]:
        """Fetch ratings data from local manual CSV dumps.

        Returns:
            List of (rating_type, records) tuples
        """
        all_ratings: list[tuple[str, list[dict[str, Any]]]] = []
        manual_dir = self._get_manual_dir()

        if not manual_dir.exists():
            print(f"Warning: Manual ratings directory not found: {manual_dir}")
            return all_ratings

        types_to_fetch = (
            ["sp", "fpi", "fei"] if self.rating_type == "all" else [self.rating_type]
        )

        for rt in types_to_fetch:
            csv_path = manual_dir / f"{rt}.csv"
            if csv_path.exists():
                try:
                    df = pd.read_csv(csv_path)
                    records = df.to_dict(orient="records")
                    all_ratings.append((rt, records))
                    print(
                        f"Found {len(records)} {rt.upper()} ratings for {self.year} Week {self.week}"
                    )
                except Exception as e:
                    print(f"Error reading {csv_path}: {e}")
            else:
                print(f"File not found: {csv_path}")

        return all_ratings

    def transform_data(
        self, data: list[tuple[str, list[dict[str, Any]]]]
    ) -> list[dict[str, Any]]:
        """Transform ratings data into unified storage format.

        Args:
            data: List of (rating_type, records) tuples

        Returns:
            List of dictionaries ready for Parquet storage
        """
        # Unified schema compatible with SP+, FPI, and FEI
        base_columns = {
            "season": self.year,
            "year": self.year,
            "week": self.week,
            "rating_type": None,
            "team": None,
            "rating": None,  # Overall predictive rating (SP+, FPI, or FEI)
            "offense_rating": None,
            "defense_rating": None,
            "special_teams_rating": None,
        }

        transformed_records = []

        for rating_type, records in data:
            for record in records:
                row = dict(base_columns)
                row["rating_type"] = rating_type

                # We expect manual CSVs to map to these exact keys if possible,
                # or fallback to common aliases if they vary slightly in user dumps.
                row["team"] = (
                    record.get("team") or record.get("Team") or record.get("School")
                )
                row["rating"] = (
                    record.get("rating")
                    or record.get(rating_type)
                    or record.get(rating_type.upper())
                )

                # Optional sub-components
                row["offense_rating"] = (
                    record.get("offense")
                    or record.get("off")
                    or record.get("offense_rating")
                    or record.get("OFF")
                    or record.get("OFEI")
                )
                row["defense_rating"] = (
                    record.get("defense")
                    or record.get("def")
                    or record.get("defense_rating")
                    or record.get("DEF")
                    or record.get("DFEI")
                )
                row["special_teams_rating"] = (
                    record.get("special_teams")
                    or record.get("st")
                    or record.get("special_teams_rating")
                    or record.get("ST")
                    or record.get("SFEI")
                )

                # Only keep records that have at least a team name
                if row["team"]:
                    transformed_records.append(row)

        return transformed_records


def ingest_external_ratings(
    year: int, week: int = 1, rating_type: str = "all", data_root: str | None = None
) -> int:
    """Convenience function to ingest external ratings data from manual CSVs.

    Args:
        year: Year to ingest
        week: Week to ingest
        rating_type: Which ratings - "sp", "fpi", "fei", or "all"
        data_root: Root path for data storage

    Returns:
        Number of records written
    """
    ingester = ExternalRatingsIngester(
        year=year, week=week, rating_type=rating_type, data_root=data_root
    )
    data = ingester.fetch_data()
    transformed = ingester.transform_data(data)

    if transformed:
        ingester.ingest_data(transformed)

    return len(transformed)
