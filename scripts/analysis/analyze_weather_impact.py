"""
Analyze the impact of weather features on the Spread model.

This script loads the weather-aware model (assumed to be in artifacts/models/2024/)
and calculates:
1. Feature Importance (CatBoost default)
2. SHAP Values (for deeper insight)
"""

import sys
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import pandas as pd
import shap

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.config import MODELS_DIR, get_data_root
from src.models.features import load_point_in_time_data


def analyze_weather_impact(year: int = 2024, model_dir: str = "2024"):
    """Analyze feature importance for the specified model."""
    model_path = MODELS_DIR / model_dir / "spread_catboost.joblib"
    print(f"Loading model from {model_path}...")

    if not model_path.exists():
        print(f"ERROR: Model not found at {model_path}")
        return

    model = joblib.load(model_path)

    # Load a sample of data (e.g., Week 10) to run analysis on
    # We use a mid-season week to ensure we have data
    print(f"Loading data for {year} Week 10...")
    df = load_point_in_time_data(year, 10, get_data_root(), include_betting_lines=True)

    if df is None or df.empty:
        print("ERROR: No data found.")
        return

    # Extract features
    if hasattr(model, "feature_names_"):
        feature_names = model.feature_names_
    else:
        print("WARNING: Model missing feature_names_. Using all numeric columns.")
        feature_names = df.select_dtypes(include=["number"]).columns.tolist()

    # Filter to available features
    available_features = [f for f in feature_names if f in df.columns]
    missing = set(feature_names) - set(available_features)
    if missing:
        print(f"WARNING: Missing {len(missing)} features: {missing}")
        # Fill missing with 0
        for f in missing:
            df[f] = 0

    x_features = df[feature_names]

    # 1. Feature Importance
    print("\n--- Feature Importance (Top 20) ---")
    importance = model.get_feature_importance()
    feat_imp = pd.DataFrame({"feature": feature_names, "importance": importance})
    feat_imp = feat_imp.sort_values("importance", ascending=False)
    print(feat_imp.head(20))

    # Check specific weather features
    weather_keywords = ["temp", "wind", "precip", "rain", "snow", "weather"]
    weather_features = feat_imp[
        feat_imp["feature"].str.contains("|".join(weather_keywords), case=False)
    ]
    print("\n--- Weather Feature Importance ---")
    if not weather_features.empty:
        print(weather_features)
    else:
        print("No weather features found in the model.")

    # 2. SHAP Analysis
    print("\n--- Calculating SHAP Values ---")
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(x_features)

    # Summary Plot
    plt.figure(figsize=(10, 8))
    shap.summary_plot(
        shap_values, x_features, plot_type="bar", show=False, max_display=20
    )
    output_plot = "artifacts/weather_shap_summary.png"
    plt.savefig(output_plot, bbox_inches="tight")
    print(f"SHAP summary plot saved to {output_plot}")


if __name__ == "__main__":
    analyze_weather_impact()
