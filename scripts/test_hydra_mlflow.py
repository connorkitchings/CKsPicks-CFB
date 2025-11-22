import sys
from pathlib import Path

import hydra
import mlflow
from omegaconf import DictConfig

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.mlflow_tracking import get_tracking_uri


@hydra.main(config_path="../conf", config_name="config", version_base=None)
def main(cfg: DictConfig) -> None:
    mlflow.set_tracking_uri(get_tracking_uri())
    mlflow.set_experiment("MLflow Hydra Test")

    with mlflow.start_run() as run:
        print(f"run_id: {run.info.run_id}")
        print(f"experiment_id: {run.info.experiment_id}")
        with open("test.txt", "w") as f:
            f.write("hello world")
        mlflow.log_artifact("test.txt", "test_artifact")


if __name__ == "__main__":
    main()
