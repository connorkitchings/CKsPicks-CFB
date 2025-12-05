import os
import sys

import pandas as pd

# Add project root to path
sys.path.append(os.getcwd())
# noqa: E402
from scripts.utils.model_registry import get_production_model
from src.config import PREDICTIONS_SUBDIR, REPORTS_DIR, get_data_root
from src.models.features import (
    build_differential_feature_list,
    build_differential_features,
    load_weekly_team_features,
)
from src.utils.local_storage import LocalStorage


def load_week_data(year, week):
    data_root = get_data_root()
    raw = LocalStorage(data_root=data_root, file_format="csv", data_type="raw")

    # Load features (Iteration 2 as per decision log)
    team_features = load_weekly_team_features(
        year, week, data_root, adjustment_iteration=2
    )
    if team_features is None:
        raise ValueError("No team features found")

    # Load games
    games = pd.DataFrame.from_records(raw.read_index("games", {"year": year}))
    week_games = games[games["week"] == week].copy()
    week_games = week_games.drop_duplicates(subset=["id"], keep="last")

    # Merge features
    home_feats = team_features.add_prefix("home_")
    away_feats = team_features.add_prefix("away_")

    merged = week_games.merge(
        home_feats,
        left_on=["season", "home_team"],
        right_on=["home_season", "home_team"],
        how="left",
    )
    merged = merged.merge(
        away_feats,
        left_on=["season", "away_team"],
        right_on=["away_season", "away_team"],
        how="left",
    )

    # Load lines
    lines = pd.DataFrame.from_records(
        raw.read_index("betting_lines", {"year": year, "week": week})
    )
    if not lines.empty:
        # Simple dedupe
        lines = lines.sort_values("provider").groupby("game_id", as_index=False).first()
        # Rename cols if needed
        rename_map = {"over_under": "total_line", "spread": "home_team_spread_line"}
        lines = lines.rename(columns=rename_map)
        merged = merged.merge(lines, left_on="id", right_on="game_id", how="left")

    return merged


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate Hybrid Bets")
    parser.add_argument("--year", type=int, required=True, help="Season year")
    parser.add_argument("--week", type=int, required=True, help="Week number")
    parser.add_argument(
        "--spread-threshold", type=float, default=1.0, help="Spread edge threshold"
    )
    parser.add_argument(
        "--total-threshold", type=float, default=10.0, help="Total edge threshold"
    )
    args = parser.parse_args()

    year = args.year
    week = args.week
    spread_th = args.spread_threshold
    total_th = args.total_threshold

    print(f"Generating Hybrid Predictions for {year} Week {week}...")

    # 1. Load PPR Predictions (Spread Source)
    ppr_path = f"artifacts/predictions/{year}/week_{week}_ratings_preds.csv"
    print(f"Loading PPR predictions from {ppr_path}...")
    ppr_df = pd.read_csv(ppr_path)
    # ppr_df cols: game_id, pred_spread, pred_total, etc.

    # 2. Generate CatBoost Predictions (Total Source)
    print("Loading CatBoost Totals model...")
    total_model = get_production_model("cfb_total_catboost")
    if total_model is None:
        raise ValueError("Could not load cfb_total_catboost")

    print("Loading feature data...")
    data_df = load_week_data(year, week)

    # Prepare features
    # Check what features the model wants
    model_features = getattr(total_model, "feature_names_", None)
    if model_features is None:
        # Try feature_names_in_ (sklearn style)
        model_features = getattr(total_model, "feature_names_in_", None)

    if model_features is None:
        print(
            "Warning: Model has no feature_names_ attribute. Using differential features as fallback."
        )
        df_totals = build_differential_features(data_df.copy())
        feature_list = build_differential_feature_list(df_totals)
        x_features = df_totals[feature_list].fillna(0.0)
    else:
        print(f"Model expects {len(model_features)} features.")
        # Check if we need differential features
        if any(f.startswith("matchup_") for f in model_features):
            print("Model uses differential features. Building...")
            df_totals = build_differential_features(data_df.copy())
            # Ensure all model features are present
            missing = [f for f in model_features if f not in df_totals.columns]
            if missing:
                print(f"Warning: Missing features: {missing}")
                for f in missing:
                    df_totals[f] = 0.0
            x_features = df_totals[model_features].fillna(0.0)
        else:
            print("Model uses standard features.")
            # Ensure all model features are present in data_df
            missing = [f for f in model_features if f not in data_df.columns]
            if missing:
                print(f"Warning: Missing features: {missing}")
                for f in missing:
                    data_df[f] = 0.0
            x_features = data_df[model_features].fillna(0.0)

    print("Predicting Totals...")
    totals_pred = total_model.predict(x_features)

    data_df["catboost_total"] = totals_pred

    # 3. Merge
    print("Merging predictions...")
    # PPR has game_id, data_df has id
    merged = ppr_df.merge(
        data_df[["id", "catboost_total", "total_line", "home_team_spread_line"]],
        left_on="game_id",
        right_on="id",
        how="left",
    )

    # 4. Apply Logic
    # Spread: Use PPR (pred_spread)
    # Total: Use CatBoost (catboost_total)

    # Thresholds from argparse (already set above)

    bets = []
    for _, row in merged.iterrows():
        # Spread
        model_spread = row["pred_spread"]
        book_spread = row["home_team_spread_line"]  # from data_df merge

        # If book_spread missing in data_df, try ppr_df (it might have it? no, ppr just has pred)
        # Actually predict_ratings.py doesn't save book lines usually?
        # Wait, predict_ratings.py output has: season,week,game_id,home_team,away_team,home_rating,away_rating,pred_spread...
        # It does NOT have book lines.
        # But generate_bets_from_ratings.py merged them.
        # Let's use the lines from data_df (which we loaded from raw).

        if pd.isna(book_spread):
            continue

        # Spread Logic (PPR)
        # PPR pred_spread is (Home - Away). Negative = Home Favored.
        # Book spread is same.
        if model_spread < (book_spread - spread_th):
            bets.append(
                {
                    "game_id": row["game_id"],
                    "Game": f"{row['away_team']} @ {row['home_team']}",
                    "Spread Bet": "Home",
                    "home_team_spread_line": book_spread,
                    "Spread Prediction": model_spread,
                    "edge_spread": book_spread - model_spread,
                    "Spread Confidence": "High",
                }
            )
        elif model_spread > (book_spread + spread_th):
            bets.append(
                {
                    "game_id": row["game_id"],
                    "Game": f"{row['away_team']} @ {row['home_team']}",
                    "Spread Bet": "Away",
                    "home_team_spread_line": book_spread,
                    "Spread Prediction": model_spread,
                    "edge_spread": model_spread - book_spread,
                    "Spread Confidence": "High",
                }
            )
        else:
            bets.append(
                {
                    "game_id": row["game_id"],
                    "Game": f"{row['away_team']} @ {row['home_team']}",
                    "Spread Bet": "No Bet",
                    "home_team_spread_line": book_spread,
                    "Spread Prediction": model_spread,
                    "edge_spread": 0.0,
                    "Spread Confidence": "",
                }
            )

        # Total Logic (CatBoost)
        model_total = row["catboost_total"]
        book_total = row["total_line"]

        if pd.isna(book_total):
            continue

        # Update last bet entry with total info
        last_bet = bets[-1]
        last_bet["total_line"] = book_total
        last_bet["Total Prediction"] = model_total
        last_bet["edge_total"] = abs(model_total - book_total)

        if model_total > (book_total + total_th):
            last_bet["Total Bet"] = "Over"
            last_bet["edge_total"] = model_total - book_total
        elif model_total < (book_total - total_th):
            last_bet["Total Bet"] = "Under"
            last_bet["edge_total"] = book_total - model_total
        else:
            last_bet["Total Bet"] = "No Bet"
            last_bet["edge_total"] = 0.0

    bets_df = pd.DataFrame(bets)

    # Save
    output_dir = os.path.join(REPORTS_DIR, str(year), PREDICTIONS_SUBDIR)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"CFB_week{week}_bets.csv")

    # Add extra cols required by publish_picks
    # Date, Time, home_team, away_team
    # We can merge these back from data_df
    bets_df = bets_df.merge(
        data_df[["id", "start_date", "home_team", "away_team"]],
        left_on="game_id",
        right_on="id",
        how="left",
    )
    bets_df["Date"] = pd.to_datetime(bets_df["start_date"]).dt.strftime("%Y-%m-%d")
    bets_df["Time"] = pd.to_datetime(bets_df["start_date"]).dt.strftime("%H:%M:%S")
    bets_df["Home Team"] = bets_df["home_team"]
    bets_df["Away Team"] = bets_df["away_team"]

    bets_df.to_csv(output_path, index=False)
    print(f"Saved hybrid bets to {output_path}")


if __name__ == "__main__":
    main()
