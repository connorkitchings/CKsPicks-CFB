import sys
from pathlib import Path

import mlflow

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cks_picks_cfb.utils.mlflow_tracking import get_tracking_uri

mlflow.set_tracking_uri(get_tracking_uri())
mlflow.set_experiment("MLflow Test")

with mlflow.start_run() as run:
    print(f"run_id: {run.info.run_id}")
    print(f"experiment_id: {run.info.experiment_id}")
    with open("test.txt", "w") as f:
        f.write("hello world")
    mlflow.log_artifact("test.txt")
