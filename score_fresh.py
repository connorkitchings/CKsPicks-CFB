#!/usr/bin/env python3
"""
Fresh scoring script - start from scratch approach
"""

import sys

sys.path.insert(0, "src")
import pandas as pd

from cfb_model.data.storage.local_storage import LocalStorage


def add_game_ids_if_missing(bets_df, games_df):
    """Add game_id column to betting report if missing"""
    if "game_id" in bets_df.columns:
        print("✅ game_id already present in betting report")
        return bets_df

    print("➡️ Adding game_id to betting report...")
    bets_with_ids = bets_df.copy()
    game_ids = []

    for _, row in bets_df.iterrows():
        game_str = row["Game"]
        if " @ " in game_str:
            away_team, home_team = game_str.split(" @ ", 1)

            # Find matching game
            match = games_df[
                (games_df["away_team"] == away_team)
                & (games_df["home_team"] == home_team)
            ]

            if len(match) == 1:
                game_ids.append(match.iloc[0]["id"])
            else:
                print(f"❌ Could not match: {game_str}")
                game_ids.append(None)
        else:
            game_ids.append(None)

    bets_with_ids["game_id"] = game_ids
    matches = sum(1 for gid in game_ids if gid is not None)
    print(f"✅ Matched {matches}/{len(game_ids)} games")
    return bets_with_ids


def parse_spread_line(spread_str, game_str):
    """Parse spread line from 'Team +/-X.X' format"""
    if pd.isna(spread_str) or spread_str == "":
        return None

    away_team, home_team = game_str.split(" @ ", 1)

    # Handle pick'em
    if spread_str.strip().upper() in ("PK", "PICK", "PICKEM"):
        return 0.0

    # Parse format like "South Florida -28.5"
    try:
        if home_team in spread_str:
            # Home team is mentioned
            parts = spread_str.split(home_team)
            if len(parts) > 1:
                line_part = parts[1].strip()
                if line_part.startswith("+"):
                    return float(line_part[1:])
                elif line_part.startswith("-"):
                    return -float(line_part[1:])
                else:
                    return float(line_part)
        elif away_team in spread_str:
            # Away team is mentioned, so home spread is opposite
            parts = spread_str.split(away_team)
            if len(parts) > 1:
                line_part = parts[1].strip()
                if line_part.startswith("+"):
                    return -float(line_part[1:])
                elif line_part.startswith("-"):
                    return float(line_part[1:])
                else:
                    return -float(line_part)
    except ValueError:
        pass

    return None


def score_bets(bets_df, games_df):
    """Score the bets against game results"""
    scored_df = bets_df.copy()

    # Parse spread and total lines
    scored_df["home_team_spread_line"] = scored_df.apply(
        lambda row: parse_spread_line(row.get("Spread", ""), row.get("Game", "")),
        axis=1,
    )
    scored_df["total_line"] = scored_df["Over/Under"].apply(
        lambda x: float(x) if pd.notna(x) and x != "" else None
    )

    # Add result columns
    scored_df["Spread Bet Result"] = "No Bet"
    scored_df["Total Bet Result"] = "No Bet"
    scored_df["Spread Result"] = None
    scored_df["Total Result"] = None

    for idx, row in scored_df.iterrows():
        game_id = row["game_id"]
        if pd.isna(game_id):
            continue

        # Find game result
        game_result = games_df[games_df["id"] == game_id]
        if len(game_result) == 0:
            continue

        game = game_result.iloc[0]

        # Check if game has scores (if it has scores, it's completed)
        if pd.isna(game.get("home_points")) or pd.isna(game.get("away_points")):
            if row["Spread Bet"] in ["home", "away"]:
                scored_df.at[idx, "Spread Bet Result"] = "Pending"
            if row["Total Bet"] in ["over", "under"]:
                scored_df.at[idx, "Total Bet Result"] = "Pending"
            continue

        home_points = float(game["home_points"])
        away_points = float(game["away_points"])

        # Calculate actual results
        spread_result = home_points - away_points  # positive = home wins by more
        total_result = home_points + away_points

        scored_df.at[idx, "Spread Result"] = spread_result
        scored_df.at[idx, "Total Result"] = total_result

        # Score spread bets
        if row["Spread Bet"] in ["home", "away"]:
            spread_line = row.get("home_team_spread_line", 0)
            if pd.isna(spread_line):
                scored_df.at[idx, "Spread Bet Result"] = "Pending"
            else:
                spread_line = float(spread_line)

                if row["Spread Bet"] == "home":
                    # Home bet wins if home covers the spread
                    # For negative spread (home favored): home wins if actual margin > |spread|
                    # For positive spread (home underdog): home wins if actual margin > spread
                    if spread_result > -spread_line:
                        scored_df.at[idx, "Spread Bet Result"] = "Win"
                    elif spread_result < -spread_line:
                        scored_df.at[idx, "Spread Bet Result"] = "Loss"
                    else:
                        scored_df.at[idx, "Spread Bet Result"] = "Push"
                else:  # away bet
                    # Away bet wins if home doesn't cover
                    # Away wins when actual margin < |spread| (for home favored)
                    if spread_result < -spread_line:
                        scored_df.at[idx, "Spread Bet Result"] = "Win"
                    elif spread_result > -spread_line:
                        scored_df.at[idx, "Spread Bet Result"] = "Loss"
                    else:
                        scored_df.at[idx, "Spread Bet Result"] = "Push"

        # Score total bets
        if row["Total Bet"] in ["over", "under"]:
            total_line = row.get("total_line", 0)
            if pd.isna(total_line):
                scored_df.at[idx, "Total Bet Result"] = "Pending"
            else:
                total_line = float(total_line)

                if row["Total Bet"] == "over":
                    if total_result > total_line:
                        scored_df.at[idx, "Total Bet Result"] = "Win"
                    elif total_result < total_line:
                        scored_df.at[idx, "Total Bet Result"] = "Loss"
                    else:
                        scored_df.at[idx, "Total Bet Result"] = "Push"
                else:  # under bet
                    if total_result < total_line:
                        scored_df.at[idx, "Total Bet Result"] = "Win"
                    elif total_result > total_line:
                        scored_df.at[idx, "Total Bet Result"] = "Loss"
                    else:
                        scored_df.at[idx, "Total Bet Result"] = "Push"

    return scored_df


