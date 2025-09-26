"""Generate weekly ATS recommendations using trained models and betting policy."""

import argparse
import os
import sys

import joblib
import numpy as np
import pandas as pd

from cfb_model.config import get_data_root
from cfb_model.data.storage.local_storage import LocalStorage
from cfb_model.models.features import prepare_team_features


def load_models(year: int, model_dir: str):
    """Load trained spread/total Ridge models for a given season.

    Args:
        year: Season year whose models to load.
        model_dir: Base directory where models/<year>/ridge_*.joblib are stored.

    Returns:
        Tuple of (spread_model, total_model).

    Raises:
        FileNotFoundError: If expected model artifacts are not found.
    """
    spread_model_path = os.path.join(model_dir, str(year), "ridge_spread.joblib")
    total_model_path = os.path.join(model_dir, str(year), "ridge_total.joblib")

    if not os.path.exists(spread_model_path):
        raise FileNotFoundError(f"Spread model not found at {spread_model_path}")
    if not os.path.exists(total_model_path):
        raise FileNotFoundError(f"Total model not found at {total_model_path}")

    spread_model = joblib.load(spread_model_path)
    total_model = joblib.load(total_model_path)
    return spread_model, total_model

def load_current_week_data(year: int, week: int, data_root: str | None = None) -> pd.DataFrame:
    """Load features and games for a specific week, optionally merging betting lines.

    Args:
        year: Season year.
        week: Target week.
        data_root: Optional data root override; defaults to environment/config.

    Returns:
        Per-game DataFrame with home/away features; includes spread_line/total_line
        and provider if betting lines are present.

    Raises:
        ValueError: If required processed/raw inputs are missing or if no games for the week.
    """
    resolved_root = data_root or get_data_root()
    processed_storage = LocalStorage(
        data_root=resolved_root, file_format="csv", data_type="processed"
    )
    raw_storage = LocalStorage(data_root=resolved_root, file_format="csv", data_type="raw")

    # Load adjusted team-season features for the season and prepare one-row-per-team features
    team_season_adj_records = processed_storage.read_index("team_season_adj", {"year": year})
    if not team_season_adj_records:
        raise ValueError(f"No adjusted team season data found for year {year}")
    team_season_adj_df = pd.DataFrame.from_records(team_season_adj_records)
    team_features = prepare_team_features(team_season_adj_df)

    # Load raw games for the season, then filter to the target week
    game_records = raw_storage.read_index("games", {"year": year})
    if not game_records:
        raise ValueError(f"No raw game data found for year {year}")
    games_season_df = pd.DataFrame.from_records(game_records)
    games_df = games_season_df[games_season_df["week"] == int(week)].copy()
    if games_df.empty:
        raise ValueError(f"No raw game data found for year {year}, week {week}")

    # Load betting lines and reduce to one line per game (prefer 'consensus')
    lines_records = raw_storage.read_index("betting_lines", {"year": year})
    lines_df = pd.DataFrame.from_records(lines_records) if lines_records else pd.DataFrame()
    if not lines_df.empty:
        lines_df["provider_rank"] = np.where(lines_df["provider"].str.lower() == "consensus", 0, 1)
        lines_df = (
            lines_df.sort_values(["game_id", "provider_rank"]).groupby("game_id", as_index=False).first()
        )
        lines_df = lines_df.rename(columns={"over_under": "total_line", "spread": "spread_line"})[
            ["game_id", "spread_line", "total_line", "provider"]
        ]

    # Merge features into games
    home_features = team_features.add_prefix("home_")
    away_features = team_features.add_prefix("away_")

    merged_df = games_df.merge(
        home_features,
        left_on=["season", "home_team"],
        right_on=["home_season", "home_team"],
        how="left",
    )
    merged_df = merged_df.merge(
        away_features,
        left_on=["season", "away_team"],
        right_on=["away_season", "away_team"],
        how="left",
    )

    if not lines_df.empty:
        merged_df = merged_df.merge(lines_df, left_on=["id"], right_on=["game_id"], how="left")

    merged_df = merged_df.drop(columns=["home_season", "away_season"], errors="ignore")
    return merged_df


def generate_predictions(model, X: pd.DataFrame) -> pd.Series:  # noqa: N803
    """Generate predictions for X using a trained model.

    Args:
        model: Fitted estimator with a predict method.
        X: Feature matrix aligned to expected model schema.

    Returns:
        Series of predictions indexed to X.index.
    """
    return pd.Series(model.predict(X), index=X.index)


def apply_betting_policy(predictions_df: pd.DataFrame) -> pd.DataFrame:
    """Apply MVP betting policy thresholds to model outputs.

    Requires columns predicted_spread, predicted_total, spread_line, total_line,
    home_games_played, away_games_played. Produces bet_spread/bet_total and edges.

    Args:
        predictions_df: DataFrame containing model predictions and sportsbook lines.

    Returns:
        DataFrame with added edge_spread/edge_total and bet_spread/bet_total columns.
    """
    # Betting policy thresholds
    spread_edge_threshold = 3.5
    total_edge_threshold = 7.5
    min_games_played = 4

    # Calculate edges
    predictions_df["edge_spread"] = abs(
        predictions_df["predicted_spread"] - predictions_df["spread_line"]
    )
    predictions_df["edge_total"] = abs(
        predictions_df["predicted_total"] - predictions_df["total_line"]
    )

    # Apply betting policy
    predictions_df["bet_spread"] = "none"
    predictions_df.loc[
        (predictions_df["edge_spread"] >= spread_edge_threshold)
        & (predictions_df["home_games_played"] >= min_games_played)
        & (predictions_df["away_games_played"] >= min_games_played),
        "bet_spread",
    ] = np.where(
        predictions_df["predicted_spread"] > predictions_df["spread_line"],
        "home",
        "away",
    )

    predictions_df["bet_total"] = "none"
    predictions_df.loc[
        (predictions_df["edge_total"] >= total_edge_threshold)
        & (predictions_df["home_games_played"] >= min_games_played)
        & (predictions_df["away_games_played"] >= min_games_played),
        "bet_total",
    ] = np.where(
        predictions_df["predicted_total"] > predictions_df["total_line"],
        "over",
        "under",
    )

    return predictions_df


def generate_csv_report(predictions_df: pd.DataFrame, output_path: str) -> None:
    """Write the weekly CSV report with standardized columns.

    Args:
        predictions_df: DataFrame after policy application with required columns.
        output_path: Destination CSV path.
    """
    # Suggested columns:
    # season, week, game_id, game_date, home_team, away_team, neutral_site,
    # sportsbook, spread_line, total_line, model_spread, model_total,
    # edge_spread, edge_total, bet_spread (home/away/none), bet_total (over/under/none), bet_units

    report_df = predictions_df[
        [
            "season",
            "week",
            "id",
            "start_date",
            "home_team",
            "away_team",
            "neutral_site",
            "provider",
            "spread_line",
            "total_line",
            "predicted_spread",
            "predicted_total",
            "edge_spread",
            "edge_total",
            "bet_spread",
            "bet_total",
        ]
    ].copy()

    report_df = report_df.rename(
        columns={
            "id": "game_id",
            "start_date": "game_date",
            "predicted_spread": "model_spread",
            "predicted_total": "model_total",
            "provider": "sportsbook",
        }
    )

    # Fill sportsbook placeholder when missing and add flat staking units
    if "sportsbook" not in report_df.columns:
        report_df["sportsbook"] = "consensus"
    report_df["bet_units"] = 1

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    report_df.to_csv(output_path, index=False)
    print(f"Weekly betting report saved to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate weekly CFB betting recommendations."
    )
    parser.add_argument(
        "--year", type=int, required=True, help="Season year for predictions."
    )
    parser.add_argument(
        "--week", type=int, required=True, help="Week number for predictions."
    )
    parser.add_argument(
        "--data-root",
        type=str,
        default=None,
        help="Absolute path to the data root directory.",
    )
    parser.add_argument(
        "--model-dir",
        type=str,
        default="./models/ridge_baseline",
        help="Directory where trained models are saved.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./reports",
        help="Directory to save the weekly report.",
    )

    args = parser.parse_args()

    try:
        print(f"Loading models for year {args.year}...")
        spread_model, total_model = load_models(args.year, args.model_dir)

        print(f"Loading data for year {args.year}, week {args.week}...")
        df = load_current_week_data(args.year, args.week, args.data_root)
        print(f"Columns of df: {df.columns}")
        print(f"Shape of df after loading: {df.shape}")

        # Build feature list to match training dynamically from available columns
        adjusted_metrics = [
            "epa_pp",
            "sr",
            "ypp",
            "expl_rate_overall_10",
            "expl_rate_overall_20",
            "expl_rate_overall_30",
            "expl_rate_rush",
            "expl_rate_pass",
        ]
        features = []
        for side in ["home", "away"]:
            for prefix in ["adj_off_", "adj_def_"]:
                for metric in adjusted_metrics:
                    col = f"{side}_{prefix}{metric}"
                    if col in df.columns:
                        features.append(col)
            for extra in [
                "off_eckel_rate",
                "off_finish_pts_per_opp",
                "stuff_rate",
                "havoc_rate",
            ]:
                col = f"{side}_{extra}"
                if col in df.columns:
                    features.append(col)

        print(f"Features being used: {features}")

        # Filter out rows with NaN in features
        df_cleaned = df.dropna(subset=features)
        print(f"Shape of df_cleaned after dropping NaNs: {df_cleaned.shape}")

        if df_cleaned.empty:
            print("No games with complete data for prediction this week.")
            sys.exit(0)

        X = df_cleaned[features]

        print("Generating spread predictions...")
        df_cleaned["predicted_spread"] = generate_predictions(spread_model, X)

        print("Generating total predictions...")
        df_cleaned["predicted_total"] = generate_predictions(total_model, X)

        print("Applying betting policy...")
        final_predictions_df = apply_betting_policy(df_cleaned)

        output_filename = f"CFB_week{args.week}_bets.csv"
        output_path = os.path.join(args.output_dir, str(args.year), output_filename)

        print("Generating CSV report...")
        generate_csv_report(final_predictions_df, output_path)

        print(
            f"Weekly betting recommendations for year {args.year}, week {args.week} generated successfully."
        )

    except Exception as e:
        print(
            f"Error during weekly bet generation for year {args.year}, week {args.week}: {e}"
        )
        import traceback
        traceback.print_exc()
        & (predictions_df["home_games_played"] >= min_games_played)
        & (predictions_df["away_games_played"] >= min_games_played),
        "bet_total",
    ] = np.where(
        predictions_df["predicted_total"] > predictions_df["total_line"],
        "over",
        "under",
    )

    return predictions_df


