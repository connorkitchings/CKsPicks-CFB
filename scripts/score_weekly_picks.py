import argparse
import os

import numpy as np
import pandas as pd


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
    bets_df["pick_win"] = np.nan
    bets_df.loc[bets_to_score.index, "pick_win"] = results

    # --- Score Totals Bets ---
    totals_to_score = bets_df[bets_df["bet_total"].isin(["over", "under"])].copy()
    if not totals_to_score.empty:
        print(f"Found {len(totals_to_score)} totals bets to score...")
        total_results = []
        for index, bet in totals_to_score.iterrows():
            game_id = bet["game_id"]
            game_matches = week_games_df[week_games_df["id"] == game_id]
            if game_matches.empty:
                total_results.append(np.nan)
                continue

            game = game_matches.iloc[0]
            home_pts = game.get("home_points")
            away_pts = game.get("away_points")

            if pd.notna(home_pts) and pd.notna(away_pts):
                actual_total = home_pts + away_pts
                total_line = bet["total_line"]
                bet_side = bet["bet_total"]

                if bet_side == "over" and actual_total > total_line:
                    win = 1
                elif bet_side == "under" and actual_total < total_line:
                    win = 1
                elif actual_total == total_line:
                    win = 0  # Push
                else:
                    win = 0  # Loss
                total_results.append(win)
            else:
                total_results.append(np.nan)

        bets_df.loc[totals_to_score.index, "total_pick_win"] = total_results

    # Save the scored bets to a new file
    output_path = os.path.join(
        args.report_dir, str(args.year), f"CFB_week{args.week}_bets_scored.csv"
    )
    bets_df.to_csv(output_path, index=False)
    print(f"Scored results saved to {output_path}")

    # 6. Calculate and print summary
    spread_valid_results = bets_df["pick_win"].dropna()
    spread_total_bets = len(spread_valid_results)
    spread_wins = int(spread_valid_results.sum())
    spread_hit_rate = (
        (spread_wins / spread_total_bets) if spread_total_bets > 0 else 0.0
    )

    print("\n--- Scoring Summary ---")
    print(f"Spread picks: {spread_wins}/{spread_total_bets} = {spread_hit_rate:.3f}")

    if "total_pick_win" in bets_df:
        total_valid_results = bets_df["total_pick_win"].dropna()
        total_total_bets = len(total_valid_results)
        total_wins = int(total_valid_results.sum())
        total_hit_rate = (
            (total_wins / total_total_bets) if total_total_bets > 0 else 0.0
        )
        print(f"Total picks:  {total_wins}/{total_total_bets} = {total_hit_rate:.3f}")


if __name__ == "__main__":
    main()