def main():
    print("=== FRESH SCORING FROM SCRATCH ===")

    # 1. Load betting report
    print("\n1️⃣ Loading betting report...")
    bets_df = pd.read_csv("reports/2025/CFB_week6_bets.csv")
    print(f"   Loaded {len(bets_df)} total rows")

    spread_bets = len(bets_df[bets_df["Spread Bet"].isin(["home", "away"])])
    total_bets = len(bets_df[bets_df["Total Bet"].isin(["over", "under"])])
    print(f"   Found {spread_bets} spread bets, {total_bets} total bets")

    # 2. Load games data
    print("\n2️⃣ Loading games data...")
    storage = LocalStorage(
        data_root="/Volumes/CK SSD/Coding Projects/cfb_model",
        file_format="csv",
        data_type="raw",
    )
    game_records = storage.read_index("games", {"year": 2025})
    games_df = pd.DataFrame.from_records(game_records)

    # Get Week 6 games and remove duplicates
    week6_games = games_df[games_df["week"] == 6].drop_duplicates(subset=["id"])
    print(f"   Loaded {len(week6_games)} unique Week 6 games")

    completed_games = (week6_games["completed"] is True).sum()
    games_with_scores = week6_games["home_points"].notna().sum()
    print(f"   {completed_games} completed games, {games_with_scores} with scores")

    # 3. Add game_ids to betting report if needed
    print("\n3️⃣ Ensuring game_ids are present...")
    bets_with_ids = add_game_ids_if_missing(bets_df, week6_games)

    # 4. Score the bets
    print("\n4️⃣ Scoring bets...")
    scored_df = score_bets(bets_with_ids, week6_games)

    # 5. Validation
    print("\n5️⃣ Validation...")
    final_spread_bets = len(scored_df[scored_df["Spread Bet"].isin(["home", "away"])])
    final_total_bets = len(scored_df[scored_df["Total Bet"].isin(["over", "under"])])

    print(f"   Original: {spread_bets} spread, {total_bets} total")
    print(f"   Final: {final_spread_bets} spread, {final_total_bets} total")

    if final_spread_bets == spread_bets and final_total_bets == total_bets:
        print("✅ VALIDATION PASSED")
    else:
        print("❌ VALIDATION FAILED")

    # 6. Show results
    print("\n6️⃣ Results Summary...")
    spread_results = scored_df[scored_df["Spread Bet"].isin(["home", "away"])][
        "Spread Bet Result"
    ].value_counts()
    total_results = scored_df[scored_df["Total Bet"].isin(["over", "under"])][
        "Total Bet Result"
    ].value_counts()

    print("Spread Bets:")
    print(spread_results)
    print("\nTotal Bets:")
    print(total_results)

    # 7. Save result
    print("\n7️⃣ Saving...")
    # Remove game_id from final output for email
    final_df = scored_df.drop(
        columns=["game_id"] if "game_id" in scored_df.columns else []
    )
    final_df.to_csv("reports/2025/CFB_week6_bets_scored.csv", index=False)
    print("✅ Saved to reports/2025/CFB_week6_bets_scored.csv")


if __name__ == "__main__":
    main()
