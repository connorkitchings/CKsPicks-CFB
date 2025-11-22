"""Generate weekly ATS recommendations using either legacy ensembles or points-for models."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from src.config import MODELS_DIR, PREDICTIONS_SUBDIR, REPORTS_DIR, get_data_root
from src.models.betting import apply_betting_policy
from src.models.features import (
    build_differential_feature_list,
    build_differential_features,
    build_feature_list,
    load_weekly_team_features,
)
from src.utils.local_storage import LocalStorage

POINTS_FOR_HOME_MODEL_NAME = "points_for_home.joblib"
POINTS_FOR_AWAY_MODEL_NAME = "points_for_away.joblib"


def _placed_mask(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series([False] * len(df), index=df.index, dtype=bool)
    return df[column] == "Bet Placed"


def build_week_metadata(
    df: pd.DataFrame,
    *,
    year: int,
    week: int,
    model_year: int,
    prediction_mode: str,
    bankroll: float,
    data_root: str,
    model_dir: str,
    output_path: str,
    spread_threshold: float,
    total_threshold: float,
    spread_std_dev_threshold: float | None,
    total_std_dev_threshold: float | None,
    max_single_bet_fraction: float,
    max_weekly_exposure_fraction: float,
    max_weekly_bets: int,
) -> dict:
    spread_mask = _placed_mask(df, "spread_bet_reason")
    total_mask = _placed_mask(df, "total_bet_reason")
    spread_units = (
        float(df.loc[spread_mask, "bet_units_spread"].sum())
        if "bet_units_spread" in df.columns
        else 0.0
    )
    total_units = (
        float(df.loc[total_mask, "bet_units_total"].sum())
        if "bet_units_total" in df.columns
        else 0.0
    )
    spread_fraction = (
        float(df.loc[spread_mask, "kelly_fraction_spread"].sum())
        if "kelly_fraction_spread" in df.columns
        else 0.0
    )
    total_fraction = (
        float(df.loc[total_mask, "kelly_fraction_total"].sum())
        if "kelly_fraction_total" in df.columns
        else 0.0
    )
    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "year": year,
        "week": week,
        "model_year": model_year,
        "prediction_mode": prediction_mode,
        "paths": {
            "data_root": data_root,
            "model_dir": model_dir,
            "report_path": output_path,
        },
        "bankroll": bankroll,
        "betting_thresholds": {
            "spread_edge": spread_threshold,
            "total_edge": total_threshold,
            "spread_std_dev": spread_std_dev_threshold,
            "total_std_dev": total_std_dev_threshold,
        },
        "risk_limits": {
            "max_single_bet_fraction": max_single_bet_fraction,
            "max_weekly_exposure_fraction": max_weekly_exposure_fraction,
            "max_weekly_bets": max_weekly_bets,
        },
        "portfolio": {
            "spread_bets": int(spread_mask.sum()),
            "total_bets": int(total_mask.sum()),
            "spread_units": spread_units,
            "total_units": total_units,
            "weekly_exposure_fraction": spread_fraction + total_fraction,
        },
    }
    return metadata


def write_metadata(path: str, payload: dict) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)


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


def load_points_for_stats(model_year: int, model_dir: str) -> dict | None:
    stats_path = Path(model_dir) / str(model_year) / "points_for_stats.json"
    if not stats_path.is_file():
        return None
    try:
        with stats_path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        print(f"Warning: unable to parse points-for stats file {stats_path}: {exc}")
        return None


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
    matrix = (
        df.reindex(columns=feature_names, fill_value=0.0).fillna(0.0).astype("float64")
    )
    return matrix


def predict_with_points_for(
    df: pd.DataFrame,
    home_model,
    away_model,
    *,
    spread_std: float,
    total_std: float,
    stats: dict | None = None,
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
    default_spread_std = float(spread_std)
    default_total_std = float(total_std)
    working_df["predicted_spread_std_dev"] = default_spread_std
    working_df["predicted_total_std_dev"] = default_total_std

    if stats:
        spread_stat = stats.get("spread_points", {}).get("std")
        total_stat = stats.get("total_points", {}).get("std")
        if isinstance(spread_stat, (int, float)) and not np.isnan(spread_stat):
            working_df["predicted_spread_std_dev"] = float(spread_stat)
        if isinstance(total_stat, (int, float)) and not np.isnan(total_stat):
            working_df["predicted_total_std_dev"] = float(total_stat)

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
    year: int,
    week: int,
    data_root: str | None = None,
    *,
    adjustment_iteration: int | None = 4,
    adjustment_iteration_offense: int | None = None,
    adjustment_iteration_defense: int | None = None,
) -> pd.DataFrame:
    resolved_root = data_root or get_data_root()
    raw = LocalStorage(data_root=resolved_root, file_format="csv", data_type="raw")

    team_features_df = load_weekly_team_features(
        year,
        week,
        resolved_root,
        adjustment_iteration=adjustment_iteration,
        adjustment_iteration_offense=adjustment_iteration_offense,
        adjustment_iteration_defense=adjustment_iteration_defense,
    )
    if team_features_df is None:
        raise ValueError(
            f"No cached weekly adjusted stats found for year {year}, week {week}"
        )

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

    # Enhanced FCS opponent filtering: exclude games where either team is FCS
    if (
        "home_classification" in merged_df.columns
        and "away_classification" in merged_df.columns
    ):
        # Convert to lowercase for consistent comparison
        merged_df["home_classification"] = (
            merged_df["home_classification"].astype(str).str.lower()
        )
        merged_df["away_classification"] = (
            merged_df["away_classification"].astype(str).str.lower()
        )

        # Filter out games where either team is FCS
        fbs_mask = (merged_df["home_classification"] == "fbs") & (
            merged_df["away_classification"] == "fbs"
        )
        original_count = len(merged_df)

        # Log specific games that would be filtered for debugging
        non_fbs_games = merged_df[~fbs_mask].copy()
        if not non_fbs_games.empty:
            print("Games with non-FBS opponents (will be filtered):")
            for _, row in non_fbs_games.iterrows():
                home_class = row.get("home_classification", "unknown")
                away_class = row.get("away_classification", "unknown")
                print(
                    f"  - {row['away_team']} @ {row['home_team']}: {home_class} vs {away_class}"
                )
            # Also validate that we're not filtering legitimate FBS games
            fbs_games = merged_df[fbs_mask].copy()
            if not fbs_games.empty:
                print(f"Confirmed FBS vs FBS games: {len(fbs_games)}")

        merged_df = merged_df[fbs_mask].copy()

        filtered_count = original_count - len(merged_df)
        if filtered_count > 0:
            print(
                f"Filtered out {filtered_count} games with FCS opponents. Remaining: {len(merged_df)} FBS vs FBS games."
            )
        else:
            print(f"All {len(merged_df)} games are FBS vs FBS matchups.")

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
        "predicted_home_points",
        "predicted_away_points",
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


def run_pipeline(args):
    model_year = args.model_year or args.year
    resolved_data_root = args.data_root or str(get_data_root())

    try:
        print(f"Loading dataset for year {args.year}, week {args.week}...")
        df = load_week_dataset(
            args.year,
            args.week,
            resolved_data_root,
            adjustment_iteration=args.adjustment_iteration,
            adjustment_iteration_offense=args.offense_adjustment_iteration,
            adjustment_iteration_defense=args.defense_adjustment_iteration,
        )
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
            stats = load_points_for_stats(model_year, args.model_dir)
            if stats is None:
                print(
                    "Warning: points-for stats not found; falling back to CLI standard deviations."
                )
            final_df = predict_with_points_for(
                df,
                home_model,
                away_model,
                spread_std=args.points_for_spread_std,
                total_std=args.points_for_total_std,
                stats=stats,
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

            metadata_path = os.path.join(
                predictions_dir, f"CFB_week{args.week}_bets_metadata.json"
            )
            metadata = build_week_metadata(
                pd.DataFrame(columns=df.columns),
                year=args.year,
                week=args.week,
                model_year=model_year,
                prediction_mode=args.prediction_mode,
                bankroll=args.bankroll,
                data_root=resolved_data_root,
                model_dir=args.model_dir,
                output_path=output_path,
                spread_threshold=args.spread_threshold,
                total_threshold=args.total_threshold,
                spread_std_dev_threshold=spread_std_threshold,
                total_std_dev_threshold=total_std_threshold,
                max_single_bet_fraction=args.max_single_bet_fraction,
                max_weekly_exposure_fraction=args.max_weekly_exposure_fraction,
                max_weekly_bets=args.max_weekly_bets,
            )
            write_metadata(metadata_path, metadata)

            sys.exit(0)

        print("Applying betting policy...")
        final_df = apply_betting_policy(
            final_df,
            spread_edge_threshold=args.spread_threshold,
            total_edge_threshold=args.total_threshold,
            spread_std_dev_threshold=spread_std_threshold,
            total_std_dev_threshold=total_std_threshold,
            min_games_played=4,
            bankroll=args.bankroll,
            max_weekly_exposure_fraction=args.max_weekly_exposure_fraction,
            max_weekly_bets=args.max_weekly_bets,
            single_bet_cap=args.max_single_bet_fraction,
        )

        year_root = os.path.join(args.output_dir, str(args.year))
        predictions_dir = os.path.join(year_root, PREDICTIONS_SUBDIR)
        os.makedirs(predictions_dir, exist_ok=True)

        output_path = os.path.join(predictions_dir, f"CFB_week{args.week}_bets.csv")
        print("Writing CSV report...")
        generate_csv_report(final_df, output_path)

        metadata_path = os.path.join(
            predictions_dir, f"CFB_week{args.week}_bets_metadata.json"
        )
        metadata = build_week_metadata(
            final_df,
            year=args.year,
            week=args.week,
            model_year=model_year,
            prediction_mode=args.prediction_mode,
            bankroll=args.bankroll,
            data_root=resolved_data_root,
            model_dir=args.model_dir,
            output_path=output_path,
            spread_threshold=args.spread_threshold,
            total_threshold=args.total_threshold,
            spread_std_dev_threshold=spread_std_threshold,
            total_std_dev_threshold=total_std_threshold,
            max_single_bet_fraction=args.max_single_bet_fraction,
            max_weekly_exposure_fraction=args.max_weekly_exposure_fraction,
            max_weekly_bets=args.max_weekly_bets,
        )
        write_metadata(metadata_path, metadata)

        print("Done.")

    except Exception as e:
        print(
            f"Error during weekly bet generation for year {args.year}, week {args.week}: {e}"
        )
        import traceback

        traceback.print_exc()
        sys.exit(1)


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
        default=str(MODELS_DIR),
        help="Directory with trained models",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(REPORTS_DIR),
        help="Directory to save the weekly report",
    )
    parser.add_argument(
        "--bankroll",
        type=float,
        required=True,
        help="Current bankroll used for bet sizing and exposure caps",
    )
    parser.add_argument(
        "--max-weekly-exposure-fraction",
        type=float,
        default=0.15,
        help="Maximum share of bankroll exposed in a single week (default 15%)",
    )
    parser.add_argument(
        "--max-single-bet-fraction",
        type=float,
        default=0.05,
        help="Maximum share of bankroll per bet (default 5%)",
    )
    parser.add_argument(
        "--max-weekly-bets",
        type=int,
        default=12,
        help="Maximum number of bets to place per week (default 12)",
    )
    parser.add_argument(
        "--spread-threshold",
        type=float,
        default=8.0,
        help="Edge threshold for spread bets. Recommended value is 8.0 based on 2024 off1_def3 backtest.",
    )
    parser.add_argument(
        "--total-threshold",
        type=float,
        default=8.0,
        help="Edge threshold for totals bets. Recommended value is 8.0 based on 2024 off1_def3 backtest.",
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
    parser.add_argument(
        "--adjustment-iteration",
        type=int,
        default=4,
        help=(
            "Opponent-adjustment iteration depth to read from the weekly cache "
            "(default: 4)."
        ),
    )
    parser.add_argument(
        "--offense-adjustment-iteration",
        type=int,
        default=None,
        help=(
            "Override the offensive feature adjustment depth. Defaults to the value "
            "passed to --adjustment-iteration."
        ),
    )
    parser.add_argument(
        "--defense-adjustment-iteration",
        type=int,
        default=None,
        help=(
            "Override the defensive feature adjustment depth. Defaults to the value "
            "passed to --adjustment-iteration."
        ),
    )

    args = parser.parse_args()
    run_pipeline(args)


if __name__ == "__main__":
    main()
