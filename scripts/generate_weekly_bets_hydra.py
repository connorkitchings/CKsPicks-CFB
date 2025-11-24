"""Generate weekly ATS recommendations using either legacy ensembles or points-for models."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import hydra
import joblib
import numpy as np
import pandas as pd
from omegaconf import DictConfig

from scripts.model_registry import get_production_model
from src.config import PREDICTIONS_SUBDIR, get_data_root
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


def load_models_from_registry(model_names: dict[str, list[str]]) -> dict[str, list]:
    """Load models from the MLflow Model Registry."""
    models = {}
    for model_type, model_name_list in model_names.items():
        models[model_type] = []
        for model_name in model_name_list:
            model = get_production_model(model_name)
            if model is None:
                raise ValueError(f"Could not load production model: {model_name}")
            models[model_type].append(model)
    return models


def predict_with_registered_models(
    models: dict[str, list], df: pd.DataFrame
) -> pd.DataFrame:
    """Generate predictions using models loaded from the MLflow Model Registry."""
    spread_feature_list = build_feature_list(df)
    df_spread_predict = df.dropna(subset=spread_feature_list).copy()

    spread_predictions = []
    if not df_spread_predict.empty:
        for m in models["spread"]:
            required_features = (
                list(getattr(m, "feature_names_in_", []))
                or list(getattr(m, "feature_names_", []))
                or spread_feature_list
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
                list(getattr(m, "feature_names_in_", []))
                or list(getattr(m, "feature_names_", []))
                or totals_feature_list
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


def predict_with_registered_points_for_models(
    models: dict[str, list], df: pd.DataFrame
) -> pd.DataFrame:
    """Generate predictions using points-for models loaded from the MLflow Model Registry."""
    # Prepare features for home models
    # Assuming all home models use the same features, check the first one
    home_model_0 = models["points_for_home"][0]
    home_features = list(getattr(home_model_0, "feature_names_in_", [])) or list(
        getattr(home_model_0, "feature_names_", [])
    )
    if not home_features:
        # Fallback to loading from config or assuming standard set if not in model
        # For now, let's assume models have feature names. If not, we might need to pass cfg.
        # But CatBoost usually saves them.
        # If missing, we can try to build from df columns matching pattern.
        home_features = [col for col in df.columns if col.startswith("home_adj_")]
        if "home_games_played" in df.columns:
            home_features.append("home_games_played")

    x_home = df.reindex(columns=home_features, fill_value=0.0).astype("float64")

    # Predict Home Points
    home_preds_list = []
    for m in models["points_for_home"]:
        home_preds_list.append(pd.Series(m.predict(x_home), index=x_home.index))

    avg_home_points = np.mean(home_preds_list, axis=0)
    std_home_points = np.std(home_preds_list, axis=0)

    # Prepare features for away models
    away_model_0 = models["points_for_away"][0]
    away_features = list(getattr(away_model_0, "feature_names_in_", [])) or list(
        getattr(away_model_0, "feature_names_", [])
    )
    if not away_features:
        away_features = [col for col in df.columns if col.startswith("away_adj_")]
        if "away_games_played" in df.columns:
            away_features.append("away_games_played")

    x_away = df.reindex(columns=away_features, fill_value=0.0).astype("float64")

    # Predict Away Points
    away_preds_list = []
    for m in models["points_for_away"]:
        away_preds_list.append(pd.Series(m.predict(x_away), index=x_away.index))

    avg_away_points = np.mean(away_preds_list, axis=0)
    std_away_points = np.std(away_preds_list, axis=0)

    # Derived Predictions
    working_df = df.copy()
    working_df["predicted_home_points"] = avg_home_points
    working_df["predicted_away_points"] = avg_away_points

    # Spread = Home - Away
    working_df["predicted_spread"] = avg_home_points - avg_away_points
    # Spread Std Dev = sqrt(HomeStd^2 + AwayStd^2) (assuming independence)
    working_df["predicted_spread_std_dev"] = np.sqrt(
        std_home_points**2 + std_away_points**2
    )

    # Total = Home + Away
    working_df["predicted_total"] = avg_home_points + avg_away_points
    # Total Std Dev = sqrt(HomeStd^2 + AwayStd^2)
    working_df["predicted_total_std_dev"] = np.sqrt(
        std_home_points**2 + std_away_points**2
    )

    working_df = working_df.replace([np.inf, -np.inf], np.nan)
    working_df = working_df.dropna(subset=["predicted_spread", "predicted_total"])
    return working_df


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


@hydra.main(config_path="../conf", config_name="config", version_base=None)
def main(cfg: DictConfig) -> None:
    model_year = cfg.weekly_bets.model_year or cfg.weekly_bets.year

    try:
        print(
            f"Loading dataset for year {cfg.weekly_bets.year}, week {cfg.weekly_bets.week}..."
        )
        df = load_week_dataset(
            cfg.weekly_bets.year,
            cfg.weekly_bets.week,
            cfg.paths.data_dir,
            adjustment_iteration=cfg.data.adjustment_iteration,
            adjustment_iteration_offense=cfg.data.adjustment_iteration_offense,
            adjustment_iteration_defense=cfg.data.adjustment_iteration_defense,
        )
        if cfg.weekly_bets.prediction_mode == "legacy":
            print("Loading models from MLflow Model Registry...")
            model_names = {
                "spread": cfg.weekly_bets.model_registry.spread_models,
                "total": cfg.weekly_bets.model_registry.total_models,
            }
            models = load_models_from_registry(model_names)
            final_df = predict_with_registered_models(models, df)
            spread_std_threshold = cfg.weekly_bets.betting.spread_std_dev_threshold
            total_std_threshold = cfg.weekly_bets.betting.total_std_dev_threshold
        elif cfg.weekly_bets.prediction_mode == "points_for_registry":
            print("Loading points-for models from MLflow Model Registry...")
            model_names = {
                "points_for_home": cfg.weekly_bets.model_registry.points_for_home_models,
                "points_for_away": cfg.weekly_bets.model_registry.points_for_away_models,
            }
            models = load_models_from_registry(model_names)
            final_df = predict_with_registered_points_for_models(models, df)
            spread_std_threshold = cfg.weekly_bets.betting.spread_std_dev_threshold
            total_std_threshold = cfg.weekly_bets.betting.total_std_dev_threshold
        else:
            print(f"Loading points-for models for year {model_year}...")
            home_model, away_model = load_points_for_models(
                model_year, cfg.weekly_bets.model_dir
            )
            stats = load_points_for_stats(model_year, cfg.weekly_bets.model_dir)
            if stats is None:
                print(
                    "Warning: points-for stats not found; falling back to CLI standard deviations."
                )
            final_df = predict_with_points_for(
                df,
                home_model,
                away_model,
                spread_std=cfg.weekly_bets.points_for.spread_std,
                total_std=cfg.weekly_bets.points_for.total_std,
                stats=stats,
            )
            spread_std_threshold = None
            total_std_threshold = None

        if final_df.empty:
            print("No games with complete predictions. Exiting.")
            year_root = os.path.join(
                cfg.weekly_bets.output_dir, str(cfg.weekly_bets.year)
            )
            predictions_dir = os.path.join(year_root, PREDICTIONS_SUBDIR)
            os.makedirs(predictions_dir, exist_ok=True)
            output_path = os.path.join(
                predictions_dir, f"CFB_week{cfg.weekly_bets.week}_bets.csv"
            )
            # Write empty df to avoid breaking downstream scoring script
            generate_csv_report(pd.DataFrame(columns=df.columns), output_path)

            sys.exit(0)

        print("Applying betting policy...")
        final_df = apply_betting_policy(
            final_df,
            spread_edge_threshold=cfg.weekly_bets.betting.spread_threshold,
            total_edge_threshold=cfg.weekly_bets.betting.total_threshold,
            spread_std_dev_threshold=spread_std_threshold,
            total_std_dev_threshold=total_std_threshold,
            min_games_played=4,
            bankroll=cfg.weekly_bets.bankroll,
            max_weekly_exposure_fraction=cfg.weekly_bets.max_weekly_exposure_fraction,
            max_weekly_bets=cfg.weekly_bets.max_weekly_bets,
            single_bet_cap=cfg.weekly_bets.max_single_bet_fraction,
        )

        year_root = os.path.join(cfg.weekly_bets.output_dir, str(cfg.weekly_bets.year))
        predictions_dir = os.path.join(year_root, PREDICTIONS_SUBDIR)
        os.makedirs(predictions_dir, exist_ok=True)

        output_path = os.path.join(
            predictions_dir, f"CFB_week{cfg.weekly_bets.week}_bets.csv"
        )
        print("Writing CSV report...")
        generate_csv_report(final_df, output_path)

        print("Done.")

    except Exception as e:
        print(
            f"Error during weekly bet generation for year {cfg.weekly_bets.year}, week {cfg.weekly_bets.week}: {e}"
        )
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
