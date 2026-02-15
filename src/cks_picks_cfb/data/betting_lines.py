"""Betting lines data ingestion from CFBD API."""

from typing import Any

import cfbd

from cks_picks_cfb.utils.base import Partition

from .base import BaseIngester


class BettingLinesIngester(BaseIngester):
    """Ingester for college football betting lines data."""

    def __init__(
        self,
        year: int = 2024,
        classification: str = "fbs",
        season_type: str = "regular",
        week: int | None = None,
        limit_games: int = None,
        data_root: str | None = None,
        storage=None,
    ):
        """Initialize the betting lines ingester.

        Args:
            year: The year to ingest data for (default: 2024)
            classification: Team classification filter (default: "fbs")
            season_type: Season type to ingest (default: "regular")
            week: Optional specific week to ingest data for.
            limit_games: Limit number of games for testing (default: None)
        """
        super().__init__(year, classification, data_root=data_root, storage=storage)
        self.season_type = season_type
        self.week = week
        self.limit_games = limit_games

    @property
    def entity_name(self) -> str:
        """The logical entity name for storage."""
        return "betting_lines"

    @property
    def partition_keys(self) -> list[str]:
        if self.week is not None:
            return ["year", "week"]
        return ["year"]

    def get_fbs_game_ids(self) -> list[int]:
        """Get list of FBS game IDs from local games index."""
        index_filters = {"year": str(self.year)}
        if self.week is not None:
            index_filters["week"] = str(self.week)
        games_index = self.storage.read_index(
            "games", filters=index_filters, columns=["id"]
        )

        if not games_index:
            raise RuntimeError(
                f"Games index not found for year {self.year}, week {self.week}. Please run the games ingester first."
            )

        game_ids = [game["id"] for game in games_index]

        if self.limit_games:
            game_ids = game_ids[: self.limit_games]
            print(f"Limited to first {self.limit_games} games for testing.")

        return game_ids

    def fetch_data(self) -> list[Any]:
        """Fetch betting lines data from the CFBD API."""
        betting_api = cfbd.BettingApi(cfbd.ApiClient(self.cfbd_config))

        print(
            f"Getting FBS game IDs from local storage for {self.year} {self.season_type} season..."
        )
        fbs_game_ids = self.get_fbs_game_ids()
        print(f"Found {len(fbs_game_ids)} FBS games to process.")

        lines_params = {"year": self.year, "season_type": self.season_type}
        if self.week is not None:
            lines_params["week"] = self.week

        year_lines = betting_api.get_lines(**lines_params)
        print(f"Fetched {len(year_lines)} total games with betting lines from API.")

        # Filter lines for our specific FBS games and flatten the structure
        all_lines = []
        fbs_game_ids_set = set(fbs_game_ids)
        for game_line in year_lines:
            if self.safe_getattr(game_line, "id") in fbs_game_ids_set:
                for sportsbook_line in self.safe_getattr(game_line, "lines", []):
                    all_lines.append(
                        {
                            "game_id": self.safe_getattr(game_line, "id"),
                            "week": self.safe_getattr(game_line, "week"),
                            "line_data": sportsbook_line,
                        }
                    )

        print(f"Filtered to {len(all_lines)} betting lines from FBS games.")
        return all_lines

    def transform_data(self, data: list[Any]) -> list[dict[str, Any]]:
        """Transform betting lines data into storage format."""
        lines_to_insert = []
        for item in data:
            game_id = item.get("game_id")
            week = item.get("week")
            line = item.get("line_data")
            if not line:
                continue

            record = {
                "year": self.year,
                "season_type": self.season_type,
                "week": week,
                "game_id": game_id,
                "provider": self.safe_getattr(line, "provider"),
                "spread": self.safe_getattr(line, "spread"),
                "formatted_spread": self.safe_getattr(line, "formatted_spread"),
                "spread_open": self.safe_getattr(line, "spread_open"),
                "over_under": self.safe_getattr(line, "over_under"),
                "over_under_open": self.safe_getattr(line, "over_under_open"),
                "home_moneyline": self.safe_getattr(line, "home_moneyline"),
                "away_moneyline": self.safe_getattr(line, "away_moneyline"),
            }
            lines_to_insert.append(record)
        return lines_to_insert

    def ingest_data(self, data: list[dict[str, Any]]) -> None:
        """Write betting lines data partitioned by year and week."""
        if not data:
            print("No data to ingest.")
            return

        from collections import defaultdict

        by_week = defaultdict(list)
        for row in data:
            if row.get("week") is not None:
                by_week[row["week"]].append(row)

        for week, rows in by_week.items():
            partition = Partition({"year": str(self.year), "week": str(week)})
            written = self.storage.write(
                self.entity_name, rows, partition, overwrite=True
            )
            print(
                f"Wrote {written} records to {self.entity_name}/{partition.path_suffix()}."
            )


def main() -> None:
    """CLI entry point for betting lines ingestion."""
    # This main function is for standalone execution and testing.
    # The primary CLI entrypoint is in scripts/cli.py
    import argparse

    parser = argparse.ArgumentParser(description="Ingest betting lines from CFBD API.")
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--week", type=int, default=None)
    parser.add_argument(
        "--season_type", type=str, default="regular", help="regular or postseason"
    )
    args = parser.parse_args()

    ingester = BettingLinesIngester(
        year=args.year, week=args.week, season_type=args.season_type
    )
    ingester.run()


if __name__ == "__main__":
    main()
