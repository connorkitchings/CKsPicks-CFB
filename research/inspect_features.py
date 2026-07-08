import numpy as np

from cks_picks_cfb.features.v1_pipeline import load_v1_data


def inspect_features():
    print("Loading 2024 Data...")
    df = load_v1_data(2024)
    if df is None:
        return

    features = [
        "home_adj_off_epa_pp",
        "home_adj_def_epa_pp",
        "away_adj_off_epa_pp",
        "away_adj_def_epa_pp",
    ]

    print("\nFeature Statistics:")
    print(df[features].describe())

    print("\nCheck for Infinite Values:")
    print(np.isinf(df[features]).sum())

    print("\nCheck for NaNs:")
    print(df[features].isna().sum())


if __name__ == "__main__":
    inspect_features()