def generate_csv_report(predictions_df: pd.DataFrame, output_path: str) -> None:
    """Write the weekly CSV report with standardized columns.

    Args:
        predictions_df: DataFrame after policy application with required columns.
        output_path: Destination CSV path.
    """
    # Suggested columns:
    # season, week, game_id, game_date, home_team, away_team, neutral_site,
    # sportsbook, spread_line, total_line, model_spread, model_total,
    # edge_spread, edge_total, bet_spread (home/away/none), bet_total (over/under/none), bet_units

    report_df = predictions_df[
        [
            "season",
            "week",
            "id",
            "start_date",
            "home_team",
            "away_team",
            "neutral_site",
            "provider",
            "spread_line",
            "total_line",
            "predicted_spread",
            "predicted_total",
            "edge_spread",
            "edge_total",
            "bet_spread",
            "bet_total",
        ]
    ].copy()

    report_df = report_df.rename(
        columns={
            "id": "game_id",
            "start_date": "game_date",
            "predicted_spread": "model_spread",
            "predicted_total": "model_total",
            "provider": "sportsbook",
        }
    )

    # Fill sportsbook placeholder when missing and add flat staking units
    if "sportsbook" not in report_df.columns:
        report_df["sportsbook"] = "consensus"
    report_df["bet_units"] = 1

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    report_df.to_csv(output_path, index=False)
    print(f"Weekly betting report saved to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate weekly CFB betting recommendations."
    )
    parser.add_argument(
        "--year", type=int, required=True, help="Season year for predictions."
    )
    parser.add_argument(
        "--week", type=int, required=True, help="Week number for predictions."
    )
    parser.add_argument(
        "--data-root",
        type=str,
        default=None,
        help="Absolute path to the data root directory.",
    )
    parser.add_argument(
        "--model-dir",
        type=str,
        default="./models/ridge_baseline",
        help="Directory where trained models are saved.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./reports",
        help="Directory to save the weekly report.",
    )

    args = parser.parse_args()

    try:
        print(f"Loading models for year {args.year}...")
        spread_model, total_model = load_models(args.year, args.model_dir)

        print(f"Loading data for year {args.year}, week {args.week}...")
        df = load_current_week_data(args.year, args.week, args.data_root)
        print(f"Columns of df: {df.columns}")
        print(f"Shape of df after loading: {df.shape}")

        # Build feature list to match training dynamically from available columns
        adjusted_metrics = [
            "epa_pp",
            "sr",
            "ypp",
            "expl_rate_overall_10",
            "expl_rate_overall_20",
            "expl_rate_overall_30",
            "expl_rate_rush",
            "expl_rate_pass",
        ]
        features = []
        for side in ["home", "away"]:
            for prefix in ["adj_off_", "adj_def_"]:
                for metric in adjusted_metrics:
                    col = f"{side}_{prefix}{metric}"
                    if col in df.columns:
                        features.append(col)
            for extra in [
                "off_eckel_rate",
                "off_finish_pts_per_opp",
                "stuff_rate",
                "havoc_rate",
            ]:
                col = f"{side}_{extra}"
                if col in df.columns:
                    features.append(col)

        print(f"Features being used: {features}")

        # Filter out rows with NaN in features
        df_cleaned = df.dropna(subset=features)
        print(f"Shape of df_cleaned after dropping NaNs: {df_cleaned.shape}")

        if df_cleaned.empty:
            print("No games with complete data for prediction this week.")
            sys.exit()

        X = df_cleaned[features]

        print("Generating spread predictions...")
        df_cleaned["predicted_spread"] = generate_predictions(spread_model, X)

        print("Generating total predictions...")
        df_cleaned["predicted_total"] = generate_predictions(total_model, X)

        # Lines were merged from betting_lines; they may be NaN if missing

        print("Applying betting policy...")
        final_predictions_df = apply_betting_policy(df_cleaned)

        output_filename = f"CFB_week{args.week}_bets.csv"
        output_path = os.path.join(args.output_dir, str(args.year), output_filename)

        print("Generating CSV report...")
        generate_csv_report(final_predictions_df, output_path)

        print(
            f"Weekly betting recommendations for year {args.year}, week {args.week} generated successfully."
        )

    except Exception as e:
        print(
            f"Error during weekly bet generation for year {args.year}, week {args.week}: {e}"
        )
        import traceback

        traceback.print_exc()
, '', regex=True)

    # Load raw games for the season, then filter to the target week
    game_records = raw_storage.read_index("games", {"year": year})
    if not game_records:
        raise ValueError(f"No raw game data found for year {year}")
    games_season_df = pd.DataFrame.from_records(game_records)
    games_df = games_season_df[games_season_df["week"] == int(week)].copy()
    if games_df.empty:
        raise ValueError(f"No raw game data found for year {year}, week {week}")

    # Load betting lines and reduce to one line per game
    lines_records = raw_storage.read_index("betting_lines", {"year": year})
    lines_df = (
        pd.DataFrame.from_records(lines_records) if lines_records else pd.DataFrame()
    )
    if not lines_df.empty:
        # Prefer 'consensus' provider if available; otherwise first per game
        lines_df["provider_rank"] = np.where(
            lines_df["provider"].str.lower() == "consensus", 0, 1
        )
        lines_df = (
            lines_df.sort_values(["game_id", "provider_rank"])
            .groupby("game_id", as_index=False)
            .first()
        )
        lines_df = lines_df.rename(
            columns={"over_under": "total_line", "spread": "spread_line"}
        )
        lines_df = lines_df[["game_id", "spread_line", "total_line", "provider"]]

    # Merge features and game data (similar to train_model.py)
    home_features = team_season_adj_df.add_prefix("home_")
    away_features = team_season_adj_df.add_prefix("away_")

    merged_df = games_df.merge(
        home_features,
        left_on=["season", "home_team"],
        right_on=["home_season", "home_team"],
        how="left",
    )

    merged_df = merged_df.merge(
        away_features,
        left_on=["season", "away_team"],
        right_on=["away_season", "away_team"],
        how="left",
        suffixes=("", "_away"),
    )

    if not lines_df.empty:
        merged_df = merged_df.merge(
            lines_df, left_on=["id"], right_on=["game_id"], how="left"
        )

    merged_df = merged_df.drop(
        columns=["home_season", "home_team", "away_season", "away_team"],
        errors="ignore",
    )

    return merged_df


def generate_predictions(model, X: pd.DataFrame) -> pd.Series:  # noqa: N803
    """Generate predictions for X using a trained model.

    Args:
        model: Fitted estimator with a predict method.
        X: Feature matrix aligned to expected model schema.

    Returns:
        Series of predictions indexed to X.index.
    """
    return pd.Series(model.predict(X), index=X.index)


def apply_betting_policy(predictions_df: pd.DataFrame) -> pd.DataFrame:
    """Apply MVP betting policy thresholds to model outputs.

    Requires columns predicted_spread, predicted_total, spread_line, total_line,
    home_games_played, away_games_played. Produces bet_spread/bet_total and edges.

    Args:
        predictions_df: DataFrame containing model predictions and sportsbook lines.

    Returns:
        DataFrame with added edge_spread/edge_total and bet_spread/bet_total columns.
    """
    # Betting policy thresholds
    spread_edge_threshold = 3.5
    total_edge_threshold = 7.5
    min_games_played = 4

    # Calculate edges
    predictions_df["edge_spread"] = abs(
        predictions_df["predicted_spread"] - predictions_df["spread_line"]
    )
    predictions_df["edge_total"] = abs(
        predictions_df["predicted_total"] - predictions_df["total_line"]
    )

    # Apply betting policy
    predictions_df["bet_spread"] = "none"
    predictions_df.loc[
        (predictions_df["edge_spread"] >= spread_edge_threshold)
        & (predictions_df["home_games_played"] >= min_games_played)
        & (predictions_df["away_games_played"] >= min_games_played),
        "bet_spread",
    ] = np.where(
        predictions_df["predicted_spread"] > predictions_df["spread_line"],
        "home",
        "away",
    )

    predictions_df["bet_total"] = "none"
    predictions_df.loc[
        (predictions_df["edge_total"] >= total_edge_threshold)
        & (predictions_df["home_games_played"] >= min_games_played)
        & (predictions_df["away_games_played"] >= min_games_played),
        "bet_total",
    ] = np.where(
        predictions_df["predicted_total"] > predictions_df["total_line"],
        "over",
        "under",
    )

    return predictions_df


