import argparse
import sys

import pandas as pd

from src.config import get_data_root
from src.utils.local_storage import LocalStorage


def validate_ingestion(year: int):
    """
    Validate raw data ingestion for a given year.
    Checks 'games' and 'betting_lines' artifacts.
    """
    print(f"Validating ingestion for {year}...")
    data_root = get_data_root()
    raw_storage = LocalStorage(data_root=data_root, file_format="csv", data_type="raw")

    errors = []

    # 1. Validate Games
    games = raw_storage.read_index("games", {"year": year})
    if not games:
        errors.append(f"❌ [Games] No games found for {year}")
    else:
        df_games = pd.DataFrame(games)
        # Standardize ID if needed (some raw data uses 'id')
        if "id" in df_games.columns and "game_id" not in df_games.columns:
            df_games = df_games.rename(columns={"id": "game_id"})

        required_cols = [
            "game_id",
            "week",
            "home_team",
            "away_team",
            "home_points",
            "away_points",
        ]
        missing = [c for c in required_cols if c not in df_games.columns]
        if missing:
            errors.append(f"❌ [Games] Missing columns: {missing}")
        else:
            # Null checks
            if df_games[required_cols].isnull().any().any():
                null_counts = df_games[required_cols].isnull().sum()
                errors.append(
                    f"❌ [Games] Null values detected in required columns:\n{null_counts[null_counts > 0]}"
                )

            # Value checks
            if (df_games[["home_points", "away_points"]] < 0).any().any():
                errors.append("❌ [Games] Negative scores detected")

            # Duplicate check
            if df_games["game_id"].duplicated().any():
                dupes = df_games[df_games["game_id"].duplicated()]["game_id"].count()
                errors.append(f"❌ [Games] {dupes} duplicate game_ids found")

        print(f"✅ [Games] Checked {len(df_games)} records")

    # 2. Validate Betting Lines
    betting = raw_storage.read_index("betting_lines", {"year": year})
    if not betting:
        print(f"⚠️ [Betting] No betting lines found for {year} (Warning only)")
    else:
        df_bet = pd.DataFrame(betting)
        if "game_id" not in df_bet.columns:
            errors.append("❌ [Betting] Missing 'game_id' column")

        if "spread" in df_bet.columns:
            # Range check: Spreads usually between -70 and 70
            outliers = df_bet[(df_bet["spread"] < -70) | (df_bet["spread"] > 70)]
            if not outliers.empty:
                errors.append(
                    f"⚠️ [Betting] {len(outliers)} spread outliers detected (<-70 or >70)"
                )

        print(f"✅ [Betting] Checked {len(df_bet)} records")

    # Final Report
    if errors:
        print("\n🛑 VALIDATION FAILED:")
        for e in errors:
            print(e)
        sys.exit(1)
    else:
        print(f"\n✨ Validation passed for {year}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True, help="Year to validate")
    args = parser.parse_args()

    validate_ingestion(args.year)
