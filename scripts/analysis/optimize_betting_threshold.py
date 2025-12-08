import hydra
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from omegaconf import DictConfig

from src.train import get_model, load_and_prepare_data


def run_threshold_analysis(model, df: pd.DataFrame, target: str):
    """
    Analyzes ROI across different betting thresholds.

    Args:
        model: A trained model with a .predict() method.
        df: The test dataframe with actuals and betting lines.
        target: The target column name ('spread_target' or 'total_target').
    """
    print(f"Analyzing thresholds for target: {target}...")

    # Ensure line column exists
    line_col = "spread_line" if target == "spread_target" else "total_line"
    if line_col not in df.columns:
        raise ValueError(f"Missing required column for analysis: {line_col}")

    # Get predictions
    preds = model.predict(df)
    vegas_line = df[line_col]

    # For totals, vegas_line is the total. For spreads, it's the home spread.
    # The 'preds' are always the predicted home-away margin.
    # We need to convert spread preds to a total prediction if that's the target.
    # THIS IS A FLAW. The model should be trained on the correct target.
    # Assuming the model passed in was trained on the correct target.

    # Let's define the model's edge
    edge = np.abs(preds - vegas_line)

    thresholds = np.arange(0, 10.5, 0.5)
    results = []

    for thresh in thresholds:
        # Filter for bets that meet the threshold
        bet_df = df[edge >= thresh]
        if len(bet_df) == 0:
            results.append(
                {
                    "threshold": thresh,
                    "n_bets": 0,
                    "hit_rate": 0,
                    "roi": 0,
                }
            )
            continue

        bet_preds = model.predict(bet_df)
        bet_actuals = bet_df[target]
        bet_vegas_line = bet_df[line_col]

        if target == "spread_target":
            # Simplified logic from baseline model
            vegas_margin = -1 * bet_vegas_line
            bet_home = bet_preds > vegas_margin
            away_cover = bet_actuals < vegas_margin
            home_cover = bet_actuals > vegas_margin
            bet_away = bet_preds < vegas_margin

            wins = (bet_home & home_cover) | (bet_away & away_cover)
            losses = (bet_home & away_cover) | (bet_away & home_cover)

        elif target == "total_target":
            bet_over = bet_preds > bet_vegas_line
            bet_under = bet_preds < bet_vegas_line

            outcome_over = bet_actuals > bet_vegas_line
            outcome_under = bet_actuals < bet_vegas_line

            wins = (bet_over & outcome_over) | (bet_under & outcome_under)
            losses = (bet_over & outcome_under) | (bet_under & outcome_over)

        n_bets = wins.sum() + losses.sum()
        if n_bets > 0:
            hit_rate = wins.sum() / n_bets
            profit = (wins.sum() * 0.90909) - losses.sum()
            roi = profit / n_bets
        else:
            hit_rate = 0
            roi = 0

        results.append(
            {
                "threshold": thresh,
                "n_bets": n_bets,
                "hit_rate": hit_rate,
                "roi": roi,
                "total_profit": roi * n_bets,
            }
        )

    return pd.DataFrame(results)


@hydra.main(config_path="../../conf", config_name="config", version_base="1.2")
def main(cfg: DictConfig):
    """
    Main function to run threshold optimization.
    Takes a trained model and a test set, and outputs a plot of ROI vs. threshold.
    """
    # --- 1. Load Data & Model ---
    # For this analysis, we only need the test data.
    # We can reuse the training pipeline functions.
    print("Loading test data...")
    # This is inefficient as it loads all training data, but reuses code.
    # A future refactor could make a "load_test_data" function.
    _, test_df = load_and_prepare_data(cfg)

    print("Initializing model...")
    # Sort features to match the order used in training
    features = sorted(list(cfg.features.groups))
    model = get_model(cfg, feature_override=features)

    print("Loading trained model weights...")
    from src.config import get_repo_root

    # Use absolute path relative to repo root
    model_dir = get_repo_root() / "models"
    model_path = model_dir / f"{cfg.model.name}_{cfg.model.target}.joblib"
    if not model_path.exists():
        print(f"ERROR: Model not found at {model_path}. Please train the model first.")
        return

    model.load(model_path)

    # --- 2. Run Analysis ---
    analysis_df = run_threshold_analysis(model, test_df, target=cfg.model.target)

    # --- 3. Report & Plot ---
    print("--- Threshold Analysis Results ---")
    print(analysis_df.to_string())

    # Find best threshold for ROI
    best_roi = analysis_df.loc[analysis_df["roi"].idxmax()]
    print("\n--- Best Threshold (Max ROI) ---")
    print(best_roi)

    # Find best threshold for Total Profit
    best_profit = analysis_df.loc[analysis_df["total_profit"].idxmax()]
    print("\n--- Best Threshold (Max Total Profit) ---")
    print(best_profit)

    # Plot
    fig, ax1 = plt.subplots(figsize=(12, 7))

    # ROI plot
    ax1.plot(analysis_df["threshold"], analysis_df["roi"] * 100, "g-")
    ax1.set_xlabel("Betting Threshold (Points of Edge)")
    ax1.set_ylabel("ROI (%)", color="g")
    ax1.tick_params("y", colors="g")
    ax1.grid(True, which="both", linestyle="--", linewidth=0.5)

    # Number of bets plot (secondary axis)
    ax2 = ax1.twinx()
    ax2.plot(analysis_df["threshold"], analysis_df["n_bets"], "b--")
    ax2.set_ylabel("Number of Bets", color="b")
    ax2.tick_params("y", colors="b")

    plt.title(
        f"Betting Threshold Optimization for {cfg.model.name} on {cfg.model.target}"
    )
    fig.tight_layout()

    # Save plot
    output_dir = get_repo_root() / "artifacts" / "analysis"
    output_dir.mkdir(parents=True, exist_ok=True)
    plot_path = output_dir / f"threshold_optimization_{cfg.model.target}.png"
    plt.savefig(plot_path)
    print(f"\nPlot saved to {plot_path}")


if __name__ == "__main__":
    main()
