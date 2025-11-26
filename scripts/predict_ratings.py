import argparse
import logging
import os
import sys
from pathlib import Path

import pandas as pd

# Add project root to path
sys.path.append(os.getcwd())

from src.config import ARTIFACTS_DIR, DATA_ROOT
from src.data.ratings import prepare_ratings_data
from src.features.weather import load_weather_data
from src.models.ratings.bayesian import ProbabilisticPowerRating

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Generate weekly predictions using Probabilistic Power Ratings."
    )
    parser.add_argument(
        "--year", type=int, required=True, help="Season year (e.g. 2025)"
    )
    parser.add_argument(
        "--week", type=int, required=True, help="Week to predict (e.g. 14)"
    )
    parser.add_argument("--draws", type=int, default=2000, help="Number of MCMC draws")
    parser.add_argument("--tune", type=int, default=1000, help="Number of tuning steps")
    args = parser.parse_args()

    logger.info(f"Starting ratings prediction for {args.year} Week {args.week}...")

    # 1. Load Training Data (Games BEFORE target week)
    # Note: prepare_ratings_data(..., week=args.week) filters to games < args.week
    train_df, team_to_idx, idx_to_team = prepare_ratings_data(args.year, week=args.week)

    # 1b. Load Weather Data for Training
    # We need weather for the games in train_df.
    # train_df has 'game_id'.
    weather_df = load_weather_data(args.year, DATA_ROOT)
    if not weather_df.empty:
        # Merge weather into train_df
        # weather_df has game_id, temperature, precipitation, wind_speed
        # We only need one row per game_id. weather_df should be unique by game_id if load_weather_data handles it.
        # But load_weather_data might return duplicates if not careful?
        # The implementation of load_weather_data in weather.py seems to return raw rows.
        # Let's deduplicate just in case.
        weather_unique = weather_df.drop_duplicates(subset=["game_id"])
        train_df = train_df.merge(weather_unique, on="game_id", how="left")

        # Fill missing weather in training data with defaults
        train_df["temperature"] = train_df["temperature"].fillna(70.0)
        train_df["precipitation"] = train_df["precipitation"].fillna(0.0)
        train_df["wind_speed"] = train_df["wind_speed"].fillna(0.0)

        logger.info(f"Merged weather data into training set. {len(train_df)} games.")
    else:
        logger.warning(
            "No weather data found. Training without weather features (defaults used)."
        )

    logger.info(
        f"Training on {len(train_df)} completed games from {args.year} weeks 1-{args.week - 1}."
    )

    # 2. Train Model
    model = ProbabilisticPowerRating(team_to_idx, idx_to_team)
    # Using baseline configuration (no team_hfa, no recency) as per optimization results
    # Now passing weather columns implicitly via df
    model.fit(train_df, draws=args.draws, tune=args.tune, chains=2)

    # 3. Load Schedule for Target Week
    games_path = Path(DATA_ROOT) / "raw" / "games" / f"year={args.year}" / "data.csv"
    if not games_path.exists():
        logger.error(f"Games data not found at {games_path}")
        return

    all_games = pd.read_csv(games_path)
    if "id" in all_games.columns and "game_id" not in all_games.columns:
        all_games = all_games.rename(columns={"id": "game_id"})

    week_games = all_games[all_games["week"] == args.week].copy()

    if week_games.empty:
        logger.warning(f"No games found for {args.year} Week {args.week}.")
        return

    # 3b. Merge Weather for Prediction Week
    if not weather_df.empty:
        weather_unique = weather_df.drop_duplicates(subset=["game_id"])
        week_games = week_games.merge(weather_unique, on="game_id", how="left")
        # Fill missing prediction weather
        week_games["temperature"] = week_games["temperature"].fillna(70.0)
        week_games["precipitation"] = week_games["precipitation"].fillna(0.0)
        week_games["wind_speed"] = week_games["wind_speed"].fillna(0.0)

    logger.info(
        f"Generating predictions for {len(week_games)} games in Week {args.week}..."
    )

    predictions = []
    ratings = model.get_ratings().set_index("team")

    for _, game in week_games.iterrows():
        home = game["home_team"]
        away = game["away_team"]
        neutral = game.get("neutral_site", False)
        if pd.isna(neutral):
            neutral = False

        # Extract weather for this game
        wind = game.get("wind_speed", 0.0)
        rain = game.get("precipitation", 0.0)
        temp = game.get("temperature", 70.0)

        # Skip if teams not in training set (e.g. FCS not played yet? or just new)
        # The model handles unknown teams gracefully-ish but let's check
        if home not in team_to_idx or away not in team_to_idx:
            logger.warning(f"Skipping {home} vs {away}: Team not in training set.")
            continue

        pred = model.predict_spread(
            home, away, neutral, wind_speed=wind, precipitation=rain, temperature=temp
        )

        # Get current ratings
        home_rating = ratings.loc[home, "net_rating"]
        away_rating = ratings.loc[away, "net_rating"]

        predictions.append(
            {
                "season": args.year,
                "week": args.week,
                "game_id": game["game_id"],
                "home_team": home,
                "away_team": away,
                "home_rating": round(home_rating, 2),
                "away_rating": round(away_rating, 2),
                "pred_spread": round(pred["pred_spread"], 2),  # Home - Away
                "pred_spread_std": round(pred["pred_spread_std"], 2),
                "pred_total": round(pred["pred_total"], 2),
                "pred_total_std": round(pred["pred_total_std"], 2),
                "home_win_prob": round(pred["prob_home_win"], 4),
                "home_pred_score": round(pred["home_score"], 2),
                "away_pred_score": round(pred["away_score"], 2),
                "wind_speed": round(wind, 1),
                "precipitation": round(rain, 2),
                "temperature": round(temp, 1),
            }
        )

    # 4. Save Predictions
    pred_df = pd.DataFrame(predictions)

    out_dir = ARTIFACTS_DIR / "predictions" / str(args.year)
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / f"week_{args.week}_ratings_preds.csv"
    pred_df.to_csv(out_path, index=False)

    logger.info(f"Saved {len(pred_df)} predictions to {out_path}")

    # Also save the ratings themselves
    ratings_path = out_dir / f"week_{args.week}_team_ratings.csv"
    ratings.to_csv(ratings_path)
    logger.info(f"Saved team ratings to {ratings_path}")


if __name__ == "__main__":
    main()
