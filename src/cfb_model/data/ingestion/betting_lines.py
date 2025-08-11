"""Betting lines data ingestion from CFBD API."""

from typing import Any

import cfbd

from .base import BaseIngester


class BettingLinesIngester(BaseIngester):
    """Ingester for college football betting lines data."""

    def __init__(
        self,
        year: int = 2024,
        classification: str = "fbs",
        season_type: str = "regular",
        limit_games: int = None,
        data_root: str | None = None,
        storage=None,
    ):
        """Initialize the betting lines ingester.

        Args:
            year: The year to ingest data for (default: 2024)
            classification: Team classification filter (default: "fbs")
            season_type: Season type to ingest (default: "regular")
            limit_games: Limit number of games for testing (default: None)
        """
        super().__init__(year, classification, data_root=data_root, storage=storage)
        self.season_type = season_type
        self.limit_games = limit_games

    @property
    def entity_name(self) -> str:
        """The logical entity name for storage."""
        return "betting_lines"

    @property
    def partition_keys(self) -> list[str]:
        return ["year", "season_type"]

    def get_fbs_game_ids(self) -> list[int]:
        """Get list of FBS game IDs from local games index."""
        index_filters = {"year": str(self.year), "season_type": self.season_type}
        games_index = self.storage.read_index(
            "games", filters=index_filters, columns=["id"]
        )

        if not games_index:
            raise RuntimeError(f"Games index not found for year {self.year} and season_type {self.season_type}. Please run the games ingester first.")

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

        year_lines = betting_api.get_lines(
            year=self.year, season_type=self.season_type
        )
        print(f"Fetched {len(year_lines)} total games with betting lines from API.")

        # Filter lines for our specific FBS games and flatten the structure
        all_lines = []
        fbs_game_ids_set = set(fbs_game_ids)
        for game_line in year_lines:
            if self.safe_getattr(game_line, "id") in fbs_game_ids_set:
                for sportsbook_line in self.safe_getattr(game_line, "lines", []):
                    all_lines.append({
                        "game_id": self.safe_getattr(game_line, "id"),
                        "line_data": sportsbook_line,
                    })

        print(f"Filtered to {len(all_lines)} betting lines from FBS games.")
        return all_lines

    def transform_data(self, data: list[Any]) -> list[dict[str, Any]]:
        """Transform betting lines data into storage format."""
        lines_to_insert = []
        for item in data:
            game_id = item.get("game_id")
            line = item.get("line_data")
            if not line:
                continue

            lines_to_insert.append(
                {
                    "year": self.year,
                    "season_type": self.season_type,
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
            )
        return lines_to_insert


def main() -> None:
    """CLI entry point for betting lines ingestion."""
    ingester = BettingLinesIngester()
    ingester.run()


if __name__ == "__main__":
    main()
