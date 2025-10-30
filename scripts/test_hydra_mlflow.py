import hydra
from omegaconf import DictConfig
import mlflow
import os

@hydra.main(config_path="../conf", config_name="config", version_base=None)
def main(cfg: DictConfig) -> None:
    mlflow.set_tracking_uri("file:./artifacts/mlruns")
    mlflow.set_experiment("MLflow Hydra Test")

    with mlflow.start_run() as run:
        print(f"run_id: {run.info.run_id}")
        print(f"experiment_id: {run.info.experiment_id}")
        with open("test.txt", "w") as f:
            f.write("hello world")
        mlflow.log_artifact("test.txt", "test_artifact")

if __name__ == "__main__":
    main()
