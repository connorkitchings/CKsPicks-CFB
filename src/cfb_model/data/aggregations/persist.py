from __future__ import annotations

import pandas as pd

from .core import apply_iterative_opponent_adjustment
from .pipeline import build_preaggregation_pipeline


def persist_preaggregations(
    *, year: int, data_root: str | None = None
) -> dict[str, int]:
    """Build and persist pre-aggregations derived from raw plays into the processed store.

    Reads raw plays for the given season from local CSV storage, computes the
    by-play enriched dataset, drive-level aggregates, team-game aggregates, and
    season-to-date team aggregates (plus adjusted), then writes them to the
    `processed/` directory using season/week (and game_id where applicable) partitioning.
    """
    try:
        from cfb_model.data.storage.base import Partition
        from cfb_model.data.storage.local_storage import LocalStorage
    except Exception as exc:
        raise RuntimeError(f"Failed to import storage backends: {exc}") from exc

    raw_storage = LocalStorage(data_root=data_root, file_format="csv", data_type="raw")
    records = raw_storage.read_index("plays", {"year": year})
    if not records:
        print(f"No raw plays found for season {year} under {raw_storage.root()}")
        return {
            "byplay": 0,
            "drives": 0,
            "team_game": 0,
            "team_season": 0,
            "team_season_adj": 0,
        }

    plays_df = pd.DataFrame.from_records(records)
    if "season" not in plays_df.columns:
        plays_df["season"] = int(year)
    if "week" not in plays_df.columns:
        raise ValueError(
            "Raw plays are missing required 'week' column for partitioning."
        )

    byplay_df, drives_df, team_game_df, team_season_df = build_preaggregation_pipeline(
        plays_df
    )
    team_season_adj_df = apply_iterative_opponent_adjustment(
        team_season_df, team_game_df
    )

    processed_storage = LocalStorage(
        data_root=data_root, file_format="csv", data_type="processed"
    )
    totals: dict[str, int] = {
        "byplay": 0,
        "drives": 0,
        "team_game": 0,
        "team_season": 0,
        "team_season_adj": 0,
    }

    # Create a game_id to team names mapping for efficient logging
    game_to_teams_map = {}
    if "home" in plays_df.columns and "away" in plays_df.columns:
        game_to_teams_map = (
            plays_df[["game_id", "home", "away"]]
            .drop_duplicates()
            .set_index("game_id")
            .to_dict("index")
        )

    # By-play: partition by year/week/game (one folder per game)
    for (week, game_id), group in byplay_df.groupby(["week", "game_id"], dropna=False):
        game_meta = game_to_teams_map.get(game_id, {})
        home_team = game_meta.get("home", "?")
        away_team = game_meta.get("away", "?")
        print(
            f"Processing season={year}, week={int(week)}, game_id={int(game_id)}: {home_team} vs {away_team}"
        )
        part = Partition(
            {"year": str(year), "week": str(int(week)), "game": str(int(game_id))}
        )
        rows = group.to_dict(orient="records")
        totals["byplay"] += processed_storage.write(
            "byplay", rows, part, overwrite=True
        )

    # Drives: partition by year/week/game (one folder per game, rows are per drive)
    for (week, game_id), group in drives_df.groupby(["week", "game_id"], dropna=False):
        game_meta = game_to_teams_map.get(game_id, {})
        home_team = game_meta.get("home", "?")
        away_team = game_meta.get("away", "?")
        print(
            f"Processing DRIVES season={year}, week={int(week)}, game_id={int(game_id)}: {home_team} vs {away_team}"
        )
        part = Partition(
            {"year": str(year), "week": str(int(week)), "game": str(int(game_id))}
        )
        rows = group.to_dict(orient="records")
        totals["drives"] += processed_storage.write(
            "drives", rows, part, overwrite=True
        )

    # Team-game: partition by year/week/team
    for (week, team), group in team_game_df.groupby(["week", "team"], dropna=False):
        week_val = week[0] if isinstance(week, tuple) else week
        part = Partition(
            {"year": str(year), "week": str(int(week_val)), "team": str(team)}
        )
        rows = group.to_dict(orient="records")
        totals["team_game"] += processed_storage.write(
            "team_game", rows, part, overwrite=True
        )

    # Team-season: partition by year/team, write offense and defense CSVs in side-specific subfolders
    for team, group in team_season_df.groupby(["team"], dropna=False):
        offense_cols = [
            c
            for c in group.columns
            if c.startswith("off_") or c in ["season", "team", "games_played"]
        ]
        defense_cols = [
            c
            for c in group.columns
            if c.startswith("def_") or c in ["season", "team", "games_played"]
        ]
        group_off = group[offense_cols].copy()
        group_def = group[defense_cols].copy()
        part_off = Partition({"year": str(year), "team": str(team), "side": "offense"})
        totals["team_season"] += processed_storage.write(
            "team_season", group_off.to_dict(orient="records"), part_off, overwrite=True
        )
        part_def = Partition({"year": str(year), "team": str(team), "side": "defense"})
        totals["team_season"] += processed_storage.write(
            "team_season", group_def.to_dict(orient="records"), part_def, overwrite=True
        )

    # Team-season-adjusted: partition by year/team, write offense and defense CSVs in side-specific subfolders
    for team, group in team_season_adj_df.groupby(["team"], dropna=False):
        offense_cols = [
            c
            for c in group.columns
            if c.startswith("adj_off_") or c in ["season", "team", "games_played"]
        ]
        defense_cols = [
            c
            for c in group.columns
            if c.startswith("adj_def_") or c in ["season", "team", "games_played"]
        ]
        group_off = group[offense_cols].copy()
        group_def = group[defense_cols].copy()
        part_off = Partition({"year": str(year), "team": str(team), "side": "offense"})
        totals["team_season_adj"] += processed_storage.write(
            "team_season_adj",
            group_off.to_dict(orient="records"),
            part_off,
            overwrite=True,
        )
        part_def = Partition({"year": str(year), "team": str(team), "side": "defense"})
        totals["team_season_adj"] += processed_storage.write(
            "team_season_adj",
            group_def.to_dict(orient="records"),
            part_def,
            overwrite=True,
        )

    root = processed_storage.root()
    print(
        f"Pre-aggregations written under {root} for season {year}: "
        f"byplay={totals['byplay']}, drives={totals['drives']}, "
        f"team_game={totals['team_game']}, team_season={totals['team_season']}, "
        f"team_season_adj={totals['team_season_adj']}"
    )
    return totals


