import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Add project root to path
project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))
# noqa: E402

def calculate_metrics(predictions_path: Path, output_path: Path):
    """
    Calculate model performance metrics for 2025 predictions.
    Note: Since betting lines are not available in the predictions CSV,
    we can only calculate calibration metrics, not actual betting performance.
    """
    print(f"Loading predictions from {predictions_path}")
    try:
        preds = pd.read_csv(predictions_path)
    except FileNotFoundError:
        print(f"Error: File not found at {predictions_path}")
        return

    print(f"\nTotal 2025 games with predictions: {len(preds)}")

    # Calculate prediction errors
    preds["spread_error"] = (
        preds["spread_actual"] - preds["spread_pred_points_for_ensemble"]
    )
    preds["total_error"] = (
        preds["total_actual"] - preds["total_pred_points_for_ensemble"]
    )

    # RMSE and MAE
    spread_rmse = np.sqrt((preds["spread_error"] ** 2).mean())
    spread_mae = preds["spread_error"].abs().mean()
    spread_bias = preds["spread_error"].mean()

    total_rmse = np.sqrt((preds["total_error"] ** 2).mean())
    total_mae = preds["total_error"].abs().mean()
    total_bias = preds["total_error"].mean()

    print("\n=== 2025 SPREAD PREDICTIONS ===")
    print(f"RMSE: {spread_rmse:.2f}")
    print(f"MAE:  {spread_mae:.2f}")
    print(f"Bias: {spread_bias:.2f} (Actual - Pred)")

    print("\n=== 2025 TOTALS PREDICTIONS ===")
    print(f"RMSE: {total_rmse:.2f}")
    print(f"MAE:  {total_mae:.2f}")
    print(f"Bias: {total_bias:.2f} (Actual - Pred)")

    # Directional accuracy (did we get the winner right?)
    preds["pred_home_win"] = preds["spread_pred_points_for_ensemble"] > 0
    preds["actual_home_win"] = preds["spread_actual"] > 0
    preds["correct_direction"] = preds["pred_home_win"] == preds["actual_home_win"]

    directional_accuracy = preds["correct_direction"].mean()
    print("\n=== DIRECTIONAL ACCURACY ===")
    print(
        f"Correctly predicted winner: {directional_accuracy:.2%} ({preds['correct_direction'].sum()}/{len(preds)} games)"
    )

    # Save detailed report
    preds.to_csv(output_path, index=False)
    print(f"\nDetailed metrics saved to {output_path}")

    print("\n=== NOTE ===")
    print("Betting lines are not available in the predictions CSV.")
    print("To calculate actual betting performance (ATS/Totals), you would need")
    print(
        "to join with a games table or CSV that contains 'spread' and 'total_line' columns."
    )


if __name__ == "__main__":
    pred_path = Path("artifacts/validation/walk_forward/2025_predictions.csv")
    out_path = Path("artifacts/reports/2025_betting_metrics.csv")
    calculate_metrics(pred_path, out_path)
