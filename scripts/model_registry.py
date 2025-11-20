"""MLflow Model Registry integration for CFB model management."""

from __future__ import annotations

import sys
from pathlib import Path

import mlflow
import mlflow.sklearn
from mlflow.tracking import MlflowClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.mlflow_tracking import get_tracking_uri


def setup_model_registry():
    """Initialize MLflow Model Registry."""
    mlflow.set_tracking_uri(get_tracking_uri())
    client = MlflowClient()
    return client


def register_model_version(
    model_path: str | Path,
    model_name: str,
    version_description: str = "",
    stage: str = "None",
) -> str:
    """
    Register a model version in MLflow Model Registry.

    Args:
        model_path: Path to the saved model file
        model_name: Name for the registered model
        version_description: Description for this version
        stage: Stage to transition to ('None', 'Staging', 'Production', 'Archived')

    Returns:
        Version number of the registered model
    """
    client = setup_model_registry()

    # Create registered model if it doesn't exist
    try:
        client.get_registered_model(model_name)
    except mlflow.exceptions.MlflowException:
        client.create_registered_model(model_name)

    # Log the model and create a version
    with mlflow.start_run():
        mlflow.sklearn.log_model(
            sk_model=mlflow.sklearn.load_model(str(model_path)),
            artifact_path="model",
            registered_model_name=model_name,
        )

        # Get the model version that was just created
        model_version = client.get_model_version(
            model_name, "1"
        )  # Start with version 1
        latest_versions = client.get_latest_versions(model_name)
        if latest_versions:
            model_version = max(latest_versions, key=lambda v: int(v.version))

        # Set description
        if version_description:
            client.update_model_version(
                name=model_name,
                version=model_version.version,
                description=version_description,
            )

        # Transition to specified stage
        if stage != "None":
            client.transition_model_version_stage(
                name=model_name, version=model_version.version, stage=stage
            )

    return model_version.version


def promote_to_production(
    model_name: str, version: str = "latest", from_stage: str | None = None
) -> bool:
    """
    Promote a model version to production stage.

    Args:
        model_name: Name of the registered model
        version: Version to promote ('latest' or specific version number)
        from_stage: Promote from a specific stage (e.g. 'Staging')

    Returns:
        True if successful, False otherwise
    """
    client = setup_model_registry()

    try:
        model_version = None
        if from_stage:
            versions = client.get_latest_versions(model_name, stages=[from_stage])
            if not versions:
                print(f"No versions found for model {model_name} in stage {from_stage}")
                return False
            model_version = versions[0]
        elif version == "latest":
            latest_versions = client.get_latest_versions(model_name)
            if not latest_versions:
                print(f"No versions found for model {model_name}")
                return False
            model_version = max(latest_versions, key=lambda v: int(v.version))
        else:
            model_version = client.get_model_version(model_name, version)

        if model_version is None:
            print("Could not determine model version to promote.")
            return False

        # Transition to production
        client.transition_model_version_stage(
            name=model_name, version=model_version.version, stage="Production"
        )

        print(
            f"Successfully promoted {model_name} version {model_version.version} to Production"
        )
        return True

    except Exception as e:
        print(f"Failed to promote model to production: {e}")
        return False


def get_production_model(model_name: str):
    """
    Load the current production model.

    Args:
        model_name: Name of the registered model

    Returns:
        Loaded model object or None if not found
    """
    client = setup_model_registry()

    try:
        production_versions = client.get_latest_versions(
            model_name, stages=["Production"]
        )
        if not production_versions:
            print(f"No production version found for model {model_name}")
            return None

        model_version = production_versions[0]
        model_uri = f"models:/{model_name}/{model_version.version}"
        return mlflow.sklearn.load_model(model_uri)

    except Exception as e:
        print(f"Failed to load production model: {e}")
        return None


def list_model_versions(model_name: str) -> list[dict]:
    """
    List all versions of a registered model.

    Args:
        model_name: Name of the registered model

    Returns:
        List of version information dictionaries
    """
    client = setup_model_registry()

    try:
        versions = client.get_latest_versions(
            model_name, stages=["None", "Staging", "Production", "Archived"]
        )
        return [
            {
                "version": v.version,
                "stage": v.current_stage,
                "description": v.description,
                "creation_timestamp": v.creation_timestamp,
            }
            for v in versions
        ]
    except Exception as e:
        print(f"Failed to list model versions: {e}")
        return []


def archive_old_versions(model_name: str, keep_versions: int = 5) -> int:
    """
    Archive old model versions, keeping only the most recent ones.

    Args:
        model_name: Name of the registered model
        keep_versions: Number of recent versions to keep active

    Returns:
        Number of versions archived
    """
    client = setup_model_registry()

    try:
        versions = client.get_latest_versions(model_name)
        versions.sort(key=lambda v: int(v.version), reverse=True)

        archived_count = 0
        for version in versions[keep_versions:]:
            if version.current_stage not in ["Production", "Archived"]:
                client.transition_model_version_stage(
                    name=model_name, version=version.version, stage="Archived"
                )
                archived_count += 1

        return archived_count

    except Exception as e:
        print(f"Failed to archive old versions: {e}")
        return 0
