"""Generate weekly ATS recommendations using trained models and betting policy (clean)."""

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
    build_feature_list,
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
            if file_name.startswith("spread_"):
                models["spread"].append(model)
            elif file_name.startswith("total_"):
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
    """Load per-game features for a specific week from the cache and merge betting lines."""
    resolved_root = data_root or get_data_root()
    processed = LocalStorage(
        data_root=resolved_root, file_format="csv", data_type="processed"
    )
    raw = LocalStorage(data_root=resolved_root, file_format="csv", data_type="raw")

    # 1. Load pre-calculated features from the cache
    team_feature_records = processed.read_index(
        "team_week_adj", {"year": year, "week": week}
    )
    if not team_feature_records:
        raise ValueError(
            f"No cached weekly adjusted stats found for year {year}, week {week}"
        )

    team_features_df = pd.DataFrame.from_records(team_feature_records)

    # 2. Load raw games for the entire year and then filter by week
    all_game_records = raw.read_index("games", {"year": year})
    if not all_game_records:
        raise ValueError(f"No raw games found for year {year}")

    all_games_df = pd.DataFrame.from_records(all_game_records)
    week_games_df = all_games_df[all_games_df["week"] == week].copy()
    if week_games_df.empty:
        raise ValueError(
            f"No raw games found for year {year}, week {week} after filtering"
        )

    # 3. Merge features into the games DataFrame for home and away teams
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

    # 4. Load and merge betting lines for the week
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

    # Derive same_conference for spread feature parity with training
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


def generate_predictions(model, X: pd.DataFrame) -> pd.Series:  # noqa: N803
    return pd.Series(model.predict(X), index=X.index)


def apply_betting_policy(
    predictions_df: pd.DataFrame,
    *,
    spread_edge_threshold: float = 5.0,
    total_edge_threshold: float = 5.5,
    spread_std_dev_threshold: float | None = None,
    total_std_dev_threshold: float | None = None,
    min_games_played: int = 4,
) -> pd.DataFrame:
    """Apply MVP betting policy to predictions and lines."""
    df = predictions_df.copy()

    # Convert spread line to expected home margin for proper comparison
    df["expected_home_margin"] = -df["home_team_spread_line"]

    # Calculate edge as difference between model prediction and expected margin
    df["edge_spread"] = (df["predicted_spread"] - df["expected_home_margin"]).abs()
    df["edge_total"] = (df["predicted_total"] - df["total_line"]).abs()

    eligible = (df.get("home_games_played", 0) >= min_games_played) & (
        df.get("away_games_played", 0) >= min_games_played
    )

    # Confidence filter (low standard deviation among models)
    if spread_std_dev_threshold is not None:
        eligible &= df["predicted_spread_std_dev"] <= spread_std_dev_threshold
    if total_std_dev_threshold is not None:
        eligible &= df["predicted_total_std_dev"] <= total_std_dev_threshold

    df["bet_spread"] = "none"
    mask_spread = eligible & (df["edge_spread"] >= spread_edge_threshold)
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
        "spread_reason_1",
        "spread_reason_2",
        "spread_reason_3",
        "total_reason_1",
        "total_reason_2",
        "total_reason_3",
        "predicted_spread_std_dev",
        "predicted_total_std_dev",
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
        default="./models",
        help="Directory with trained models",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./reports",
        help="Directory to save the weekly report",
    )
    parser.add_argument(
        "--spread-threshold",
        type=float,
        default=6.0,
        help="Edge threshold (in points) for spread bets (default: 6.0)",
    )
    parser.add_argument(
        "--total-threshold",
        type=float,
        default=6.0,
        help="Edge threshold (in points) for totals bets (default: 6.0)",
    )
    parser.add_argument(
        "--spread-std-dev-threshold",
        type=float,
        default=None,
        help="Standard deviation threshold for spread bets",
    )
    parser.add_argument(
        "--total-std-dev-threshold",
        type=float,
        default=None,
        help="Standard deviation threshold for total bets",
    )
    args = parser.parse_args()

    try:
        print(f"Loading ensemble models for year {args.year}...")
        models = load_ensemble_models(args.year, args.model_dir)

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

        x = df_clean[feature_list].astype("float64")

        # --- Ensemble Prediction ---
        print("Generating ensemble predictions...")
        spread_predictions = [generate_predictions(m, x) for m in models["spread"]]
        df_clean["predicted_spread"] = np.mean(spread_predictions, axis=0)
        df_clean["predicted_spread_std_dev"] = np.std(spread_predictions, axis=0)

        total_predictions = [generate_predictions(m, x) for m in models["total"]]
        df_clean["predicted_total"] = np.mean(total_predictions, axis=0)
        df_clean["predicted_total_std_dev"] = np.std(total_predictions, axis=0)

        print("Generating SHAP explanations...")
        import shap

        # Use the first model in each ensemble for SHAP explanations as a representative
        spread_explainer = shap.Explainer(models["spread"][0], x)
        spread_shap_values = spread_explainer(x).values
        spread_shap_df = (
            pd.DataFrame(spread_shap_values, columns=x.columns, index=x.index)
            .apply(pd.to_numeric, errors="coerce")
            .fillna(0.0)
        )

        top_spread_features = []
        for index, row in spread_shap_df.iterrows():
            top_features = row.abs().nlargest(3).index
            reasons = [f"{feat}: {row[feat]:+.2f}" for feat in top_features]
            top_spread_features.append(reasons)

        spread_reasons_df = pd.DataFrame(
            top_spread_features,
            index=df_clean.index,
            columns=["spread_reason_1", "spread_reason_2", "spread_reason_3"],
        )
        df_clean = df_clean.join(spread_reasons_df)

        total_explainer = shap.Explainer(models["total"][0], x)
        total_shap_values = total_explainer(x).values
        total_shap_df = (
            pd.DataFrame(total_shap_values, columns=x.columns, index=x.index)
            .apply(pd.to_numeric, errors="coerce")
            .fillna(0.0)
        )

        top_total_features = []
        for index, row in total_shap_df.iterrows():
            top_features = row.abs().nlargest(3).index
            reasons = [f"{feat}: {row[feat]:+.2f}" for feat in top_features]
            top_total_features.append(reasons)

        total_reasons_df = pd.DataFrame(
            top_total_features,
            index=df_clean.index,
            columns=["total_reason_1", "total_reason_2", "total_reason_3"],
        )
        df_clean = df_clean.join(total_reasons_df)

        print("Applying betting policy...")
        final_df = apply_betting_policy(
            df_clean,
            spread_edge_threshold=args.spread_threshold,
            total_edge_threshold=args.total_threshold,
            spread_std_dev_threshold=args.spread_std_dev_threshold,
            total_std_dev_threshold=args.total_std_dev_threshold,
            min_games_played=4,
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
