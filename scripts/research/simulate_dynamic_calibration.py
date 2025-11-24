from pathlib import Path

import pandas as pd


def load_all_predictions(base_dir: Path) -> pd.DataFrame:
    """Load and concatenate all prediction CSVs."""
    files = sorted(base_dir.glob("*_predictions.csv"))
    dfs = []
    for f in files:
        df = pd.read_csv(f)
        dfs.append(df)

    if not dfs:
        raise FileNotFoundError(f"No prediction files found in {base_dir}")

    full_df = pd.concat(dfs, ignore_index=True)
    # Sort chronologically
    full_df = full_df.sort_values(["season", "week", "id"])
    return full_df


def calculate_betting_metrics(
    df: pd.DataFrame, pred_col: str, actual_col: str, threshold: float = 0.0
) -> dict:
    """Calculate Hit Rate and ROI for a given set of predictions."""
    # Betting logic: Bet if abs(pred) > threshold
    # For spread:
    #   If pred > threshold (Home favored by more than threshold), bet Home.
    #   If pred < -threshold (Away favored), bet Away.
    #   Note: spread_target is Home - Away.
    #   If pred > 0, we predict Home wins by X. If Line is 0 (implied), we bet Home.
    #   Wait, the 'pred' here is the *edge* relative to the line?
    #   No, the model predicts the score margin (Home - Away).
    #   The 'actual' is the actual score margin (Home - Away).
    #   The 'line' is usually built into the target or handled separately.
    #   In walk_forward_validation.py:
    #     week_predictions["spread_actual"] = y_test_spread
    #     week_predictions["spread_pred_..."] = preds
    #   And y_test_spread is typically (Home Score - Away Score) - Line?
    #   Let's verify what 'spread_target' is in the codebase.
    #   Usually spread_target = (Home - Away) + Spread. (If Spread is "Home -7", then Spread = -7).
    #   Let's assume standard "Edge" logic: Edge = Pred - Line.
    #   BUT, walk_forward_validation just logs "spread_actual" vs "spread_pred".
    #   If these are "Points-For" derived, then:
    #     spread_pred = Home_Pred - Away_Pred.
    #     spread_actual = Home_Actual - Away_Actual.
    #   This is the MARGIN, not the ATS margin.
    #   To get ATS results, we need the betting line.
    #   Does the prediction CSV contain the line?
    #   Let's check the columns in the CSV.

    #   If we don't have the line, we can't calculate ATS hit rate exactly unless 'spread_actual' IS the ATS margin.
    #   In `src/data/targets.py` or similar, spread_target is usually `home_score - away_score`.
    #   Wait, if we are predicting the SCORE, we need the LINE to bet.
    #   The walk_forward script saves: ["season", "week", "id", "home_team", "away_team", "spread_actual", "total_actual", "home_points_actual", "away_points_actual", preds...]
    #   It does NOT seem to save the betting line explicitly in the `week_predictions` DataFrame in `walk_forward_validation.py`.
    #   HOWEVER, `spread_target` might be the margin.
    #   If we don't have the line, we can assume the "Closing Line" was used to create the target?
    #   Actually, `load_point_in_time_data` returns a DF.
    #   Let's look at `src/models/features.py` or `src/features/targets.py` to see what `spread_target` is.
    #   If `spread_target` is just margin, we are missing the line.
    #   BUT, `walk_forward_validation.py` calculates metrics like RMSE on `spread_actual` vs `spread_pred`.
    #   If `spread_actual` is margin, then RMSE is margin error.
    #   To get ATS Hit Rate, we need the line.
    #
    #   CRITICAL CHECK: Does the CSV have the line?
    #   I will assume for now that I can't calculate exact betting ROI without the line,
    #   BUT I can calculate RMSE improvement.
    #   AND, if `spread_target` is the margin, then `Bias = Mean(Actual - Pred)`.
    #
    #   Wait, if I can't calculate Hit Rate, I can't fulfill the "Success Criteria".
    #   I need to check if the CSVs have the line.
    #   Let's peek at one CSV first.
    pass


