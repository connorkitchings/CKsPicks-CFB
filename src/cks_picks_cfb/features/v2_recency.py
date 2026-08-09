import os

import numpy as np
import pandas as pd
from tqdm import tqdm

from cks_picks_cfb.config import get_data_root
from cks_picks_cfb.features.core import apply_iterative_opponent_adjustment

MIN_CURRENT_SEASON_GAMES = 4


def completed_game_regime(games: int | float | None) -> str:
    """Return the public routing label for a completed-game count."""
    count = 0 if games is None or pd.isna(games) else max(0, int(games))
    return {
        0: "preseason",
        1: "one_game",
        2: "two_games",
        3: "three_games",
    }.get(count, "established")


def _calculate_ewma(series, alpha):
    """
    Calculate Exponentially Weighted Moving Average.
    pandas ewm uses alpha=alpha, adjust=True/False.
    If adjust=True, uses weights (1-alpha)**i.
    """
    return series.ewm(alpha=alpha, min_periods=1).mean()


def aggregate_team_season_ewma(team_game_df, alpha):
    """
    Aggregate team-game metrics using EWMA (Exponential Decay).
    """
    team_game_df = team_game_df.copy()
    date_column = next(
        (
            column
            for column in ("kickoff_utc", "start_date", "date")
            if column in team_game_df
        ),
        None,
    )
    sort_columns = ["season", "team"]
    if date_column:
        team_game_df[date_column] = pd.to_datetime(
            team_game_df[date_column], utc=True, errors="raise"
        )
        sort_columns.append(date_column)
    else:
        sort_columns.append("week")
    if "game_id" in team_game_df:
        sort_columns.append("game_id")
    team_game_df = team_game_df.sort_values(sort_columns)

    # Columns to aggregate (excluding identifiers)
    exclude_cols = [
        "season",
        "week",
        "game_id",
        "team",
        "opponent",
        "home_away",
        "date",
    ]
    metric_cols = [
        c
        for c in team_game_df.columns
        if c not in exclude_cols and pd.api.types.is_numeric_dtype(team_game_df[c])
    ]

    ewma = team_game_df.groupby(["season", "team"], sort=False)[metric_cols].transform(
        lambda series: series.ewm(alpha=alpha, min_periods=1).mean().shift(1)
    )
    team_season = team_game_df[["season", "week", "team", "game_id"]].copy()
    team_season[metric_cols] = ewma
    team_season = team_season.dropna(subset=metric_cols, how="all")

    return team_season


def _normalize_games_df(records) -> pd.DataFrame:
    games_df = pd.DataFrame(records)
    if games_df.empty:
        return games_df
    if "id" in games_df.columns:
        games_df = games_df.rename(columns={"id": "game_id"})
    if "season_type" in games_df.columns:
        games_df["season_type"] = games_df["season_type"].fillna("regular")
        games_df["week"] = np.where(
            games_df["season_type"] == "postseason",
            games_df["week"] + 15,
            games_df["week"],
        )
    return games_df


def _current_game_counts(
    team_game_df: pd.DataFrame, week: int, kickoff: object | None = None
) -> pd.Series:
    if team_game_df.empty or "week" not in team_game_df or "team" not in team_game_df:
        return pd.Series(dtype="int64")
    date_column = next(
        (column for column in ("start_date", "date") if column in team_game_df), None
    )
    if date_column and kickoff is not None and pd.notna(kickoff):
        dates = pd.to_datetime(team_game_df[date_column], utc=True, errors="coerce")
        prior_games = team_game_df[dates < pd.to_datetime(kickoff, utc=True)]
    else:
        prior_games = team_game_df[team_game_df["week"] < week]
    if prior_games.empty:
        return pd.Series(dtype="int64")
    return prior_games.groupby("team")["game_id"].nunique()


def _latest_prior_team_snapshot(read_entity, year: int) -> pd.DataFrame:
    if year == 2020:
        raise ValueError("2020 is excluded from feature construction")
    prior_year = 2019 if year == 2021 else year - 1
    if prior_year == 2020:
        raise ValueError("2020 cannot be used as prior-season feature lineage")
    records = read_entity("team_week_adj", prior_year)
    if not records:
        return pd.DataFrame()

    snapshot = pd.DataFrame.from_records(records)
    if snapshot.empty or "team" not in snapshot or "week" not in snapshot:
        return pd.DataFrame()

    snapshot = snapshot.sort_values(["team", "week"])
    return snapshot.groupby("team", as_index=False).tail(1).reset_index(drop=True)


