"""Utilities for model loading and prediction."""

from __future__ import annotations

import os
import joblib

def load_hybrid_ensemble_models(
    model_year: int, spread_model_dir: str, total_model_dir: str
) -> dict[str, list]:
    """Load spread models from one dir and total models from another."""
    models = {"spread": [], "total": []}

    # Load Spread Models
    spread_dir = os.path.join(spread_model_dir, str(model_year))
    if not os.path.isdir(spread_dir):
        raise FileNotFoundError(f"Spread model directory not found: {spread_dir}")
    for file_name in os.listdir(spread_dir):
        if file_name.endswith(".joblib") and (
            file_name.startswith("spread_") or "spread" in file_name
        ):
            model_path = os.path.join(spread_dir, file_name)
            models["spread"].append(joblib.load(model_path))

    # Load Total Models
    total_dir = os.path.join(total_model_dir, str(model_year))
    if not os.path.isdir(total_dir):
        raise FileNotFoundError(f"Total model directory not found: {total_dir}")
    for file_name in os.listdir(total_dir):
        if file_name.endswith(".joblib") and file_name.startswith("total_"):
            model_path = os.path.join(total_dir, file_name)
            models["total"].append(joblib.load(model_path))

    if not models["spread"]:
        raise FileNotFoundError(f"No spread models found in {spread_dir}")
    if not models["total"]:
        raise FileNotFoundError(f"No total models found in {total_dir}")

    print(
        f"Loaded {len(models['spread'])} spread models and {len(models['total'])} total models."
    )
    return models