def generate_csv_report(predictions_df: pd.DataFrame, output_path: str) -> None:
    """Write the weekly CSV report with standardized columns.

    Args:
        predictions_df: DataFrame after policy application with required columns.
        output_path: Destination CSV path.
    """
    # Suggested columns:
    # season, week, game_id, game_date, home_team, away_team, neutral_site,
    # sportsbook, spread_line, total_line, model_spread, model_total,
    # edge_spread, edge_total, bet_spread (home/away/none), bet_total (over/under/none), bet_units

    report_df = predictions_df[
        [
            "season",
            "week",
            "id",
            "start_date",
            "home_team",
            "away_team",
            "neutral_site",
            "provider",
            "spread_line",
            "total_line",
            "predicted_spread",
            "predicted_total",
            "edge_spread",
            "edge_total",
            "bet_spread",
            "bet_total",
        ]
    ].copy()

    report_df = report_df.rename(
        columns={
            "id": "game_id",
            "start_date": "game_date",
            "predicted_spread": "model_spread",
            "predicted_total": "model_total",
            "provider": "sportsbook",
        }
    )

    # Fill sportsbook placeholder when missing and add flat staking units
    if "sportsbook" not in report_df.columns:
        report_df["sportsbook"] = "consensus"
    report_df["bet_units"] = 1

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    report_df.to_csv(output_path, index=False)
    print(f"Weekly betting report saved to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate weekly CFB betting recommendations."
    )
    parser.add_argument(
        "--year", type=int, required=True, help="Season year for predictions."
    )
    parser.add_argument(
        "--week", type=int, required=True, help="Week number for predictions."
    )
    parser.add_argument(
        "--data-root",
        type=str,
        default=None,
        help="Absolute path to the data root directory.",
    )
    parser.add_argument(
        "--model-dir",
        type=str,
        default="./models/ridge_baseline",
        help="Directory where trained models are saved.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./reports",
        help="Directory to save the weekly report.",
    )

    args = parser.parse_args()

    try:
        print(f"Loading models for year {args.year}...")
        spread_model, total_model = load_models(args.year, args.model_dir)

        print(f"Loading data for year {args.year}, week {args.week}...")
        df = load_current_week_data(args.year, args.week, args.data_root)
        print(f"Columns of df: {df.columns}")
        print(f"Shape of df after loading: {df.shape}")

        # Build feature list to match training dynamically from available columns
        adjusted_metrics = [
            "epa_pp",
            "sr",
            "ypp",
            "expl_rate_overall_10",
            "expl_rate_overall_20",
            "expl_rate_overall_30",
            "expl_rate_rush",
            "expl_rate_pass",
        ]
        features = []
        for side in ["home", "away"]:
            for prefix in ["adj_off_", "adj_def_"]:
                for metric in adjusted_metrics:
                    col = f"{side}_{prefix}{metric}"
                    if col in df.columns:
                        features.append(col)
            for extra in [
                "off_eckel_rate",
                "off_finish_pts_per_opp",
                "stuff_rate",
                "havoc_rate",
            ]:
                col = f"{side}_{extra}"
                if col in df.columns:
                    features.append(col)

        print(f"Features being used: {features}")

        # Filter out rows with NaN in features
        df_cleaned = df.dropna(subset=features)
        print(f"Shape of df_cleaned after dropping NaNs: {df_cleaned.shape}")

        if df_cleaned.empty:
            print("No games with complete data for prediction this week.")
            sys.exit()

        X = df_cleaned[features]

        print("Generating spread predictions...")
        df_cleaned["predicted_spread"] = generate_predictions(spread_model, X)

        print("Generating total predictions...")
        df_cleaned["predicted_total"] = generate_predictions(total_model, X)

        # Lines were merged from betting_lines; they may be NaN if missing

        print("Applying betting policy...")
        final_predictions_df = apply_betting_policy(df_cleaned)

        output_filename = f"CFB_week{args.week}_bets.csv"
        output_path = os.path.join(args.output_dir, str(args.year), output_filename)

        print("Generating CSV report...")
        generate_csv_report(final_predictions_df, output_path)

        print(
            f"Weekly betting recommendations for year {args.year}, week {args.week} generated successfully."
        )

    except Exception as e:
        print(
            f"Error during weekly bet generation for year {args.year}, week {args.week}: {e}"
        )
        import traceback

        traceback.print_exc()
