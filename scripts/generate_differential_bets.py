"""Generate weekly ATS recommendations using differential feature models."""

from __future__ import annotations

import argparse
import os
import sys

import joblib
import numpy as np
import pandas as pd

from cfb_model.config import get_data_root
from cfb_model.data.storage.local_storage import LocalStorage
from cfb_model.models.features import (
    build_differential_feature_list,
    build_differential_features,
)


def load_ensemble_models(model_year: int, model_dir: str) -> dict[str, list]:
    """Load all models for a given year, grouped by target."""
    ensemble_dir = os.path.join(model_dir, str(model_year))
    if not os.path.isdir(ensemble_dir):
        raise FileNotFoundError(f"Model directory not found: {ensemble_dir}")

    models = {"spread": [], "total": []}
    for file_name in os.listdir(ensemble_dir):
        if file_name.endswith(".joblib"):
            model_path = os.path.join(ensemble_dir, file_name)
            model = joblib.load(model_path)
            name_lower = file_name.lower()
            if name_lower.startswith("spread_"):
                models["spread"].append(model)
            elif name_lower.startswith("total_"):
                models["total"].append(model)

    if not models["spread"]:
        raise FileNotFoundError(f"No spread models found in {ensemble_dir}")
    if not models["total"]:
        raise FileNotFoundError(f"No total models found in {ensemble_dir}")

    print(
        f"Loaded {len(models['spread'])} spread models and {len(models['total'])} total models."
    )
    return models


def _reduce_betting_lines(lines_df: pd.DataFrame) -> pd.DataFrame:
    if lines_df.empty:
        return lines_df
    df = lines_df.copy()
    if "provider" in df.columns:
        df["provider_rank"] = np.where(
            df["provider"].astype(str).str.lower() == "consensus", 0, 1
        )
    else:
        df["provider_rank"] = 1
    df = (
        df.sort_values(["game_id", "provider_rank"])
        .groupby("game_id", as_index=False)
        .first()
    )
    rename_map = {"over_under": "total_line", "spread": "home_team_spread_line"}
    for old, new in rename_map.items():
        if old in df.columns and new not in df.columns:
            df = df.rename(columns={old: new})
    return df


