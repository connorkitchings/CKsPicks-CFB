"""Game stats data ingestion from CFBD API."""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import cfbd

from src.utils.base import Partition

from .base import BaseIngester


class GameStatsIngester(BaseIngester):
    """Ingester for college football team game stats (box scores)."""

    def __init__(
        self,
        year: int = 2024,
        classification: str = "fbs",
        season_type: str = "regular",
        limit_games: int = None,
        data_root: str | None = None,
        storage=None,
    ):
        super().__init__(year, classification, data_root=data_root, storage=storage)
        self.season_type = season_type
        self.limit_games = limit_games

    @property
    def entity_name(self) -> str:
        return "game_stats_raw"

    def get_fbs_games_info(self) -> list[tuple[int, int]]:
        """Get list of (game ID, week) tuples from local games index."""
        index_filters = {"year": str(self.year)}
        games_index = self.storage.read_index(
            "games", filters=index_filters, columns=["id", "week"]
        )
        if not games_index:
            raise RuntimeError(
                f"Games index not found for year {self.year}. Please run the games ingester first."
            )
        games_info = []
        for game in games_index:
            if game.get("id") and game.get("week"):
                games_info.append((game["id"], game["week"]))

        if self.limit_games:
            games_info = games_info[: self.limit_games]
            print(f"Limited to first {self.limit_games} games for testing.")
        return games_info

    def fetch_data(self) -> list[Any]:
        """Fetch game team stats (bulk by week) from the CFBD API for FBS games."""
        games_info = self.get_fbs_games_info()
        print(f"Found {len(games_info)} FBS games to process for team stats.")

        games_by_week: dict[int, set[int]] = {}
        for gid, week in games_info:
            if week is None:
                continue
            games_by_week.setdefault(int(week), set()).add(int(gid))

        def fetch_week_stats(week: int) -> list[Any]:
            try:
                api = cfbd.GamesApi(cfbd.ApiClient(self.cfbd_config))
                return api.get_game_team_stats(
                    year=self.year, week=week, season_type=self.season_type
                )
            except Exception as e:
                print(f"    Error fetching team stats for week {week}: {e}")
                return []

        all_stats: list[Any] = []
        weeks = sorted(games_by_week.keys())

        # Minimize API calls: skip weeks that are already present in raw storage
        base_week_dir = self.storage.root() / "game_stats_raw" / f"year={self.year}"
        weeks_to_fetch: list[int] = []
        for w in weeks:
            week_dir = base_week_dir / f"week={int(w)}"
            expected_games = len(games_by_week.get(w, set()))
            existing = 0
            if week_dir.exists():
                try:
                    existing = len(
                        [
                            d
                            for d in week_dir.iterdir()
                            if d.is_dir() and d.name.startswith("game_id=")
                        ]
                    )
                except FileNotFoundError:
                    existing = 0
            if existing >= expected_games and expected_games > 0:
                print(
                    f"  Skipping team stats for week {w}: already ingested ({existing}/{expected_games} games)."
                )
                continue
            weeks_to_fetch.append(w)

        workers = max(1, getattr(self, "workers", 4))
        if weeks_to_fetch:
            with ThreadPoolExecutor(max_workers=workers) as ex:
                futures = {ex.submit(fetch_week_stats, w): w for w in weeks_to_fetch}
                for fut in as_completed(futures):
                    w = futures[fut]
                    week_stats = fut.result() or []
                    wanted_gids = games_by_week[w]
                    for s in week_stats:
                        gid = self.safe_getattr(s, "game_id", None)
                        if gid in wanted_gids:
                            all_stats.append((w, s))

        print(f"Total raw team stats objects collected: {len(all_stats)}")
        return all_stats

    def transform_data(self, data: list[Any]) -> list[dict[str, Any]]:
        """Transform weekly team stats into storage format with raw JSON per game/team row.

        Input 'data' elements are tuples: (week, team_stats_object)
        """
        records = []
        for tup in data:
            try:
                # Support (week, item) or (week, gid, item)
                if len(tup) == 3:
                    week, gid, item = tup
                else:
                    week, item = tup
                    gid = None
                raw_dict = item.to_dict()
                game_id = raw_dict.get("game_id") or raw_dict.get("gameId")
                if not game_id:
                    gi = raw_dict.get("game_info") or raw_dict.get("gameInfo")
                    if isinstance(gi, dict):
                        game_id = gi.get("id")
                if not game_id:
                    game_id = raw_dict.get("id")
                if not game_id and gid is not None:
                    game_id = gid
                if not game_id:
                    # Skip if no game id could be resolved
                    continue
                raw_json = json.dumps(raw_dict)
                records.append(
                    {
                        "game_id": int(game_id),
                        "year": self.year,
                        "week": int(week),
                        "raw_data": raw_json,
                    }
                )
            except Exception as e:
                print(f"Could not serialize team stats object: {e}")
        print(f"Successfully transformed {len(records)} records.")
        return records

    def ingest_data(self, data: list[dict[str, Any]]) -> None:
        """Write raw game_stats data partitioned by year/week/game_id."""
        if not data:
            print("No data to ingest.")
            return

        total_written = 0
        for record in data:
            game_id = record.get("game_id")
            week = record.get("week")
            if not game_id or not week:
                continue

            rows_to_write = [record]
            partition = Partition(
                {
                    "year": str(self.year),
                    "week": str(week),
                    "game_id": str(game_id),
                }
            )

            written = self.storage.write(
                self.entity_name, rows_to_write, partition, overwrite=True
            )
            total_written += written
        print(f"Total {self.entity_name} records written: {total_written}")


#
