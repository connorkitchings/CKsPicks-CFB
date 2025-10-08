#!/usr/bin/env python3
"""
Add game_id column to older format betting reports by matching team names.

This script reads a betting report in the older format (Game column with "Away @ Home")
and adds a game_id column by matching against the games database.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

# Add src to path for local imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cfb_model.config import get_data_root
from cfb_model.data.storage.local_storage import LocalStorage


def main() -> None:
    """Add game_id column to betting report by matching team names."""
    parser = argparse.ArgumentParser(
        description="Add game_id column to older format betting reports."
    )
    parser.add_argument("--year", type=int, required=True, help="The season year.")
    parser.add_argument("--week", type=int, required=True, help="The week.")
    parser.add_argument(
        "--data-root",
        type=str,
        default=None,
        help="Absolute path to the data root directory. Defaults to env var or ./data.",
    )
    parser.add_argument(
        "--report-dir",
        type=str,
        default="./reports",
        help="Directory where weekly reports are located.",
    )
    args = parser.parse_args()

    # Resolve data root using the centralized config helper
    data_root = args.data_root or get_data_root()

    # Load the betting report
    bets_file = f"{args.report_dir}/{args.year}/CFB_week{args.week}_bets.csv"
    bets_df = pd.read_csv(bets_file)

    # Load games data
    try:
        storage = LocalStorage(data_root=data_root, file_format="csv", data_type="raw")
        game_records = storage.read_index("games", {"year": args.year})
        if not game_records:
            print(f"Error: No game data found for year {args.year} in {data_root}")
            return
        games_df = pd.DataFrame.from_records(game_records)
    except FileNotFoundError:
        print(f"Error: Could not find games data for year {args.year} in {data_root}")
        return

    # Filter to the specific week and remove duplicates
    week_games_df = games_df[games_df["week"] == args.week].copy()
    week_games_df = week_games_df.drop_duplicates(subset=["id"])

    # Debug: show available teams
    print(f"Available teams in Week {args.week} games:")
    print(f"Sample away teams: {list(week_games_df['away_team'].head(3))}")
    print(f"Sample home teams: {list(week_games_df['home_team'].head(3))}")
    print(f"Total Week {args.week} games: {len(week_games_df)}")
    print()

    # Create a mapping function
    game_ids = []
    for i, row in bets_df.iterrows():
        game_str = row["Game"]
        if " @ " in game_str:
            away_team, home_team = game_str.split(" @ ", 1)

            # Debug first few matches
            if i < 3:
                print(f"Looking for: {away_team} @ {home_team}")
                available_matches = week_games_df[
                    week_games_df["away_team"].str.contains(away_team[:10], na=False)
                    | week_games_df["home_team"].str.contains(home_team[:10], na=False)
                ]
                print(f"  Possible matches: {len(available_matches)}")
                if len(available_matches) > 0:
                    print(
                        f"  First match: {available_matches.iloc[0]['away_team']} @ {available_matches.iloc[0]['home_team']}"
                    )

            # Find matching game
            match = week_games_df[
                (week_games_df["away_team"] == away_team)
                & (week_games_df["home_team"] == home_team)
            ]

            if len(match) == 1:
                game_ids.append(match.iloc[0]["id"])
                if i < 3:
                    print(f"  Found exact match! ID: {match.iloc[0]['id']}")
            else:
                if i < 3:
                    print(
                        f"  Warning: Could not find unique match for {game_str} (found {len(match)} matches)"
                    )
                else:
                    print(f"Warning: Could not find unique match for {game_str}")
                game_ids.append(None)
        else:
            print(f"Warning: Invalid game format: {game_str}")
            game_ids.append(None)

    # Add game_id column
    bets_df["game_id"] = game_ids

    # Parse spread and total lines for scoring compatibility
    home_team_spread_lines = []
    total_lines = []

    for _, row in bets_df.iterrows():
        game_str = row["Game"]
        spread_str = row["Spread"]
        total_str = row["Over/Under"]

        # Parse home_team_spread_line from the Spread column
        if " @ " in game_str and pd.notna(spread_str) and spread_str != "":
            away_team, home_team = game_str.split(" @ ", 1)

            # Check if spread mentions home team or away team
            if home_team in spread_str:
                # Extract the number after team name
                parts = spread_str.split(home_team)
                if len(parts) > 1:
                    line_part = parts[1].strip()
                    try:
                        if line_part.startswith("+"):
                            home_team_spread_line = float(line_part[1:])
                        elif line_part.startswith("-"):
                            home_team_spread_line = -float(line_part[1:])
                        else:
                            home_team_spread_line = float(line_part)
                        home_team_spread_lines.append(home_team_spread_line)
                    except ValueError:
                        home_team_spread_lines.append(None)
                else:
                    home_team_spread_lines.append(None)
            elif away_team in spread_str:
                # Away team is mentioned, so home spread is opposite
                parts = spread_str.split(away_team)
                if len(parts) > 1:
                    line_part = parts[1].strip()
                    try:
                        if line_part.startswith("+"):
                            home_team_spread_line = -float(line_part[1:])
                        elif line_part.startswith("-"):
                            home_team_spread_line = float(line_part[1:])
                        else:
                            home_team_spread_line = -float(line_part)
                        home_team_spread_lines.append(home_team_spread_line)
                    except ValueError:
                        home_team_spread_lines.append(None)
                else:
                    home_team_spread_lines.append(None)
            else:
                home_team_spread_lines.append(None)
        else:
            home_team_spread_lines.append(None)

        # Parse total_line
        try:
            if pd.notna(total_str) and total_str != "":
                total_lines.append(float(total_str))
            else:
                total_lines.append(None)
        except ValueError:
            total_lines.append(None)

    bets_df["home_team_spread_line"] = home_team_spread_lines
    bets_df["total_line"] = total_lines

    # Save the updated report
    output_file = f"{args.report_dir}/{args.year}/CFB_week{args.week}_bets_with_ids.csv"
    bets_df.to_csv(output_file, index=False)
    print(f"Updated report saved to {output_file}")

    # Show how many matches we found
    matches = sum(1 for gid in game_ids if gid is not None)
    print(f"Successfully matched {matches} out of {len(game_ids)} games")


if __name__ == "__main__":
    main()