def _prior_seed_rows(
    games_df: pd.DataFrame,
    read_entity,
    year: int,
    *,
    team_game_df: pd.DataFrame | None = None,
    min_current_games: int = MIN_CURRENT_SEASON_GAMES,
) -> pd.DataFrame:
    """Build prediction stats from prior-season snapshots for cold-start teams."""
    if games_df.empty:
        return pd.DataFrame()

    snapshot = _latest_prior_team_snapshot(read_entity, year)
    if snapshot.empty:
        return pd.DataFrame()

    snapshot_by_team = {row["team"]: row for _, row in snapshot.iterrows()}
    numeric_means = snapshot.select_dtypes(include=["number"]).mean(numeric_only=True)

    def base_row(team: str) -> dict:
        if team in snapshot_by_team:
            return snapshot_by_team[team].to_dict()
        row = numeric_means.to_dict()
        row["team"] = team
        return row

    rows = []
    current_df = team_game_df if team_game_df is not None else pd.DataFrame()
    for _, game in games_df.iterrows():
        if pd.isna(game.get("game_id")) or pd.isna(game.get("week")):
            continue
        week = int(game["week"])
        counts = _current_game_counts(current_df, week, game.get("start_date"))
        prior_source_year = 2019 if year == 2021 else year - 1
        for team_col, opponent_col, side in (
            ("home_team", "away_team", "home"),
            ("away_team", "home_team", "away"),
        ):
            team = game.get(team_col)
            opponent = game.get(opponent_col)
            if not isinstance(team, str) or not isinstance(opponent, str):
                continue
            current_games = int(counts.get(team, 0))
            if current_games >= min_current_games:
                continue
            row = base_row(team)
            row.update(
                {
                    "season": year,
                    "week": week,
                    "game_id": int(game["game_id"]),
                    "team": team,
                    "opponent": opponent,
                    "home_away": side,
                    "date": game.get("start_date"),
                    "current_season_games": current_games,
                    "seeded_from_prior_season": True,
                    "prior_source_season": prior_source_year,
                    "prior_season_gap": year - prior_source_year,
                }
            )
            rows.append(row)

    return pd.DataFrame(rows)


