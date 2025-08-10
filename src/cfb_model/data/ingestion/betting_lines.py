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
    ):
        """Initialize the betting lines ingester.

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
        return "betting_lines"

    def get_fbs_game_ids(self) -> list[int]:
        """Get list of FBS game IDs from our games table.

        Returns:
            List of FBS game IDs
        """
        response = (
            self.supabase.table("games").select("id").eq("season", self.year).execute()
        )
        game_ids = [game["id"] for game in response.data]

        if self.limit_games:
            game_ids = game_ids[: self.limit_games]
            print(f"Limited to first {self.limit_games} games for testing.")

        return game_ids

    def fetch_data(self) -> list[Any]:
        """Fetch betting lines data from the CFBD API using optimized single call.

        Returns:
            List of betting line objects from CFBD API
        """
        betting_api = cfbd.BettingApi(cfbd.ApiClient(self.cfbd_config))

        print(
            f"Getting FBS game IDs from database for {self.year} {self.season_type} season..."
        )
        fbs_game_ids = self.get_fbs_game_ids()
        print(f"Found {len(fbs_game_ids)} FBS games to process.")

        try:
            # OPTIMIZATION: Make single API call instead of multiple calls in loop
            print(
                f"Fetching all betting lines for {self.year} {self.season_type} season in single API call..."
            )
            year_lines = betting_api.get_lines(
                year=self.year, season_type=self.season_type
            )

            print(f"Fetched {len(year_lines)} total games with betting lines from API.")

            # Filter lines for our specific FBS games and process
            all_lines = []
            fbs_game_ids_set = set(fbs_game_ids)  # Convert to set for faster lookup

            for line in year_lines:
                line_game_id = self.safe_getattr(line, "id", None)
                if line_game_id in fbs_game_ids_set:
                    # Process each sportsbook's lines for this game
                    lines = self.safe_getattr(line, "lines", [])
                    for sportsbook_line in lines:
                        all_lines.append((line, sportsbook_line))

            print(
                f"Filtered to {len(all_lines)} betting lines from {len([line for line in year_lines if self.safe_getattr(line, 'id', None) in fbs_game_ids_set])} FBS games."
            )
            return all_lines

        except Exception as e:
            print(f"Error with bulk betting lines fetch: {e}")
            print("Falling back to original batched method...")

            # Fallback to original method if bulk call fails
            all_lines = []
            batch_size = 50  # Process games in batches to avoid overwhelming the API

            for i in range(0, len(fbs_game_ids), batch_size):
                batch_game_ids = fbs_game_ids[i : i + batch_size]
                print(
                    f"Processing games {i + 1}-{min(i + batch_size, len(fbs_game_ids))} of {len(fbs_game_ids)}..."
                )

                try:
                    # Get all betting lines for this year
                    year_lines = betting_api.get_lines(
                        year=self.year, season_type=self.season_type
                    )

                    # Filter lines for our specific FBS games
                    for line in year_lines:
                        line_game_id = self.safe_getattr(line, "id", None)
                        if line_game_id in batch_game_ids:
                            # Process each sportsbook's lines for this game
                            lines = self.safe_getattr(line, "lines", [])
                            for sportsbook_line in lines:
                                all_lines.append((line, sportsbook_line))

                    print(
                        f"  Found {len([line_tuple for line_tuple in all_lines if self.safe_getattr(line_tuple[0], 'id', None) in batch_game_ids])} lines for this batch"
                    )

                except Exception as e:
                    print(f"  Error fetching betting lines for batch: {e}")
                    continue

            print(f"Total betting lines collected: {len(all_lines)}")
            return all_lines

    def transform_data(self, data: list[Any]) -> list[dict[str, Any]]:
        """Transform betting lines data into Supabase table format.

        Args:
            data: List of tuples containing (game_line, sportsbook_line) from CFBD API

        Returns:
            List of dictionaries ready for Supabase insertion
        """
        lines_to_insert = []

        for game_line, sportsbook_line in data:
            # Handle datetime fields
            formatted_spread = self.safe_getattr(
                sportsbook_line, "formatted_spread", None
            )
            over_under = self.safe_getattr(sportsbook_line, "over_under", None)

            lines_to_insert.append(
                {
                    "game_id": self.safe_getattr(game_line, "id", None),
                    "provider": self.safe_getattr(sportsbook_line, "provider", None),
                    "spread": self.safe_getattr(sportsbook_line, "spread", None),
                    "formatted_spread": formatted_spread,
                    "spread_open": self.safe_getattr(
                        sportsbook_line, "spread_open", None
                    ),
                    "over_under": over_under,
                    "over_under_open": self.safe_getattr(
                        sportsbook_line, "over_under_open", None
                    ),
                    "home_moneyline": self.safe_getattr(
                        sportsbook_line, "home_moneyline", None
                    ),
                    "away_moneyline": self.safe_getattr(
                        sportsbook_line, "away_moneyline", None
                    ),
                }
            )

        return lines_to_insert


def main() -> None:
    """CLI entry point for betting lines ingestion."""
    ingester = BettingLinesIngester()
    ingester.run()


if __name__ == "__main__":
    main()