, '', regex=True)
    team_season_adj_df.columns = team_season_adj_df.columns.str.replace('_def
    game_records = raw_storage.read_index("games", {"year": year})
    if not game_records:
        raise ValueError(f"No raw game data found for year {year}")
    games_season_df = pd.DataFrame.from_records(game_records)
    games_df = games_season_df[games_season_df["week"] == int(week)].copy()
    if games_df.empty:
        raise ValueError(f"No raw game data found for year {year}, week {week}")

    # Load betting lines and reduce to one line per game
    lines_records = raw_storage.read_index("betting_lines", {"year": year})
    lines_df = (
        pd.DataFrame.from_records(lines_records) if lines_records else pd.DataFrame()
    )
    if not lines_df.empty:
        # Prefer 'consensus' provider if available; otherwise first per game
        lines_df["provider_rank"] = np.where(
            lines_df["provider"].str.lower() == "consensus", 0, 1
        )
        lines_df = (
            lines_df.sort_values(["game_id", "provider_rank"])
            .groupby("game_id", as_index=False)
            .first()
        )
        lines_df = lines_df.rename(
            columns={"over_under": "total_line", "spread": "spread_line"}
        )
        lines_df = lines_df[["game_id", "spread_line", "total_line", "provider"]]

    # Merge features and game data (similar to train_model.py)
    home_features = team_season_adj_df.add_prefix("home_")
    away_features = team_season_adj_df.add_prefix("away_")

    merged_df = games_df.merge(
        home_features,
        left_on=["season", "home_team"],
        right_on=["home_season", "home_team"],
        how="left",
    )

    merged_df = merged_df.merge(
        away_features,
        left_on=["season", "away_team"],
        right_on=["away_season", "away_team"],
        how="left",
        suffixes=("", "_away"),
    )

    if not lines_df.empty:
        merged_df = merged_df.merge(
            lines_df, left_on=["id"], right_on=["game_id"], how="left"
        )

    merged_df = merged_df.drop(
        columns=["home_season", "home_team", "away_season", "away_team"],
        errors="ignore",
    )

    return merged_df


def generate_predictions(model, X: pd.DataFrame) -> pd.Series:  # noqa: N803
    """Generate predictions for X using a trained model.

    Args:
        model: Fitted estimator with a predict method.
        X: Feature matrix aligned to expected model schema.

    Returns:
        Series of predictions indexed to X.index.
    """
    return pd.Series(model.predict(X), index=X.index)


def apply_betting_policy(predictions_df: pd.DataFrame) -> pd.DataFrame:
    """Apply MVP betting policy thresholds to model outputs.

    Requires columns predicted_spread, predicted_total, spread_line, total_line,
    home_games_played, away_games_played. Produces bet_spread/bet_total and edges.

    Args:
        predictions_df: DataFrame containing model predictions and sportsbook lines.

    Returns:
        DataFrame with added edge_spread/edge_total and bet_spread/bet_total columns.
    """
    # Betting policy thresholds
    spread_edge_threshold = 3.5
    total_edge_threshold = 7.5
    min_games_played = 4

    # Calculate edges
    predictions_df["edge_spread"] = abs(
        predictions_df["predicted_spread"] - predictions_df["spread_line"]
    )
    predictions_df["edge_total"] = abs(
        predictions_df["predicted_total"] - predictions_df["total_line"]
    )

    # Apply betting policy
    predictions_df["bet_spread"] = "none"
    predictions_df.loc[
        (predictions_df["edge_spread"] >= spread_edge_threshold)
        & (predictions_df["home_games_played"] >= min_games_played)
        & (predictions_df["away_games_played"] >= min_games_played),
        "bet_spread",
    ] = np.where(
        predictions_df["predicted_spread"] > predictions_df["spread_line"],
        "home",
        "away",
    )

    predictions_df["bet_total"] = "none"
    predictions_df.loc[
        (predictions_df["edge_total"] >= total_edge_threshold)
        & (predictions_df["home_games_played"] >= min_games_played)
        & (predictions_df["away_games_played"] >= min_games_played),
        "bet_total",
    ] = np.where(
        predictions_df["predicted_total"] > predictions_df["total_line"],
        "over",
        "under",
    )

    return predictions_df


def generate_csv_report(predictions_df: pd.DataFrame, output_path: str) -> None:
    """Write the weekly CSV report with standardized columns.

    Args:
        predictions_df: DataFrame after policy application with required columns.
        output_path: Destination CSV path.
    """
    # Suggested columns:
    # season, week, game_id, game_date, home_team, away_team, neutral_site,
    # sportsbook, spread_line, total_line, model_spread, model_total,
    # edge_spread, edge_total, bet_spread (home/away/none), bet_total (over/under/none), bet_units

    report_df = predictions_df[
        [
            "season",
            "week",
            "id",
            "start_date",
            "home_team",
            "away_team",
            "neutral_site",
            "provider",
            "spread_line",
            "total_line",
            "predicted_spread",
            "predicted_total",
            "edge_spread",
            "edge_total",
            "bet_spread",
            "bet_total",
        ]
    ].copy()

    report_df = report_df.rename(
        columns={
            "id": "game_id",
            "start_date": "game_date",
            "predicted_spread": "model_spread",
            "predicted_total": "model_total",
            "provider": "sportsbook",
        }
    )

    # Fill sportsbook placeholder when missing and add flat staking units
    if "sportsbook" not in report_df.columns:
        report_df["sportsbook"] = "consensus"
    report_df["bet_units"] = 1

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    report_df.to_csv(output_path, index=False)
    print(f"Weekly betting report saved to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate weekly CFB betting recommendations."
    )
    parser.add_argument(
        "--year", type=int, required=True, help="Season year for predictions."
    )
    parser.add_argument(
        "--week", type=int, required=True, help="Week number for predictions."
    )
    parser.add_argument(
        "--data-root",
        type=str,
        default=None,
        help="Absolute path to the data root directory.",
    )
    parser.add_argument(
        "--model-dir",
        type=str,
        default="./models/ridge_baseline",
        help="Directory where trained models are saved.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./reports",
        help="Directory to save the weekly report.",
    )

    args = parser.parse_args()

    try:
        print(f"Loading models for year {args.year}...")
        spread_model, total_model = load_models(args.year, args.model_dir)

        print(f"Loading data for year {args.year}, week {args.week}...")
        df = load_current_week_data(args.year, args.week, args.data_root)
        print(f"Columns of df: {df.columns}")
        print(f"Shape of df after loading: {df.shape}")

        # Build feature list to match training dynamically from available columns
        adjusted_metrics = [
            "epa_pp",
            "sr",
            "ypp",
            "expl_rate_overall_10",
            "expl_rate_overall_20",
            "expl_rate_overall_30",
            "expl_rate_rush",
            "expl_rate_pass",
        ]
        features = []
        for side in ["home", "away"]:
            for prefix in ["adj_off_", "adj_def_"]:
                for metric in adjusted_metrics:
                    col = f"{side}_{prefix}{metric}"
                    if col in df.columns:
                        features.append(col)
            for extra in [
                "off_eckel_rate",
                "off_finish_pts_per_opp",
                "stuff_rate",
                "havoc_rate",
            ]:
                col = f"{side}_{extra}"
                if col in df.columns:
                    features.append(col)

        print(f"Features being used: {features}")

        # Filter out rows with NaN in features
        df_cleaned = df.dropna(subset=features)
        print(f"Shape of df_cleaned after dropping NaNs: {df_cleaned.shape}")

        if df_cleaned.empty:
            print("No games with complete data for prediction this week.")
            sys.exit()

        X = df_cleaned[features]

        print("Generating spread predictions...")
        df_cleaned["predicted_spread"] = generate_predictions(spread_model, X)

        print("Generating total predictions...")
        df_cleaned["predicted_total"] = generate_predictions(total_model, X)

        # Lines were merged from betting_lines; they may be NaN if missing

        print("Applying betting policy...")
        final_predictions_df = apply_betting_policy(df_cleaned)

        output_filename = f"CFB_week{args.week}_bets.csv"
        output_path = os.path.join(args.output_dir, str(args.year), output_filename)

        print("Generating CSV report...")
        generate_csv_report(final_predictions_df, output_path)

        print(
            f"Weekly betting recommendations for year {args.year}, week {args.week} generated successfully."
        )

    except Exception as e:
        print(
            f"Error during weekly bet generation for year {args.year}, week {args.week}: {e}"
        )
        import traceback

        traceback.print_exc()
, '', regex=True)
    team_season_adj_df.columns = team_season_adj_df.columns.str.replace('_def

    # Load raw games for the season, then filter to the target week
    game_records = raw_storage.read_index("games", {"year": year})
    if not game_records:
        raise ValueError(f"No raw game data found for year {year}")
    games_season_df = pd.DataFrame.from_records(game_records)
    games_df = games_season_df[games_season_df["week"] == int(week)].copy()
    if games_df.empty:
        raise ValueError(f"No raw game data found for year {year}, week {week}")

    # Load betting lines and reduce to one line per game
    lines_records = raw_storage.read_index("betting_lines", {"year": year})
    lines_df = (
        pd.DataFrame.from_records(lines_records) if lines_records else pd.DataFrame()
    )
    if not lines_df.empty:
        # Prefer 'consensus' provider if available; otherwise first per game
        lines_df["provider_rank"] = np.where(
            lines_df["provider"].str.lower() == "consensus", 0, 1
        )
        lines_df = (
            lines_df.sort_values(["game_id", "provider_rank"])
            .groupby("game_id", as_index=False)
            .first()
        )
        lines_df = lines_df.rename(
            columns={"over_under": "total_line", "spread": "spread_line"}
        )
        lines_df = lines_df[["game_id", "spread_line", "total_line", "provider"]]

    # Merge features and game data (similar to train_model.py)
    home_features = team_season_adj_df.add_prefix("home_")
    away_features = team_season_adj_df.add_prefix("away_")

    merged_df = games_df.merge(
        home_features,
        left_on=["season", "home_team"],
        right_on=["home_season", "home_team"],
        how="left",
    )

    merged_df = merged_df.merge(
        away_features,
        left_on=["season", "away_team"],
        right_on=["away_season", "away_team"],
        how="left",
        suffixes=("", "_away"),
    )

    if not lines_df.empty:
        merged_df = merged_df.merge(
            lines_df, left_on=["id"], right_on=["game_id"], how="left"
        )

    merged_df = merged_df.drop(
        columns=["home_season", "home_team", "away_season", "away_team"],
        errors="ignore",
    )

    return merged_df


def generate_predictions(model, X: pd.DataFrame) -> pd.Series:  # noqa: N803
    """Generate predictions for X using a trained model.

    Args:
        model: Fitted estimator with a predict method.
        X: Feature matrix aligned to expected model schema.

    Returns:
        Series of predictions indexed to X.index.
    """
    return pd.Series(model.predict(X), index=X.index)


def apply_betting_policy(predictions_df: pd.DataFrame) -> pd.DataFrame:
    """Apply MVP betting policy thresholds to model outputs.

    Requires columns predicted_spread, predicted_total, spread_line, total_line,
    home_games_played, away_games_played. Produces bet_spread/bet_total and edges.

    Args:
        predictions_df: DataFrame containing model predictions and sportsbook lines.

    Returns:
        DataFrame with added edge_spread/edge_total and bet_spread/bet_total columns.
    """
    # Betting policy thresholds
    spread_edge_threshold = 3.5
    total_edge_threshold = 7.5
    min_games_played = 4

    # Calculate edges
    predictions_df["edge_spread"] = abs(
        predictions_df["predicted_spread"] - predictions_df["spread_line"]
    )
    predictions_df["edge_total"] = abs(
        predictions_df["predicted_total"] - predictions_df["total_line"]
    )

    # Apply betting policy
    predictions_df["bet_spread"] = "none"
    predictions_df.loc[
        (predictions_df["edge_spread"] >= spread_edge_threshold)
        & (predictions_df["home_games_played"] >= min_games_played)
        & (predictions_df["away_games_played"] >= min_games_played),
        "bet_spread",
    ] = np.where(
        predictions_df["predicted_spread"] > predictions_df["spread_line"],
        "home",
        "away",
    )

    predictions_df["bet_total"] = "none"
    predictions_df.loc[
        (predictions_df["edge_total"] >= total_edge_threshold)
        & (predictions_df["home_games_played"] >= min_games_played)
        & (predictions_df["away_games_played"] >= min_games_played),
        "bet_total",
    ] = np.where(
        predictions_df["predicted_total"] > predictions_df["total_line"],
        "over",
        "under",
    )

    return predictions_df


def generate_csv_report(predictions_df: pd.DataFrame, output_path: str) -> None:
    """Write the weekly CSV report with standardized columns.

    Args:
        predictions_df: DataFrame after policy application with required columns.
        output_path: Destination CSV path.
    """
    # Suggested columns:
    # season, week, game_id, game_date, home_team, away_team, neutral_site,
    # sportsbook, spread_line, total_line, model_spread, model_total,
    # edge_spread, edge_total, bet_spread (home/away/none), bet_total (over/under/none), bet_units

    report_df = predictions_df[
        [
            "season",
            "week",
            "id",
            "start_date",
            "home_team",
            "away_team",
            "neutral_site",
            "provider",
            "spread_line",
            "total_line",
            "predicted_spread",
            "predicted_total",
            "edge_spread",
            "edge_total",
            "bet_spread",
            "bet_total",
        ]
    ].copy()

    report_df = report_df.rename(
        columns={
            "id": "game_id",
            "start_date": "game_date",
            "predicted_spread": "model_spread",
            "predicted_total": "model_total",
            "provider": "sportsbook",
        }
    )

    # Fill sportsbook placeholder when missing and add flat staking units
    if "sportsbook" not in report_df.columns:
        report_df["sportsbook"] = "consensus"
    report_df["bet_units"] = 1

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    report_df.to_csv(output_path, index=False)
    print(f"Weekly betting report saved to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate weekly CFB betting recommendations."
    )
    parser.add_argument(
        "--year", type=int, required=True, help="Season year for predictions."
    )
    parser.add_argument(
        "--week", type=int, required=True, help="Week number for predictions."
    )
    parser.add_argument(
        "--data-root",
        type=str,
        default=None,
        help="Absolute path to the data root directory.",
    )
    parser.add_argument(
        "--model-dir",
        type=str,
        default="./models/ridge_baseline",
        help="Directory where trained models are saved.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./reports",
        help="Directory to save the weekly report.",
    )

    args = parser.parse_args()

    try:
        print(f"Loading models for year {args.year}...")
        spread_model, total_model = load_models(args.year, args.model_dir)

        print(f"Loading data for year {args.year}, week {args.week}...")
        df = load_current_week_data(args.year, args.week, args.data_root)
        print(f"Columns of df: {df.columns}")
        print(f"Shape of df after loading: {df.shape}")

        # Build feature list to match training dynamically from available columns
        adjusted_metrics = [
            "epa_pp",
            "sr",
            "ypp",
            "expl_rate_overall_10",
            "expl_rate_overall_20",
            "expl_rate_overall_30",
            "expl_rate_rush",
            "expl_rate_pass",
        ]
        features = []
        for side in ["home", "away"]:
            for prefix in ["adj_off_", "adj_def_"]:
                for metric in adjusted_metrics:
                    col = f"{side}_{prefix}{metric}"
                    if col in df.columns:
                        features.append(col)
            for extra in [
                "off_eckel_rate",
                "off_finish_pts_per_opp",
                "stuff_rate",
                "havoc_rate",
            ]:
                col = f"{side}_{extra}"
                if col in df.columns:
                    features.append(col)

        print(f"Features being used: {features}")

        # Filter out rows with NaN in features
        df_cleaned = df.dropna(subset=features)
        print(f"Shape of df_cleaned after dropping NaNs: {df_cleaned.shape}")

        if df_cleaned.empty:
            print("No games with complete data for prediction this week.")
            sys.exit()

        X = df_cleaned[features]

        print("Generating spread predictions...")
        df_cleaned["predicted_spread"] = generate_predictions(spread_model, X)

        print("Generating total predictions...")
        df_cleaned["predicted_total"] = generate_predictions(total_model, X)

        # Lines were merged from betting_lines; they may be NaN if missing

        print("Applying betting policy...")
        final_predictions_df = apply_betting_policy(df_cleaned)

        output_filename = f"CFB_week{args.week}_bets.csv"
        output_path = os.path.join(args.output_dir, str(args.year), output_filename)

        print("Generating CSV report...")
        generate_csv_report(final_predictions_df, output_path)

        print(
            f"Weekly betting recommendations for year {args.year}, week {args.week} generated successfully."
        )

    except Exception as e:
        print(
            f"Error during weekly bet generation for year {args.year}, week {args.week}: {e}"
        )
        import traceback

        traceback.print_exc()
, '', regex=True)

    # Load raw games for the season, then filter to the target week
    game_records = raw_storage.read_index("games", {"year": year})
    if not game_records:
        raise ValueError(f"No raw game data found for year {year}")
    games_season_df = pd.DataFrame.from_records(game_records)
    games_df = games_season_df[games_season_df["week"] == int(week)].copy()
    if games_df.empty:
        raise ValueError(f"No raw game data found for year {year}, week {week}")

    # Load betting lines and reduce to one line per game
    lines_records = raw_storage.read_index("betting_lines", {"year": year})
    lines_df = (
        pd.DataFrame.from_records(lines_records) if lines_records else pd.DataFrame()
    )
    if not lines_df.empty:
        # Prefer 'consensus' provider if available; otherwise first per game
        lines_df["provider_rank"] = np.where(
            lines_df["provider"].str.lower() == "consensus", 0, 1
        )
        lines_df = (
            lines_df.sort_values(["game_id", "provider_rank"])
            .groupby("game_id", as_index=False)
            .first()
        )
        lines_df = lines_df.rename(
            columns={"over_under": "total_line", "spread": "spread_line"}
        )
        lines_df = lines_df[["game_id", "spread_line", "total_line", "provider"]]

    # Merge features and game data (similar to train_model.py)
    home_features = team_season_adj_df.add_prefix("home_")
    away_features = team_season_adj_df.add_prefix("away_")

    merged_df = games_df.merge(
        home_features,
        left_on=["season", "home_team"],
        right_on=["home_season", "home_team"],
        how="left",
    )

    merged_df = merged_df.merge(
        away_features,
        left_on=["season", "away_team"],
        right_on=["away_season", "away_team"],
        how="left",
        suffixes=("", "_away"),
    )

    if not lines_df.empty:
        merged_df = merged_df.merge(
            lines_df, left_on=["id"], right_on=["game_id"], how="left"
        )

    merged_df = merged_df.drop(
        columns=["home_season", "home_team", "away_season", "away_team"],
        errors="ignore",
    )

    return merged_df


