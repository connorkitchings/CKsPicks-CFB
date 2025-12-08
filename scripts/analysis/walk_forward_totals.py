import pandas as pd

from src.features.v2_recency import load_v2_recency_data
from src.models.v1_baseline import V1BaselineModel


def run_validation():
    print("=== Walk-Forward Validation: Totals (Matchup V1) ===")

    # Configuration
    ALPHA = 0.3
    HOLDOUT_YEARS = [2021, 2022, 2023, 2024]

    # Feature Set (from matchup_v1.yaml)
    FEATURES = [
        "home_adj_off_epa_pp",
        "home_adj_def_epa_pp",
        "home_adj_off_sr",
        "home_adj_def_sr",
        "away_adj_off_epa_pp",
        "away_adj_def_epa_pp",
        "away_adj_off_sr",
        "away_adj_def_sr",
        "home_adj_off_rush_ypp",
        "home_adj_def_rush_ypp",
        "home_adj_off_pass_ypp",
        "home_adj_def_pass_ypp",
        "away_adj_off_rush_ypp",
        "away_adj_def_rush_ypp",
        "away_adj_off_pass_ypp",
        "away_adj_def_pass_ypp",
    ]

    TARGET = "total_target"

    # Results storage
    results = []

    for test_year in HOLDOUT_YEARS:
        print(f"\nProcessing Holdout Year: {test_year}")

        # Define training years (All available years PRIOR to test_year, excluding 2020)
        # Assuming available years are 2019, 2021, 2022, 2023, 2024
        all_years = [2019, 2021, 2022, 2023, 2024]
        train_years = [y for y in all_years if y < test_year and y != 2020]

        if not train_years:
            print(f"Skipping {test_year}: No training data available.")
            continue

        print(f"  Training on: {train_years}")

        # Load Training Data
        train_dfs = []
        for ty in train_years:
            try:
                # Assuming alpha=0.3 consistent with Matchup V1 config
                df = load_v2_recency_data(ty, alpha=ALPHA)
                if df is not None:
                    train_dfs.append(df)
            except Exception as e:
                print(f"  Error loading {ty}: {e}")

        if not train_dfs:
            print("  Failed to load any training data.")
            continue

        train_df = pd.concat(train_dfs, ignore_index=True)
        print(f"  Train Size: {len(train_df)} games")

        # Load Test Data
        try:
            test_df = load_v2_recency_data(test_year, alpha=ALPHA)
        except Exception as e:
            print(f"  Error loading test data {test_year}: {e}")
            continue

        if test_df is None or test_df.empty:
            print("  No test data.")
            continue

        print(f"  Test Size: {len(test_df)} games")

        # Train Model
        model = V1BaselineModel(alpha=1.0, features=FEATURES, target=TARGET)
        model.fit(train_df)

        # Evaluate
        # We need to manually calculate ROI with 0.5 threshold if evaluate() doesn't support custom thresholds yet
        # But evaluate() in V1BaselineModel calculates hit_rate/roi at standard metrics.
        # However, for Totals, the decision log mentions "0.5 pt threshold".
        # The standard evaluate() likely uses 0 threshold (simple > line).
        # We should calculate strict ROI with the optimal threshold (0.5).

        preds = model.predict(test_df)
        actuals = test_df[TARGET]
        lines = test_df["total_line"] if "total_line" in test_df.columns else None

        metric_row = {"year": test_year}

        if lines is not None:
            # Calculate betting Performance with threshold=0.5
            THRESHOLD = 0.5

            # Bet Over: Pred > Line + Threshold
            bet_over = preds > (lines + THRESHOLD)
            # Bet Under: Pred < Line - Threshold
            bet_under = preds < (lines - THRESHOLD)

            outcome_over = actuals > lines
            outcome_under = actuals < lines
            # Push = actuals == lines (not counted in wins/losses)

            wins_over = (bet_over & outcome_over).sum()
            losses_over = (bet_over & outcome_under).sum()

            wins_under = (bet_under & outcome_under).sum()
            losses_under = (bet_under & outcome_over).sum()

            total_wins = wins_over + wins_under
            total_losses = losses_over + losses_under
            total_bets = total_wins + total_losses

            if total_bets > 0:
                hit_rate = total_wins / total_bets
                profit_units = (total_wins * 0.9091) - total_losses
                roi = profit_units / total_bets
            else:
                hit_rate = 0.0
                profit_units = 0.0
                roi = 0.0

            metric_row["bets"] = total_bets
            metric_row["hit_rate"] = hit_rate
            metric_row["roi"] = roi
            metric_row["profit"] = profit_units

            print(f"  Bets: {total_bets} | Hit Rate: {hit_rate:.1%} | ROI: {roi:.2%}")
        else:
            print("  No betting lines found for ROI calc.")

        results.append(metric_row)

    # Summary
    print("\n=== Summary Results ===")
    res_df = pd.DataFrame(results)
    if not res_df.empty:
        print(res_df.to_markdown(index=False, floatfmt=".2%"))

        # Check stability gate
        positive_years = res_df[res_df["roi"] > 0]
        print(f"\nPositive ROI Years: {len(positive_years)}/{len(res_df)}")
        avg_roi = res_df["roi"].mean()
        print(f"Average ROI: {avg_roi:.2%}")


if __name__ == "__main__":
    run_validation()
