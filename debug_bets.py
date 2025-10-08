#!/usr/bin/env python3

import pandas as pd

df = pd.read_csv("reports/2025/CFB_week6_bets_scored.csv")
df_clean = df.drop_duplicates()

spread_bets = df_clean[df_clean["Spread Bet"].isin(["home", "away"])]
total_bets = df_clean[df_clean["Total Bet"].isin(["over", "under"])]

print(f"Spread bets: {len(spread_bets)}")
print(f"Total bets: {len(total_bets)}")

print("\nSpread bet results:")
print(spread_bets["Spread Bet Result"].value_counts())

print("\nTotal bet results:")
print(total_bets["Total Bet Result"].value_counts())

print("\n=== SPREAD BETS ===")
for _, row in spread_bets.iterrows():
    print(f"{row['Game']}: {row['Spread Bet']} - {row['Spread Bet Result']}")

print("\n=== TOTAL BETS ===")
for _, row in total_bets.iterrows():
    print(f"{row['Game']}: {row['Total Bet']} - {row['Total Bet Result']}")
