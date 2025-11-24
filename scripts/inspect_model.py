import sys
from pathlib import Path

import joblib

# Add src to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.models.ensemble import EnsembleModel


def inspect(path):
    print(f"Inspecting {path}...")
    model = joblib.load(path)
    print(f"Type: {type(model)}")

    if hasattr(model, "feature_names_in_"):
        names = model.feature_names_in_
        print(f"feature_names_in_ length: {len(names)}")
        print(f"First 5 features: {names[:5]}")
    else:
        print("No feature_names_in_ attribute found.")

    if isinstance(model, EnsembleModel):
        print("EnsembleModel detected.")
        if model.models:
            first_model = model.models[0]
            print(f"First model type: {type(first_model)}")
            if hasattr(first_model, "feature_names_in_"):
                print(f"First model features[:5]: {first_model.feature_names_in_[:5]}")
            else:
                print("First model has no feature_names_in_")


if __name__ == "__main__":
    inspect("artifacts/models/2024/points_for_away.joblib")