def generate_predictions(model, X: pd.DataFrame) -> pd.Series:  # noqa: N803
    """Generate predictions for X using a trained model.

    Args:
        model: Fitted estimator with a predict method.
        X: Feature matrix aligned to expected model schema.

    Returns:
        Series of predictions indexed to X.index.
    """
    return pd.Series(model.predict(X), index=X.index)


def apply_betting_policy(predictions_df: pd.DataFrame) -> pd.DataFrame:
    """Apply MVP betting policy thresholds to model outputs.

    Requires columns predicted_spread, predicted_total, spread_line, total_line,
    home_games_played, away_games_played. Produces bet_spread/bet_total and edges.

    Args:
        predictions_df: DataFrame containing model predictions and sportsbook lines.

    Returns:
        DataFrame with added edge_spread/edge_total and bet_spread/bet_total columns.
    """
    # Betting policy thresholds
    spread_edge_threshold = 3.5
    total_edge_threshold = 7.5
    min_games_played = 4

    # Calculate edges
    predictions_df["edge_spread"] = abs(
        predictions_df["predicted_spread"] - predictions_df["spread_line"]
    )
    predictions_df["edge_total"] = abs(
        predictions_df["predicted_total"] - predictions_df["total_line"]
    )

    # Apply betting policy
    predictions_df["bet_spread"] = "none"
    predictions_df.loc[
        (predictions_df["edge_spread"] >= spread_edge_threshold)
        & (predictions_df["home_games_played"] >= min_games_played)
        & (predictions_df["away_games_played"] >= min_games_played),
        "bet_spread",
    ] = np.where(
        predictions_df["predicted_spread"] > predictions_df["spread_line"],
        "home",
        "away",
    )

    predictions_df["bet_total"] = "none"
    predictions_df.loc[
        (predictions_df["edge_total"] >= total_edge_threshold)
        & (predictions_df["home_games_played"] >= min_games_played)
        & (predictions_df["away_games_played"] >= min_games_played),
        "bet_total",
    ] = np.where(
        predictions_df["predicted_total"] > predictions_df["total_line"],
        "over",
        "under",
    )

    return predictions_df


