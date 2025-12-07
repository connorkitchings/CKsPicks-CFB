import argparse
import sys

import numpy as np

from src.features.v1_pipeline import load_v1_data


def validate_features(year: int):
    """
    Validate engineered features for a given year.
    Loads data via v1_pipeline (mimicking training) and checks integrity.
    """
    print(f"Validating features for {year}...")

    errors = []

    # Load Data (default features = adj + raw typically)
    # We load 'Unadjusted' features to start, or we can check the default set.
    # v1_pipeline load_v1_data defaults to legacy adjusted unless specified.
    # Let's check with NO features specified (gets whatever load_v1_data gives, typically 'team_week_adj' columns)

    try:
        df = load_v1_data(year)
    except Exception as e:
        print(f"❌ [Features] Failed to load data: {e}")
        sys.exit(1)

    if df is None or df.empty:
        errors.append(f"❌ [Features] No data loaded for {year}")
    else:
        # Check integrity of the MERGED dataset (Game + Home Stats + Away Stats)

        # 1. Target Integrity
        if "spread_target" not in df.columns:
            errors.append("❌ [Features] Missing 'spread_target' column after merge")
        else:
            if df["spread_target"].isnull().any():
                n = df["spread_target"].isnull().sum()
                errors.append(f"❌ [Features] {n} rows with missing spread_target")

        # 2. Feature Columns Check (Basic V1/V2 features)
        # load_v1_data default returns ADJUSTED features (legacy/Phase 1 fallback)
        # So we expect 'home_adj_off_epa_pp' etc.
        expected_bases = [
            "home_adj_off_epa_pp",
            "home_adj_def_epa_pp",
            "away_adj_off_epa_pp",
            "away_adj_def_epa_pp",
        ]
        # These might be named differently depending on what load_v1_data defaults to.
        # But 'minimal_unadjusted_v1' expects these.

        missing = [c for c in expected_bases if c not in df.columns]
        if missing:
            # This might not be an error if we loaded different features, but for validation we want to know.
            # Actually load_v1_data without args loads everything present in team_week_adj.
            # So if they are missing from team_week_adj, that's an Issue.
            errors.append(f"⚠️ [Features] Expected base features missing: {missing}")
        else:
            # Infinite / NaN checks
            if (
                df[expected_bases]
                .replace([np.inf, -np.inf], np.nan)
                .isnull()
                .any()
                .any()
            ):
                errors.append(
                    "❌ [Features] NaN or Infinite values found in base features"
                )

        # 3. Correlation Check (Sanity)
        # Home Off EPA should correlate positively with Home Points
        if "home_points" in df.columns and "home_off_epa_pp" in df.columns:
            corr = (
                df["home_points"]
                .astype(float)
                .corr(df["home_off_epa_pp"].astype(float))
            )
            if corr < 0.2:  # Loose threshold
                errors.append(
                    f"⚠️ [Features] Suspiciously low correlation ({corr:.2f}) between home_points and home_off_epa_pp"
                )

        print(f"✅ [Features] Checked {len(df)} records")

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

    validate_features(args.year)
