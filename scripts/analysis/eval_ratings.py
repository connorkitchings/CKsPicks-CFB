import argparse
import logging
import os
import sys
from pathlib import Path

sys.path.append(os.getcwd())
# noqa: E402
import numpy as np
import pandas as pd

from src.data.ratings import prepare_ratings_data
from src.models.ratings.bayesian import ProbabilisticPowerRating

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--start-week", type=int, default=5)
    parser.add_argument("--end-week", type=int, default=14)
    parser.add_argument("--draws", type=int, default=500)
    parser.add_argument("--tune", type=int, default=500)
    parser.add_argument("--team-hfa", action="store_true", help="Use team-specific HFA")
    parser.add_argument(
        "--recency", type=float, default=None, help="Recency decay weight (e.g. 0.1)"
    )
    args = parser.parse_args()

    results = []

    # Load full season games for evaluation
    full_games, _, _ = prepare_ratings_data(args.year, week=None)

    for week in range(args.start_week, args.end_week + 1):
        logger.info(f"Processing Week {week}...")

        # 1. Train on past data
        train_df, team_to_idx, idx_to_team = prepare_ratings_data(args.year, week=week)

        if len(train_df) < 50:
            logger.warning(f"Not enough games to train for week {week}. Skipping.")
            continue

        model = ProbabilisticPowerRating(team_to_idx, idx_to_team)
        model.fit(
            train_df,
            draws=args.draws,
            tune=args.tune,
            chains=2,
            use_team_hfa=args.team_hfa,
            recency_weight=args.recency,
        )

        # 2. Predict current week
        # Get games for this week from full set
        week_games = full_games[full_games["week"] == week].copy()

        for _, game in week_games.iterrows():
            home = game["home_team"]
            away = game["away_team"]
            neutral = game["neutral_site"]

            pred = model.predict_spread(home, away, neutral)

            if pred is None:
                continue  # Skip if new team

            actual_margin = game["home_points"] - game["away_points"]
            actual_total = game["home_points"] + game["away_points"]

            res = {
                "week": week,
                "game_id": game["game_id"],
                "home_team": home,
                "away_team": away,
                "pred_spread": pred["pred_spread"],
                "pred_spread_std": pred["pred_spread_std"],
                "actual_margin": actual_margin,
                "spread_error": pred["pred_spread"] - actual_margin,
                "pred_total": pred["pred_total"],
                "actual_total": actual_total,
                "total_error": pred["pred_total"] - actual_total,
                "home_rating": model.get_ratings()
                .set_index("team")
                .loc[home, "net_rating"],
                "away_rating": model.get_ratings()
                .set_index("team")
                .loc[away, "net_rating"],
            }
            results.append(res)

    # 3. Summary
    res_df = pd.DataFrame(results)
    if res_df.empty:
        logger.error("No results generated.")
        return

    rmse_spread = np.sqrt(np.mean(res_df["spread_error"] ** 2))
    mae_spread = np.mean(np.abs(res_df["spread_error"]))
    rmse_total = np.sqrt(np.mean(res_df["total_error"] ** 2))

    print("\n=== Evaluation Results ===")
    print(f"Games Evaluated: {len(res_df)}")
    print(f"Spread RMSE: {rmse_spread:.2f}")
    print(f"Spread MAE: {mae_spread:.2f}")
    print(f"Total RMSE: {rmse_total:.2f}")

    # Save results
    out_dir = Path(f"artifacts/ratings/{args.year}")
    out_dir.mkdir(parents=True, exist_ok=True)
    res_df.to_csv(out_dir / "eval_results.csv", index=False)
    print(f"Results saved to {out_dir / 'eval_results.csv'}")


if __name__ == "__main__":
    main()
