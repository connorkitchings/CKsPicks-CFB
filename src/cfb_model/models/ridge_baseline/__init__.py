"""Ridge baseline modeling package.

Provides multi-year training and evaluation for the MVP ridge regression model.
"""

from .train import main as train_main  # re-export CLI entry

__all__ = ["train_main"]
