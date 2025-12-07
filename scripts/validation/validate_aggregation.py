import argparse
import sys

import pandas as pd

from src.config import get_data_root
from src.utils.local_storage import LocalStorage


def validate_aggregation(year: int):
    """
    Validate processed data aggregation for a given year.
    Checks 'team_week_adj' artifacts.
    """
    print(f"Validating aggregation for {year}...")
    data_root = get_data_root()
    processed_storage = LocalStorage(
        data_root=data_root, file_format="csv", data_type="processed"
    )

    errors = []

    # Load Team Stats
    stats = processed_storage.read_index("team_week_adj", {"year": year})
    if not stats:
        errors.append(f"❌ [Aggregation] No team stats found for {year}")
    else:
        df = pd.DataFrame(stats)

        # 1. Required Columns
        required_cols = [
            "team",
            "season",
            "week",
            "off_epa_pp",
            "def_epa_pp",
            "off_sr",
            "def_sr",
        ]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            errors.append(f"❌ [Aggregation] Missing columns: {missing}")

        # 2. Null Checks
        if not missing:
            if df[required_cols].isnull().any().any():
                null_counts = df[required_cols].isnull().sum()
                errors.append(
                    f"❌ [Aggregation] Null values in required columns:\n{null_counts[null_counts > 0]}"
                )

        # 3. Key Uniqueness
        if df.duplicated(subset=["team", "season", "week"]).any():
            dupes = df[df.duplicated(subset=["team", "season", "week"])].shape[0]
            errors.append(f"❌ [Aggregation] {dupes} duplicate team-season-weeks found")

        # 4. Outlier Detection (EPA per play usually between -1.0 and 1.0)
        # 3-sigma check or hard bounds? Let's use hard bounds for sanity first.
        epa_cols = ["off_epa_pp", "def_epa_pp"]
        for col in epa_cols:
            if col in df.columns:
                outliers = df[(df[col] < -1.5) | (df[col] > 1.5)]
                if not outliers.empty:
                    errors.append(
                        f"⚠️ [Aggregation] {len(outliers)} rows with extreme {col} values (<-1.5 or >1.5)"
                    )

        print(f"✅ [Aggregation] Checked {len(df)} records")

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

    validate_aggregation(args.year)
