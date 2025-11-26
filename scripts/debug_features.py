import sys
from pathlib import Path

from dotenv import load_dotenv

# Add src to path
sys.path.append(str(Path(__file__).resolve().parents[1]))
load_dotenv()

from src.config import get_data_root  # noqa: E402
from src.models.features import (  # noqa: E402
    load_point_in_time_data,
    load_weekly_team_features,
    prepare_team_features,
)


def main():
    year = 2024
    week = 2
    data_root = get_data_root()

    print(f"Loading data for {year} Week {week} from {data_root}...")

    # 1. Load raw team features
    team_features = load_weekly_team_features(
        year, week, data_root, adjustment_iteration=2
    )
    if team_features is None:
        print("Error: team_features is None")
        return

    print(f"\nTeam Features Columns ({len(team_features.columns)}):")
    print([c for c in team_features.columns if "plays" in c or "luck" in c])

    # 2. Prepare team features
    prepared = prepare_team_features(team_features)
    print(f"\nPrepared Features Columns ({len(prepared.columns)}):")
    print([c for c in prepared.columns if "plays" in c or "luck" in c])

    # 3. Load merged point-in-time data
    merged = load_point_in_time_data(year, week, data_root)
    if merged is None:
        print("Error: merged is None")
        return

    print(f"\nMerged Columns ({len(merged.columns)}):")
    print([c for c in merged.columns if "tempo" in c or "plays" in c])


if __name__ == "__main__":
    main()