def generate_csv_report(predictions_df: pd.DataFrame, output_path: str) -> None:
    """Write the weekly CSV report with standardized columns.

    Args:
        predictions_df: DataFrame after policy application with required columns.
        output_path: Destination CSV path.
    """
    # Suggested columns:
    # season, week, game_id, game_date, home_team, away_team, neutral_site,
    # sportsbook, spread_line, total_line, model_spread, model_total,
    # edge_spread, edge_total, bet_spread (home/away/none), bet_total (over/under/none), bet_units

    report_df = predictions_df[
        [
            "season",
            "week",
            "id",
            "start_date",
            "home_team",
            "away_team",
            "neutral_site",
            "provider",
            "spread_line",
            "total_line",
            "predicted_spread",
            "predicted_total",
            "edge_spread",
            "edge_total",
            "bet_spread",
            "bet_total",
        ]
    ].copy()

    report_df = report_df.rename(
        columns={
            "id": "game_id",
            "start_date": "game_date",
            "predicted_spread": "model_spread",
            "predicted_total": "model_total",
            "provider": "sportsbook",
        }
    )

    # Fill sportsbook placeholder when missing and add flat staking units
    if "sportsbook" not in report_df.columns:
        report_df["sportsbook"] = "consensus"
    report_df["bet_units"] = 1

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    report_df.to_csv(output_path, index=False)
    print(f"Weekly betting report saved to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate weekly CFB betting recommendations."
    )
    parser.add_argument(
        "--year", type=int, required=True, help="Season year for predictions."
    )
    parser.add_argument(
        "--week", type=int, required=True, help="Week number for predictions."
    )
    parser.add_argument(
        "--data-root",
        type=str,
        default=None,
        help="Absolute path to the data root directory.",
    )
    parser.add_argument(
        "--model-dir",
        type=str,
        default="./models/ridge_baseline",
        help="Directory where trained models are saved.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./reports",
        help="Directory to save the weekly report.",
    )

    args = parser.parse_args()

    try:
        print(f"Loading models for year {args.year}...")
        spread_model, total_model = load_models(args.year, args.model_dir)

        print(f"Loading data for year {args.year}, week {args.week}...")
        df = load_current_week_data(args.year, args.week, args.data_root)
        print(f"Columns of df: {df.columns}")
        print(f"Shape of df after loading: {df.shape}")

        # Build feature list to match training dynamically from available columns
        adjusted_metrics = [
            "epa_pp",
            "sr",
            "ypp",
            "expl_rate_overall_10",
            "expl_rate_overall_20",
            "expl_rate_overall_30",
            "expl_rate_rush",
            "expl_rate_pass",
        ]
        features = []
        for side in ["home", "away"]:
            for prefix in ["adj_off_", "adj_def_"]:
                for metric in adjusted_metrics:
                    col = f"{side}_{prefix}{metric}"
                    if col in df.columns:
                        features.append(col)
            for extra in [
                "off_eckel_rate",
                "off_finish_pts_per_opp",
                "stuff_rate",
                "havoc_rate",
            ]:
                col = f"{side}_{extra}"
                if col in df.columns:
                    features.append(col)

        print(f"Features being used: {features}")

        # Filter out rows with NaN in features
        df_cleaned = df.dropna(subset=features)
        print(f"Shape of df_cleaned after dropping NaNs: {df_cleaned.shape}")

        if df_cleaned.empty:
            print("No games with complete data for prediction this week.")
            sys.exit()

        X = df_cleaned[features]

        print("Generating spread predictions...")
        df_cleaned["predicted_spread"] = generate_predictions(spread_model, X)

        print("Generating total predictions...")
        df_cleaned["predicted_total"] = generate_predictions(total_model, X)

        # Lines were merged from betting_lines; they may be NaN if missing

        print("Applying betting policy...")
        final_predictions_df = apply_betting_policy(df_cleaned)

        output_filename = f"CFB_week{args.week}_bets.csv"
        output_path = os.path.join(args.output_dir, str(args.year), output_filename)

        print("Generating CSV report...")
        generate_csv_report(final_predictions_df, output_path)

        print(
            f"Weekly betting recommendations for year {args.year}, week {args.week} generated successfully."
        )

    except Exception as e:
        print(
            f"Error during weekly bet generation for year {args.year}, week {args.week}: {e}"
        )
        import traceback

        traceback.print_exc()
, '', regex=True)

    # Load raw games for the season, then filter to the target week
    game_records = raw_storage.read_index("games", {"year": year})
    if not game_records:
        raise ValueError(f"No raw game data found for year {year}")
    games_season_df = pd.DataFrame.from_records(game_records)
    games_df = games_season_df[games_season_df["week"] == int(week)].copy()
    if games_df.empty:
        raise ValueError(f"No raw game data found for year {year}, week {week}")

    # Load betting lines and reduce to one line per game
    lines_records = raw_storage.read_index("betting_lines", {"year": year})
    lines_df = (
        pd.DataFrame.from_records(lines_records) if lines_records else pd.DataFrame()
    )
    if not lines_df.empty:
        # Prefer 'consensus' provider if available; otherwise first per game
        lines_df["provider_rank"] = np.where(
            lines_df["provider"].str.lower() == "consensus", 0, 1
        )
        lines_df = (
            lines_df.sort_values(["game_id", "provider_rank"])
            .groupby("game_id", as_index=False)
            .first()
        )
        lines_df = lines_df.rename(
            columns={"over_under": "total_line", "spread": "spread_line"}
        )
        lines_df = lines_df[["game_id", "spread_line", "total_line", "provider"]]

    # Merge features and game data (similar to train_model.py)
    home_features = team_season_adj_df.add_prefix("home_")
    away_features = team_season_adj_df.add_prefix("away_")

    merged_df = games_df.merge(
        home_features,
        left_on=["season", "home_team"],
        right_on=["home_season", "home_team"],
        how="left",
    )

    merged_df = merged_df.merge(
        away_features,
        left_on=["season", "away_team"],
        right_on=["away_season", "away_team"],
        how="left",
        suffixes=("", "_away"),
    )

    if not lines_df.empty:
        merged_df = merged_df.merge(
            lines_df, left_on=["id"], right_on=["game_id"], how="left"
        )

    merged_df = merged_df.drop(
        columns=["home_season", "home_team", "away_season", "away_team"],
        errors="ignore",
    )

    return merged_df


def generate_predictions(model, X: pd.DataFrame) -> pd.Series:  # noqa: N803
    """Generate predictions for X using a trained model.

    Args:
        model: Fitted estimator with a predict method.
        X: Feature matrix aligned to expected model schema.

    Returns:
        Series of predictions indexed to X.index.
    """
    return pd.Series(model.predict(X), index=X.index)


def apply_betting_policy(predictions_df: pd.DataFrame) -> pd.DataFrame:
    """Apply MVP betting policy thresholds to model outputs.

    Requires columns predicted_spread, predicted_total, spread_line, total_line,
    home_games_played, away_games_played. Produces bet_spread/bet_total and edges.

    Args:
        predictions_df: DataFrame containing model predictions and sportsbook lines.

    Returns:
        DataFrame with added edge_spread/edge_total and bet_spread/bet_total columns.
    """
    # Betting policy thresholds
    spread_edge_threshold = 3.5
    total_edge_threshold = 7.5
    min_games_played = 4

    # Calculate edges
    predictions_df["edge_spread"] = abs(
        predictions_df["predicted_spread"] - predictions_df["spread_line"]
    )
    predictions_df["edge_total"] = abs(
        predictions_df["predicted_total"] - predictions_df["total_line"]
    )

    # Apply betting policy
    predictions_df["bet_spread"] = "none"
    predictions_df.loc[
        (predictions_df["edge_spread"] >= spread_edge_threshold)
        & (predictions_df["home_games_played"] >= min_games_played)
        & (predictions_df["away_games_played"] >= min_games_played),
        "bet_spread",
    ] = np.where(
        predictions_df["predicted_spread"] > predictions_df["spread_line"],
        "home",
        "away",
    )

    predictions_df["bet_total"] = "none"
    predictions_df.loc[
        (predictions_df["edge_total"] >= total_edge_threshold)
        & (predictions_df["home_games_played"] >= min_games_played)
        & (predictions_df["away_games_played"] >= min_games_played),
        "bet_total",
    ] = np.where(
        predictions_df["predicted_total"] > predictions_df["total_line"],
        "over",
        "under",
    )

    return predictions_df


def generate_csv_report(predictions_df: pd.DataFrame, output_path: str) -> None:
    """Write the weekly CSV report with standardized columns.

    Args:
        predictions_df: DataFrame after policy application with required columns.
        output_path: Destination CSV path.
    """
    # Suggested columns:
    # season, week, game_id, game_date, home_team, away_team, neutral_site,
    # sportsbook, spread_line, total_line, model_spread, model_total,
    # edge_spread, edge_total, bet_spread (home/away/none), bet_total (over/under/none), bet_units

    report_df = predictions_df[
        [
            "season",
            "week",
            "id",
            "start_date",
            "home_team",
            "away_team",
            "neutral_site",
            "provider",
            "spread_line",
            "total_line",
            "predicted_spread",
            "predicted_total",
            "edge_spread",
            "edge_total",
            "bet_spread",
            "bet_total",
        ]
    ].copy()

    report_df = report_df.rename(
        columns={
            "id": "game_id",
            "start_date": "game_date",
            "predicted_spread": "model_spread",
            "predicted_total": "model_total",
            "provider": "sportsbook",
        }
    )

    # Fill sportsbook placeholder when missing and add flat staking units
    if "sportsbook" not in report_df.columns:
        report_df["sportsbook"] = "consensus"
    report_df["bet_units"] = 1

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    report_df.to_csv(output_path, index=False)
    print(f"Weekly betting report saved to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate weekly CFB betting recommendations."
    )
    parser.add_argument(
        "--year", type=int, required=True, help="Season year for predictions."
    )
    parser.add_argument(
        "--week", type=int, required=True, help="Week number for predictions."
    )
    parser.add_argument(
        "--data-root",
        type=str,
        default=None,
        help="Absolute path to the data root directory.",
    )
    parser.add_argument(
        "--model-dir",
        type=str,
        default="./models/ridge_baseline",
        help="Directory where trained models are saved.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./reports",
        help="Directory to save the weekly report.",
    )

    args = parser.parse_args()

    try:
        print(f"Loading models for year {args.year}...")
        spread_model, total_model = load_models(args.year, args.model_dir)

        print(f"Loading data for year {args.year}, week {args.week}...")
        df = load_current_week_data(args.year, args.week, args.data_root)
        print(f"Columns of df: {df.columns}")
        print(f"Shape of df after loading: {df.shape}")

        # Build feature list to match training dynamically from available columns
        adjusted_metrics = [
            "epa_pp",
            "sr",
            "ypp",
            "expl_rate_overall_10",
            "expl_rate_overall_20",
            "expl_rate_overall_30",
            "expl_rate_rush",
            "expl_rate_pass",
        ]
        features = []
        for side in ["home", "away"]:
            for prefix in ["adj_off_", "adj_def_"]:
                for metric in adjusted_metrics:
                    col = f"{side}_{prefix}{metric}"
                    if col in df.columns:
                        features.append(col)
            for extra in [
                "off_eckel_rate",
                "off_finish_pts_per_opp",
                "stuff_rate",
                "havoc_rate",
            ]:
                col = f"{side}_{extra}"
                if col in df.columns:
                    features.append(col)

        print(f"Features being used: {features}")

        # Filter out rows with NaN in features
        df_cleaned = df.dropna(subset=features)
        print(f"Shape of df_cleaned after dropping NaNs: {df_cleaned.shape}")

        if df_cleaned.empty:
            print("No games with complete data for prediction this week.")
            sys.exit()

        X = df_cleaned[features]

        print("Generating spread predictions...")
        df_cleaned["predicted_spread"] = generate_predictions(spread_model, X)

        print("Generating total predictions...")
        df_cleaned["predicted_total"] = generate_predictions(total_model, X)

        # Lines were merged from betting_lines; they may be NaN if missing

        print("Applying betting policy...")
        final_predictions_df = apply_betting_policy(df_cleaned)

        output_filename = f"CFB_week{args.week}_bets.csv"
        output_path = os.path.join(args.output_dir, str(args.year), output_filename)

        print("Generating CSV report...")
        generate_csv_report(final_predictions_df, output_path)

        print(
            f"Weekly betting recommendations for year {args.year}, week {args.week} generated successfully."
        )

    except Exception as e:
        print(
            f"Error during weekly bet generation for year {args.year}, week {args.week}: {e}"
        )
        import traceback

        traceback.print_exc()
