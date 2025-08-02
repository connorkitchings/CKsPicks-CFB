"""Utilities for MLflow tracking and experiment management."""

import mlflow

# Default local tracking URI. For a remote server, use a different URI.
TRACKING_URI = "file:./mlruns"

def setup_mlflow(tracking_uri: str = TRACKING_URI) -> None:
    """
    Sets the MLflow tracking URI.

    Args:
        tracking_uri (str): The URI for the MLflow tracking server.
                            Defaults to a local './mlruns' directory.
    """
    mlflow.set_tracking_uri(tracking_uri)

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
        print(f"Using existing experiment: {experiment_name} (ID: {experiment.experiment_id})")
        return experiment.experiment_id

# Example usage:
if __name__ == '__main__':
    experiment_id = get_or_create_experiment("Default Experiment")

    with mlflow.start_run(experiment_id=experiment_id) as run:
        print(f"Started run: {run.info.run_id}")
        mlflow.log_param("learning_rate", 0.01)
        mlflow.log_metric("accuracy", 0.95)
        print("Run complete. Check the MLflow UI.")
