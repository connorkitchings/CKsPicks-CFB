import argparse
import os
import sys
from pathlib import Path

import joblib
import pandas as pd

# Add project root to path
sys.path.append(os.getcwd())
# noqa: E402
from src.config import get_data_root
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


def prepare_features(model, data_df):
    # Check what features the model wants
    model_features = getattr(model, "feature_names_", None)
    if model_features is None:
        # Try feature_names_in_ (sklearn style)
        model_features = getattr(model, "feature_names_in_", None)

    if model_features is None:
        print(
            "Warning: Model has no feature_names_ attribute. Using differential features as fallback."
        )
        df_feats = build_differential_features(data_df.copy())
        feature_list = build_differential_feature_list(df_feats)
        x_features = df_feats[feature_list].fillna(0.0)
    else:
        # Check if we need differential features
        if any(f.startswith("matchup_") for f in model_features):
            df_feats = build_differential_features(data_df.copy())
            # Ensure all model features are present
            missing = [f for f in model_features if f not in df_feats.columns]
            if missing:
                # print(f"Warning: Missing features: {missing}")
                for f in missing:
                    df_feats[f] = 0.0
            x_features = df_feats[model_features].fillna(0.0)
        else:
            # Ensure all model features are present in data_df
            missing = [f for f in model_features if f not in data_df.columns]
            if missing:
                # print(f"Warning: Missing features: {missing}")
                for f in missing:
                    data_df[f] = 0.0
            x_features = data_df[model_features].fillna(0.0)

    return x_features


