"""Games data ingestion from CFBD API."""

import argparse
from typing import Any

import cfbd

from .base import BaseIngester


class GamesIngester(BaseIngester):
    """Ingester for college football games data."""

    def __init__(
        self,
        year: int = 2024,
        classification: str = "fbs",
        season_type: str = "regular",
        *,
        data_root: str | None = None,
        storage=None,
    ):
        """Initialize the games ingester.

        Args:
            year: The year to ingest data for (default: 2024)
            classification: Team classification filter (default: "fbs")
            season_type: Season type to ingest (default: "regular")
        """
        super().__init__(year, classification, data_root=data_root, storage=storage)
        self.season_type = season_type

    @property
    def entity_name(self) -> str:
        """The logical entity name for storage."""
        return "games"

    @property
    def partition_keys(self) -> list[str]:
        return ["year", "season_type"]

    def get_fbs_team_names(self) -> set[str]:
        """Get list of FBS team names for filtering games.

        Returns:
            Set of FBS team names
        """
        teams_api = cfbd.TeamsApi(cfbd.ApiClient(self.cfbd_config))
        teams = teams_api.get_teams(year=self.year)
        fbs_teams = [
            team.school
            for team in teams
            if getattr(team, "classification", "").lower() == self.classification
        ]
        return set(fbs_teams)

    def fetch_data(self) -> list[Any]:
        """Fetch games data from the CFBD API.

        Returns:
            List of game objects from CFBD API
        """
        games_api = cfbd.GamesApi(cfbd.ApiClient(self.cfbd_config))

        # Get FBS team names for filtering
        fbs_team_names = self.get_fbs_team_names()
        print(f"Found {len(fbs_team_names)} FBS teams for filtering.")

        # Fetch all games for the year and season type
        all_games = games_api.get_games(year=self.year, season_type=self.season_type)

        # Filter for FBS games only (games where both teams are FBS)
        fbs_games = [
            game
            for game in all_games
            if (
                self.safe_getattr(game, "home_team", "") in fbs_team_names
                and self.safe_getattr(game, "away_team", "") in fbs_team_names
            )
        ]

        print(f"Found {len(fbs_games)} FBS games out of {len(all_games)} total games.")
        return fbs_games

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
                }
            )

        return games_to_insert


def main() -> None:
    """CLI entry point for games ingestion."""
    parser = argparse.ArgumentParser(description="Ingest games data from CFBD API.")
    parser.add_argument("--year", type=int, default=2024, help="The year to ingest data for.")
    parser.add_argument(
        "--season_type", type=str, default="regular", help="Season type (regular/postseason)."
    )
    parser.add_argument(
        "--data-root", type=str, default=None, help="Local data root path (defaults to placeholder)."
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
