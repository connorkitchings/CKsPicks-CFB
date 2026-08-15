"""Betting lines data ingestion from CFBD API."""

import hashlib
import time
from typing import Any

import cfbd

from cks_picks_cfb.utils.base import Partition

from .base import BaseIngester
from .week_policy import canonical_week_overrides_for_season


class BettingLineCoverageError(RuntimeError):
    """Raised when a publish requires lines for every scheduled FBS game."""

    def __init__(
        self,
        *,
        year: int,
        week: int,
        missing_spread_game_ids: set[int],
        missing_total_game_ids: set[int],
    ):
        missing_game_ids = missing_spread_game_ids | missing_total_game_ids
        super().__init__(
            f"CFBD betting-line coverage is incomplete for {year} week {week}: "
            f"{len(missing_spread_game_ids)} games lack a spread and "
            f"{len(missing_total_game_ids)} games lack a total."
        )
        self.year = year
        self.week = week
        self.missing_game_ids = missing_game_ids
        self.missing_spread_game_ids = missing_spread_game_ids
        self.missing_total_game_ids = missing_total_game_ids


class BettingLinesIngester(BaseIngester):
    """Ingester for college football betting lines data."""

    def __init__(
        self,
        year: int = 2024,
        classification: str = "fbs",
        season_type: str = "regular",
        week: int | None = None,
        limit_games: int = None,
        require_full_coverage: bool = False,
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
            require_full_coverage: Fail before writing when any scheduled FBS
                game lacks a sportsbook line. Use for a pregame publish.
        """
        super().__init__(year, classification, data_root=data_root, storage=storage)
        self.season_type = season_type
        self.week = week
        self.limit_games = limit_games
        self.require_full_coverage = require_full_coverage
        self._provider_weeks: set[int] = set()

    @property
    def entity_name(self) -> str:
        """The logical entity name for storage."""
        return "raw/betting_lines"

    @property
    def source_endpoint(self) -> str:
        return "BettingApi.get_lines"

    def source_parameters(self) -> dict[str, Any]:
        parameters: dict[str, Any] = {
            "year": self.year,
            "season_type": self.season_type,
            "classification": self.classification,
            "require_full_coverage": self.require_full_coverage,
        }
        if self.week is not None:
            # Resolve the provider week before the immutable request manifest is
            # created so lineage describes the actual CFBD request as well as
            # the canonical partition requested by the operator.
            self.get_fbs_game_ids()
            parameters["canonical_week"] = self.week
            if len(self._provider_weeks) == 1:
                parameters["week"] = next(iter(self._provider_weeks))
            else:
                parameters["provider_weeks"] = sorted(self._provider_weeks)
        return parameters

    @property
    def partition_keys(self) -> list[str]:
        if self.week is not None:
            return ["year", "week"]
        return ["year"]

    def get_fbs_game_ids(self) -> list[int]:
        """Get FBS game IDs, tolerating brief object-index visibility lag."""
        self._provider_weeks = set()
        # Read games at year level (games are year-level files, not week-partitioned)
        games_index = []
        for attempt in range(4):
            games_index = self.storage.read_index(
                "raw/games",
                filters={"year": str(self.year)},
                columns=["id", "week"],
            )
            if games_index:
                break
            if attempt < 3:
                time.sleep(0.5 * (2**attempt))
        if self.week is not None:
            overrides = canonical_week_overrides_for_season(self.year)
            selected = []
            for game in games_index:
                game_id = int(game["id"])
                provider_week = int(game.get("week", 0))
                canonical_week = overrides.get(game_id, provider_week)
                if canonical_week == self.week:
                    selected.append(game)
                    self._provider_weeks.add(provider_week)
            games_index = selected

        if not games_index:
            raise RuntimeError(
                f"Games index not found for year {self.year}. Please run the games ingester first."
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
        if self.week is not None and len(self._provider_weeks) == 1:
            # CFBD labels some opening slates as provider Week 1 while the
            # checked-in policy assigns canonical Week 0. Query the provider's
            # label, then filter to the canonical slate by game ID below.
            lines_params["week"] = next(iter(self._provider_weeks))

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
                            "provider_week": self.safe_getattr(game_line, "week"),
                            "week": self.week
                            if self.week is not None
                            else self.safe_getattr(game_line, "week"),
                            "line_data": sportsbook_line,
                        }
                    )

        print(f"Filtered to {len(all_lines)} betting lines from FBS games.")
        if self.require_full_coverage:
            if self.week is None:
                raise ValueError(
                    "require_full_coverage requires a specific week so coverage "
                    "can be evaluated against that slate."
                )
            spread_game_ids = {
                row["game_id"]
                for row in all_lines
                if self.safe_getattr(row["line_data"], "spread") is not None
            }
            total_game_ids = {
                row["game_id"]
                for row in all_lines
                if self.safe_getattr(row["line_data"], "over_under") is not None
            }
            missing_spread_game_ids = set(fbs_game_ids) - spread_game_ids
            missing_total_game_ids = set(fbs_game_ids) - total_game_ids
            if missing_spread_game_ids or missing_total_game_ids:
                raise BettingLineCoverageError(
                    year=self.year,
                    week=self.week,
                    missing_spread_game_ids=missing_spread_game_ids,
                    missing_total_game_ids=missing_total_game_ids,
                )
        return all_lines

    def transform_data(self, data: list[Any]) -> list[dict[str, Any]]:
        """Transform betting lines data into storage format."""
        lines_to_insert = []
        for item in data:
            game_id = item.get("game_id")
            week = item.get("week")
            provider_week = item.get("provider_week", week)
            line = item.get("line_data")
            if not line:
                continue

            record = {
                "year": self.year,
                "season_type": self.season_type,
                "week": week,
                "provider_week": provider_week,
                "game_id": game_id,
                "provider": self.safe_getattr(line, "provider"),
                "spread": self.safe_getattr(line, "spread"),
                "formatted_spread": self.safe_getattr(line, "formatted_spread"),
                "spread_open": self.safe_getattr(line, "spread_open"),
                "over_under": self.safe_getattr(line, "over_under"),
                "over_under_open": self.safe_getattr(line, "over_under_open"),
                "home_moneyline": self.safe_getattr(line, "home_moneyline"),
                "away_moneyline": self.safe_getattr(line, "away_moneyline"),
                "captured_at": self.capture_time.isoformat(),
            }
            quote_identity = (
                f"cfbd:{game_id}:{record['provider']}:{record['spread']}:"
                f"{record['over_under']}:{record['captured_at']}"
            )
            record["quote_id"] = hashlib.sha256(
                quote_identity.encode("utf-8")
            ).hexdigest()[:32]
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