def simulate_strategy(
    df: pd.DataFrame, window_size: int, is_std: bool = False
) -> pd.DataFrame:
    """
    Simulate dynamic calibration.

    Args:
        df: DataFrame sorted by date.
        window_size: Number of previous weeks to use for bias calc.
        is_std: If True, use Season-to-Date (expanding window) resetting each season.
    """
    # Calculate Residuals (Actual - Pred)
    # Positive Residual = Actual > Pred (Underprediction)
    # We want to ADD the bias to the pred to correct it.
    # Bias = Mean(Residuals)

    df = df.copy()
    df["residual"] = df["spread_actual"] - df["spread_pred_points_for_ensemble"]

    # We need to calculate the bias available at the START of each week.
    # So we group by (season, week) to get weekly average residuals,
    # then calculate the rolling mean of those weekly averages, shifted by 1.

    # 1. Calculate weekly mean residual
    weekly_bias = df.groupby(["season", "week"])["residual"].mean().reset_index()
    weekly_bias = weekly_bias.sort_values(["season", "week"])

    # 2. Calculate rolling/expanding bias
    if is_std:
        # Season-to-date: Group by season, expanding mean, shift 1
        weekly_bias["correction"] = weekly_bias.groupby("season")["residual"].transform(
            lambda x: x.expanding().mean().shift(1)
        )
    else:
        # Rolling window: Rolling mean, shift 1.
        # Note: This ignores season boundaries (carries over bias from previous season).
        # To respect season boundaries for fixed window, we would group by season.
        # Let's try BOTH: Global Rolling vs Seasonal Rolling.
        # For now, let's do Global Rolling as "Game Dynamics" might persist.
        weekly_bias["correction"] = (
            weekly_bias["residual"]
            .rolling(window=window_size, min_periods=1)
            .mean()
            .shift(1)
        )

    # 3. Merge correction back to games
    # Fill NA correction with 0 (no bias info yet)
    weekly_bias["correction"] = weekly_bias["correction"].fillna(0.0)

    df = df.merge(
        weekly_bias[["season", "week", "correction"]], on=["season", "week"], how="left"
    )

    # 4. Apply correction
    df["calibrated_pred"] = df["spread_pred_points_for_ensemble"] + df["correction"]

    return df


def main():
    base_dir = Path("artifacts/validation/walk_forward")
    output_dir = Path("artifacts/research/dynamic_calibration")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Loading predictions...")
    try:
        df = load_all_predictions(base_dir)
    except FileNotFoundError as e:
        print(e)
        return

    print(f"Loaded {len(df)} games from {df['season'].min()} to {df['season'].max()}")

    # Check for betting line
    # If 'spread_line' or similar exists, use it.
    # If not, we can only report RMSE improvement, not ATS Hit Rate.
    # Let's check columns.
    print(f"Columns: {df.columns.tolist()}")

    # Define strategies
    strategies = [
        {"name": "Baseline (No Calib)", "window": 0, "std": False},
        {"name": "Rolling 4 Weeks", "window": 4, "std": False},
        {"name": "Season-to-Date", "window": 0, "std": True},
    ]

    results = []

    for strat in strategies:
        print(f"Simulating {strat['name']}...")
        if strat["name"] == "Baseline (No Calib)":
            sim_df = df.copy()
            sim_df["calibrated_pred"] = sim_df["spread_pred_points_for_ensemble"]
            sim_df["correction"] = 0.0
        else:
            sim_df = simulate_strategy(df, strat["window"], strat["std"])

        # Calculate metrics by season
        for season, group in sim_df.groupby("season"):
            rmse = (
                (group["spread_actual"] - group["calibrated_pred"]) ** 2
            ).mean() ** 0.5
            bias = (group["spread_actual"] - group["calibrated_pred"]).mean()
            results.append(
                {
                    "Strategy": strat["name"],
                    "Season": season,
                    "RMSE": rmse,
                    "Bias": bias,
                    "Avg_Correction": group["correction"].abs().mean(),
                }
            )

        # Overall
        rmse = (
            (sim_df["spread_actual"] - sim_df["calibrated_pred"]) ** 2
        ).mean() ** 0.5
        bias = (sim_df["spread_actual"] - sim_df["calibrated_pred"]).mean()
        results.append(
            {
                "Strategy": strat["name"],
                "Season": "All",
                "RMSE": rmse,
                "Bias": bias,
                "Avg_Correction": sim_df["correction"].abs().mean(),
            }
        )

    results_df = pd.DataFrame(results)
    # Sort by Season, then Strategy
    results_df = results_df.sort_values(["Season", "Strategy"])
    print("\nResults by Year:")
    print(results_df.to_string())

    results_df.to_csv(
        output_dir / "calibration_simulation_results_by_year.csv", index=False
    )
    print(f"Saved results to {output_dir}")


if __name__ == "__main__":
    main()