def _merge_seeded_prediction_rows(
    full_adj_df: pd.DataFrame,
    games_df: pd.DataFrame,
    team_game_df: pd.DataFrame,
    read_entity,
    year: int,
) -> pd.DataFrame:
    """Keep prior and current feature blocks separate for model-level routing.

    This function retains its historical name for compatibility.  It no longer
    applies fixed shrinkage weights: direct hybrid models consume both blocks,
    while prediction blends are selected later from temporal OOF predictions.
    """
    seed_df = _prior_seed_rows(
        games_df,
        read_entity,
        year,
        team_game_df=team_game_df,
    )
    if seed_df.empty:
        result = full_adj_df.copy()
        if not result.empty:
            counts = pd.to_numeric(
                result.get("current_season_games", 0), errors="coerce"
            ).fillna(0)
            result["prediction_regime"] = counts.map(completed_game_regime)
            result["prior_features_missing"] = True
        return result

    key_columns = ["game_id", "team"]
    seed_by_key = seed_df.set_index(key_columns, drop=False)
    current_by_key = (
        full_adj_df.set_index(key_columns, drop=False)
        if not full_adj_df.empty
        else pd.DataFrame(columns=key_columns).set_index(key_columns, drop=False)
    )
    all_columns = list(dict.fromkeys([*full_adj_df.columns, *seed_df.columns]))
    metadata_columns = {
        "season",
        "week",
        "game_id",
        "iteration",
        "current_season_games",
        "prior_source_season",
        "prior_season_gap",
        "team",
        "opponent",
        "home_away",
        "date",
        "seeded_from_prior_season",
        "prediction_regime",
    }
    rows: list[dict] = []

    for key in current_by_key.index.union(seed_by_key.index):
        has_current = key in current_by_key.index
        has_prior = key in seed_by_key.index
        current = current_by_key.loc[key].to_dict() if has_current else {}
        prior = seed_by_key.loc[key].to_dict() if has_prior else {}
        # Duplicate keys should not occur, but fail loudly instead of blending
        # an ambiguous Series/DataFrame shape.
        if has_current and isinstance(current_by_key.loc[key], pd.DataFrame):
            raise ValueError(f"Duplicate current feature key: {key}")
        if has_prior and isinstance(seed_by_key.loc[key], pd.DataFrame):
            raise ValueError(f"Duplicate prior feature key: {key}")

        raw_count = prior.get(
            "current_season_games", current.get("current_season_games", 0)
        )
        count = pd.to_numeric(raw_count, errors="coerce")
        count = 0 if pd.isna(count) else int(count)
        row = dict(current or prior)
        for column in ("prior_source_season", "prior_season_gap"):
            if column in prior:
                row[column] = prior[column]

        for column in all_columns:
            if column in metadata_columns or column.startswith("prior_"):
                continue
            prior_value = prior.get(column)
            if prior_value is not None:
                row[f"prior_{column}"] = prior_value
            if not current and column in row:
                # Week 0 has no current observation.  Keep the prior only in its
                # explicit block so downstream code cannot accidentally use it as
                # a current-season measurement.
                row[column] = pd.NA

        row["current_season_games"] = count
        row["seeded_from_prior_season"] = bool(prior)
        row["prior_features_missing"] = not bool(prior)
        row["current_features_missing"] = not bool(current)
        row["prediction_regime"] = completed_game_regime(count)
        rows.append(row)

    return pd.DataFrame(rows).reset_index(drop=True)


