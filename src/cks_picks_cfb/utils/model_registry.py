"""
Utilities for interacting with the MLflow Model Registry and generating standardized Model IDs.
"""

import datetime
import hashlib
import logging
from typing import Optional

import mlflow
from mlflow.tracking import MlflowClient

logger = logging.getLogger(__name__)


def generate_model_id(
    model_type: str,
    feature_set: str,
    tuning: str = "baseline",
    data_version: str = "default",
) -> str:
    """
    Generate a standardized Model ID.

    Format: {model_type}-{feature_set}-{tuning}-{data_version}-{timestamp}

    Args:
        model_type: Type of model (e.g., 'catboost', 'xgboost').
        feature_set: Name of the feature set (e.g., 'standard_v1').
        tuning: Tuning strategy (e.g., 'baseline', 'optuna').
        data_version: Identifier for the training data (e.g., '2024_w14').

    Returns:
        Unique Model ID string.
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    # Add a short hash of the inputs to ensure uniqueness even if called rapidly
    input_str = f"{model_type}{feature_set}{tuning}{data_version}"
    short_hash = hashlib.md5(input_str.encode()).hexdigest()[:6]

    return (
        f"{model_type}-{feature_set}-{tuning}-{data_version}-{timestamp}-{short_hash}"
    )


def register_model(
    run_id: str,
    model_name: str,
    model_id: Optional[str] = None,
    tags: Optional[dict] = None,
    stage: Optional[str] = None,
) -> None:
    """
    Register a model from an MLflow run to the Model Registry.

    Args:
        run_id: The MLflow run ID containing the model artifact.
        model_name: The name of the registered model in the registry (e.g., "Spread_Model").
        model_id: Optional standardized Model ID to set as a tag/version description.
        tags: Dictionary of tags to apply to the registered model version.
        stage: Optional stage to transition the model to (e.g., "Staging", "Production").
    """
    client = MlflowClient()
    model_uri = f"runs:/{run_id}/model"

    try:
        # Create registered model if it doesn't exist
        try:
            client.create_registered_model(model_name)
            logger.info(f"Created new registered model: {model_name}")
        except mlflow.exceptions.MlflowException:
            pass  # Model already exists

        # Create a new version
        result = client.create_model_version(
            name=model_name,
            source=model_uri,
            run_id=run_id,
            description=f"Model ID: {model_id}" if model_id else None,
        )
        version = result.version
        logger.info(f"Registered model {model_name} version {version}")

        # Set tags
        if tags:
            for key, value in tags.items():
                client.set_model_version_tag(
                    name=model_name, version=version, key=key, value=value
                )

        if model_id:
            client.set_model_version_tag(
                name=model_name, version=version, key="model_id", value=model_id
            )

        # Transition stage if requested
        if stage:
            client.transition_model_version_stage(
                name=model_name,
                version=version,
                stage=stage,
                archive_existing_versions=(stage == "Production"),
            )
            logger.info(f"Transitioned {model_name} version {version} to {stage}")

    except Exception as e:
        logger.error(f"Failed to register model: {e}")
        raise
