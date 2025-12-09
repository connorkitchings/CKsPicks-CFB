"""Persistence layer for pre-aggregations.

Reads raw plays for a season, builds byplay/drives/team-game/team-season
artifacts, applies opponent adjustment, and writes partitioned CSV outputs to
processed storage.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from utils.base import Partition
from utils.local_storage import LocalStorage

from .core import (
    aggregate_team_season,
    apply_iterative_opponent_adjustment,
)
from .pipeline import build_preaggregation_pipeline
from .weather import load_weather_data


def persist_preaggregations(
    *, year: int, data_root: str | None = None, verbose: bool = True
) -> dict[str, int]:
    raw_storage = LocalStorage(data_root=data_root, file_format="csv", data_type="raw")
    records = raw_storage.read_index("plays", {"year": year})
    if not records:
        logging.info(f"No raw plays found for season {year} under {raw_storage.root()}")
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

    # Load games data for situational features
    games_records = raw_storage.read_index("games", {"year": year})
    games_df = pd.DataFrame.from_records(games_records) if games_records else pd.DataFrame()

    # Load teams and venues data for travel distance calculation
    teams_records = raw_storage.read_index("teams", {"year": year})
    teams_df = pd.DataFrame.from_records(teams_records) if teams_records else pd.DataFrame()
    venues_records = raw_storage.read_index("venues", {"year": year})
    venues_df = pd.DataFrame.from_records(venues_records) if venues_records else pd.DataFrame()

    # Load weather data
    weather_df = load_weather_data(year, raw_storage.root().parent)

    byplay_df, drives_df, team_game_df, team_season_df = build_preaggregation_pipeline(
        plays_df,
        games_df=games_df,
        teams_df=teams_df,
        venues_df=venues_df,
        weather_df=weather_df,
    )
    team_season_adj_iterations_df = apply_iterative_opponent_adjustment(
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
        "team_season_adj_iterations": 0,
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

    # By-play: partition by year/week/game_id (one folder per game)
    for (week, game_id), group in byplay_df.groupby(["week", "game_id"], dropna=False):
        if verbose:
            game_meta = game_to_teams_map.get(game_id, {})
            home_team = game_meta.get("home", "?")
            away_team = game_meta.get("away", "?")
            logging.info(
                f"Processing season={year}, week={int(week)}, game_id={int(game_id)}: {home_team} vs {away_team}"
            )
        part = Partition(
            {"year": str(year), "week": str(int(week)), "game_id": str(int(game_id))}
        )
        rows = group.to_dict(orient="records")
        totals["byplay"] += processed_storage.write(
            "byplay", rows, part, overwrite=True
        )

    # Drives: partition by year/week/game_id (one folder per game, rows are per drive)
    for (week, game_id), group in drives_df.groupby(["week", "game_id"], dropna=False):
        if verbose:
            game_meta = game_to_teams_map.get(game_id, {})
            home_team = game_meta.get("home", "?")
            away_team = game_meta.get("away", "?")
            logging.info(
                f"Processing DRIVES season={year}, week={int(week)}, game_id={int(game_id)}: {home_team} vs {away_team}"
            )
        part = Partition(
            {"year": str(year), "week": str(int(week)), "game_id": str(int(game_id))}
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
    for team, group in team_season_df.groupby("team", dropna=False):
        offense_cols = [
            c
            for c in group.columns
            if c.startswith("off_")
            or c
            in [
                "season",
                "team",
                "games_played",
                "plays_per_game",
                "drives_per_game",
                "cumulative_luck_factor",
            ]
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

    # Save the new long-format DataFrame with all adjustment iterations
    part = Partition({"year": str(year)})
    rows = team_season_adj_iterations_df.to_dict(orient="records")
    totals["team_season_adj_iterations"] += processed_storage.write(
        "team_season_adj_iterations", rows, part, overwrite=True
    )

    # Team-week-adjusted: partition by year/week (for training)
    # This logic needs to be updated to use the new iteration-aware data.
    # For now, we will extract the final iteration for the point-in-time calculation.
    logging.info(f"Generating team_week_adj for {year}...")

    # Load PPR ratings for this year
    ppr_path = Path("artifacts/features/ppr_ratings.parquet")
    ppr_year_df = pd.DataFrame()
    if ppr_path.exists():
        logging.info(f"Loading PPR ratings for {year} from {ppr_path}...")
        ppr_df = pd.read_parquet(ppr_path)
        ppr_year_df = ppr_df[ppr_df["year"] == int(year)].copy()
        logging.info(f"Loaded {len(ppr_year_df)} ratings for {year}.")
    else:
        logging.warning(
            f"PPR ratings file not found at {ppr_path.absolute()}. Skipping injection."
        )

    max_week = team_game_df["week"].max()
    for week in range(1, int(max_week) + 2):
        past_games = team_game_df[team_game_df["week"] < week].copy()
        if past_games.empty:
            continue

        std_df = aggregate_team_season(past_games)

        # We run the adjustment on point-in-time data
        std_adj_iterations_df = apply_iterative_opponent_adjustment(std_df, past_games)

        # For the team_week_adj dataset, we only need the FINAL iteration
        final_iteration = std_adj_iterations_df["iteration"].max()
        std_adj_df = std_adj_iterations_df[
            std_adj_iterations_df["iteration"] == final_iteration
        ].copy()

        std_adj_df["week"] = week

        if not ppr_year_df.empty:
            week_ratings = ppr_year_df[ppr_year_df["week"] == week][
                ["team", "ppr_rating"]
            ]
            if not week_ratings.empty:
                std_adj_df = std_adj_df.merge(week_ratings, on="team", how="left")
                if "ppr_rating" in std_adj_df.columns:
                    std_adj_df["ppr_rating"] = std_adj_df["ppr_rating"].fillna(0.0)

        part = Partition({"year": str(year), "week": str(week)})
        # Note: This total is not captured in the final summary, as it's part of the same conceptual dataset.
        processed_storage.write(
            "team_week_adj",
            std_adj_df.to_dict(orient="records"),
            part,
            overwrite=True,
        )

    root = processed_storage.root()
    if verbose:
        logging.info(
            f"Pre-aggregations written under {root} for season {year}: "
            f"byplay={totals['byplay']}, drives={totals['drives']}, "
            f"team_game={totals['team_game']}, team_season={totals['team_season']}, "
            f"team_season_adj_iterations={totals['team_season_adj_iterations']}"
        )
    return totals


def persist_byplay_only(
    *, year: int, data_root: str | None = None, verbose: bool = True
) -> int:
    """Build and persist only the byplay dataset from raw plays."""
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

    if verbose:
        print(
            f"Byplay written under {processed_storage.root()} for season {year}: rows={total_written}"
        )
    return total_written


#