def load_v2_recency_data(
    year,
    alpha=0.5,
    iterations=4,
    for_prediction=False,
    dataset_reader=None,
):
    """
    Load raw team-game data, calculate EWMA stats, apply adjustment, and return training/test DF.
    """
    # Use cloud storage if configured, otherwise fall back to LocalStorage
    storage_backend = os.getenv("CFB_STORAGE_BACKEND", "local").lower()

    if dataset_reader is not None:
        read_entity = dataset_reader
    elif storage_backend in ("r2", "s3"):
        # Use cloud storage
        from cks_picks_cfb.data.storage import get_storage

        storage = get_storage()

        def read_entity(entity: str, year: int):
            if entity in ("games", "betting_lines"):
                full_entity = f"raw/{entity}"
            else:
                full_entity = f"processed/{entity}"
            return storage.read_index(full_entity, {"year": year})

    else:
        # Use legacy LocalStorage for local files
        from cks_picks_cfb.utils.local_storage import LocalStorage

        data_root = get_data_root()
        raw_storage = LocalStorage(
            data_root=data_root, file_format="csv", data_type="raw"
        )
        processed_storage = LocalStorage(
            data_root=data_root, file_format="csv", data_type="processed"
        )

        def read_entity(entity: str, year: int):
            if entity in ("games", "betting_lines"):
                return raw_storage.read_index(entity, {"year": year})
            else:
                return processed_storage.read_index(entity, {"year": year})

    games = read_entity("games", year)
    games_df = _normalize_games_df(games)

    records = read_entity("team_game", year)
    if not records:
        print(f"No team_game data for {year}")
        if for_prediction:
            seeded_df = _prior_seed_rows(games_df, read_entity, year)
            if not seeded_df.empty:
                print(
                    f"Using prior-season cold-start features for {len(seeded_df)} team-game rows."
                )
                from cks_picks_cfb.features.internal_ratings import (
                    add_internal_power_ratings,
                )

                seeded_df = add_internal_power_ratings(seeded_df)
                return _merge_for_training(
                    seeded_df,
                    year,
                    for_prediction=for_prediction,
                    dataset_reader=read_entity,
                )
        return None

    team_game_df = pd.DataFrame.from_records(records)

    # Create mapping: game_id -> season_type
    if "season_type" in games_df.columns:
        # Map back to team_game_df
        # We can merge on game_id
        week_map = games_df[["game_id", "week"]].set_index("game_id")["week"]

        # Update team_game_df week
        # Only update if game_id exists in map (it should)
        team_game_df["week"] = (
            team_game_df["game_id"].map(week_map).fillna(team_game_df["week"])
        )

    # Attach opponent from games_df (home/away mapping)
    if {"home_team", "away_team", "game_id"}.issubset(games_df.columns):
        opp_map = pd.concat(
            [
                games_df[["game_id", "home_team", "away_team"]].rename(
                    columns={"home_team": "team", "away_team": "opponent"}
                ),
                games_df[["game_id", "home_team", "away_team"]].rename(
                    columns={"away_team": "team", "home_team": "opponent"}
                ),
            ],
            ignore_index=True,
        )
        team_game_df = team_game_df.merge(opp_map, on=["game_id", "team"], how="left")

    if for_prediction:
        # Reuse games_df loaded earlier to avoid redundant S3 call
        # games_df already loaded at line 122 and renamed id->game_id at line 125
        if "games_df" not in locals():
            # Fallback: load games if not already loaded (shouldn't happen)
            games = read_entity("games", year)
            games_df = pd.DataFrame(games)
            if "id" in games_df.columns:
                games_df = games_df.rename(columns={"id": "game_id"})

        # Identify missing games in team_game_df
        existing_ids = set(team_game_df["game_id"].unique())
        future_games = games_df[~games_df["game_id"].isin(existing_ids)]

        if not future_games.empty:
            print(f"Injecting {len(future_games)} future games for prediction...")
            rows = []
            for _, g in future_games.iterrows():
                rows.append(
                    {
                        "season": g["season"],
                        "week": g["week"],  # Already adjusted above
                        "game_id": g["game_id"],
                        "team": g["home_team"],
                        "opponent": g["away_team"],
                        "home_away": "home",
                        "date": g.get("start_date"),
                    }
                )
                rows.append(
                    {
                        "season": g["season"],
                        "week": g["week"],  # Already adjusted above
                        "game_id": g["game_id"],
                        "team": g["away_team"],
                        "opponent": g["home_team"],
                        "home_away": "away",
                        "date": g.get("start_date"),
                    }
                )
            future_df = pd.DataFrame(rows)
            team_game_df = pd.concat([team_game_df, future_df], ignore_index=True)

    # Calculate EWMA Unadjusted
    print(f"Calculating EWMA (alpha={alpha}) for {year}...")
    team_season = aggregate_team_season_ewma(team_game_df, alpha=alpha)

    # Clip extreme pass YPP matchup metrics to reduce numerical blow-ups downstream
    pass_cols = [
        "home_adj_off_pass_ypp",
        "home_adj_def_pass_ypp",
        "away_adj_off_pass_ypp",
        "away_adj_def_pass_ypp",
    ]
    for col in pass_cols:
        if col in team_season.columns:
            lower = team_season[col].quantile(0.005)
            upper = team_season[col].quantile(0.995)
            team_season[col] = team_season[col].clip(lower=lower, upper=upper)

    # Opponent Adjustment
    # We need an iterator because `apply_iterative_opponent_adjustment`
    # expects a full season DF and prior_games_df.
    # But wait, `apply_iterative_opponent_adjustment` adjusts a SINGLE week based on PRIOR games.
    # We can batch this.

    print("Applying Opponent Adjustments (Iterative)...")
    weeks = sorted(team_season["week"].unique())
    adj_dfs = []

    for week in tqdm(weeks):
        # Stats entering this week
        current_week_stats = team_season[team_season["week"] == week]
        # Games played prior to this week (for opponent strength lookup)
        prior_games = team_game_df[team_game_df["week"] < week]

        if current_week_stats.empty:
            continue

        # Opponent strength features: average opponent defensive form entering this week
        opp_strength = None
        if not prior_games.empty:
            opp_strength = (
                prior_games.groupby("team")[
                    [
                        "def_epa_pp",
                        "def_sr",
                        "def_pass_ypp",
                        "def_rush_ypp",
                    ]
                ]
                .mean()
                .rename(
                    columns={
                        "def_epa_pp": "opp_avg_def_epa_pp",
                        "def_sr": "opp_avg_def_sr",
                        "def_pass_ypp": "opp_avg_def_pass_ypp",
                        "def_rush_ypp": "opp_avg_def_rush_ypp",
                    }
                )
            )

        adj_input = current_week_stats.copy()
        # Re-attach opponent for mapping (team_season lost opponent during aggregation)
        opp_map = (
            team_game_df[team_game_df["week"] == week][["team", "opponent"]]
            .drop_duplicates()
            .set_index("team")
        )
        adj_input = adj_input.merge(
            opp_map,
            left_on="team",
            right_index=True,
            how="left",
        )
        if opp_strength is not None:
            # Map opponent strength onto each row via the opponent column
            adj_input = adj_input.merge(
                opp_strength,
                left_on="opponent",
                right_index=True,
                how="left",
            )
            # Fill early-season missing values with league means to avoid NaNs
            for col in [
                "opp_avg_def_epa_pp",
                "opp_avg_def_sr",
                "opp_avg_def_pass_ypp",
                "opp_avg_def_rush_ypp",
            ]:
                if col in adj_input.columns:
                    adj_input[col] = adj_input[col].fillna(adj_input[col].mean())

        # Run adjustment
        adj_df = apply_iterative_opponent_adjustment(
            adj_input.drop(columns=["opponent"], errors="ignore"),
            prior_games,
            iterations=iterations,
        )
        # Only keep the final iteration for training
        adj_df = adj_df[adj_df["iteration"] == iterations]
        current_counts = prior_games.groupby("team")["game_id"].nunique()
        adj_df["current_season_games"] = (
            adj_df["team"].map(current_counts).fillna(0).astype(int)
        )
        adj_df["seeded_from_prior_season"] = False
        adj_dfs.append(adj_df)

    if not adj_dfs:
        # If no adjusted stats, we can't do much.
        # But for prediction, we might be predicting Week 1. (which has no prior stats)
        # In that case, we return what we can?
        # But team_season depends on PRIOR games.
        pass

    if adj_dfs:
        full_adj_df = pd.concat(adj_dfs, ignore_index=True)
    else:
        full_adj_df = pd.DataFrame()  # Should fallback or handle empty

    if for_prediction:
        full_adj_df = _merge_seeded_prediction_rows(
            full_adj_df,
            games_df,
            team_game_df,
            read_entity,
            year,
        )

    # Inject Option 2: Internal SP+ Metrics
    from cks_picks_cfb.features.internal_ratings import add_internal_power_ratings

    full_adj_df = add_internal_power_ratings(full_adj_df)

    # Merge with Targets (Merge Home/Away for training)
    # Re-use v1_pipeline merge logic or implement simpler one here
    return _merge_for_training(
        full_adj_df,
        year,
        for_prediction=for_prediction,
        dataset_reader=read_entity,
    )