, '', regex=True)
    team_season_adj_df.columns = team_season_adj_df.columns.str.replace('_def

    # Load raw games for the season, then filter to the target week
    game_records = raw_storage.read_index("games", {"year": year})
    if not game_records:
        raise ValueError(f"No raw game data found for year {year}")
    games_season_df = pd.DataFrame.from_records(game_records)
    games_df = games_season_df[games_season_df["week"] == int(week)].copy()
    if games_df.empty:
        raise ValueError(f"No raw game data found for year {year}, week {week}")

    # Load betting lines and reduce to one line per game
    lines_records = raw_storage.read_index("betting_lines", {"year": year})
    lines_df = (
        pd.DataFrame.from_records(lines_records) if lines_records else pd.DataFrame()
    )
    if not lines_df.empty:
        # Prefer 'consensus' provider if available; otherwise first per game
        lines_df["provider_rank"] = np.where(
            lines_df["provider"].str.lower() == "consensus", 0, 1
        )
        lines_df = (
            lines_df.sort_values(["game_id", "provider_rank"])
            .groupby("game_id", as_index=False)
            .first()
        )
        lines_df = lines_df.rename(
            columns={"over_under": "total_line", "spread": "spread_line"}
        )
        lines_df = lines_df[["game_id", "spread_line", "total_line", "provider"]]

    # Merge features and game data (similar to train_model.py)
    home_features = team_season_adj_df.add_prefix("home_")
    away_features = team_season_adj_df.add_prefix("away_")

    merged_df = games_df.merge(
        home_features,
        left_on=["season", "home_team"],
        right_on=["home_season", "home_team"],
        how="left",
    )

    merged_df = merged_df.merge(
        away_features,
        left_on=["season", "away_team"],
        right_on=["away_season", "away_team"],
        how="left",
        suffixes=("", "_away"),
    )

    if not lines_df.empty:
        merged_df = merged_df.merge(
            lines_df, left_on=["id"], right_on=["game_id"], how="left"
        )

    merged_df = merged_df.drop(
        columns=["home_season", "home_team", "away_season", "away_team"],
        errors="ignore",
    )

    return merged_df


def generate_predictions(model, X: pd.DataFrame) -> pd.Series:  # noqa: N803
    """Generate predictions for X using a trained model.

    Args:
        model: Fitted estimator with a predict method.
        X: Feature matrix aligned to expected model schema.

    Returns:
        Series of predictions indexed to X.index.
    """
    return pd.Series(model.predict(X), index=X.index)


def apply_betting_policy(predictions_df: pd.DataFrame) -> pd.DataFrame:
    """Apply MVP betting policy thresholds to model outputs.

    Requires columns predicted_spread, predicted_total, spread_line, total_line,
    home_games_played, away_games_played. Produces bet_spread/bet_total and edges.

    Args:
        predictions_df: DataFrame containing model predictions and sportsbook lines.

    Returns:
        DataFrame with added edge_spread/edge_total and bet_spread/bet_total columns.
    """
    # Betting policy thresholds
    spread_edge_threshold = 3.5
    total_edge_threshold = 7.5
    min_games_played = 4

    # Calculate edges
    predictions_df["edge_spread"] = abs(
        predictions_df["predicted_spread"] - predictions_df["spread_line"]
    )
    predictions_df["edge_total"] = abs(
        predictions_df["predicted_total"] - predictions_df["total_line"]
    )

    # Apply betting policy
    predictions_df["bet_spread"] = "none"
    predictions_df.loc[
        (predictions_df["edge_spread"] >= spread_edge_threshold)
        & (predictions_df["home_games_played"] >= min_games_played)
        & (predictions_df["away_games_played"] >= min_games_played),
        "bet_spread",
    ] = np.where(
        predictions_df["predicted_spread"] > predictions_df["spread_line"],
        "home",
        "away",
    )

    predictions_df["bet_total"] = "none"
    predictions_df.loc[
        (predictions_df["edge_total"] >= total_edge_threshold)
        & (predictions_df["home_games_played"] >= min_games_played)
        & (predictions_df["away_games_played"] >= min_games_played),
        "bet_total",
    ] = np.where(
        predictions_df["predicted_total"] > predictions_df["total_line"],
        "over",
        "under",
    )

    return predictions_df


def generate_csv_report(predictions_df: pd.DataFrame, output_path: str) -> None:
    """Write the weekly CSV report with standardized columns.

    Args:
        predictions_df: DataFrame after policy application with required columns.
        output_path: Destination CSV path.
    """
    # Suggested columns:
    # season, week, game_id, game_date, home_team, away_team, neutral_site,
    # sportsbook, spread_line, total_line, model_spread, model_total,
    # edge_spread, edge_total, bet_spread (home/away/none), bet_total (over/under/none), bet_units

    report_df = predictions_df[
        [
            "season",
            "week",
            "id",
            "start_date",
            "home_team",
            "away_team",
            "neutral_site",
            "provider",
            "spread_line",
            "total_line",
            "predicted_spread",
            "predicted_total",
            "edge_spread",
            "edge_total",
            "bet_spread",
            "bet_total",
        ]
    ].copy()

    report_df = report_df.rename(
        columns={
            "id": "game_id",
            "start_date": "game_date",
            "predicted_spread": "model_spread",
            "predicted_total": "model_total",
            "provider": "sportsbook",
        }
    )

    # Fill sportsbook placeholder when missing and add flat staking units
    if "sportsbook" not in report_df.columns:
        report_df["sportsbook"] = "consensus"
    report_df["bet_units"] = 1

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    report_df.to_csv(output_path, index=False)
    print(f"Weekly betting report saved to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate weekly CFB betting recommendations."
    )
    parser.add_argument(
        "--year", type=int, required=True, help="Season year for predictions."
    )
    parser.add_argument(
        "--week", type=int, required=True, help="Week number for predictions."
    )
    parser.add_argument(
        "--data-root",
        type=str,
        default=None,
        help="Absolute path to the data root directory.",
    )
    parser.add_argument(
        "--model-dir",
        type=str,
        default="./models/ridge_baseline",
        help="Directory where trained models are saved.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./reports",
        help="Directory to save the weekly report.",
    )

    args = parser.parse_args()

    try:
        print(f"Loading models for year {args.year}...")
        spread_model, total_model = load_models(args.year, args.model_dir)

        print(f"Loading data for year {args.year}, week {args.week}...")
        df = load_current_week_data(args.year, args.week, args.data_root)
        print(f"Columns of df: {df.columns}")
        print(f"Shape of df after loading: {df.shape}")

        # Build feature list to match training dynamically from available columns
        adjusted_metrics = [
            "epa_pp",
            "sr",
            "ypp",
            "expl_rate_overall_10",
            "expl_rate_overall_20",
            "expl_rate_overall_30",
            "expl_rate_rush",
            "expl_rate_pass",
        ]
        features = []
        for side in ["home", "away"]:
            for prefix in ["adj_off_", "adj_def_"]:
                for metric in adjusted_metrics:
                    col = f"{side}_{prefix}{metric}"
                    if col in df.columns:
                        features.append(col)
            for extra in [
                "off_eckel_rate",
                "off_finish_pts_per_opp",
                "stuff_rate",
                "havoc_rate",
            ]:
                col = f"{side}_{extra}"
                if col in df.columns:
                    features.append(col)

        print(f"Features being used: {features}")

        # Filter out rows with NaN in features
        df_cleaned = df.dropna(subset=features)
        print(f"Shape of df_cleaned after dropping NaNs: {df_cleaned.shape}")

        if df_cleaned.empty:
            print("No games with complete data for prediction this week.")
            sys.exit()

        X = df_cleaned[features]

        print("Generating spread predictions...")
        df_cleaned["predicted_spread"] = generate_predictions(spread_model, X)

        print("Generating total predictions...")
        df_cleaned["predicted_total"] = generate_predictions(total_model, X)

        # Lines were merged from betting_lines; they may be NaN if missing

        print("Applying betting policy...")
        final_predictions_df = apply_betting_policy(df_cleaned)

        output_filename = f"CFB_week{args.week}_bets.csv"
        output_path = os.path.join(args.output_dir, str(args.year), output_filename)

        print("Generating CSV report...")
        generate_csv_report(final_predictions_df, output_path)

        print(
            f"Weekly betting recommendations for year {args.year}, week {args.week} generated successfully."
        )

    except Exception as e:
        print(
            f"Error during weekly bet generation for year {args.year}, week {args.week}: {e}"
        )
        import traceback

        traceback.print_exc()
, '', regex=True)

    # Load raw games for the season, then filter to the target week
    game_records = raw_storage.read_index("games", {"year": year})
    if not game_records:
        raise ValueError(f"No raw game data found for year {year}")
    games_season_df = pd.DataFrame.from_records(game_records)
    games_df = games_season_df[games_season_df["week"] == int(week)].copy()
    if games_df.empty:
        raise ValueError(f"No raw game data found for year {year}, week {week}")

    # Load betting lines and reduce to one line per game
    lines_records = raw_storage.read_index("betting_lines", {"year": year})
    lines_df = (
        pd.DataFrame.from_records(lines_records) if lines_records else pd.DataFrame()
    )
    if not lines_df.empty:
        # Prefer 'consensus' provider if available; otherwise first per game
        lines_df["provider_rank"] = np.where(
            lines_df["provider"].str.lower() == "consensus", 0, 1
        )
        lines_df = (
            lines_df.sort_values(["game_id", "provider_rank"])
            .groupby("game_id", as_index=False)
            .first()
        )
        lines_df = lines_df.rename(
            columns={"over_under": "total_line", "spread": "spread_line"}
        )
        lines_df = lines_df[["game_id", "spread_line", "total_line", "provider"]]

    # Merge features and game data (similar to train_model.py)
    home_features = team_season_adj_df.add_prefix("home_")
    away_features = team_season_adj_df.add_prefix("away_")

    merged_df = games_df.merge(
        home_features,
        left_on=["season", "home_team"],
        right_on=["home_season", "home_team"],
        how="left",
    )

    merged_df = merged_df.merge(
        away_features,
        left_on=["season", "away_team"],
        right_on=["away_season", "away_team"],
        how="left",
        suffixes=("", "_away"),
    )

    if not lines_df.empty:
        merged_df = merged_df.merge(
            lines_df, left_on=["id"], right_on=["game_id"], how="left"
        )

    merged_df = merged_df.drop(
        columns=["home_season", "home_team", "away_season", "away_team"],
        errors="ignore",
    )

    return merged_df


