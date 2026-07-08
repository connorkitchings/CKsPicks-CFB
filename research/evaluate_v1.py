import pandas as pd

from cks_picks_cfb.features.v1_pipeline import load_v1_data
from cks_picks_cfb.models.v1_baseline import V1BaselineModel


def run_evaluation():
    print("Loading Training Data (2019, 2021-2023)...")
    train_years = [2019, 2021, 2022, 2023]
    train_dfs = []
    for y in train_years:
        df = load_v1_data(y)
        if df is not None:
            train_dfs.append(df)

    if not train_dfs:
        print("No training data found.")
        return

    train_df = pd.concat(train_dfs, ignore_index=True)
    print(f"Training on {len(train_df)} games.")

    # Train
    model = V1BaselineModel()
    model.fit(train_df)

    # Test
    print("\nLoading Test Data (2024)...")
    test_df = load_v1_data(2024)
    if test_df is None or test_df.empty:
        print("No test data found for 2024.")
        return

    print(f"Testing on {len(test_df)} games.")
    metrics = model.evaluate(test_df)

    print("\n=== V1 Baseline Results (2024) ===")
    print(f"RMSE: {metrics['rmse']:.4f}")
    print(f"MAE:  {metrics['mae']:.4f}")

    # Win Rate vs Closing Line (if available)
    # We need to load betting lines separately or ensure they are in the raw data
    # For now, just RMSE/MAE is a good start for "Day 1"


if __name__ == "__main__":
    run_evaluation()
