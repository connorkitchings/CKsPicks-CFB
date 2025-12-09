import numpy as np
import pandas as pd
from tqdm import tqdm

from src.config import get_data_root
from src.features.core import apply_iterative_opponent_adjustment
from src.utils.local_storage import LocalStorage


def _calculate_ewma(series, alpha):
    """
    Calculate Exponentially Weighted Moving Average.
    pandas ewm uses alpha=alpha, adjust=True/False.
    If adjust=True, uses weights (1-alpha)**i.
    """
    return series.ewm(alpha=alpha, min_periods=1).mean()


def _augment_with_style_metrics(df):
    # Simplified style metrics for on-the-fly generation
    # We can skip complex rolling windows for now or implement if critical
    # Just returning raw for speed, style metrics are usually secondary
    return df


def aggregate_team_season_ewma(team_game_df, alpha):
    """
    Aggregate team-game metrics using EWMA (Exponential Decay).
    """
    # Sort by date/week
    team_game_df = team_game_df.sort_values(["season", "week"])

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

    # helper for groupby apply
    def _apply_ewma(g):
        # We want the EWMA of *past* games at the start of the current week.
        # shift(1) means row[i] gets stats from 0..i-1
        # ewm().mean() calculates usage including current row.
        # So we ewm() then shift(1).

        # Note: We need to handle weeks. If a team plays multiple times (rare) or gaps.
        # Assuming one row per game per team.
        ewma = g[metric_cols].ewm(alpha=alpha, min_periods=1).mean().shift(1)
        ewma["season"] = g["season"]
        ewma["week"] = g["week"]
        ewma["team"] = g["team"]
        ewma["game_id"] = g["game_id"]  # Join key
        return ewma

    # Apply per team
    team_season = team_game_df.groupby(["season", "team"], group_keys=False).apply(
        _apply_ewma
    )

    # Drop first game (NaNs)
    team_season = team_season.dropna(subset=metric_cols, how="all")

    return team_season


def load_v2_recency_data(year, alpha=0.5, iterations=4, for_prediction=False):
    """
    Load raw team-game data, calculate EWMA stats, apply adjustment, and return training/test DF.
    """
    data_root = get_data_root()
    storage = LocalStorage(
        data_root=data_root, file_format="csv", data_type="processed"
    )

    # Load Team Game Data (Raw stats)
    # We need prior year data for early season continuity?
    # For now, let's just load the specific year. Cold start is a known issue.
    # To mitigate, maybe load year-1 and filter?
    # Let's simple start: load `year` data.
    records = storage.read_index("team_game", {"year": year})
    if not records:
        print(f"No team_game data for {year}")
        return None

    team_game_df = pd.DataFrame.from_records(records)

    # Normalize Weeks for Postseason (Week 1 -> Week 16+)
    # We need to map game_id to season_type to identify postseason games
    raw_storage = LocalStorage(data_root=data_root, file_format="csv", data_type="raw")
    games = raw_storage.read_index("games", {"year": year})
    games_df = pd.DataFrame(games)
    if "id" in games_df.columns:
        games_df = games_df.rename(columns={"id": "game_id"})

    # Create mapping: game_id -> season_type
    if "season_type" in games_df.columns:
        # Fill missing season_type with regular
        games_df["season_type"] = games_df["season_type"].fillna("regular")

        # Adjust week in games_df first
        # Assuming regular season max week is 15. Postseason week 1 becomes 16.
        # Check specific values
        games_df["week"] = np.where(
            games_df["season_type"] == "postseason",
            games_df["week"] + 15,
            games_df["week"],
        )

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
                games_df[["game_id", "home_team", "away_team"]]
                .rename(columns={"home_team": "team", "away_team": "opponent"}),
                games_df[["game_id", "home_team", "away_team"]]
                .rename(columns={"away_team": "team", "home_team": "opponent"}),
            ],
            ignore_index=True,
        )
        team_game_df = team_game_df.merge(
            opp_map, on=["game_id", "team"], how="left"
        )

    if for_prediction:
        # Load raw schedule to ensure future games are present
        # We need LocalStorage initialized with raw
        raw_storage = LocalStorage(
            data_root=data_root, file_format="csv", data_type="raw"
        )
        games = raw_storage.read_index("games", {"year": year})
        games_df = pd.DataFrame(games)

        # Rename id to game_id if needed
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

    # Ideally we'd augment style metrics here
    # team_season = _augment_with_style_metrics(team_season)

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
                    adj_input[col] = adj_input[col].fillna(
                        adj_input[col].mean()
                    )

        # Run adjustment
        adj_df = apply_iterative_opponent_adjustment(
            adj_input.drop(columns=["opponent"], errors="ignore"),
            prior_games,
            iterations=iterations,
        )
        # Only keep the final iteration for training
        adj_df = adj_df[adj_df["iteration"] == iterations]
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

    # Merge with Targets (Merge Home/Away for training)
    # Re-use v1_pipeline merge logic or implement simpler one here
    return _merge_for_training(full_adj_df, year, for_prediction=for_prediction)


def _merge_for_training(team_stats, year, for_prediction=False):
    # Load Games (Targets)
    data_root = get_data_root()
    raw_storage = LocalStorage(data_root=data_root, file_format="csv", data_type="raw")
    games = raw_storage.read_index("games", {"year": year})
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
    betting = raw_storage.read_index("betting_lines", {"year": year})
    if betting:
        betting_df = pd.DataFrame(betting)
        if "id" in betting_df.columns:
            betting_df = betting_df.rename(columns={"id": "game_id"})
        # Take mean line
        betting_df = (
            betting_df.groupby("game_id")
            .agg({"spread": "mean", "over_under": "mean"})
            .reset_index()
            .rename(columns={"spread": "spread_line", "over_under": "total_line"})
        )
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

    return merged
