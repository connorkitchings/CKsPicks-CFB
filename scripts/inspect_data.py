import pandas as pd

from cks_picks_cfb.config import get_data_root
from cks_picks_cfb.utils.local_storage import LocalStorage


def inspect_columns():
    data_root = get_data_root()
    processed_storage = LocalStorage(
        data_root=data_root, file_format="csv", data_type="processed"
    )

    # Load 2023 stats
    team_stats = processed_storage.read_index("team_season_adj", {"year": 2023})
    if not team_stats:
        print("No stats found for 2023")
        return

    df = pd.DataFrame(team_stats)
    print("Columns found in team_season_adj:")
    for c in sorted(df.columns):
        print(c)


if __name__ == "__main__":
    inspect_columns()