def persist_byplay_only(*, year: int, data_root: str | None = None) -> int:
    """Build and persist only the byplay dataset from raw plays."""
    try:
        from cfb_model.data.storage.base import Partition
        from cfb_model.data.storage.local_storage import LocalStorage
    except Exception as exc:
        raise RuntimeError(f"Failed to import storage backends: {exc}") from exc

    raw_storage = LocalStorage(data_root=data_root, file_format="csv", data_type="raw")
    records = raw_storage.read_index("plays", {"year": year})
    if not records:
        print(f"No raw plays found for season {year} under {raw_storage.root()}")
        return 0

    plays_df = pd.DataFrame.from_records(records)
    if "season" not in plays_df.columns:
        plays_df["season"] = int(year)
    if "week" not in plays_df.columns:
        raise ValueError("Raw plays missing required 'week' column for partitioning.")

    from .byplay import allplays_to_byplay

    byplay_df = allplays_to_byplay(plays_df)
    processed_storage = LocalStorage(
        data_root=data_root, file_format="csv", data_type="processed"
    )
    total_written = 0
    for game_id, group in byplay_df.groupby(["game_id"], dropna=False):
        part = Partition({"year": str(year), "game_id": str(int(game_id))})
        rows = group.to_dict(orient="records")
        total_written += processed_storage.write("byplay", rows, part, overwrite=True)

    print(
        f"Byplay written under {processed_storage.root()} for season {year}: rows={total_written}"
    )
    return total_written
