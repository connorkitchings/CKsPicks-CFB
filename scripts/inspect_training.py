import numpy as np
import pandas as pd

from cks_picks_cfb.features.v1_pipeline import load_v1_data


def inspect_training_data():
    print("Loading Training Data (2019, 2021-2023)...")
    train_years = [2019, 2021, 2022, 2023]
    dfs = []
    for y in train_years:
        df = load_v1_data(y)
        if df is not None:
            dfs.append(df)

    if not dfs:
        return

    df = pd.concat(dfs, ignore_index=True)

    features = [
        "home_adj_off_epa_pp",
        "home_adj_def_epa_pp",
        "away_adj_off_epa_pp",
        "away_adj_def_epa_pp",
    ]

    print("\nTraining Feature Statistics:")
    print(df[features].describe())

    print("\nCheck for Infinite Values:")
    print(np.isinf(df[features]).sum())

    print("\nCheck for NaNs:")
    print(df[features].isna().sum())


if __name__ == "__main__":
    inspect_training_data()
