from pathlib import Path

import joblib
import mlflow
import mlflow.catboost
import mlflow.sklearn

from scripts.utils.model_registry import promote_to_production, setup_model_registry


def main():
    model_path = Path("artifacts/models/totals_catboost_baseline_v1.joblib")
    model_name = "totals_catboost_baseline_v1"

    if not model_path.exists():
        print(f"Error: Model file not found at {model_path}")
        return

    print(f"Loading model from {model_path}...")
    model = joblib.load(model_path)

    print(f"Registering model {model_name}...")
    client = setup_model_registry()

    # Create registered model if needed
    try:
        client.get_registered_model(model_name)
    except mlflow.exceptions.MlflowException:
        client.create_registered_model(model_name)

    with mlflow.start_run():
        # Log as CatBoost model since it is one
        mlflow.catboost.log_model(
            cb_model=model,
            artifact_path="model",
            registered_model_name=model_name,
        )

        # Get version
        latest_versions = client.get_latest_versions(model_name)
        model_version = max(latest_versions, key=lambda v: int(v.version))

        # Set description
        client.update_model_version(
            name=model_name,
            version=model_version.version,
            description="Baseline CatBoost model for Totals (2024)",
        )

    print(f"Registered version {model_version.version}")

    print(f"Promoting {model_name} version {model_version.version} to Production...")
    success = promote_to_production(model_name, version=model_version.version)

    if success:
        print("Success!")
    else:
        print("Failed to promote to production.")


if __name__ == "__main__":
    main()