def _merge_for_training(team_stats, year, for_prediction=False, dataset_reader=None):
    # Load Games (Targets)
    # Use cloud storage if configured, otherwise fall back to LocalStorage
    storage_backend = os.getenv("CFB_STORAGE_BACKEND", "local").lower()

    if dataset_reader is not None:
        read_entity = dataset_reader
    elif storage_backend in ("r2", "s3"):
        from cks_picks_cfb.data.storage import get_storage

        storage = get_storage()

        def read_entity(entity: str, year: int):
            full_entity = f"raw/{entity}"
            return storage.read_index(full_entity, {"year": year})
    else:
        from cks_picks_cfb.utils.local_storage import LocalStorage

        data_root = get_data_root()
        raw_storage = LocalStorage(
            data_root=data_root, file_format="csv", data_type="raw"
        )

        def read_entity(entity: str, year: int):
            return raw_storage.read_index(entity, {"year": year})

    games = read_entity("games", year)
    games_df = pd.DataFrame(games)

    if "id" in games_df.columns:
        games_df = games_df.rename(columns={"id": "game_id"})

    # Normalize Weeks for Postseason in Games DF (for accurate filtering/merging)
    if "season_type" in games_df.columns:
        games_df["season_type"] = games_df["season_type"].fillna("regular")
        # Assuming regular season max week is 15. Postseason week 1 becomes 16.
        games_df["week"] = np.where(
            games_df["season_type"] == "postseason",
            games_df["week"] + 15,
            games_df["week"],
        )

    # Betting Lines
    betting = read_entity("betting_lines", year)
    if betting:
        betting_df = pd.DataFrame(betting)
        if "id" in betting_df.columns:
            betting_df = betting_df.rename(columns={"id": "game_id"})
        from cks_picks_cfb.data.lake import canonicalize_market_quotes_frame

        betting_df = canonicalize_market_quotes_frame(betting_df)
        games_df = games_df.merge(betting_df, on="game_id", how="left")

    # Merge Home/Away Stats
    # team_stats has 'team' column.

    # Filter valid games
    if not for_prediction:
        games_df = games_df[games_df["completed"]]

    # Prepare stats
    # team_stats has 'team'.

    merged = games_df.merge(
        team_stats.rename(columns={"team": "home_team"}),
        on=["game_id", "home_team"],
        how="inner",
        suffixes=("", "_home_stats"),
    )

    merged = merged.merge(
        team_stats.rename(columns={"team": "away_team"}),
        on=["game_id", "away_team"],
        how="inner",
        suffixes=("", "_away"),
    )

    # Rename collisions
    # The suffixes above handle it mostly.
    # features will be columns in team_stats.

    # Elo differential (pregame elo columns come from games_df)
    if "home_pregame_elo" in merged.columns and "away_pregame_elo" in merged.columns:
        merged["elo_diff"] = merged["home_pregame_elo"] - merged["away_pregame_elo"]

    # External features: ratings, recruiting, rankings
    from cks_picks_cfb.features.external import (
        merge_external_ratings,
        merge_rankings,
        merge_recruiting_composite,
    )

    _storage = storage if storage_backend in ("r2", "s3") else None

    # Merge external ratings week by week since they are now weekly snapshots
    if "week" in merged.columns:
        weeks = merged["week"].unique()
        merged_chunks = []
        for w in weeks:
            chunk = merged[merged["week"] == w].copy()
            chunk = merge_external_ratings(chunk, year, int(w), storage=_storage)
            merged_chunks.append(chunk)
        if merged_chunks:
            # Reconstruct the merged dataframe with ratings joined
            merged = pd.concat(merged_chunks, ignore_index=True)
    else:
        # Fallback if week is somehow missing (shouldn't happen for training data)
        merged = merge_external_ratings(merged, year, 1, storage=_storage)

    merged = merge_recruiting_composite(merged, year, storage=_storage)
    merged = merge_rankings(merged, year, storage=_storage)

    # Calculate Target
    merged["spread_target"] = merged["home_points"] - merged["away_points"]
    merged["total_target"] = merged["home_points"] + merged["away_points"]

    # Prefix features
    feature_cols = [
        c for c in team_stats.columns if c not in ["game_id", "season", "week", "team"]
    ]

    # Rename correctly
    # Above merge creates: {col} (for home) and {col}_away (for away).
    # We want home_{col} and away_{col}.

    rename_map = {}
    for c in feature_cols:
        rename_map[c] = f"home_{c}"
        rename_map[f"{c}_away"] = f"away_{c}"

    merged = merged.rename(columns=rename_map)

    if for_prediction:
        home_games = merged.get("home_current_season_games")
        away_games = merged.get("away_current_season_games")
        if home_games is not None and away_games is not None:
            merged["high_confidence_eligible"] = (
                pd.to_numeric(home_games, errors="coerce").fillna(0)
                >= MIN_CURRENT_SEASON_GAMES
            ) & (
                pd.to_numeric(away_games, errors="coerce").fillna(0)
                >= MIN_CURRENT_SEASON_GAMES
            )
            min_games = pd.concat(
                [
                    pd.to_numeric(home_games, errors="coerce").fillna(0),
                    pd.to_numeric(away_games, errors="coerce").fillna(0),
                ],
                axis=1,
            ).min(axis=1)
            merged["prediction_regime"] = min_games.map(completed_game_regime)
        else:
            merged["high_confidence_eligible"] = True
            merged["prediction_regime"] = "established"

    return merged
