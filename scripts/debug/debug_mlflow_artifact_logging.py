import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
# noqa: E402
import hydra
import mlflow
from omegaconf import DictConfig
from sklearn.linear_model import Ridge

from src.models.features import load_point_in_time_data
from src.models.train_model import _build_feature_list, _concat_years
from src.utils.mlflow_tracking import get_tracking_uri


@hydra.main(config_path="../../conf", config_name="config", version_base=None)
def main(cfg: DictConfig) -> None:
    mlflow.set_tracking_uri(get_tracking_uri())
    mlflow.set_experiment("MLflow Debug")

    print(f"Current working directory before run: {os.getcwd()}")
    with mlflow.start_run() as run:
        print(f"Current working directory after run: {os.getcwd()}")
        print(f"run_id: {run.info.run_id}")
        print(f"experiment_id: {run.info.experiment_id}")

        # Load data for a single week
        weekly_features = load_point_in_time_data(
            2023,
            5,
            cfg.data.data_root,
            adjustment_iteration=cfg.data.adjustment_iteration,
        )
        train_df = _concat_years([weekly_features])
        target_col = "spread_target"
        if target_col not in train_df.columns:
            train_df[target_col] = train_df["home_points"] - train_df["away_points"]

        feature_list = _build_feature_list(train_df)
        train_df = train_df.dropna(subset=feature_list + [target_col])

        x_train = train_df[feature_list]
        y_train = train_df[target_col]

        # Train a simple model
        model = Ridge()
        model.fit(x_train, y_train)

        # Log the model
        mlflow.sklearn.log_model(model, "model")
        print("Model logged")


if __name__ == "__main__":
    main()
