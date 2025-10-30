import mlflow
import os

mlflow.set_tracking_uri("file:./artifacts/mlruns")
mlflow.set_experiment("MLflow Test")

with mlflow.start_run() as run:
    print(f"run_id: {run.info.run_id}")
    print(f"experiment_id: {run.info.experiment_id}")
    with open("test.txt", "w") as f:
        f.write("hello world")
    mlflow.log_artifact("test.txt")
