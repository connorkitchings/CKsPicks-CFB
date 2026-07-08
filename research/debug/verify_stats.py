import glob
from pathlib import Path

import pandas as pd


def verify_stats():
    # Define thresholds
    spread_threshold = 0.0
    total_threshold = 5.0

    print(
        f"Verifying stats with Spread >= {spread_threshold}, Total >= {total_threshold}"
    )

    # --- 2025 ---
    print("\n--- 2025 Stats ---")
    data_dir_2025 = Path("artifacts/reports/2025/scored")
    files_2025 = glob.glob(str(data_dir_2025 / "CFB_week*_bets_scored.csv"))
    print(
        f"Found {len(files_2025)} files for 2025: {[Path(f).name for f in files_2025]}"
    )

    if files_2025:
        df_2025 = pd.concat([pd.read_csv(f) for f in files_2025], ignore_index=True)
        print(f"Total bets loaded for 2025: {len(df_2025)}")

        # Filter Spreads
        spreads_2025 = df_2025[
            df_2025["Spread Bet"].astype(str).str.lower().isin(["home", "away"])
            & (df_2025["edge_spread"] >= spread_threshold)
        ]
        print(f"2025 Spread Bets (filtered): {len(spreads_2025)}")

        # Filter Totals
        totals_2025 = df_2025[
            df_2025["Total Bet"].astype(str).str.lower().isin(["over", "under"])
            & (df_2025["edge_total"] >= total_threshold)
        ]
        print(f"2025 Total Bets (filtered): {len(totals_2025)}")
    else:
        print("No files found for 2025.")

    # --- 2024 ---
    print("\n--- 2024 Stats ---")
    data_dir_2024 = Path("artifacts/reports/2024/scored")
    files_2024 = glob.glob(str(data_dir_2024 / "CFB_week*_bets_scored.csv"))
    print(f"Found {len(files_2024)} files for 2024.")

    if files_2024:
        df_2024 = pd.concat([pd.read_csv(f) for f in files_2024], ignore_index=True)
        print(f"Total bets loaded for 2024: {len(df_2024)}")

        # Filter Spreads
        spreads_2024 = df_2024[
            df_2024["Spread Bet"].astype(str).str.lower().isin(["home", "away"])
            & (df_2024["edge_spread"] >= spread_threshold)
        ]
        print(f"2024 Spread Bets (filtered): {len(spreads_2024)}")

        # Filter Totals
        totals_2024 = df_2024[
            df_2024["Total Bet"].astype(str).str.lower().isin(["over", "under"])
            & (df_2024["edge_total"] >= total_threshold)
        ]
        print(f"2024 Total Bets (filtered): {len(totals_2024)}")
    else:
        print("No files found for 2024.")


if __name__ == "__main__":
    verify_stats()
