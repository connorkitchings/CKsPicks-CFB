#!/usr/bin/env python3

import sys

sys.path.insert(0, "src")
import pandas as pd

from cfb_model.data.storage.local_storage import LocalStorage

# Check what games actually have scores
storage = LocalStorage(
    data_root="/Volumes/CK SSD/Coding Projects/cfb_model/data",
    file_format="csv",
    data_type="raw",
)
game_records = storage.read_index("games", {"year": 2025})
games_df = pd.DataFrame.from_records(game_records)
week6_games = games_df[games_df["week"] == 6].drop_duplicates(subset=["id"])

print(f"Total Week 6 games: {len(week6_games)}")
print(f"Completed games: {(week6_games['completed'] is True).sum()}")
print(f"Games with scores: {week6_games['home_points'].notna().sum()}")

# Check specific games from our betting report
bets_df = pd.read_csv("reports/2025/CFB_week6_bets.csv")
print("\nOriginal bets to score:")
print(f"Spread bets: {len(bets_df[bets_df['Spread Bet'].isin(['home', 'away'])])}")
print(f"Total bets: {len(bets_df[bets_df['Total Bet'].isin(['over', 'under'])])}")

# Check if our bet games have scores
bet_games = bets_df[
    bets_df["Spread Bet"].isin(["home", "away"])
    | bets_df["Total Bet"].isin(["over", "under"])
]
print("\nChecking bet games for scores:")
for _, bet_row in bet_games.iterrows():
    game_str = bet_row["Game"]
    if " @ " in game_str:
        away, home = game_str.split(" @ ")
        match = week6_games[
            (week6_games["away_team"] == away) & (week6_games["home_team"] == home)
        ]
        if len(match) > 0:
            game = match.iloc[0]
            spread_bet = (
                bet_row["Spread Bet"]
                if bet_row["Spread Bet"] in ["home", "away"]
                else None
            )
            total_bet = (
                bet_row["Total Bet"]
                if bet_row["Total Bet"] in ["over", "under"]
                else None
            )
            bet_type = f"spread={spread_bet}" if spread_bet else f"total={total_bet}"
            print(
                f"{game_str} ({bet_type}): completed={game['completed']}, scores={game['away_points']}-{game['home_points']}"
            )
        else:
            print(f"{game_str}: NO MATCH FOUND")

print(f"\nTotal unique bet games: {len(bet_games)}")
