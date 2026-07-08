import sys
from pathlib import Path

import mlflow
from dotenv import load_dotenv

load_dotenv()
sys.path.append(str(Path(__file__).resolve().parents[2]))
# noqa: E402
from scripts.utils.model_registry import setup_model_registry  # noqa: E402


def main():
    setup_model_registry()
    client = mlflow.tracking.MlflowClient()

    print("Registered Models:")
    for rm in client.search_registered_models():
        print(f"- {rm.name}")
        for v in rm.latest_versions:
            print(f"  - Version: {v.version}, Stage: {v.current_stage}")


if __name__ == "__main__":
    main()
