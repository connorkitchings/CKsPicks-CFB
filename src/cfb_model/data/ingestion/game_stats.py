"""Game stats data ingestion from CFBD API."""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import cfbd

from ..storage.base import Partition
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
        """Fetch game team stats (bulk by week) from the CFBD API for FBS games.

        This reduces API calls from per-game to per-week.
        """
        games_info = self.get_fbs_games_info()
        print(f"Found {len(games_info)} FBS games to process for team stats.")

        # Build mapping week -> set(game_ids)
        games_by_week: dict[int, set[int]] = {}
        for gid, week in games_info:
            if week is None:
                continue
            games_by_week.setdefault(int(week), set()).add(int(gid))

        def fetch_week_stats(week: int) -> list[Any]:
            try:
                api = cfbd.GamesApi(cfbd.ApiClient(self.cfbd_config))
                # Use team stats endpoint (bulk) to avoid per-game calls
                return api.get_game_team_stats(year=self.year, week=week, season_type=self.season_type)
            except Exception as e:
                print(f"    Error fetching team stats for week {week}: {e}")
                return []

        all_stats: list[Any] = []
        weeks = sorted(games_by_week.keys())
        workers = max(1, getattr(self, "workers", 4))
        if workers > 1:
            with ThreadPoolExecutor(max_workers=workers) as ex:
                futures = {ex.submit(fetch_week_stats, w): w for w in weeks}
                for fut in as_completed(futures):
                    w = futures[fut]
                    week_stats = fut.result() or []
                    wanted_gids = games_by_week[w]
                    # Filter to our FBS game ids for this week
                    for s in week_stats:
                        gid = self.safe_getattr(s, "game_id", None)
                        if gid in wanted_gids:
                            all_stats.append((w, s))
        else:
            for w in weeks:
                week_stats = fetch_week_stats(w)
                wanted_gids = games_by_week[w]
                for s in week_stats:
                    gid = self.safe_getattr(s, "game_id", None)
                    if gid in wanted_gids:
                        all_stats.append((w, s))

        print(f"Total raw team stats objects collected: {len(all_stats)}")

        # Fallback: if weekly team stats returned nothing, fetch per-game advanced box scores
        if not all_stats:
            # The games_info list is already limited by get_fbs_games_info if --limit-games was passed.
            # We use the full list here.
            sample = games_info
            print(f"Weekly team stats empty. Falling back to per-game advanced box scores for {len(sample)} games...")

            def fetch_box(gid: int, wk: int):
                try:
                    api = cfbd.GamesApi(cfbd.ApiClient(self.cfbd_config))
                    box = api.get_advanced_box_score(id=gid)
                    # include gid so we can persist even if box dict lacks id path
                    return wk, gid, box
                except Exception as e:
                    print(f"    Error fetching advanced box score for game {gid}: {e}")
                    return None

            with ThreadPoolExecutor(max_workers=max(1, getattr(self, "workers", 8))) as ex:
                futures = {ex.submit(fetch_box, gid, wk): gid for gid, wk in sample}
                for fut in as_completed(futures):
                    res = fut.result()
                    if res:
                        all_stats.append(res)
            print(f"Collected {len(all_stats)} advanced box scores in fallback mode.")

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
