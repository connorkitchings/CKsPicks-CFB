"""Experiment configurations for training and inference."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class ExperimentConfig:
    name: str
    description: str
    model_type: str  # "catboost", "xgboost", "linear", etc.
    features: List[str]
    target: str
    hyperparameters: dict = field(default_factory=dict)

    # Data filtering/preprocessing
    start_year: int = 2014
    exclude_years: List[int] = field(default_factory=lambda: [2020])

    # Validation
    validation_years: List[int] = field(default_factory=lambda: [2024])


# Define standard feature sets to avoid repetition
BASE_FEATURES = [
    "home_adj_off_epa_pp",
    "home_adj_off_sr",
    "home_adj_off_ypp",
    "away_adj_def_epa_pp",
    "away_adj_def_sr",
    "away_adj_def_ypp",
    # ... (Add full list of base features here or import from a central feature registry)
]

# Example Experiment
SPREAD_CATBOOST_V1 = ExperimentConfig(
    name="spread_catboost_v1",
    description="Baseline CatBoost model for spread prediction.",
    model_type="catboost",
    features=BASE_FEATURES,  # Placeholder, needs actual list
    target="spread_target",
    hyperparameters={
        "iterations": 1000,
        "learning_rate": 0.05,
        "depth": 6,
        "loss_function": "RMSE",
    },
)

# Registry of available experiments
EXPERIMENTS = {
    "spread_catboost_v1": SPREAD_CATBOOST_V1,
}


def get_experiment(name: str) -> ExperimentConfig:
    if name not in EXPERIMENTS:
        raise ValueError(f"Experiment '{name}' not found.")
    return EXPERIMENTS[name]
