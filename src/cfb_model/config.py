"""Configuration helpers for paths and environment-derived settings."""

from __future__ import annotations

import os
from pathlib import Path


def get_env(name: str, default: str | None = None) -> str | None:
    """Read environment variable by name with an optional default."""
    return os.environ.get(name, default)


def get_repo_root() -> Path:
    """Best-effort repo root detection based on this file location."""
    return Path(__file__).resolve().parents[2]


def get_data_root() -> str:
    """Resolve data root from env CFB_MODEL_DATA_ROOT or default to ./data.

    Returns a string path suitable for LocalStorage's data_root parameter.
    """
    env_path = get_env("CFB_MODEL_DATA_ROOT")
    if env_path:
        return env_path
    # Default to repo_root/data if available, else cwd/data
    repo_default = get_repo_root() / "data"
    return str(repo_default)


def get_logo_path() -> str:
    """Resolve path for team logos from env CFB_MODEL_LOGO_PATH or default to data/logos/."""
    path = get_env("CFB_MODEL_LOGO_PATH")
    if path:
        return path if path.endswith("/") else path + "/"
    return str(Path(get_data_root()) / "logos") + "/"
