"""Generate predictions for a given week using a specified model."""

import argparse
import os
import sys
from typing import Optional

import joblib
import numpy as np
import pandas as pd

from src.config import get_data_root
from src.models.features import build_feature_list, load_point_in_time_data


def predict_week(
    year: int,
    week: int,
    model_path: str,
    output_path: Optional[str] = None,
    data_root: Optional[str] = None,
    use_subprocess: bool = True,
) -> pd.DataFrame:
    """
    Generate predictions for a specific week.

    Args:
        year: Season year.
        week: Week number.
        model_path: Path to the trained model artifact.
        output_path: Optional path to save predictions CSV.
        data_root: Path to data root.
        use_subprocess: Whether to run prediction in a subprocess (recommended for CatBoost).

    Returns:
        DataFrame with predictions.
    """
    resolved_data_root = data_root or str(get_data_root())

    # 1. Load Data
    print(f"Loading data for {year} Week {week}...")
    df = load_point_in_time_data(
        year, week, resolved_data_root, include_betting_lines=True
    )
    if df is None or df.empty:
        print(f"No data found for {year} Week {week}.")
        return pd.DataFrame()

    # 2. Load Model
    print(f"Loading model from {model_path}...")
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model not found at {model_path}")

    model = joblib.load(model_path)

    # 3. Prepare Features
    # Ideally, the model artifact should contain the feature list.
    # For now, we'll try to infer or use the fallback builder.
    if hasattr(model, "feature_names_"):
        feature_names = model.feature_names_
    else:
        # Fallback: Re-generate feature list from dataframe columns matching known patterns
        # This is risky but necessary if feature list isn't saved.
        # Better approach: Save feature list with model.
        print(
            "WARNING: Model does not have feature_names_. Using fallback feature builder."
        )
        feature_names = build_feature_list(df)

    # Ensure all features exist
    missing_features = [f for f in feature_names if f not in df.columns]
    if missing_features:
        # Try to fill missing features with defaults if possible, or raise error
        print(
            f"WARNING: Missing {len(missing_features)} features. Filling with 0/defaults."
        )
        for f in missing_features:
            df[f] = 0.0  # simplified default

    x = df[feature_names].copy()  # noqa: N806

    # 4. Predict
    print("Generating predictions...")
    if use_subprocess:
        preds = _predict_subprocess(model_path, x)
    else:
        preds = model.predict(x)

    # 5. Format Output
    output_cols = [
        "id",
        "season",
        "week",
        "home_team",
        "away_team",
        "home_points",
        "away_points",
    ]
    if "spread_line" in df.columns:
        output_cols.append("spread_line")
    if "total_line" in df.columns:
        output_cols.append("total_line")
    if "home_games_played" in df.columns:
        output_cols.append("home_games_played")
    if "away_games_played" in df.columns:
        output_cols.append("away_games_played")

    results = df[output_cols].copy()
    results["prediction"] = preds

    if output_path:
        results.to_csv(output_path, index=False)
        print(f"Predictions saved to {output_path}")

    return results


def _predict_subprocess(model_path: str, x: pd.DataFrame) -> np.ndarray:  # noqa: N803
    """Run prediction in a separate process to avoid CatBoost environment issues."""
    import subprocess
    import tempfile

    with (
        tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as tmp_in,
        tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as tmp_out,
    ):
        input_path = tmp_in.name
        output_path = tmp_out.name

    try:
        x.to_pickle(input_path)

        # We need a helper script. We can write a tiny one on the fly or use a dedicated one.
        # Let's write a tiny one on the fly to keep this self-contained?
        # Or better, assume a 'predict_worker.py' exists or use `python -c`.

        worker_code = f"""
import joblib
import pandas as pd
import sys

try:
    model = joblib.load('{model_path}')
    X = pd.read_pickle('{input_path}')
    preds = model.predict(X.values) # Use .values to strip metadata
    pd.Series(preds).to_pickle('{output_path}')
except Exception as e:
    print(e, file=sys.stderr)
    sys.exit(1)
"""
        cmd = [sys.executable, "-c", worker_code]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Prediction subprocess failed: {result.stderr}")

        preds_series = pd.read_pickle(output_path)
        return preds_series.values

    finally:
        if os.path.exists(input_path):
            os.remove(input_path)
        if os.path.exists(output_path):
            os.remove(output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--model-path", type=str, required=True)
    parser.add_argument("--output", type=str, default="predictions.csv")
    parser.add_argument("--data-root", type=str)
    args = parser.parse_args()

    predict_week(args.year, args.week, args.model_path, args.output, args.data_root)
