import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor

# Add project root to path
sys.path.append(os.getcwd())
# noqa: E402
from hydra import compose, initialize
from omegaconf import OmegaConf

from scripts.utils.model_registry import get_production_model
from src.features.selector import select_features
from src.models.features import load_point_in_time_data

DATA_ROOT = "/Volumes/CK SSD/Coding Projects/cfb_model/"
ADJUSTMENT_ITERATION = 2

# Feature config (standard_v1) - Must match training!
FEATURE_CONFIG = OmegaConf.create(
    {
        "features": {
            "name": "standard_v1",
            "groups": ["off_def_stats", "pace_stats", "recency_stats", "luck_stats"],
            "recency_window": "standard",
            "include_pace_interactions": False,
            "exclude": [],
        }
    }
)


def main():
    parser = argparse.ArgumentParser(description="Generate Stacked Bets")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    args = parser.parse_args()

    year = args.year
    week = args.week

    print(f"Generating Stacked Bets for {year} Week {week}...")

    # Load Config
    with initialize(version_base=None, config_path="../conf"):
        cfg = compose(
            config_name="config",
            overrides=[f"weekly_bets.year={year}", f"weekly_bets.week={week}"],
        )

    # 1. Load Data
    print("Loading feature data...")
    # include_betting_lines=True so we can calculate edges
    raw_df = load_point_in_time_data(
        year,
        week,
        DATA_ROOT,
        adjustment_iteration=ADJUSTMENT_ITERATION,
        include_betting_lines=True,
    )
    if raw_df is None:
        print("No data found.")
        return

    if "id" in raw_df.columns:
        raw_df["game_id"] = raw_df["id"]

    # 2. Load PPR Predictions (for features)
    ppr_path = f"artifacts/predictions/{year}/week_{week}_ratings_preds.csv"
    if not os.path.exists(ppr_path):
        print(f"PPR predictions not found at {ppr_path}")
        return

    print(f"Loading PPR predictions from {ppr_path}...")
    ppr_df = pd.read_csv(ppr_path)

    # Rename cols to match training expectation
    # Training expected: ppr_home_rating, ppr_away_rating, ppr_predicted_spread
    # PPR output has: home_rating, away_rating, pred_spread
    ppr_df = ppr_df.rename(
        columns={
            "home_rating": "ppr_home_rating",
            "away_rating": "ppr_away_rating",
            "pred_spread": "ppr_predicted_spread",
        }
    )

    # Drop duplicates to prevent row explosion
    if "game_id" in raw_df.columns:
        raw_df = raw_df.drop_duplicates(subset=["game_id"])

    ppr_df = ppr_df.drop_duplicates(subset=["game_id"])

    # Merge
    merged_df = raw_df.merge(
        ppr_df[
            ["game_id", "ppr_home_rating", "ppr_away_rating", "ppr_predicted_spread"]
        ],
        on="game_id",
        how="inner",
    )

    # 3. Predict Spread
    spread_model_type = cfg.get("spread_model_type", "stacked")
    print(f"Spread Model Type: {spread_model_type}")

    if spread_model_type == "points_for":
        # Load Home and Away Models
        home_model_name = cfg.spread_models[0]
        away_model_name = cfg.spread_models[1]

        print(f"Loading Home Model ({home_model_name})...")
        home_model = get_production_model(home_model_name)

        print(f"Loading Away Model ({away_model_name})...")
        away_model = get_production_model(away_model_name)

        if home_model is None or away_model is None:
            raise ValueError("Could not load Points-For models")

        # Features for Points-For (Standard)
        # Use cfg to allow feature config overrides (e.g. interaction_v1)
        x_pf = select_features(merged_df, cfg)

        # Align features to Home Model expectation

        # Align features to Home Model expectation
        expected_features = getattr(home_model, "feature_names_", None)
        if expected_features:
            # Check for missing features
            missing = set(expected_features) - set(x_pf.columns)
            if missing:
                print(f"Warning: Missing features for home model: {missing}")
                for col in missing:
                    x_pf[col] = np.nan

            # Reorder
            x_pf = x_pf[expected_features]

        # Predict
        print("Predicting Scores...")
        home_preds = home_model.predict(x_pf)
        away_preds = away_model.predict(x_pf)

        # Derive Spread (Home - Away)
        spread_preds = home_preds - away_preds

        # Add score predictions to results later if needed
        merged_df["pred_home_score"] = home_preds
        merged_df["pred_away_score"] = away_preds

    else:
        # Legacy Stacked Model
        print("Loading Stacked Model...")
        stacked_model = CatBoostRegressor()
        stacked_model.load_model("artifacts/models/stacked_model.cbm")

        # Prepare Features for Stacked Model
        x_standard = select_features(merged_df, FEATURE_CONFIG)
        ppr_cols = ["ppr_home_rating", "ppr_away_rating", "ppr_predicted_spread"]
        x_stacked = pd.concat([x_standard, merged_df[ppr_cols]], axis=1)

        # Ensure columns match model expectation
        expected_features = stacked_model.feature_names_
        if expected_features:
            # Check for missing features
            missing = set(expected_features) - set(x_stacked.columns)
            if missing:
                print(f"Warning: Missing features for stacked model: {missing}")
                print("Filling missing features with NaN...")
                for col in missing:
                    x_stacked[col] = np.nan

            # Reorder
            x_stacked = x_stacked[expected_features]

        # Predict Spread
        print("Predicting Spreads...")
        spread_preds = stacked_model.predict(x_stacked)

    # 4. Load Totals Model (CatBoost)
    # 4. Load Totals Model (CatBoost)
    total_model_name = cfg.weekly_bets.model_registry.total_models[0]
    print(f"Loading Totals Model ({total_model_name})...")
    total_model = get_production_model(total_model_name)
    if total_model is None:
        raise ValueError(f"Could not load {total_model_name}")

    # Prepare Features for Totals Model
    # It likely uses standard features too, but let's check feature_names_
    total_features = getattr(total_model, "feature_names_", None) or getattr(
        total_model, "feature_names_in_", None
    )

    if total_features is None:
        # Fallback to standard selection if we can't inspect
        x_total = select_features(merged_df, FEATURE_CONFIG)
    else:
        # Ensure we have all columns
        # Some might be missing if the model uses different features
        # But for now, let's assume standard features cover it or use the same X_standard if compatible
        # Actually, let's try to select specifically
        available_cols = [c for c in total_features if c in merged_df.columns]
        if len(available_cols) < len(total_features):
            missing = set(total_features) - set(available_cols)
            print(f"Warning: Missing features for totals model: {missing}")
        x_total = merged_df[total_features]

    # Predict Totals
    print("Predicting Totals...")
    total_preds = total_model.predict(x_total)

    # 5. Assemble Results
    results = merged_df[["game_id", "season", "week", "home_team", "away_team"]].copy()

    # Add Date/Time for Publisher
    if "start_date" in merged_df.columns:
        dt = pd.to_datetime(merged_df["start_date"], format="mixed", utc=True)
        # Convert to US/Eastern
        dt = dt.dt.tz_convert("US/Eastern")
        results["Date"] = dt.dt.strftime("%m/%d/%Y")
        results["Time"] = dt.dt.strftime("%I:%M %p")
    else:
        results["Date"] = ""
        results["Time"] = ""

    # Spread
    results["Spread Prediction"] = spread_preds
    if "pred_home_score" in merged_df.columns:
        results["pred_home_score"] = merged_df["pred_home_score"]
        results["pred_away_score"] = merged_df["pred_away_score"]
    # Edge Calculation & Bet Determination
    # Spread
    if "spread_line" in merged_df.columns:
        results["home_team_spread_line"] = merged_df["spread_line"]
        # Edge = Pred - (-Line). Positive = Home Value.
        results["edge_spread"] = results["Spread Prediction"] - (
            -results["home_team_spread_line"]
        )

        # Bet Decision (Threshold 0.0 for Stacked Model)
        results["Spread Bet"] = np.where(results["edge_spread"] > 0, "Home", "Away")
    else:
        results["home_team_spread_line"] = np.nan
        results["edge_spread"] = np.nan
        results["Spread Bet"] = "No Bet"

    # Total
    results["Total Prediction"] = total_preds
    if "total_line" in merged_df.columns:
        results["total_line"] = merged_df["total_line"]
        results["edge_total"] = results["Total Prediction"] - results["total_line"]
    elif "over_under" in merged_df.columns:
        results["total_line"] = merged_df["over_under"]
        results["edge_total"] = results["Total Prediction"] - results["total_line"]
    else:
        results["total_line"] = np.nan
        results["edge_total"] = np.nan

    # Bet Decision (Threshold 5.0 for Totals)
    # Bet Decision (Threshold 0.0 for Totals)
    # Note: We can filter later, but let's mark all for now or use threshold?
    # score_weekly_picks scores whatever is in "Total Bet".
    # If we want to evaluate performance at 5.0, we should only bet if edge > 5.0.
    # But for backfill analysis, we might want to see all.
    # However, score_weekly_picks doesn't filter.
    # Bet Decision (Threshold 0.0 for Totals to allow full analysis)
    if "edge_total" in results.columns:
        conditions = [results["edge_total"] >= 0.0, results["edge_total"] <= -0.0]
        choices = ["Over", "Under"]
        results["Total Bet"] = np.select(conditions, choices, default="No Bet")
    else:
        results["Total Bet"] = "No Bet"

    # Save
    out_dir = Path(f"artifacts/reports/{year}/predictions")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"CFB_week{week}_stacked_bets.csv"
    results.to_csv(out_path, index=False)


if __name__ == "__main__":
    main()
