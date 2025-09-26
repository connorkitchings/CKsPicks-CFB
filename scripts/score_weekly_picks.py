import pandas as pd
import os
import argparse
import numpy as np


def main():
    parser = argparse.ArgumentParser(
        description="A fast, simple script to score weekly bets against historical data."
    )
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--data-root", type=str, required=True)
    parser.add_argument("--report-dir", type=str, default="./reports")
    args = parser.parse_args()

    bets_file = os.path.join(
        args.report_dir, str(args.year), f"CFB_week{args.week}_bets.csv"
    )

    if not os.path.exists(bets_file):
        print(f"Error: Bets file not found at {bets_file}")
        return

    # 1. Load the bets
    bets_df = pd.read_csv(bets_file)

    # Diagnostic: Print games played for all potential bets
    print("--- Diagnostic: Games Played Analysis ---")
    diag_cols = [
        "game_id",
        "home_team",
        "away_team",
        "home_games_played",
        "away_games_played",
        "edge_spread",
    ]
    print(bets_df[diag_cols].to_string())

    bets_to_score = bets_df[bets_df["bet_spread"].isin(["home", "away"])].copy()

    if bets_to_score.empty:
        print("No spread bets to score in the report.")
        return

    print(f"Found {len(bets_to_score)} spread bets to score for Week {args.week}...")

    results = []
    # 2. Load all games data for the year (games are stored in simple year partitions)
    games_path = os.path.join(
        args.data_root, f"data/raw/games/year={args.year}/data.csv"
    )

    try:
        games_df = pd.read_csv(games_path)
        print(f"Loaded {len(games_df)} games for year {args.year}")
    except FileNotFoundError:
        print(f"Error: Could not find games data at {games_path}")
        return

    # Filter to just the target week
    week_games_df = games_df[games_df["week"] == args.week].copy()
    print(f"Found {len(week_games_df)} games for week {args.week}")

    # 3. Loop through bets and lookup game results
    for index, bet in bets_to_score.iterrows():
        game_id = bet["game_id"]

        # Look up the game in the week's games
        game_matches = week_games_df[week_games_df["id"] == game_id]

        if game_matches.empty:
            print(f"Warning: Could not find game_id {game_id} in week {args.week} data")
            results.append(np.nan)
            continue

        game = game_matches.iloc[0]
        home_pts = game.get("home_points")
        away_pts = game.get("away_points")

        if pd.notna(home_pts) and pd.notna(away_pts):
            actual_margin = home_pts - away_pts
            spread_line = bet["home_team_spread_line"]
            bet_side = bet["bet_spread"]

            # Convert spread line to expected margin
            # If spread is -7.0 (home favored by 7), expected margin is +7.0
            expected_margin = -spread_line

            # 4. Determine winner based on actual vs expected margin
            if bet_side == "home" and actual_margin > expected_margin:
                win = 1  # Home bet wins if actual margin > expected margin
            elif bet_side == "away" and actual_margin < expected_margin:
                win = 1  # Away bet wins if actual margin < expected margin
            elif actual_margin == expected_margin:
                win = 0  # Push
            else:
                win = 0  # Loss
            results.append(win)
        else:
            results.append(np.nan)  # Game not finished or data missing

    # 5. Add results and save scored output
    bets_to_score["pick_win"] = results

    # Save the scored bets to a new file
    output_path = os.path.join(
        args.report_dir, str(args.year), f"CFB_week{args.week}_bets_scored.csv"
    )
    bets_to_score.to_csv(output_path, index=False)
    print(f"Scored results saved to {output_path}")

    # 6. Calculate and print summary
    bets_to_score["win"] = results
    valid_results = bets_to_score["win"].dropna()

    total_bets = len(valid_results)
    wins = int(valid_results.sum())
    hit_rate = (wins / total_bets) if total_bets > 0 else 0.0

    print("\n--- Scoring Summary ---")
    print(f"Spread picks: {wins}/{total_bets} = {hit_rate:.3f}")


if __name__ == "__main__":
    main()
