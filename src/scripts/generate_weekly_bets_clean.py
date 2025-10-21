"""Generate weekly ATS recommendations using either legacy ensembles or points-for models."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from src.config import (
    PREDICTIONS_SUBDIR,
    REPORTS_DIR,
    get_data_root,
)
from src.models.betting import apply_betting_policy
from src.models.features import (
    build_differential_feature_list,
    build_differential_features,
    build_feature_list,
)
from src.utils.local_storage import LocalStorage

POINTS_FOR_HOME_MODEL_NAME = "points_for_home.joblib"
POINTS_FOR_AWAY_MODEL_NAME = "points_for_away.joblib"


def load_points_for_models(model_year: int, model_dir: str) -> tuple:
    """Load points-for models for home and away scoring predictions."""

    base_path = Path(model_dir) / str(model_year)
    home_path = base_path / POINTS_FOR_HOME_MODEL_NAME
    away_path = base_path / POINTS_FOR_AWAY_MODEL_NAME

    if not home_path.is_file():
        raise FileNotFoundError(
            f"Points-for home model not found at {home_path}. Train and save the model before running predictions."
        )
    if not away_path.is_file():
        raise FileNotFoundError(
            f"Points-for away model not found at {away_path}. Train and save the model before running predictions."
        )

    return joblib.load(home_path), joblib.load(away_path)


def _prepare_feature_matrix(df: pd.DataFrame, model, prefix: str) -> pd.DataFrame:
    feature_names = list(getattr(model, "feature_names_in_", []))
    if not feature_names:
        feature_names = [col for col in df.columns if col.startswith(f"{prefix}adj_")]
        games_col = f"{prefix}games_played"
        if games_col in df.columns:
            feature_names.append(games_col)
    if not feature_names:
        raise ValueError(
            f"No features found for prefix '{prefix}'. Ensure weekly caches include opponent-adjusted columns."
        )
    matrix = df.reindex(columns=feature_names, fill_value=0.0).astype("float64")
    return matrix


def predict_with_points_for(
    df: pd.DataFrame,
    home_model,
    away_model,
    *,
    spread_std: float,
    total_std: float,
) -> pd.DataFrame:
    working_df = df.copy()
    x_home = _prepare_feature_matrix(working_df, home_model, "home_")
    x_away = _prepare_feature_matrix(working_df, away_model, "away_")

    preds_home = home_model.predict(x_home)
    preds_away = away_model.predict(x_away)

    working_df["predicted_home_points"] = preds_home
    working_df["predicted_away_points"] = preds_away
    working_df["predicted_spread"] = preds_home - preds_away
    working_df["predicted_total"] = preds_home + preds_away
    working_df["predicted_spread_std_dev"] = float(spread_std)
    working_df["predicted_total_std_dev"] = float(total_std)

    working_df = working_df.replace([np.inf, -np.inf], np.nan)
    working_df = working_df.dropna(subset=["predicted_spread", "predicted_total"])
    return working_df


def predict_with_legacy(models: dict[str, list], df: pd.DataFrame) -> pd.DataFrame:
    spread_feature_list = build_feature_list(df)
    df_spread_predict = df.dropna(subset=spread_feature_list).copy()

    spread_predictions = []
    if not df_spread_predict.empty:
        for m in models["spread"]:
            required_features = (
                list(getattr(m, "feature_names_in_", [])) or spread_feature_list
            )
            x_model = df_spread_predict.reindex(
                columns=required_features, fill_value=0.0
            ).astype("float64")
            spread_predictions.append(
                pd.Series(m.predict(x_model), index=x_model.index)
            )

    if spread_predictions:
        df_spread_predict["predicted_spread"] = np.mean(spread_predictions, axis=0)
        df_spread_predict["predicted_spread_std_dev"] = np.std(
            spread_predictions, axis=0
        )
    else:
        df_spread_predict["predicted_spread"] = np.nan
        df_spread_predict["predicted_spread_std_dev"] = np.nan

    df_totals_predict = build_differential_features(df.copy())
    totals_feature_list = build_differential_feature_list(df_totals_predict)
    df_totals_predict = df_totals_predict.dropna(subset=totals_feature_list).copy()

    total_predictions = []
    if not df_totals_predict.empty:
        for m in models["total"]:
            required_features = (
                list(getattr(m, "feature_names_in_", [])) or totals_feature_list
            )
            x_model = df_totals_predict.reindex(
                columns=required_features, fill_value=0.0
            ).astype("float64")
            total_predictions.append(pd.Series(m.predict(x_model), index=x_model.index))

    if total_predictions:
        df_totals_predict["predicted_total"] = np.mean(total_predictions, axis=0)
        df_totals_predict["predicted_total_std_dev"] = np.std(total_predictions, axis=0)
    else:
        df_totals_predict["predicted_total"] = np.nan
        df_totals_predict["predicted_total_std_dev"] = np.nan

    final_df = df.copy()
    final_df = final_df.join(
        df_spread_predict[["predicted_spread", "predicted_spread_std_dev"]]
    )
    final_df = final_df.join(
        df_totals_predict[["predicted_total", "predicted_total_std_dev"]]
    )
    final_df = final_df.dropna(subset=["predicted_spread", "predicted_total"])
    return final_df


def load_hybrid_ensemble_models(
    model_year: int, spread_model_dir: str, total_model_dir: str
) -> dict[str, list]:
    """Load spread models from one dir and total models from another."""
    models = {"spread": [], "total": []}

    # Load Spread Models
    spread_dir = os.path.join(spread_model_dir, str(model_year))
    if not os.path.isdir(spread_dir):
        raise FileNotFoundError(f"Spread model directory not found: {spread_dir}")
    for file_name in os.listdir(spread_dir):
        if file_name.endswith(".joblib") and (
            file_name.startswith("spread_") or "spread" in file_name
        ):
            model_path = os.path.join(spread_dir, file_name)
            models["spread"].append(joblib.load(model_path))

    # Load Total Models
    total_dir = os.path.join(total_model_dir, str(model_year))
    if not os.path.isdir(total_dir):
        raise FileNotFoundError(f"Total model directory not found: {total_dir}")
    for file_name in os.listdir(total_dir):
        if file_name.endswith(".joblib") and file_name.startswith("total_"):
            model_path = os.path.join(total_dir, file_name)
            models["total"].append(joblib.load(model_path))

    if not models["spread"]:
        raise FileNotFoundError(f"No spread models found in {spread_dir}")
    if not models["total"]:
        raise FileNotFoundError(f"No total models found in {total_dir}")

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
    if "id" not in week_games_df.columns:
        raise ValueError("Games dataset missing game identifier column 'id'.")

    # Keep the latest snapshot per game (prefer completed rows over interim ingests).
    sort_cols: list[str] = []
    if "completed" in week_games_df.columns:
        sort_cols.append("completed")
    if "start_date" in week_games_df.columns:
        sort_cols.append("start_date")
    if sort_cols:
        week_games_df = week_games_df.sort_values(sort_cols)
    week_games_df = week_games_df.drop_duplicates(subset=["id"], keep="last")

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

    lines_records = raw.read_index("betting_lines", {"year": year, "week": week})
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

    # Normalize duplicated merge columns so downstream code can rely on canonical names.
    if "week" not in merged_df.columns:
        if "week_x" in merged_df.columns:
            merged_df["week"] = merged_df["week_x"]
        elif "week_y" in merged_df.columns:
            merged_df["week"] = merged_df["week_y"]
    if "year" not in merged_df.columns:
        if "year_x" in merged_df.columns:
            merged_df["year"] = merged_df["year_x"]
        elif "year_y" in merged_df.columns:
            merged_df["year"] = merged_df["year_y"]
    merged_df = merged_df.drop(
        columns=["week_x", "week_y", "year_x", "year_y"], errors="ignore"
    )

    return merged_df


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
        "home_moneyline",
        "away_moneyline",
        "Spread Prediction",
        "Total Prediction",
        "predicted_spread_std_dev",
        "predicted_total_std_dev",
        "edge_spread",
        "edge_total",
        "Spread Bet",
        "bet_units_spread",
        "spread_bet_reason",
        "Total Bet",
        "bet_units_total",
        "total_bet_reason",
    ]
    final_report_df = report_df[[col for col in final_cols if col in report_df.columns]]
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    final_report_df.to_csv(output_path, index=False)
    print(f"Weekly betting report saved to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate weekly CFB betting recommendations using a hybrid model strategy."
    )
    parser.add_argument(
        "--year", type=int, required=True, help="Season year for predictions"
    )
    parser.add_argument(
        "--week", type=int, required=True, help="Week number for predictions"
    )
    parser.add_argument(
        "--model-year",
        type=int,
        default=None,
        help="Year of the trained models to use (defaults to the prediction year)",
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
        default="./models",
        help="Directory with trained models",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(REPORTS_DIR),
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
    parser.add_argument(
        "--spread-std-dev-threshold",
        type=float,
        default=2.0,
        help="Std dev threshold for spread bets",
    )
    parser.add_argument(
        "--total-std-dev-threshold",
        type=float,
        default=1.5,
        help="Std dev threshold for total bets",
    )
    parser.add_argument(
        "--prediction-mode",
        choices=["legacy", "points_for"],
        default="legacy",
        help="Which prediction workflow to run (default: legacy ensemble)",
    )
    parser.add_argument(
        "--points-for-spread-std",
        type=float,
        default=18.0,
        help="Assumed spread prediction std-dev for points-for mode",
    )
    parser.add_argument(
        "--points-for-total-std",
        type=float,
        default=17.0,
        help="Assumed total prediction std-dev for points-for mode",
    )

    args = parser.parse_args()
    model_year = args.model_year or args.year

    try:
        print(f"Loading dataset for year {args.year}, week {args.week}...")
        df = load_week_dataset(args.year, args.week, args.data_root)
        if args.prediction_mode == "legacy":
            print(f"Loading hybrid ensemble models for year {model_year}...")
            models = load_hybrid_ensemble_models(
                model_year, args.model_dir, args.model_dir
            )
            final_df = predict_with_legacy(models, df)
            spread_std_threshold = args.spread_std_dev_threshold
            total_std_threshold = args.total_std_dev_threshold
        else:
            print(f"Loading points-for models for year {model_year}...")
            home_model, away_model = load_points_for_models(model_year, args.model_dir)
            final_df = predict_with_points_for(
                df,
                home_model,
                away_model,
                spread_std=args.points_for_spread_std,
                total_std=args.points_for_total_std,
            )
            spread_std_threshold = None
            total_std_threshold = None

        if final_df.empty:
            print("No games with complete predictions. Exiting.")
            year_root = os.path.join(args.output_dir, str(args.year))
            predictions_dir = os.path.join(year_root, PREDICTIONS_SUBDIR)
            os.makedirs(predictions_dir, exist_ok=True)
            output_path = os.path.join(predictions_dir, f"CFB_week{args.week}_bets.csv")
            # Write empty df to avoid breaking downstream scoring script
            generate_csv_report(pd.DataFrame(columns=df.columns), output_path)

            sys.exit(0)

        print("Applying betting policy...")
        final_df = apply_betting_policy(
            final_df,
            spread_edge_threshold=args.spread_threshold,
            total_edge_threshold=args.total_threshold,
            spread_std_dev_threshold=spread_std_threshold,
            total_std_dev_threshold=total_std_threshold,
            min_games_played=4,
        )

        year_root = os.path.join(args.output_dir, str(args.year))
        predictions_dir = os.path.join(year_root, PREDICTIONS_SUBDIR)
        os.makedirs(predictions_dir, exist_ok=True)

        output_path = os.path.join(predictions_dir, f"CFB_week{args.week}_bets.csv")
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
