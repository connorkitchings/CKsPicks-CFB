"""Utilities for MLflow tracking and experiment management."""

from __future__ import annotations

import os

import mlflow

from cks_picks_cfb.config import get_repo_root


def _default_tracking_uri() -> str:
    """Return the canonical MLflow file URI under the repo's artifacts dir."""

    return (get_repo_root() / "artifacts" / "mlruns").resolve().as_uri()


TRACKING_URI = _default_tracking_uri()


def get_tracking_uri() -> str:
    """Return the active tracking URI, honoring ``MLFLOW_TRACKING_URI`` overrides."""

    return os.getenv("MLFLOW_TRACKING_URI", TRACKING_URI)


def setup_mlflow(tracking_uri: str | None = None) -> str:
    """Set MLflow's tracking URI and return the resolved target."""

    resolved = tracking_uri or get_tracking_uri()
    mlflow.set_tracking_uri(resolved)
    return resolved


def get_or_create_experiment(experiment_name: str) -> str:
    """
    Gets the ID of an existing MLflow experiment or creates a new one.

    Args:
        experiment_name (str): The name of the experiment.

    Returns:
        str: The ID of the experiment.
    """
    setup_mlflow()
    experiment = mlflow.get_experiment_by_name(experiment_name)
    if experiment is None:
        experiment_id = mlflow.create_experiment(experiment_name)
        print(f"Created new experiment: {experiment_name} (ID: {experiment_id})")
        return experiment_id
    else:
        print(
            f"Using existing experiment: {experiment_name} (ID: {experiment.experiment_id})"
        )
        return experiment.experiment_id


# Example usage:
if __name__ == "__main__":
    experiment_id = get_or_create_experiment("Default Experiment")

    with mlflow.start_run(experiment_id=experiment_id) as run:
        print(f"Started run: {run.info.run_id}")
        mlflow.log_param("learning_rate", 0.01)
        mlflow.log_metric("accuracy", 0.95)
        print("Run complete. Check the MLflow UI.")
