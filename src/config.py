"""Configuration helpers for paths and environment-derived settings."""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def get_repo_root() -> Path:
    """Get the project's root directory."""
    return Path(__file__).resolve().parents[1]


def get_data_root() -> Path:
    """
    Resolve the data root from the CFB_DATA_ROOT environment variable.
    Falls back to 'data/' in the repo root if not set.
    """
    env_path = os.getenv("CFB_DATA_ROOT")
    if env_path:
        return Path(env_path)
    return get_repo_root() / "data"


# Define core paths
DATA_ROOT = get_data_root()
RAW_DATA_DIR = DATA_ROOT / "raw"
PROCESSED_DATA_DIR = DATA_ROOT / "processed"

REPO_ROOT = get_repo_root()
MODELS_DIR = REPO_ROOT / "models"
LOGOS_DIR = REPO_ROOT / "Logos"
ARTIFACTS_DIR = REPO_ROOT / "artifacts"
REPORTS_DIR = ARTIFACTS_DIR / "reports"

# Subdirectories within per-season report folders
PREDICTIONS_SUBDIR = "predictions"
SCORED_SUBDIR = "scored"
METRICS_SUBDIR = "metrics"


if __name__ == "__main__":
    # For debugging and verification
    print(f"Repository Root: {REPO_ROOT}")
    print(f"Data Root: {DATA_ROOT}")
    print(f"Raw Data Directory: {RAW_DATA_DIR}")
    print(f"Processed Data Directory: {PROCESSED_DATA_DIR}")
    print(f"Models Directory: {MODELS_DIR}")
    print(f"Reports Directory: {REPORTS_DIR}")
