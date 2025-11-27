import glob
from pathlib import Path

import numpy as np
import pandas as pd

# Mock config
REPORTS_DIR = Path("artifacts/reports")
SCORED_SUBDIR = "scored"


def _season_subdir(report_dir: Path, year: int, subdir: str) -> Path:
    preferred = report_dir / str(year) / subdir
    if preferred.exists():
        return preferred
    return report_dir / str(year)


def debug_hit_rates(year=2025, up_to_week=14):
    report_dir = REPORTS_DIR
    scored_dir = _season_subdir(report_dir, year, SCORED_SUBDIR)
    print(f"Looking for scored files in: {scored_dir}")

    pattern = str(scored_dir / "CFB_week*_bets_scored.csv")
    paths = [Path(p) for p in glob.glob(pattern)]
    print(f"Found {len(paths)} files: {[p.name for p in paths]}")

    if not paths:
        print("No files found.")
        return

    frames = []
    for p in paths:
        try:
            df = pd.read_csv(p)
            print(f"  {p.name}: {len(df)} rows")
            frames.append(df)
        except Exception as e:
            print(f"  Error reading {p.name}: {e}")

    scored = pd.concat(frames, ignore_index=True)
    print(f"Total rows before filtering: {len(scored)}")

    print("Columns in concatenated DF:", scored.columns.tolist())

    if up_to_week is not None:
        # Coalesce Week and week
        if "Week" in scored.columns and "week" in scored.columns:
            print("Found both 'Week' and 'week'. Coalescing...")
            scored["Week"] = scored["Week"].fillna(scored["week"])
            week_col = "Week"
        elif "Week" in scored.columns:
            week_col = "Week"
        else:
            week_col = "week"
        if week_col in scored.columns:
            print(f"Week column '{week_col}' found.")
            print("Unique values in Week column:", scored[week_col].unique())
            week_numeric = pd.to_numeric(scored[week_col], errors="coerce")
            print("Unique numeric weeks:", week_numeric.unique())
            print("NaN weeks:", week_numeric.isna().sum())

            scored = scored[week_numeric <= up_to_week]
            print(f"Rows after week filtering (<= {up_to_week}): {len(scored)}")
        else:
            print(f"Warning: '{week_col}' column not found.")

    # Spread Logic
    spread_threshold = 0.0

    # Recalculate edge like publish_picks.py
    # Ensure numeric
    for col in [
        "Spread Prediction",
        "home_team_spread_line",
        "home_points",
        "away_points",
    ]:
        scored[col] = pd.to_numeric(scored[col], errors="coerce")

    scored["edge_spread"] = abs(
        scored["Spread Prediction"] - (-scored["home_team_spread_line"])
    )

    # Filter
    spread_bets = scored[scored["edge_spread"] >= spread_threshold]
    print(f"Spread Bets (Edge >= {spread_threshold}): {len(spread_bets)}")

    # Check for NaNs
    nans = (
        spread_bets[
            ["Spread Prediction", "home_team_spread_line", "home_points", "away_points"]
        ]
        .isnull()
        .sum()
    )
    print("NaNs in Spread Columns:\n", nans)

    # Simulate Result
    spread_bets["bet_side_spread"] = np.where(
        spread_bets["Spread Prediction"] > -spread_bets["home_team_spread_line"],
        "home",
        "away",
    )
    spread_bets["margin"] = spread_bets["home_points"] - spread_bets["away_points"]
    spread_bets["cover_margin"] = (
        spread_bets["margin"] + spread_bets["home_team_spread_line"]
    )

    conditions = [
        (spread_bets["bet_side_spread"] == "home") & (spread_bets["cover_margin"] > 0),
        (spread_bets["bet_side_spread"] == "home") & (spread_bets["cover_margin"] < 0),
        (spread_bets["bet_side_spread"] == "away") & (spread_bets["cover_margin"] < 0),
        (spread_bets["bet_side_spread"] == "away") & (spread_bets["cover_margin"] > 0),
    ]
    choices = ["Win", "Loss", "Win", "Loss"]
    spread_bets["sim_spread_result"] = np.select(conditions, choices, default="Push")

    print("Spread Results Breakdown:")
    print(spread_bets["sim_spread_result"].value_counts())

    # Total Logic
    total_threshold = 5.0
    scored["edge_total"] = abs(scored["Total Prediction"] - scored["total_line"])
    total_bets = scored[scored["edge_total"] >= total_threshold]
    print(f"\nTotal Bets (Edge >= {total_threshold}): {len(total_bets)}")

    # Simulate Result
    total_bets["bet_side_total"] = np.where(
        total_bets["Total Prediction"] > total_bets["total_line"], "over", "under"
    )
    total_bets["total_score"] = total_bets["home_points"] + total_bets["away_points"]

    conditions_t = [
        (total_bets["bet_side_total"] == "over")
        & (total_bets["total_score"] > total_bets["total_line"]),
        (total_bets["bet_side_total"] == "over")
        & (total_bets["total_score"] < total_bets["total_line"]),
        (total_bets["bet_side_total"] == "under")
        & (total_bets["total_score"] < total_bets["total_line"]),
        (total_bets["bet_side_total"] == "under")
        & (total_bets["total_score"] > total_bets["total_line"]),
    ]
    choices_t = ["Win", "Loss", "Win", "Loss"]
    total_bets["sim_total_result"] = np.select(conditions_t, choices_t, default="Push")

    print("Total Results Breakdown:")
    print(total_bets["sim_total_result"].value_counts())


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--week", type=int, default=14)
    args = parser.parse_args()
    debug_hit_rates(year=args.year, up_to_week=args.week)
