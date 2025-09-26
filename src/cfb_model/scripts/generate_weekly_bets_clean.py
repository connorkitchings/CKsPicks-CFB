"""Generate weekly ATS recommendations using trained models and betting policy (clean)."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Tuple

import joblib
import numpy as np
import pandas as pd

from cfb_model.config import get_data_root
from cfb_model.data.storage.local_storage import LocalStorage
from cfb_model.models.features import (
    prepare_team_features,
    build_feature_list,
    generate_point_in_time_features,
)


def load_models(model_year: int, model_dir: str) -> Tuple[object, object]:
    """Load trained spread/total Ridge models for a given season (saved under model_dir/<year>/).

    Raises FileNotFoundError if artifacts are missing.
    """
    spread_path = os.path.join(model_dir, str(model_year), "ridge_spread.joblib")
    total_path = os.path.join(model_dir, str(model_year), "ridge_total.joblib")
    if not os.path.exists(spread_path):
        raise FileNotFoundError(f"Spread model not found at {spread_path}")
    if not os.path.exists(total_path):
        raise FileNotFoundError(f"Total model not found at {total_path}")
    return joblib.load(spread_path), joblib.load(total_path)


def _reduce_betting_lines(lines_df: pd.DataFrame) -> pd.DataFrame:
    """Reduce betting_lines to one row per game, preferring provider == 'consensus'."""
    if lines_df.empty:
        return lines_df
    df = lines_df.copy()
    df["provider_rank"] = np.where(df["provider"].str.lower() == "consensus", 0, 1)
    df = (
        df.sort_values(["game_id", "provider_rank"])  # consensus first
        .groupby("game_id", as_index=False)
        .first()
    )
    df = df.rename(
        columns={"over_under": "total_line", "spread": "home_team_spread_line"}
    )[["game_id", "home_team_spread_line", "total_line", "provider"]]
    return df


def load_week_dataset(
    year: int, week: int, data_root: str | None = None
) -> pd.DataFrame:
    """Load per-game features for a specific week using point-in-time generation and merge betting lines."""
    # 1. Generate leakage-free features for the target week
    week_features_df = generate_point_in_time_features(year, week, data_root)

    # 2. Load and merge betting lines for the week
    resolved_root = data_root or get_data_root()
    raw = LocalStorage(data_root=resolved_root, file_format="csv", data_type="raw")
    lines_records = raw.read_index("betting_lines", {"year": year})
    lines_df = (
        pd.DataFrame.from_records(lines_records) if lines_records else pd.DataFrame()
    )
    if not lines_df.empty:
        lines_df = _reduce_betting_lines(lines_df)
        # Filter lines to only games in the current week to avoid unnecessary data
        week_game_ids = week_features_df["id"].unique()
        lines_for_week = lines_df[lines_df["game_id"].isin(week_game_ids)]
        week_features_df = week_features_df.merge(
            lines_for_week, left_on=["id"], right_on=["game_id"], how="left"
        )

    return week_features_df


def generate_predictions(model, X: pd.DataFrame) -> pd.Series:  # noqa: N803
    return pd.Series(model.predict(X), index=X.index)


def apply_betting_policy(predictions_df: pd.DataFrame) -> pd.DataFrame:
    """Apply MVP betting policy to predictions and lines.

    Requires columns:
    - predicted_spread, predicted_total
    - spread_line, total_line
    - home_games_played, away_games_played

    Spread convention: negative spread means home team is favored
    e.g., -7.0 means home favored by 7 points
    """
    spread_edge_threshold = 3.5
    total_edge_threshold = 7.5
    min_games_played = 4

    df = predictions_df.copy()

    # Convert spread line to expected home margin for proper comparison
    # If spread is -7.0 (home favored by 7), expected margin is +7.0
    df["expected_home_margin"] = -df["home_team_spread_line"]

    # Calculate edge as difference between model prediction and expected margin
    df["edge_spread"] = (df["predicted_spread"] - df["expected_home_margin"]).abs()
    df["edge_total"] = (df["predicted_total"] - df["total_line"]).abs()

    eligible = (df.get("home_games_played", 0) >= min_games_played) & (
        df.get("away_games_played", 0) >= min_games_played
    )

    df["bet_spread"] = "none"
    mask_spread = eligible & (df["edge_spread"] >= spread_edge_threshold)
    # Bet home if model predicts higher margin than expected, away if lower
    df.loc[mask_spread, "bet_spread"] = np.where(
        df.loc[mask_spread, "predicted_spread"]
        > df.loc[mask_spread, "expected_home_margin"],
        "home",
        "away",
    )

    df["bet_total"] = "none"
    mask_total = eligible & (df["edge_total"] >= total_edge_threshold)
    df.loc[mask_total, "bet_total"] = np.where(
        df.loc[mask_total, "predicted_total"] > df.loc[mask_total, "total_line"],
        "over",
        "under",
    )

    return df


def generate_csv_report(predictions_df: pd.DataFrame, output_path: str) -> None:
    """Write the weekly CSV report using the standardized columns."""
    cols = [
        "season",
        "week",
        "id",
        "start_date",
        "home_team",
        "away_team",
        "neutral_site",
        "provider",
        "home_team_spread_line",
        "total_line",
        "predicted_spread",
        "predicted_total",
        "edge_spread",
        "edge_total",
        "bet_spread",
        "bet_total",
        "home_games_played",
        "away_games_played",
    ]
    report_df = predictions_df.loc[
        :, [c for c in cols if c in predictions_df.columns]
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
    if "sportsbook" not in report_df.columns:
        report_df["sportsbook"] = "consensus"
    report_df["bet_units"] = 1

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    report_df.to_csv(output_path, index=False)
    print(f"Weekly betting report saved to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate weekly CFB betting recommendations (clean)."
    )
    parser.add_argument(
        "--year", type=int, required=True, help="Season year for predictions"
    )
    parser.add_argument(
        "--week", type=int, required=True, help="Week number for predictions"
    )
    parser.add_argument(
        "--data-root",
        type=str,
        default=None,
        help="Absolute path to the data root directory",
    )
    parser.add_argument(
        "--model-dir",
        type=str,
        default="./models/ridge_baseline",
        help="Directory with trained models",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./reports",
        help="Directory to save the weekly report",
    )
    args = parser.parse_args()

    try:
        print(f"Loading models for year {args.year}...")
        spread_model, total_model = load_models(args.year, args.model_dir)

        print(f"Loading dataset for year {args.year}, week {args.week}...")
        df = load_week_dataset(args.year, args.week, args.data_root)
        print(
            f"Loaded {len(df)} games for week {args.week} with columns: {sorted(df.columns)[:8]} ..."
        )

        # Build feature list similar to training
        feature_list = build_feature_list(df)
        print(f"Using {len(feature_list)} features")
        if not feature_list:
            print("No usable features found in dataset. Exiting.")
            sys.exit(0)

        # Drop rows missing any required feature columns
        df_clean = df.dropna(subset=feature_list)
        if df_clean.empty:
            print("No games with complete feature data this week.")
            sys.exit(0)

        X = df_clean[feature_list]
        print("Generating spread predictions...")
        df_clean["predicted_spread"] = generate_predictions(spread_model, X)
        print("Generating total predictions...")
        df_clean["predicted_total"] = generate_predictions(total_model, X)

        print("Applying betting policy...")
        final_df = apply_betting_policy(df_clean)

        output_path = os.path.join(
            args.output_dir, str(args.year), f"CFB_week{args.week}_bets.csv"
        )
        print("Writing CSV report...")
        generate_csv_report(final_df, output_path)
        print("Done.")

    except Exception as e:
        print(
            f"Error during weekly bet generation for year {args.year}, week {args.week}: {e}"
        )
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
