import glob

import numpy as np
import pandas as pd


def recalculate_stats():
    # Define thresholds
    spread_threshold = 0.0
    total_threshold = 5.0

    print(
        f"Recalculating stats with Spread >= {spread_threshold}, Total >= {total_threshold}"
    )

    def process_season(year, files):
        if not files:
            print(f"No files for {year}")
            return

        df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
        print(f"Total games loaded for {year}: {len(df)}")

        # --- Spread Logic ---
        # Edge = abs(Pred - (-Line))
        # Bet Home if Pred > -Line
        # Bet Away if Pred < -Line

        # Ensure columns are numeric
        df["Spread Prediction"] = pd.to_numeric(
            df["Spread Prediction"], errors="coerce"
        )
        df["home_team_spread_line"] = pd.to_numeric(
            df["home_team_spread_line"], errors="coerce"
        )
        df["home_points"] = pd.to_numeric(df["home_points"], errors="coerce")
        df["away_points"] = pd.to_numeric(df["away_points"], errors="coerce")

        # Calculate Edge
        # Note: CSV might already have edge_spread, but let's re-calc to be safe or use existing if reliable
        # Using existing edge_spread if available as it matches the model's exact logic
        if "edge_spread" in df.columns:
            df["calc_edge_spread"] = df["edge_spread"]
        else:
            df["calc_edge_spread"] = abs(
                df["Spread Prediction"] - (-df["home_team_spread_line"])
            )

        # Determine Bet Side
        # Pred > -Line => Home is "better" than Line implies => Bet Home
        # Example: Line -5.5. -Line = 5.5. Pred 5.12. 5.12 < 5.5. Bet Away. Correct.
        # Example: Line 10.5. -Line = -10.5. Pred -4.26. -4.26 > -10.5. Bet Home. Correct.
        df["bet_side_spread"] = np.where(
            df["Spread Prediction"] > -df["home_team_spread_line"], "home", "away"
        )

        # Determine Result
        # Margin = Home - Away
        # Home Cover if Margin + Line > 0
        df["margin"] = df["home_points"] - df["away_points"]
        df["cover_margin"] = df["margin"] + df["home_team_spread_line"]

        conditions = [
            (df["bet_side_spread"] == "home") & (df["cover_margin"] > 0),
            (df["bet_side_spread"] == "home") & (df["cover_margin"] < 0),
            (df["bet_side_spread"] == "away")
            & (
                df["cover_margin"] < 0
            ),  # Away wins if Home fails to cover (margin+line < 0)
            (df["bet_side_spread"] == "away") & (df["cover_margin"] > 0),
        ]
        choices = ["Win", "Loss", "Win", "Loss"]
        df["sim_spread_result"] = np.select(conditions, choices, default="Push")

        # Filter by Threshold
        spread_bets = df[df["calc_edge_spread"] >= spread_threshold]

        s_wins = len(spread_bets[spread_bets["sim_spread_result"] == "Win"])
        s_losses = len(spread_bets[spread_bets["sim_spread_result"] == "Loss"])
        s_pushes = len(spread_bets[spread_bets["sim_spread_result"] == "Push"])
        s_total = s_wins + s_losses + s_pushes
        s_rate = s_wins / (s_wins + s_losses) if (s_wins + s_losses) > 0 else 0.0

        print(
            f"Spread: {s_rate:.1%} ({s_total} bets) - {s_wins}W-{s_losses}L-{s_pushes}P"
        )

        # --- Total Logic ---
        df["Total Prediction"] = pd.to_numeric(df["Total Prediction"], errors="coerce")
        df["total_line"] = pd.to_numeric(df["total_line"], errors="coerce")

        if "edge_total" in df.columns:
            df["calc_edge_total"] = df["edge_total"]
        else:
            df["calc_edge_total"] = abs(df["Total Prediction"] - df["total_line"])

        df["bet_side_total"] = np.where(
            df["Total Prediction"] > df["total_line"], "over", "under"
        )

        df["total_score"] = df["home_points"] + df["away_points"]

        conditions_t = [
            (df["bet_side_total"] == "over") & (df["total_score"] > df["total_line"]),
            (df["bet_side_total"] == "over") & (df["total_score"] < df["total_line"]),
            (df["bet_side_total"] == "under") & (df["total_score"] < df["total_line"]),
            (df["bet_side_total"] == "under") & (df["total_score"] > df["total_line"]),
        ]
        choices_t = ["Win", "Loss", "Win", "Loss"]
        df["sim_total_result"] = np.select(conditions_t, choices_t, default="Push")

        total_bets = df[df["calc_edge_total"] >= total_threshold]

        t_wins = len(total_bets[total_bets["sim_total_result"] == "Win"])
        t_losses = len(total_bets[total_bets["sim_total_result"] == "Loss"])
        t_pushes = len(total_bets[total_bets["sim_total_result"] == "Push"])
        t_total = t_wins + t_losses + t_pushes
        t_rate = t_wins / (t_wins + t_losses) if (t_wins + t_losses) > 0 else 0.0

        print(
            f"Total:  {t_rate:.1%} ({t_total} bets) - {t_wins}W-{t_losses}L-{t_pushes}P"
        )

    # --- 2025 ---
    print("\n--- 2025 Stats (Recalculated) ---")
    files_2025 = glob.glob("artifacts/reports/2025/scored/CFB_week*_bets_scored.csv")
    process_season(2025, files_2025)

    # --- 2024 ---
    print("\n--- 2024 Stats (Recalculated) ---")
    files_2024 = glob.glob("artifacts/reports/2024/scored/CFB_week*_bets_scored.csv")
    process_season(2024, files_2024)


if __name__ == "__main__":
    recalculate_stats()
