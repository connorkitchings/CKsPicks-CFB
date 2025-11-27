import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import get_data_root
from src.features.byplay import allplays_to_byplay
from src.features.core import aggregate_drives
from src.utils.local_storage import LocalStorage


def debug_aggregation(year: int, data_root: str | None):
    """
    Debugs the aggregation pipeline by inspecting the intermediate drives_df.
    """
    print(f"--- Debugging aggregation for year {year} ---")

    raw_storage = LocalStorage(data_root=data_root, file_format="csv", data_type="raw")
    records = raw_storage.read_index("plays", {"year": year})
    if not records:
        print(f"No raw plays found for season {year} under {raw_storage.root()}")
        return

    plays_df = pd.DataFrame.from_records(records)
    if "season" not in plays_df.columns:
        plays_df["season"] = int(year)
    if "week" not in plays_df.columns:
        print("Raw plays are missing required 'week' column for partitioning.")
        return

    byplay_df = allplays_to_byplay(plays_df)
    drives_df = aggregate_drives(byplay_df)

    print("--- Drives DataFrame Head ---")
    print(drives_df.head())
    print("\n--- Drives DataFrame Info ---")
    drives_df.info()
    print("\n--- Duplicate Drive Check (same game_id and drive_number) ---")
    duplicate_drives = drives_df[
        drives_df.duplicated(subset=["game_id", "drive_number"], keep=False)
    ]
    if not duplicate_drives.empty:
        print(duplicate_drives)
    else:
        print("No duplicate drives found.")


if __name__ == "__main__":
    data_root = get_data_root()
    debug_aggregation(2024, data_root)
