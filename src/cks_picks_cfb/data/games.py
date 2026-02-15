"""Games data ingestion from CFBD API."""

import argparse
import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import cfbd
import pandas as pd

from cks_picks_cfb.utils.base import Partition

from .base import BaseIngester


class GamesIngester(BaseIngester):
    """Ingester for college football games data."""

    def __init__(
        self,
        year: int = 2024,
        classification: str = "fbs",
        season_type: str = "regular",
        week: int | None = None,  # Add week parameter
        *,
        data_root: str | None = None,
        storage=None,
    ):
        """Initialize the games ingester.

        Args:
            year: The year to ingest data for (default: 2024)
            classification: Team classification filter (default: "fbs")
            season_type: Season type to ingest (default: "regular")
            week: Optional specific week to ingest data for.
        """
        super().__init__(year, classification, data_root=data_root, storage=storage)
        self.season_type = season_type
        self.week = week

    @property
    def entity_name(self) -> str:
        """The logical entity name for storage."""
        return "games"

    @property
    def partition_keys(self) -> list[str]:
        # If fetching for a specific week, partition by week as well
        if self.week is not None:
            return ["year", "week"]
        return ["year"]

    def get_fbs_team_names(self) -> set[str]:
        """Deprecated: prefer filtering games by classification fields from get_games.

        This method is kept for backward compatibility but is no longer used by default.
        """
        try:
            teams_api = cfbd.TeamsApi(cfbd.ApiClient(self.cfbd_config))
            teams = teams_api.get_teams(year=self.year)
            fbs_teams = [
                team.school
                for team in teams
                if getattr(team, "classification", "").lower() == self.classification
            ]
            return set(fbs_teams)
        except Exception:
            return set()

    def fetch_data(self) -> list[Any]:
        """Fetch games data from the CFBD API.

        Returns:
            List of game objects from CFBD API
        """
        games_api = cfbd.GamesApi(cfbd.ApiClient(self.cfbd_config))

        # Prepare arguments for the API call
        api_kwargs = {
            "year": self.year,
            "season_type": self.season_type,
            "classification": self.classification,
        }
        if self.week is not None:
            api_kwargs["week"] = self.week

        # Fetch games using the specified parameters
        all_games = games_api.get_games(**api_kwargs)

        # The API call with classification="fbs" should already filter the games,
        # so the manual filtering below is a fallback/verification step.
        print(f"Found {len(all_games)} FBS games.")
        return all_games

    def transform_data(self, data: list[Any]) -> list[dict[str, Any]]:
        """Transform games data into storage format.

        Args:
            data: List of game objects from CFBD API

        Returns:
            List of dictionaries ready for storage
        """
        games_to_insert = []

        for game in data:
            # Handle line scores (convert to PostgreSQL array format)
            home_line_scores = self.safe_getattr(game, "home_line_scores", None)
            away_line_scores = self.safe_getattr(game, "away_line_scores", None)

            # Handle datetime fields - normalize to US/Eastern tz-aware datetime
            start_date = self.normalize_to_eastern(
                self.safe_getattr(game, "start_date", None)
            )

            games_to_insert.append(
                {
                    "id": game.id,
                    "season": game.season,
                    "season_type": self.safe_getattr(
                        game, "season_type", self.season_type
                    ),
                    "week": self.safe_getattr(game, "week", None),
                    "start_date": start_date,
                    "start_time_tbd": self.safe_getattr(game, "start_time_tbd", None),
                    "venue_id": self.safe_getattr(game, "venue_id", None),
                    "venue": self.safe_getattr(game, "venue", None),
                    "neutral_site": self.safe_getattr(game, "neutral_site", None),
                    "conference_game": self.safe_getattr(game, "conference_game", None),
                    "attendance": self.safe_getattr(game, "attendance", None),
                    "excitement_index": self.safe_getattr(
                        game, "excitement_index", None
                    ),
                    "highlights": self.safe_getattr(game, "highlights", None),
                    "notes": self.safe_getattr(game, "notes", None),
                    "home_id": self.safe_getattr(game, "home_id", None),
                    "home_team": self.safe_getattr(game, "home_team", None),
                    "home_conference": self.safe_getattr(game, "home_conference", None),
                    "home_classification": self.safe_getattr(
                        game, "home_classification", None
                    ),
                    "home_points": self.safe_getattr(game, "home_points", None),
                    "home_line_scores": home_line_scores,
                    "home_pregame_elo": self.safe_getattr(
                        game, "home_pregame_elo", None
                    ),
                    "home_postgame_elo": self.safe_getattr(
                        game, "home_postgame_elo", None
                    ),
                    "home_postgame_win_probability": self.safe_getattr(
                        game, "home_postgame_win_probability", None
                    ),
                    "away_id": self.safe_getattr(game, "away_id", None),
                    "away_team": self.safe_getattr(game, "away_team", None),
                    "away_conference": self.safe_getattr(game, "away_conference", None),
                    "away_classification": self.safe_getattr(
                        game, "away_classification", None
                    ),
                    "away_points": self.safe_getattr(game, "away_points", None),
                    "away_line_scores": away_line_scores,
                    "away_pregame_elo": self.safe_getattr(
                        game, "away_pregame_elo", None
                    ),
                    "away_postgame_elo": self.safe_getattr(
                        game, "away_postgame_elo", None
                    ),
                    "away_postgame_win_probability": self.safe_getattr(
                        game, "away_postgame_win_probability", None
                    ),
                    "completed": self.safe_getattr(game, "completed", None),
                    "year": self.year,
                }
            )

        return games_to_insert

    def ingest_data(self, data: list[dict[str, Any]]) -> None:
        """Persist games data with per-week partitions and year-level upserts.

        When a specific week is requested we overwrite that week's partition and
        update the year-level CSV so completed box scores replace earlier
        in-progress snapshots.
        """
        if not data:
            print("No data to ingest.")
            return

        if self.week is None:
            super().ingest_data(data)
            return

        # 1) Persist the week-specific partition (overwrites existing snapshot).
        partition_week = Partition({"year": str(self.year), "week": str(self.week)})
        written = self.storage.write(
            self.entity_name, data, partition_week, overwrite=True
        )
        print(
            f"Wrote {written} records to "
            f"{self.entity_name}/{partition_week.path_suffix()}."
        )

        # 2) Upsert into the year-level file so downstream reads get the latest scores.
        year_dir = Path(self.storage.root()) / self.entity_name / f"year={self.year}"
        year_file = year_dir / "data.csv"
        if year_file.exists():
            existing_df = pd.read_csv(year_file)
        else:
            existing_df = pd.DataFrame()

        def _normalize_record(record: dict[str, Any]) -> dict[str, Any]:
            normalized: dict[str, Any] = {}
            for key, value in record.items():
                if isinstance(value, (datetime, pd.Timestamp)):
                    normalized[key] = value.isoformat()
                elif isinstance(value, Enum):
                    normalized[key] = (
                        value.value if hasattr(value, "value") else str(value)
                    )
                elif isinstance(value, (list, tuple, set)):
                    normalized[key] = json.dumps(list(value))
                else:
                    normalized[key] = value
            return normalized

        normalized_data = [_normalize_record(row) for row in data]
        new_df = pd.DataFrame(normalized_data)

        if existing_df.empty:
            combined_df = new_df
        else:
            combined_df = pd.concat(
                [existing_df, new_df], ignore_index=True, sort=False
            )
            # Keep the last occurrence so freshly-ingested games overwrite stale rows.
            combined_df = combined_df.drop_duplicates(subset="id", keep="last")

        # Optional stability: sort by week then start date for reproducible ordering.
        sort_cols = [col for col in ["week", "start_date", "id"] if col in combined_df]
        if sort_cols:
            combined_df = combined_df.sort_values(sort_cols).reset_index(drop=True)

        combined_records = combined_df.to_dict(orient="records")
        partition_year = Partition({"year": str(self.year)})
        # Avoid removing the entire year directory (which also holds week= subfolders).
        self.storage.write(
            self.entity_name,
            combined_records,
            partition_year,
            overwrite=False,
        )


def main() -> None:
    """CLI entry point for games ingestion."""
    parser = argparse.ArgumentParser(description="Ingest games data from CFBD API.")
    parser.add_argument(
        "--year", type=int, default=2024, help="The year to ingest data for."
    )
    parser.add_argument(
        "--season_type",
        type=str,
        default="regular",
        help="Season type (regular/postseason).",
    )
    parser.add_argument(
        "--data-root",
        type=str,
        default=None,
        help="Local data root path (defaults to placeholder).",
    )
    parser.add_argument(
        "--exclude-seasons",
        type=str,
        default="2020",
        help="Comma-separated list of seasons to skip (default: 2020).",
    )
    args = parser.parse_args()

    excluded = {int(s.strip()) for s in args.exclude_seasons.split(",") if s.strip()}
    if args.year in excluded:
        print(f"Season {args.year} is excluded. Skipping.")
        return

    ingester = GamesIngester(
        year=args.year,
        season_type=args.season_type,
        data_root=args.data_root,
        classification="fbs",
    )
    ingester.run()


if __name__ == "__main__":
    main()
