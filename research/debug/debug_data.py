from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cks_picks_cfb.config import DATA_ROOT
from cks_picks_cfb.utils.local_storage import LocalStorage


def main():
    data_root = (
        os.getenv("CFB_DATA_ROOT") or os.getenv("CFB_MODEL_DATA_ROOT") or str(DATA_ROOT)
    )
    storage = LocalStorage(
        data_root=data_root, file_format="csv", data_type="processed"
    )
    records = storage.read_index("team_game", {"year": 2019, "week": 1})
    if records:
        print(f"Successfully read {len(records)} records.")
    else:
        print("No records found.")


if __name__ == "__main__":
    main()