def generate_predictions(model, X: pd.DataFrame) -> pd.Series:  # noqa: N803
    """Generate predictions for X using a trained model.

    Args:
        model: Fitted estimator with a predict method.
        X: Feature matrix aligned to expected model schema.

    Returns:
        Series of predictions indexed to X.index.
    """
    return pd.Series(model.predict(X), index=X.index)


def apply_betting_policy(predictions_df: pd.DataFrame) -> pd.DataFrame:
    """Apply MVP betting policy thresholds to model outputs.

    Requires columns predicted_spread, predicted_total, spread_line, total_line,
    home_games_played, away_games_played. Produces bet_spread/bet_total and edges.

    Args:
        predictions_df: DataFrame containing model predictions and sportsbook lines.

    Returns:
        DataFrame with added edge_spread/edge_total and bet_spread/bet_total columns.
    """
    # Betting policy thresholds
    spread_edge_threshold = 3.5
    total_edge_threshold = 7.5
    min_games_played = 4

    # Calculate edges
    predictions_df["edge_spread"] = abs(
        predictions_df["predicted_spread"] - predictions_df["spread_line"]
    )
    predictions_df["edge_total"] = abs(
        predictions_df["predicted_total"] - predictions_df["total_line"]
    )

    # Apply betting policy
    predictions_df["bet_spread"] = "none"
    predictions_df.loc[
        (predictions_df["edge_spread"] >= spread_edge_threshold)
        & (predictions_df["home_games_played"] >= min_games_played)
        & (predictions_df["away_games_played"] >= min_games_played),
        "bet_spread",
    ] = np.where(
        predictions_df["predicted_spread"] > predictions_df["spread_line"],
        "home",
        "away",
    )

    predictions_df["bet_total"] = "none"
    predictions_df.loc[
        (predictions_df["edge_total"] >= total_edge_threshold)
        & (predictions_df["home_games_played"] >= min_games_played)
        & (predictions_df["away_games_played"] >= min_games_played),
        "bet_total",
    ] = np.where(
        predictions_df["predicted_total"] > predictions_df["total_line"],
        "over",
        "under",
    )

    return predictions_df


def generate_csv_report(predictions_df: pd.DataFrame, output_path: str) -> None:
    """Write the weekly CSV report with standardized columns.

    Args:
        predictions_df: DataFrame after policy application with required columns.
        output_path: Destination CSV path.
    """
    # Suggested columns:
    # season, week, game_id, game_date, home_team, away_team, neutral_site,
    # sportsbook, spread_line, total_line, model_spread, model_total,
    # edge_spread, edge_total, bet_spread (home/away/none), bet_total (over/under/none), bet_units

    report_df = predictions_df[
        [
            "season",
            "week",
            "id",
            "start_date",
            "home_team",
            "away_team",
            "neutral_site",
            "provider",
            "spread_line",
            "total_line",
            "predicted_spread",
            "predicted_total",
            "edge_spread",
            "edge_total",
            "bet_spread",
            "bet_total",
        ]
    ].copy()

    report_df = report_df.rename(
        columns={
            "id": "game_id",
            "start_date": "game_date",
            "predicted_spread": "model_spread",
            "predicted_total": "model_total",
            "provider": "sportsbook",
        }
    )

    # Fill sportsbook placeholder when missing and add flat staking units
    if "sportsbook" not in report_df.columns:
        report_df["sportsbook"] = "consensus"
    report_df["bet_units"] = 1

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    report_df.to_csv(output_path, index=False)
    print(f"Weekly betting report saved to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate weekly CFB betting recommendations."
    )
    parser.add_argument(
        "--year", type=int, required=True, help="Season year for predictions."
    )
    parser.add_argument(
        "--week", type=int, required=True, help="Week number for predictions."
    )
    parser.add_argument(
        "--data-root",
        type=str,
        default=None,
        help="Absolute path to the data root directory.",
    )
    parser.add_argument(
        "--model-dir",
        type=str,
        default="./models/ridge_baseline",
        help="Directory where trained models are saved.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./reports",
        help="Directory to save the weekly report.",
    )

    args = parser.parse_args()

    try:
        print(f"Loading models for year {args.year}...")
        spread_model, total_model = load_models(args.year, args.model_dir)

        print(f"Loading data for year {args.year}, week {args.week}...")
        df = load_current_week_data(args.year, args.week, args.data_root)
        print(f"Columns of df: {df.columns}")
        print(f"Shape of df after loading: {df.shape}")

        # Build feature list to match training dynamically from available columns
        adjusted_metrics = [
            "epa_pp",
            "sr",
            "ypp",
            "expl_rate_overall_10",
            "expl_rate_overall_20",
            "expl_rate_overall_30",
            "expl_rate_rush",
            "expl_rate_pass",
        ]
        features = []
        for side in ["home", "away"]:
            for prefix in ["adj_off_", "adj_def_"]:
                for metric in adjusted_metrics:
                    col = f"{side}_{prefix}{metric}"
                    if col in df.columns:
                        features.append(col)
            for extra in [
                "off_eckel_rate",
                "off_finish_pts_per_opp",
                "stuff_rate",
                "havoc_rate",
            ]:
                col = f"{side}_{extra}"
                if col in df.columns:
                    features.append(col)

        print(f"Features being used: {features}")

        # Filter out rows with NaN in features
        df_cleaned = df.dropna(subset=features)
        print(f"Shape of df_cleaned after dropping NaNs: {df_cleaned.shape}")

        if df_cleaned.empty:
            print("No games with complete data for prediction this week.")
            sys.exit()

        X = df_cleaned[features]

        print("Generating spread predictions...")
        df_cleaned["predicted_spread"] = generate_predictions(spread_model, X)

        print("Generating total predictions...")
        df_cleaned["predicted_total"] = generate_predictions(total_model, X)

        # Lines were merged from betting_lines; they may be NaN if missing

        print("Applying betting policy...")
        final_predictions_df = apply_betting_policy(df_cleaned)

        output_filename = f"CFB_week{args.week}_bets.csv"
        output_path = os.path.join(args.output_dir, str(args.year), output_filename)

        print("Generating CSV report...")
        generate_csv_report(final_predictions_df, output_path)

        print(
            f"Weekly betting recommendations for year {args.year}, week {args.week} generated successfully."
        )

    except Exception as e:
        print(
            f"Error during weekly bet generation for year {args.year}, week {args.week}: {e}"
        )
        import traceback

        traceback.print_exc()