def load_week_dataset(
    year: int, week: int, data_root: str | None = None
) -> pd.DataFrame:
    resolved_root = data_root or get_data_root()
    processed = LocalStorage(
        data_root=resolved_root, file_format="csv", data_type="processed"
    )
    raw = LocalStorage(data_root=resolved_root, file_format="csv", data_type="raw")

    team_feature_records = processed.read_index(
        "team_week_adj", {"year": year, "week": week}
    )
    if not team_feature_records:
        raise ValueError(
            f"No cached weekly adjusted stats found for year {year}, week {week}"
        )

    team_features_df = pd.DataFrame.from_records(team_feature_records)

    all_game_records = raw.read_index("games", {"year": year})
    if not all_game_records:
        raise ValueError(f"No raw games found for year {year}")

    all_games_df = pd.DataFrame.from_records(all_game_records)
    week_games_df = all_games_df[all_games_df["week"] == week].copy()
    if week_games_df.empty:
        raise ValueError(
            f"No raw games found for year {year}, week {week} after filtering"
        )

    home_features = team_features_df.add_prefix("home_")
    away_features = team_features_df.add_prefix("away_")

    merged_df = week_games_df.merge(
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
    merged_df = merged_df.drop(columns=["home_season", "away_season"], errors="ignore")

    lines_records = raw.read_index("betting_lines", {"year": year})
    lines_df = (
        pd.DataFrame.from_records(lines_records) if lines_records else pd.DataFrame()
    )
    if not lines_df.empty:
        lines_df = _reduce_betting_lines(lines_df)
        week_game_ids = merged_df["id"].unique()
        lines_for_week = lines_df[lines_df["game_id"].isin(week_game_ids)]
        merged_df = merged_df.merge(
            lines_for_week, left_on=["id"], right_on=["game_id"], how="left"
        )

    if (
        "home_conference" in merged_df.columns
        and "away_conference" in merged_df.columns
    ):
        merged_df["same_conference"] = (
            merged_df["home_conference"].astype(str)
            == merged_df["away_conference"].astype(str)
        ).astype(int)
    elif "conference_game" in merged_df.columns:
        try:
            merged_df["same_conference"] = merged_df["conference_game"].astype(int)
        except Exception:
            merged_df["same_conference"] = 0
    else:
        merged_df["same_conference"] = 0

    return merged_df


def apply_betting_policy(
    predictions_df: pd.DataFrame,
    *,
    spread_edge_threshold: float = 5.0,
    total_edge_threshold: float = 5.5,
    min_games_played: int = 2,
) -> pd.DataFrame:
    df = predictions_df.copy()
    df["expected_home_margin"] = -df["home_team_spread_line"]
    df["edge_spread"] = (df["predicted_spread"] - df["expected_home_margin"]).abs()
    df["edge_total"] = (df["predicted_total"] - df["total_line"]).abs()

    df["spread_bet_reason"] = "Bet Placed"
    df["total_bet_reason"] = "Bet Placed"

    home_count = df.get("home_games_played", 0)
    away_count = df.get("away_games_played", 0)
    ineligible_games = (home_count < min_games_played) | (away_count < min_games_played)
    df.loc[ineligible_games, ["spread_bet_reason", "total_bet_reason"]] = (
        "No Bet - Min Games"
    )

    eligible_mask = ~ineligible_games

    small_edge_spread = df["edge_spread"] < spread_edge_threshold
    df.loc[eligible_mask & small_edge_spread, "spread_bet_reason"] = (
        "No Bet - Small Edge"
    )

    small_edge_total = df["edge_total"] < total_edge_threshold
    df.loc[eligible_mask & small_edge_total, "total_bet_reason"] = "No Bet - Small Edge"

    df["bet_spread"] = "none"
    spread_bet_mask = df["spread_bet_reason"] == "Bet Placed"
    df.loc[spread_bet_mask, "bet_spread"] = np.where(
        df.loc[spread_bet_mask, "predicted_spread"]
        > df.loc[spread_bet_mask, "expected_home_margin"],
        "home",
        "away",
    )

    df["bet_total"] = "none"
    total_bet_mask = df["total_bet_reason"] == "Bet Placed"
    df.loc[total_bet_mask, "bet_total"] = np.where(
        df.loc[total_bet_mask, "predicted_total"]
        > df.loc[total_bet_mask, "total_line"],
        "over",
        "under",
    )

    return df


def generate_csv_report(predictions_df: pd.DataFrame, output_path: str) -> None:
    report_df = predictions_df.copy()
    report_df["game_date_dt"] = pd.to_datetime(report_df["start_date"])
    report_df["Year"] = report_df["season"]
    report_df["Week"] = report_df["week"]
    report_df["Date"] = report_df["game_date_dt"].dt.strftime("%Y-%m-%d")
    report_df["Time"] = report_df["game_date_dt"].dt.strftime("%H:%M:%S")
    report_df["Game"] = report_df["away_team"] + " @ " + report_df["home_team"]
    report_df["game_id"] = report_df["id"]

    report_df["Spread"] = report_df.apply(
        lambda row: f"{row['home_team']} {row['home_team_spread_line']:+.1f}"
        if pd.notna(row["home_team_spread_line"])
        else "",
        axis=1,
    )

    report_df["Over/Under"] = report_df["total_line"]
    report_df["Spread Prediction"] = report_df["predicted_spread"]
    report_df["Total Prediction"] = report_df["predicted_total"]
    report_df["Spread Bet"] = report_df["bet_spread"]
    report_df["Total Bet"] = report_df["bet_total"]

    final_cols = [
        "game_id",
        "Year",
        "Week",
        "Date",
        "Time",
        "Game",
        "home_team",
        "away_team",
        "Spread",
        "home_team_spread_line",
        "Over/Under",
        "total_line",
        "Spread Prediction",
        "Total Prediction",
        "edge_spread",
        "edge_total",
        "Spread Bet",
        "spread_bet_reason",
        "Total Bet",
        "total_bet_reason",
    ]
    final_report_df = report_df[[col for col in final_cols if col in report_df.columns]]

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    final_report_df.to_csv(output_path, index=False)
    print(f"Weekly betting report saved to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate weekly CFB betting recommendations using differential models."
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
        default="./models/differential",
        help="Directory with trained differential models",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./reports/differential",
        help="Directory to save the weekly report",
    )
    parser.add_argument(
        "--spread-threshold",
        type=float,
        default=6.0,
        help="Edge threshold for spread bets",
    )
    parser.add_argument(
        "--total-threshold",
        type=float,
        default=6.0,
        help="Edge threshold for totals bets",
    )
    args = parser.parse_args()

    try:
        print(f"Loading differential ensemble models for year {args.year}...")
        models = load_ensemble_models(args.year, args.model_dir)

        print(f"Loading dataset for year {args.year}, week {args.week}...")
        df = load_week_dataset(args.year, args.week, args.data_root)

        print("Building differential features...")
        df = build_differential_features(df)

        feature_list = build_differential_feature_list(df)
        print(f"Using {len(feature_list)} differential features")
        if not feature_list:
            print("No usable features found. Exiting.")
            sys.exit(0)

        df_clean = df.dropna(subset=feature_list)
        if df_clean.empty:
            print("No games with complete feature data this week.")
            sys.exit(0)

        x = df_clean[feature_list].astype("float64")

        print("Generating ensemble predictions...")
        spread_predictions = []
        for m in models["spread"]:
            spread_predictions.append(pd.Series(m.predict(x), index=df_clean.index))
        df_clean["predicted_spread"] = np.mean(spread_predictions, axis=0)

        total_predictions = []
        for m in models["total"]:
            total_predictions.append(pd.Series(m.predict(x), index=df_clean.index))
        df_clean["predicted_total"] = np.mean(total_predictions, axis=0)

        print("Applying betting policy...")
        final_df = apply_betting_policy(
            df_clean,
            spread_edge_threshold=args.spread_threshold,
            total_edge_threshold=args.total_threshold,
            min_games_played=4,  # Using a reasonable default
        )

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
