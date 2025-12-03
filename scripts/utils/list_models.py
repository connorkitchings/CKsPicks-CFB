import os
import sys

sys.path.append(os.getcwd())
from mlflow.tracking import MlflowClient

from src.utils.mlflow_tracking import setup_mlflow

setup_mlflow()

client = MlflowClient()
for rm in client.search_registered_models():
    print(f"Model: {rm.name}")
    for v in rm.latest_versions:
        print(f"  Version: {v.version}, Stage: {v.current_stage}")
