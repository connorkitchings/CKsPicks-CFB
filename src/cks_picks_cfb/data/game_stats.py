"""Game stats data ingestion from CFBD API."""

import json
from datetime import datetime, timezone
from typing import Any

import cfbd

from cks_picks_cfb.utils.base import Partition

from .base import BaseIngester
from .sources import SourceRequest
from .week_policy import select_canonical_week_games


class GameStatsIngester(BaseIngester):
    """Ingester for college football team game stats (box scores)."""

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
        super().__init__(year, classification, data_root=data_root, storage=storage)
        self.season_type = season_type
        self.week = week
        self.limit_games = limit_games

    @property
    def entity_name(self) -> str:
        return "raw/game_stats"

    @property
    def source_endpoint(self) -> str:
        return "GamesApi.get_game_team_stats"

    def get_fbs_games_info(self) -> list[tuple[int, int]]:
        """Get list of (game ID, week) tuples from local games index."""
        index_filters = {"year": str(self.year)}
        games_index = self.storage.read_index(
            "raw/games", filters=index_filters, columns=["id", "week"]
        )
        if not games_index:
            raise RuntimeError(
                f"Games index not found for year {self.year}. Please run the games ingester first."
            )
        if self.week is not None:
            selected = select_canonical_week_games(
                games_index, season=self.year, canonical_week=self.week
            )
            games_info = [(item.game_id, item.provider_week) for item in selected]
        else:
            games_info = [
                (game["id"], game["week"])
                for game in games_index
                if game.get("id") is not None and game.get("week") is not None
            ]

        if self.limit_games:
            games_info = games_info[: self.limit_games]
            print(f"Limited to first {self.limit_games} games for testing.")
        return games_info

    def source_requests(self) -> list[SourceRequest]:
        games_info = self.get_fbs_games_info()
        print(f"Found {len(games_info)} FBS games to process for team stats.")

        games_by_week: dict[int, set[int]] = {}
        for gid, week in games_info:
            if week is None:
                continue
            games_by_week.setdefault(int(week), set()).add(int(gid))

        weeks = sorted(games_by_week.keys())
        if not weeks:
            raise RuntimeError(
                f"No scheduled games found for {self.year} week {self.week}"
            )
        requested_at = datetime.now(timezone.utc)
        return [
            SourceRequest(
                provider="cfbd",
                entity="game_stats",
                endpoint=self.source_endpoint,
                parameters={
                    "year": self.year,
                    "week": week,
                    **({"canonical_week": self.week} if self.week is not None else {}),
                    "season_type": self.season_type,
                    "classification": self.classification,
                    "expected_game_ids": sorted(games_by_week[week]),
                },
                requested_at=requested_at,
            )
            for week in weeks
        ]

    def fetch_source_request(self, request: dict[str, Any]) -> list[Any]:
        api = cfbd.GamesApi(cfbd.ApiClient(self.cfbd_config))
        week = int(request["week"])
        wanted = {int(game_id) for game_id in request["expected_game_ids"]}
        stats = api.get_game_team_stats(
            year=int(request["year"]),
            week=week,
            season_type=str(request["season_type"]),
            classification=str(request["classification"]),
            _request_timeout=self.request_timeout_seconds,
        )
        return [
            {
                "request_week": week,
                "canonical_week": int(request.get("canonical_week", week)),
                "provider_record": stat,
            }
            for stat in stats
            if self.safe_getattr(stat, "game_id", None) in wanted
        ]

    def fetch_data(self) -> list[Any]:
        return [
            record
            for request in self.source_requests()
            for record in self.fetch_source_request(dict(request.parameters))
        ]

    def transform_data(self, data: list[Any]) -> list[dict[str, Any]]:
        """Transform weekly team stats into storage format with raw JSON per game/team row.

        Input 'data' elements are tuples: (week, team_stats_object)
        """
        records = []
        for tup in data:
            try:
                provider_week: int | None = None
                if isinstance(tup, dict) and "provider_record" in tup:
                    provider_week = int(tup["request_week"])
                    week = int(tup.get("canonical_week", provider_week))
                    item = tup["provider_record"]
                    gid = None
                # Support (week, item) or (week, gid, item)
                elif len(tup) == 3:
                    week, gid, item = tup
                else:
                    week, item = tup
                    gid = None
                raw_dict = item.to_dict() if hasattr(item, "to_dict") else dict(item)
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
                    raise ValueError(f"Team stats row has no game_id: {raw_dict}")
                raw_json = json.dumps(raw_dict)
                records.append(
                    {
                        "game_id": int(game_id),
                        "year": self.year,
                        "week": int(week),
                        "provider_week": int(provider_week or week),
                        "raw_data": raw_json,
                    }
                )
            except Exception as e:
                raise ValueError(f"Could not serialize team stats row {tup!r}") from e
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
            if game_id is None or week is None:
                raise ValueError("Team stats record is missing game_id or week")

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
