from pathlib import Path

import pandas as pd


def verify_ats():
    root = Path("artifacts/reports/2024/scored")
    all_files = list(root.glob("*.csv"))

    if not all_files:
        print("No scored files found.")
        return

    print(f"Found {len(all_files)} scored files. Processing...")

    dfs = []
    for f in all_files:
        try:
            df = pd.read_csv(f)
            dfs.append(df)
        except Exception as e:
            print(f"Error reading {f}: {e}")

    full_df = pd.concat(dfs, ignore_index=True)

    # Columns check
    required = [
        "home_points",
        "away_points",
        "home_team_spread_line",
        "Spread Prediction",
    ]
    if not all(col in full_df.columns for col in required):
        print(f"Missing columns. Available: {full_df.columns.tolist()}")
        return

    # Filter valid games (completed games with lines)
    valid = full_df.dropna(subset=required).copy()

    # 1. Determine Actual Result
    # Home Margin = Home - Away
    valid["actual_margin"] = valid["home_points"] - valid["away_points"]

    # Result relative to spread (Home Perspective)
    # Line is usually negative for Home Fav (e.g. -7)
    # Home Cover if Actual Margin > -Line
    # e.g. Margin 10, Line -7. 10 > 7. Cover.
    # e.g. Margin 3, Line -7. 3 < 7. Loss.
    # Let's use "Cover Margin" = Actual Margin + Line
    # If > 0, Home Covers. If < 0, Away Covers.
    valid["cover_margin"] = valid["actual_margin"] + valid["home_team_spread_line"]

    # 2. Determine Model Pick
    # Pred Margin = Spread Prediction
    # Edge = Pred Margin + Line
    # If Edge > 0, Model expects Home to outperform line -> Pick Home
    valid["model_edge"] = valid["Spread Prediction"] + valid["home_team_spread_line"]

    # 3. Evaluate
    results = []

    # A. All Games (Model vs Line)
    # Exclude Pushes
    no_push = valid[valid["cover_margin"] != 0].copy()

    # Correct if (Edge > 0 AND Cover > 0) OR (Edge < 0 AND Cover < 0)
    # i.e. Signs match
    no_push["correct"] = (no_push["model_edge"] > 0) == (no_push["cover_margin"] > 0)

    ats_all_acc = no_push["correct"].mean()
    ats_all_count = len(no_push)

    # B. Bet Filtered (Using 'Spread Bet' column if available, or re-deriving)
    # The user mentioned "bet winner", implying we should check the high-confidence picks.
    # Let's check the 'Spread Bet' column logic if it exists
    if "Spread Bet" in valid.columns:
        # Filter for 'Home' or 'Away' bets
        bets = valid[valid["Spread Bet"].isin(["Home", "Away"])].copy()
        bets = bets[bets["cover_margin"] != 0]  # Exclude pushes

        # If Bet Home, Correct if Cover > 0
        # If Bet Away, Correct if Cover < 0
        bets["bet_correct"] = (
            (bets["Spread Bet"] == "Home") & (bets["cover_margin"] > 0)
        ) | ((bets["Spread Bet"] == "Away") & (bets["cover_margin"] < 0))

        bet_acc = bets["bet_correct"].mean()
        bet_count = len(bets)
    else:
        bet_acc = 0.0
        bet_count = 0

    # C. Straight Up Accuracy (for context)
    # Actual Winner: Margin > 0
    # Pred Winner: Pred > 0
    su_valid = valid[valid["actual_margin"] != 0]
    su_correct = (
        (su_valid["Spread Prediction"] > 0) == (su_valid["actual_margin"] > 0)
    ).mean()

    print("\n--- Independent Verification Results (2024 Scored Files) ---")
    print(f"Total Games Processed: {len(valid)}")
    print(f"Straight Up Accuracy: {su_correct:.4%}")
    print(f"ATS Accuracy (All Games): {ats_all_acc:.4%} ({ats_all_count} games)")
    if bet_count > 0:
        print(f"ATS Accuracy (Bets Only): {bet_acc:.4%} ({bet_count} bets)")
    else:
        print("No bets found in 'Spread Bet' column.")

    # Save detailed diagnostics
    no_push[
        [
            "home_team",
            "away_team",
            "home_team_spread_line",
            "Spread Prediction",
            "actual_margin",
            "model_edge",
            "cover_margin",
            "correct",
        ]
    ].to_csv("artifacts/validation/ats_verification_2024.csv", index=False)
    print(
        "Detailed diagnostics saved to artifacts/validation/ats_verification_2024.csv"
    )


if __name__ == "__main__":
    verify_ats()