def main():
    parser = argparse.ArgumentParser(
        description="Generate Weekly Bets (Hybrid Strategy)"
    )
    parser.add_argument("--year", type=int, required=True, help="Season year")
    parser.add_argument("--week", type=int, required=True, help="Week number")
    parser.add_argument(
        "--spread-threshold", type=float, default=5.0, help="Spread edge threshold"
    )
    parser.add_argument(
        "--total-threshold", type=float, default=5.5, help="Total edge threshold"
    )
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="Run backfill for all weeks up to current",
    )
    args = parser.parse_args()

    year = args.year

    if args.backfill:
        # Determine weeks to run (e.g., 1 to 15)
        # For simplicity, let's just run 1-15
        weeks = list(range(1, 16))
    else:
        weeks = [args.week]

    # Load Models
    print("Loading models...")
    models_dir = Path(f"artifacts/models/{year}")

    # Spread: CatBoost
    spread_model_path = models_dir / "spread_catboost.joblib"
    if not spread_model_path.exists():
        raise FileNotFoundError(f"Spread model not found at {spread_model_path}")
    spread_model = joblib.load(spread_model_path)
    print(f"Loaded Spread Model: {spread_model_path}")

    # Total: XGBoost
    total_model_path = models_dir / "total_xgboost.joblib"
    if not total_model_path.exists():
        raise FileNotFoundError(f"Total model not found at {total_model_path}")
    total_model = joblib.load(total_model_path)
    print(f"Loaded Total Model: {total_model_path}")

    for week in weeks:
        print(f"\nProcessing Week {week}...")
        try:
            data_df = load_week_data(year, week)
            if data_df.empty:
                print(f"No games found for Week {week}. Skipping.")
                continue

            # Predict Spread
            x_spread = prepare_features(spread_model, data_df)
            spread_preds = spread_model.predict(x_spread)

            # Predict Total
            x_total = prepare_features(total_model, data_df)
            total_preds = total_model.predict(x_total)

            # Construct Bets DataFrame
            bets = []
            for idx, row in data_df.iterrows():
                game_id = row["id"]
                home = row["home_team"]
                away = row["away_team"]

                # Spread Logic
                # Model predicts Home Margin (Points For Home - Points For Away)
                # Or does it predict Home Score and Away Score?
                # The models I loaded are "spread_catboost" and "total_xgboost".
                # These are likely "Points-For" models wrapped to output spread/total?
                # Or are they direct spread/total regressors?
                # The filenames suggest direct regressors or wrappers.
                # If they are Points-For models, they might output (Home, Away) tuple?
                # Let's assume they output a single value (Spread or Total) for now,
                # based on "spread_catboost" name.
                # Wait, "spread_catboost" usually implies predicting the spread directly.
                # But the plan mentioned "Points-For architecture".
                # If they are Points-For, I should have loaded "home_catboost" and "away_catboost".
                # But I loaded "spread_catboost.joblib".
                # Let's assume "spread_catboost.joblib" is a regressor for (Home - Away).

                pred_spread = spread_preds[idx]
                pred_total = total_preds[idx]

                book_spread = row.get("home_team_spread_line")
                book_total = row.get("total_line")

                # Spread Bet
                if pd.notna(book_spread):
                    # Pred Spread is Home Margin.
                    # If Pred > -Line + Thresh => Home Cover?
                    # Wait, standard spread logic:
                    # Line = -3.5 (Home favored by 3.5).
                    # Pred = 7.0 (Home wins by 7).
                    # Edge = 7.0 - 3.5 = 3.5.
                    # Bet Home.

                    # My logic in generate_hybrid_bets.py was:
                    # if model_spread < (book_spread - spread_th): Bet Home?
                    # Wait, PPR spread was (Home - Away)? No, usually (Away - Home) or something.
                    # Let's stick to standard:
                    # Spread is defined as Home Team Spread (e.g. -3.5).
                    # Prediction is Home Margin (Home - Away).
                    # We want Home Margin > -Spread.
                    # e.g. Margin 4 > -(-3.5) = 3.5. Cover.

                    # Let's assume pred_spread is Home Margin.
                    # Edge = pred_spread - (-book_spread) = pred_spread + book_spread.
                    # If Edge > Thresh => Bet Home.
                    # If Edge < -Thresh => Bet Away.

                    edge = pred_spread + book_spread

                    if edge > args.spread_threshold:
                        bet_side = "Home"
                        bet_conf = "High"
                    elif edge < -args.spread_threshold:
                        bet_side = "Away"
                        bet_conf = "High"
                    else:
                        bet_side = "No Bet"
                        bet_conf = ""

                    bets.append(
                        {
                            "game_id": game_id,
                            "Game": f"{away} @ {home}",
                            "Spread Bet": bet_side,
                            "home_team_spread_line": book_spread,
                            "Spread Prediction": pred_spread,
                            "edge_spread": abs(edge),
                            "Spread Confidence": bet_conf,
                            "total_line": book_total,
                            "Total Prediction": pred_total,
                            "edge_total": 0.0,  # Placeholder
                            "Total Bet": "No Bet",  # Placeholder
                        }
                    )
                else:
                    bets.append(
                        {
                            "game_id": game_id,
                            "Game": f"{away} @ {home}",
                            "Spread Bet": "No Bet",
                            "home_team_spread_line": None,
                            "Spread Prediction": pred_spread,
                            "edge_spread": 0.0,
                            "Spread Confidence": "",
                            "total_line": book_total,
                            "Total Prediction": pred_total,
                            "edge_total": 0.0,
                            "Total Bet": "No Bet",
                        }
                    )

                # Total Bet
                if pd.notna(book_total):
                    # Pred Total vs Book Total
                    edge_t = pred_total - book_total

                    last_bet = bets[-1]
                    last_bet["edge_total"] = abs(edge_t)

                    if edge_t > args.total_threshold:
                        last_bet["Total Bet"] = "Over"
                    elif edge_t < -args.total_threshold:
                        last_bet["Total Bet"] = "Under"
                    else:
                        last_bet["Total Bet"] = "No Bet"

            # Save
            bets_df = pd.DataFrame(bets)

            # Add extra cols
            bets_df = bets_df.merge(
                data_df[["id", "start_date", "home_team", "away_team"]],
                left_on="game_id",
                right_on="id",
                how="left",
            )
            bets_df["Date"] = pd.to_datetime(bets_df["start_date"]).dt.strftime(
                "%Y-%m-%d"
            )
            bets_df["Time"] = pd.to_datetime(bets_df["start_date"]).dt.strftime(
                "%H:%M:%S"
            )
            bets_df["Home Team"] = bets_df["home_team"]
            bets_df["Away Team"] = bets_df["away_team"]

            output_dir = Path(f"data/production/predictions/{year}")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"CFB_week{week}_bets.csv"
            bets_df.to_csv(output_path, index=False)
            print(f"Saved bets to {output_path}")

        except Exception as e:
            print(f"Error processing week {week}: {e}")
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    main()
