"""Plays data ingestion from CFBD API."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import cfbd

from ..storage.base import Partition
from .base import BaseIngester


class PlaysIngester(BaseIngester):
    """Ingester for college football plays data."""

    def __init__(
        self,
        year: int = 2024,
        classification: str = "fbs",
        season_type: str = "regular",
        data_root: str | None = None,
        limit_games: int = None,
        storage=None,
    ):
        """Initialize the plays ingester.

        Args:
            year: The year to ingest data for (default: 2024)
            classification: Team classification filter (default: "fbs")
            season_type: Season type to ingest (default: "regular")
            data_root: Root path for local data storage (optional)
            limit_games: Limit number of games for testing (default: None)
        """
        super().__init__(year, classification, data_root=data_root, storage=storage)
        self.season_type = season_type
        self.limit_games = limit_games

    @property
    def entity_name(self) -> str:
        """The logical entity name for storage."""
        return "plays"

    def get_fbs_game_ids(self) -> list[tuple[int, int]]:
        """Get list of FBS game IDs and weeks from local games index."""
        idx = self.storage.read_index(
            "games", {"year": self.year}, columns=["id", "week"]
        )
        if not idx:
            raise RuntimeError(f"Games index not found for year {self.year}. Please run the games ingester first.")

        games_data = [(g["id"], g.get("week")) for g in idx]
        if self.limit_games:
            games_data = games_data[: self.limit_games]
            print(f"Limited to first {self.limit_games} games for testing.")
        return games_data

    def fetch_data(self) -> list[Any]:
        """Fetch plays data from the CFBD API.

        Returns:
            List of play objects from CFBD API
        """
        print(
            f"Getting FBS game IDs from database for {self.year} {self.season_type} season..."
        )
        fbs_games_data = self.get_fbs_game_ids()
        print(f"Found {len(fbs_games_data)} FBS games to process.")

        # Build mapping week -> set(game_ids)
        games_by_week: dict[int, set[int]] = {}
        for gid, week in fbs_games_data:
            if week is None:
                continue
            games_by_week.setdefault(int(week), set()).add(int(gid))

        def fetch_week(year: int, season_type: str, week: int) -> list[Any]:
            try:
                api = cfbd.PlaysApi(cfbd.ApiClient(self.cfbd_config))
                return api.get_plays(year=year, season_type=season_type, week=week)
            except Exception as e:
                print(f"    Error fetching plays for week {week}: {e}")
                return []

        all_plays: list[Any] = []
        weeks = sorted(games_by_week.keys())
        workers = getattr(self, "workers", 1)
        if workers and workers > 1:
            print(
                f"Fetching plays concurrently with {workers} workers across {len(weeks)} weeks..."
            )
            with ThreadPoolExecutor(max_workers=workers) as ex:
                futures = {
                    ex.submit(fetch_week, self.year, self.season_type, w): w
                    for w in weeks
                }
                for fut in as_completed(futures):
                    w = futures[fut]
                    week_plays = fut.result() or []
                    game_ids_in_week = games_by_week[w]
                    fbs_plays = [
                        p
                        for p in week_plays
                        if self.safe_getattr(p, "game_id", None) in game_ids_in_week
                    ]
                    all_plays.extend(fbs_plays)
                    print(f"  Week {w}: {len(fbs_plays)} FBS plays")
        else:
            for w in weeks:
                print(f"  Fetching plays for week {w}...")
                week_plays = fetch_week(self.year, self.season_type, w)
                game_ids_in_week = games_by_week[w]
                fbs_plays = [
                    p
                    for p in week_plays
                    if self.safe_getattr(p, "game_id", None) in game_ids_in_week
                ]
                all_plays.extend(fbs_plays)
                print(f"    Week {w}: {len(fbs_plays)} FBS plays")

        print(f"Total plays collected: {len(all_plays)}")
        return all_plays

    def transform_data(self, data: list[Any]) -> list[dict[str, Any]]:
        """Transform plays data into storage format.

        Args:
            data: List of play objects from CFBD API

        Returns:
            List of dictionaries ready for storage
        """
        plays_to_insert = []

        for play in data:
            # Handle clock data - extract minutes and seconds from clock object
            clock = self.safe_getattr(play, "clock", None)
            clock_minutes = None
            clock_seconds = None
            if clock:
                clock_minutes = self.safe_getattr(clock, "minutes", None)
                clock_seconds = self.safe_getattr(clock, "seconds", None)

            # Handle datetime fields (normalize to US/Eastern tz-aware datetime)
            wallclock = self.normalize_to_eastern(
                self.safe_getattr(play, "wallclock", None)
            )

            # Add season and week to the record
            record = {
                "season": self.year,
                "week": self.safe_getattr(play, "week", None),  # Get week from play object if available
                "id": self.safe_getattr(play, "id", None),
                "game_id": self.safe_getattr(play, "game_id", None),
                "play_number": self.safe_getattr(play, "play_number", None),
                "period": self.safe_getattr(play, "period", None),
                "clock_minutes": clock_minutes,
                "clock_seconds": clock_seconds,
                "wallclock": wallclock,
                "offense": self.safe_getattr(play, "offense", None),
                "offense_conference": self.safe_getattr(
                    play, "offense_conference", None
                ),
                "offense_score": self.safe_getattr(play, "offense_score", None),
                "offense_timeouts": self.safe_getattr(
                    play, "offense_timeouts", None
                ),
                "defense": self.safe_getattr(play, "defense", None),
                "defense_conference": self.safe_getattr(
                    play, "defense_conference", None
                ),
                "defense_score": self.safe_getattr(play, "defense_score", None),
                "defense_timeouts": self.safe_getattr(
                    play, "defense_timeouts", None
                ),
                "home": self.safe_getattr(play, "home", None),
                "away": self.safe_getattr(play, "away", None),
                "down": self.safe_getattr(play, "down", None),
                "distance": self.safe_getattr(play, "distance", None),
                "yardline": self.safe_getattr(play, "yard_line", None),
                "yards_to_goal": self.safe_getattr(play, "yards_to_goal", None),
                "yards_gained": self.safe_getattr(play, "yards_gained", None),
                "play_type": self.safe_getattr(play, "play_type", None),
                "play_text": self.safe_getattr(play, "play_text", None),
                "ppa": self.safe_getattr(play, "ppa", None),
                "scoring": self.safe_getattr(play, "scoring", None),
            }
            plays_to_insert.append(record)

        return plays_to_insert

    @property
    def partition_keys(self) -> list[str]:
        return ["year", "week", "game_id"]

    def ingest_data(self, data: list[dict[str, Any]]) -> None:
        """Write plays data partitioned by season/week/game_id to CSV."""
        if not data:
            print("No data to ingest.")
            return

        from collections import defaultdict

        # Build game_id -> week map from games index to ensure correct partitioning
        idx = self.storage.read_index(
            "games", {"year": self.year}, columns=["id", "week"]
        )
        game_week_map: dict[int, int] = {
            int(row["id"]): int(row.get("week"))
            for row in idx
            if row.get("id") is not None
        }

        by_key: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
        for row in data:
            gid_val = row.get("game_id")
            game_id = int(gid_val) if gid_val is not None else -1
            # Determine week: prefer explicit row value; else look up from games index
            week_val = row.get("week")
            if week_val is None and game_id in game_week_map:
                week_val = game_week_map[game_id]
            week = int(week_val) if week_val is not None else 0
            if game_id == -1:
                continue
            # Ensure week field is present for downstream pathing; if missing, we will try to infer later
            if "week" not in row or row["week"] is None:
                row["week"] = week
            by_key[(int(row["week"]), game_id)].append(row)

        total_written = 0
        for (week, game_id), rows in sorted(by_key.items()):
            partition = Partition(
                {"year": str(self.year), "week": str(week), "game_id": str(game_id)}
            )
            written = self.storage.write(self.entity_name, rows, partition, overwrite=True)
            total_written += written
            print(f"  Wrote {written} plays to {self.entity_name}/{self.year}/{week}/{game_id}")
        print(f"Total plays written: {total_written}")


def main() -> None:
    """CLI entry point for plays ingestion."""
    parser = argparse.ArgumentParser(description="Ingest plays data from CFBD API.")
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
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes for week fetches.",
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

    ingester = PlaysIngester(
        year=args.year,
        season_type=args.season_type,
        data_root=args.data_root,
        classification="fbs",
    )
    ingester.workers = max(1, int(args.workers))
    ingester.run()


if __name__ == "__main__":
    main()
