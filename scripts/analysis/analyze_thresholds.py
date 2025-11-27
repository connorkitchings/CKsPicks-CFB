import glob
from pathlib import Path

import numpy as np
import pandas as pd


def analyze_thresholds(year=2025):
    """
    Analyze win rates and volume at different edge thresholds for Spreads and Totals.
    """
    scored_dir = Path(f"artifacts/reports/{year}/scored")
    pattern = str(scored_dir / "CFB_week*_bets_scored.csv")
    paths = [Path(p) for p in glob.glob(pattern)]

    if not paths:
        print(f"No scored files found for {year}")
        return

    frames = []
    for p in paths:
        try:
            df = pd.read_csv(p)
            if not df.empty:
                # Infer week if missing (for consistency, though 2025 has it mostly)
                if "Week" not in df.columns and "week" not in df.columns:
                    if "_week" in p.name:
                        w_part = p.name.split("_week")[1].split("_")[0]
                        df["Week"] = int(w_part)
                frames.append(df)
        except Exception:
            pass

    if not frames:
        print("No data loaded.")
        return

    df = pd.concat(frames, ignore_index=True)

    # Coalesce Week
    if "Week" in df.columns and "week" in df.columns:
        df["Week"] = df["Week"].fillna(df["week"])

    print(f"Loaded {len(df)} rows for {year}")

    # --- Spread Analysis ---
    print("\n--- Spread Threshold Analysis ---")
    print(
        f"{'Threshold':<10} | {'Record':<12} | {'Win %':<8} | {'Volume':<6} | {'ROI':<6}"
    )
    print("-" * 55)

    # Ensure numeric
    cols = ["Spread Prediction", "home_team_spread_line", "home_points", "away_points"]
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df["edge_spread"] = abs(df["Spread Prediction"] - (-df["home_team_spread_line"]))

    # Sim Result
    df["bet_side_spread"] = np.where(
        df["Spread Prediction"] > -df["home_team_spread_line"], "home", "away"
    )
    df["margin"] = df["home_points"] - df["away_points"]
    df["cover_margin"] = df["margin"] + df["home_team_spread_line"]

    conditions = [
        (df["bet_side_spread"] == "home") & (df["cover_margin"] > 0),
        (df["bet_side_spread"] == "home") & (df["cover_margin"] < 0),
        (df["bet_side_spread"] == "away") & (df["cover_margin"] < 0),
        (df["bet_side_spread"] == "away") & (df["cover_margin"] > 0),
    ]
    choices = ["Win", "Loss", "Win", "Loss"]
    df["sim_spread_result"] = np.select(conditions, choices, default="Push")

    for thresh in np.arange(0.0, 10.5, 0.5):
        subset = df[df["edge_spread"] >= thresh]
        wins = len(subset[subset["sim_spread_result"] == "Win"])
        losses = len(subset[subset["sim_spread_result"] == "Loss"])
        pushes = len(subset[subset["sim_spread_result"] == "Push"])
        total = wins + losses
        win_rate = (wins / total * 100) if total > 0 else 0.0
        volume = len(subset)

        # Simple ROI (assuming -110 odds -> win 0.909, loss -1)
        net_units = (wins * 0.909) - losses
        roi = (net_units / total * 100) if total > 0 else 0.0

        print(
            f"{thresh:<10.1f} | {wins}-{losses}-{pushes:<5} | {win_rate:<7.1f}% | {volume:<6} | {roi:+.1f}%"
        )

    # --- Total Analysis ---
    print("\n--- Total Threshold Analysis ---")
    print(
        f"{'Threshold':<10} | {'Record':<12} | {'Win %':<8} | {'Volume':<6} | {'ROI':<6}"
    )
    print("-" * 55)

    cols_t = ["Total Prediction", "total_line"]
    for c in cols_t:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df["edge_total"] = abs(df["Total Prediction"] - df["total_line"])

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

    for thresh in np.arange(0.0, 15.5, 0.5):
        subset = df[df["edge_total"] >= thresh]
        wins = len(subset[subset["sim_total_result"] == "Win"])
        losses = len(subset[subset["sim_total_result"] == "Loss"])
        pushes = len(subset[subset["sim_total_result"] == "Push"])
        total = wins + losses
        win_rate = (wins / total * 100) if total > 0 else 0.0
        volume = len(subset)

        net_units = (wins * 0.909) - losses
        roi = (net_units / total * 100) if total > 0 else 0.0

        print(
            f"{thresh:<10.1f} | {wins}-{losses}-{pushes:<5} | {win_rate:<7.1f}% | {volume:<6} | {roi:+.1f}%"
        )


if __name__ == "__main__":
    analyze_thresholds()
