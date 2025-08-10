"""Drives data ingestion from CFBD API."""

import argparse
from typing import Any

import cfbd

from .base import BaseIngester


class DrivesIngester(BaseIngester):
    """Ingester for college football drives data."""

    def __init__(
        self,
        year: int = 2024,
        classification: str = "fbs",
        season_type: str = "regular",
        limit_games: int = None,
    ):
        """Initialize the drives ingester.

        Args:
            year: The year to ingest data for (default: 2024)
            classification: Team classification filter (default: "fbs")
            season_type: Season type to ingest (default: "regular")
            limit_games: Limit number of games for testing (default: None)
        """
        super().__init__(year, classification)
        self.season_type = season_type
        self.limit_games = limit_games

    @property
    def table_name(self) -> str:
        """The name of the Supabase table to ingest data into."""
        return "drives"

    def get_fbs_game_ids(self) -> list[tuple[int, int]]:
        """Get list of FBS game IDs and weeks from our games table.

        Returns:
            List of tuples containing (game_id, week)
        """
        response = (
            self.supabase.table("games")
            .select("id, week")
            .eq("season", self.year)
            .execute()
        )
        games_data = [(game["id"], game["week"]) for game in response.data]

        if self.limit_games:
            games_data = games_data[: self.limit_games]
            print(f"Limited to first {self.limit_games} games for testing.")

        return games_data

    def fetch_data(self) -> list[Any]:
        """Fetch drives data from the CFBD API.

        Returns:
            List of drive objects from CFBD API
        """
        drives_api = cfbd.DrivesApi(cfbd.ApiClient(self.cfbd_config))

        print(
            f"Getting FBS game IDs from database for {self.year} {self.season_type} season..."
        )
        fbs_games_data = self.get_fbs_game_ids()
        print(f"Found {len(fbs_games_data)} FBS games to process.")

        all_drives = []
        batch_size = 50  # Process games in batches to avoid overwhelming the API

        for i in range(0, len(fbs_games_data), batch_size):
            batch_games_data = fbs_games_data[i : i + batch_size]
            print(
                f"Processing games {i + 1}-{min(i + batch_size, len(fbs_games_data))} of {len(fbs_games_data)}..."
            )

            # Group games by week to minimize API calls
            games_by_week = {}
            for game_id, week in batch_games_data:
                if week not in games_by_week:
                    games_by_week[week] = []
                games_by_week[week].append(game_id)

            for week, game_ids_in_week in games_by_week.items():
                try:
                    print(f"  Fetching drives for week {week}...")
                    week_drives = drives_api.get_drives(
                        year=self.year, season_type=self.season_type, week=week
                    )

                    # Filter drives to only those from our FBS games
                    fbs_drives = [
                        drive
                        for drive in week_drives
                        if self.safe_getattr(drive, "game_id", None) in game_ids_in_week
                    ]

                    all_drives.extend(fbs_drives)
                    print(
                        f"    Found {len(fbs_drives)} drives from FBS games in week {week}"
                    )

                except Exception as e:
                    print(f"    Error fetching drives for week {week}: {e}")
                    continue

        print(f"Total drives collected: {len(all_drives)}")
        return all_drives

    def transform_data(self, data: list[Any]) -> list[dict[str, Any]]:
        """Transform drives data into Supabase table format.

        Args:
            data: List of drive objects from CFBD API

        Returns:
            List of dictionaries ready for Supabase insertion
        """
        drives_to_insert = []

        for drive in data:
            drives_to_insert.append(
                {
                    "id": self.safe_getattr(drive, "id", None),
                    "game_id": self.safe_getattr(drive, "game_id", None),
                    "drive_number": self.safe_getattr(drive, "drive_number", None),
                    "scoring": self.safe_getattr(drive, "scoring", None),
                    "offense": self.safe_getattr(drive, "offense", None),
                    "offense_conference": self.safe_getattr(
                        drive, "offense_conference", None
                    ),
                    "defense": self.safe_getattr(drive, "defense", None),
                    "defense_conference": self.safe_getattr(
                        drive, "defense_conference", None
                    ),
                    "plays": self.safe_getattr(drive, "plays", None),
                    "yards": self.safe_getattr(drive, "yards", None),
                    "drive_result": self.safe_getattr(drive, "drive_result", None),
                    "is_home_offense": self.safe_getattr(drive, "is_home_offense", None),
                    "start_period": self.safe_getattr(drive, "start_period", None),
                    "start_yardline": self.safe_getattr(drive, "start_yardline", None),
                    "start_yards_to_goal": self.safe_getattr(
                        drive, "start_yards_to_goal", None
                    ),
                    "start_time_minutes": self.safe_getattr(drive, "start_time_minutes", None),
                    "start_time_seconds": self.safe_getattr(drive, "start_time_seconds", None),
                    "start_offense_score": self.safe_getattr(drive, "start_offense_score", None),
                    "start_defense_score": self.safe_getattr(drive, "start_defense_score", None),
                    "end_period": self.safe_getattr(drive, "end_period", None),
                    "end_yardline": self.safe_getattr(drive, "end_yardline", None),
                    "end_yards_to_goal": self.safe_getattr(
                        drive, "end_yards_to_goal", None
                    ),
                    "end_time_minutes": self.safe_getattr(drive, "end_time_minutes", None),
                    "end_time_seconds": self.safe_getattr(drive, "end_time_seconds", None),
                    "end_offense_score": self.safe_getattr(drive, "end_offense_score", None),
                    "end_defense_score": self.safe_getattr(drive, "end_defense_score", None),
                }
            )

        return drives_to_insert


def main() -> None:
    """CLI entry point for drives ingestion."""
    parser = argparse.ArgumentParser(description="Ingest drives data from CFBD API.")
    parser.add_argument(
        "--year", type=int, default=2024, help="The year to ingest data for."
    )
    parser.add_argument(
        "--season_type",
        type=str,
        default="regular",
        help="Season type to ingest (regular, postseason, or both).",
    )
    args = parser.parse_args()

    ingester = DrivesIngester(year=args.year, season_type=args.season_type)
    ingester.run()


if __name__ == "__main__":
    main()
