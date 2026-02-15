import argparse
import os
import sys
from pathlib import Path

import pandas as pd

# Add project root to path
sys.path.append(os.getcwd())
# noqa: E402
from cks_picks_cfb.config import get_data_root
from cks_picks_cfb.utils.local_storage import LocalStorage


def load_week_scores(year, week):
    data_root = get_data_root()
    raw = LocalStorage(data_root=data_root, file_format="csv", data_type="raw")

    # Load games to get scores
    games = pd.DataFrame.from_records(raw.read_index("games", {"year": year}))
    week_games = games[games["week"] == week].copy()

    # Ensure we have scores
    if (
        "home_points" not in week_games.columns
        or "away_points" not in week_games.columns
    ):
        print(f"Warning: No score columns found for Week {week}")
        return week_games

    # Filter to completed games (non-null scores)
    week_games = week_games.dropna(subset=["home_points", "away_points"])

    return week_games[["id", "home_points", "away_points"]]


def score_bets(bets_df, scores_df):
    # Merge scores
    scored = bets_df.merge(scores_df, left_on="game_id", right_on="id", how="left")

    # Calculate Results
    scored["home_margin"] = scored["home_points"] - scored["away_points"]
    scored["total_score"] = scored["home_points"] + scored["away_points"]

    # Spread Result (Home Margin - (-Line)) = Home Margin + Line
    # If > 0 => Home Cover
    # If < 0 => Away Cover
    # If = 0 => Push

    def get_spread_result(row):
        if pd.isna(row["home_points"]) or pd.isna(row["home_team_spread_line"]):
            return None

        margin = row["home_points"] - row["away_points"]
        line = row["home_team_spread_line"]
        cover_margin = margin + line

        bet_side = str(row.get("Spread Bet", "")).lower()

        if cover_margin > 0:
            return (
                "Win"
                if bet_side == "home"
                else "Loss"
                if bet_side == "away"
                else "No Bet"
            )
        elif cover_margin < 0:
            return (
                "Loss"
                if bet_side == "home"
                else "Win"
                if bet_side == "away"
                else "No Bet"
            )
        else:
            return "Push"

    def get_total_result(row):
        if pd.isna(row["total_score"]) or pd.isna(row["total_line"]):
            return None

        score = row["total_score"]
        line = row["total_line"]
        bet_side = str(row.get("Total Bet", "")).lower()

        if score > line:
            return (
                "Win"
                if bet_side == "over"
                else "Loss"
                if bet_side == "under"
                else "No Bet"
            )
        elif score < line:
            return (
                "Loss"
                if bet_side == "over"
                else "Win"
                if bet_side == "under"
                else "No Bet"
            )
        else:
            return "Push"

    scored["Spread Bet Result"] = scored.apply(get_spread_result, axis=1)
    scored["Total Bet Result"] = scored.apply(get_total_result, axis=1)

    # For compatibility with publish_review, add numeric results?
    # publish_review uses:
    # all_games_df["Spread Result"] + all_games_df["Total Result"] to reconstruct scores?
    # Wait, publish_review lines 248-253:
    # all_games_df["home_points"] = (all_games_df["Spread Result"] + all_games_df["Total Result"]) / 2
    # This implies "Spread Result" and "Total Result" in the CSV are actually the SCORES?
    # Let's check `publish_review.py` again.
    # It reads `bets_scored.csv`.
    # It calculates `home_points` and `away_points` FROM `Spread Result` and `Total Result`.
    # This is weird naming.
    # Let's look at `publish_review.py` lines 248-253 again.
    # home_points = (Spread Result + Total Result) / 2
    # away_points = (Total Result - Spread Result) / 2
    # This means:
    # Total Result = home + away
    # Spread Result = home - away
    # So "Spread Result" column should be the actual game margin (Home - Away).
    # And "Total Result" column should be the actual game total (Home + Away).

    scored["Spread Result"] = scored["home_margin"]
    scored["Total Result"] = scored["total_score"]

    return scored


def main():
    parser = argparse.ArgumentParser(description="Score Weekly Bets")
    parser.add_argument("--year", type=int, required=True, help="Season year")
    parser.add_argument("--week", type=int, required=True, help="Week number")
    args = parser.parse_args()

    year = args.year
    week = args.week

    print(f"Scoring bets for {year} Week {week}...")

    # Load Bets
    bets_dir = Path(f"data/production/predictions/{year}")
    bets_path = bets_dir / f"CFB_week{week}_bets.csv"

    if not bets_path.exists():
        print(f"No bets file found at {bets_path}")
        return

    bets_df = pd.read_csv(bets_path)

    # Load Scores
    scores_df = load_week_scores(year, week)
    if scores_df.empty:
        print(f"No scores available for Week {week}")
        return

    # Score
    scored_df = score_bets(bets_df, scores_df)

    # Save
    output_dir = Path(f"data/production/scored/{year}")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"CFB_week{week}_bets_scored.csv"

    scored_df.to_csv(output_path, index=False)
    print(f"Saved scored bets to {output_path}")


if __name__ == "__main__":
    main()
