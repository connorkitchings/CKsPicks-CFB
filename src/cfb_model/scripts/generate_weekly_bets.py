import argparse
import os

import joblib
import numpy as np
import pandas as pd

from cfb_model.data.storage.local_storage import LocalStorage


def load_models(year: int, model_dir: str):
    """
    Loads the trained Ridge Regression models for a given year.
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


def load_current_week_data(year: int, week: int, data_root: str) -> pd.DataFrame:
    """
    Loads opponent-adjusted features and game data for the current week.
    """
    processed_storage = LocalStorage(
        data_root=data_root, file_format="csv", data_type="processed"
    )
    raw_storage = LocalStorage(data_root=data_root, file_format="csv", data_type="raw")

    # Load opponent-adjusted team season features for the entire season
    team_season_adj_records = processed_storage.read_index(
        "team_season_adj", {"year": year}
    )
    if not team_season_adj_records:
        raise ValueError(f"No adjusted team season data found for year {year}")
    team_season_adj_df = pd.DataFrame.from_records(team_season_adj_records)

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


def generate_predictions(model, X: pd.DataFrame) -> pd.Series:
    """
    Generates predictions using the loaded model.
    """
    return pd.Series(model.predict(X), index=X.index)


def apply_betting_policy(predictions_df: pd.DataFrame) -> pd.DataFrame:
    """
    Applies the betting policy to the predictions.
    """
    # Betting policy thresholds
    SPREAD_EDGE_THRESHOLD = 3.5
    TOTAL_EDGE_THRESHOLD = 7.5
    MIN_GAMES_PLAYED = 4

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
        (predictions_df["edge_spread"] >= SPREAD_EDGE_THRESHOLD)
        & (predictions_df["home_games_played"] >= MIN_GAMES_PLAYED)
        & (predictions_df["away_games_played"] >= MIN_GAMES_PLAYED),
        "bet_spread",
    ] = np.where(
        predictions_df["predicted_spread"] > predictions_df["spread_line"],
        "home",
        "away",
    )

    predictions_df["bet_total"] = "none"
    predictions_df.loc[
        (predictions_df["edge_total"] >= TOTAL_EDGE_THRESHOLD)
        & (predictions_df["home_games_played"] >= MIN_GAMES_PLAYED)
        & (predictions_df["away_games_played"] >= MIN_GAMES_PLAYED),
        "bet_total",
    ] = np.where(
        predictions_df["predicted_total"] > predictions_df["total_line"],
        "over",
        "under",
    )

    return predictions_df


def generate_csv_report(predictions_df: pd.DataFrame, output_path: str) -> None:
    """
    Generates and saves the weekly CSV report.
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

        # Filter out rows with NaN in features
        df_cleaned = df.dropna(subset=features)

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
