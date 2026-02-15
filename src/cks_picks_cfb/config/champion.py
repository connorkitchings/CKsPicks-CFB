"""Configuration for the current champion models."""

from pathlib import Path

from cks_picks_cfb.config import MODELS_DIR

# Define the current champion model versions
CHAMPION_YEAR = "2024_champion"

# Paths to the champion models
SPREAD_MODEL_PATH = MODELS_DIR / CHAMPION_YEAR / "spread_catboost.joblib"
TOTAL_MODEL_PATH = MODELS_DIR / CHAMPION_YEAR / "total_catboost.joblib"

# Expected feature lists for the champion models (loaded from artifacts if possible, or defined here)
# Ideally, these should be stored alongside the models in a JSON file.
SPREAD_FEATURES_PATH = MODELS_DIR / CHAMPION_YEAR / "spread_features.json"
TOTAL_FEATURES_PATH = MODELS_DIR / CHAMPION_YEAR / "total_features.json"


def get_champion_model_paths() -> dict[str, Path]:
    return {"spread": SPREAD_MODEL_PATH, "total": TOTAL_MODEL_PATH}
