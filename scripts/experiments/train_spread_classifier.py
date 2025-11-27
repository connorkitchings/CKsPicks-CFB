import logging
import sys
import uuid
from pathlib import Path

import hydra
import mlflow
import numpy as np
import pandas as pd
from catboost import CatBoostClassifier
from dotenv import load_dotenv
from omegaconf import DictConfig
from sklearn.metrics import accuracy_score, log_loss

load_dotenv()

# Add src to path
sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.config import get_data_root  # noqa: E402
from src.features.selector import select_features  # noqa: E402
from src.models.features import load_point_in_time_data  # noqa: E402
from src.models.train_model import _concat_years  # noqa: E402
from src.utils.local_storage import LocalStorage  # noqa: E402
from src.utils.mlflow_tracking import setup_mlflow  # noqa: E402

log = logging.getLogger(__name__)


@hydra.main(config_path="../../conf", config_name="config", version_base="1.2")
def main(cfg: DictConfig):
    run_id = str(uuid.uuid4())
    log.info(f"Starting Spread Classification run: {run_id}")

    # Setup MLflow
    setup_mlflow()
    experiment_name = "spread_classification_v1"
    mlflow.set_experiment(experiment_name)

    # Training years: 2019, 2021-2023
    train_years = [2019, 2021, 2022, 2023]
    test_years = [2024]
    adjustment_iteration = 2

    log.info(f"Training years: {train_years}")
    log.info(f"Test years: {test_years}")

    # Load Training Data
    all_train_data = []
    for t_year in train_years:
        for week in range(1, 16):
            df = load_point_in_time_data(
                t_year,
                week,
                cfg.paths.data_dir,
                adjustment_iteration=adjustment_iteration,
            )
            if df is not None:
                all_train_data.append(df)

    if not all_train_data:
        log.error("No training data found.")
        return

    train_df = _concat_years(all_train_data)

    # Load Betting Lines for Training
    storage = LocalStorage(
        data_root=get_data_root(), file_format="csv", data_type="raw"
    )

    # We need lines for all training years
    lines_dfs = []
    for year in train_years:
        try:
            records = storage.read_index("betting_lines", {"year": year})
            if records:
                ldf = pd.DataFrame.from_records(records)
                # Filter for consensus
                if "provider" in ldf.columns:
                    ldf["provider_rank"] = np.where(
                        ldf["provider"].astype(str).str.lower() == "consensus", 0, 1
                    )
                else:
                    ldf["provider_rank"] = 1

                ldf = (
                    ldf.sort_values(["game_id", "provider_rank"])
                    .groupby("game_id", as_index=False)
                    .first()
                )
                lines_dfs.append(ldf)
        except Exception as e:
            log.warning(f"Could not load lines for {year}: {e}")

    if not lines_dfs:
        log.error("No betting lines found for training.")
        return

    all_lines = pd.concat(lines_dfs, ignore_index=True)
    if "spread" in all_lines.columns and "spread_line" not in all_lines.columns:
        all_lines["spread_line"] = all_lines["spread"]

    # Merge lines into train_df
    # train_df has 'id' as game_id
    train_df = train_df.merge(
        all_lines[["game_id", "spread_line"]],
        left_on="id",
        right_on="game_id",
        how="inner",
    )

    if "spread_line" not in train_df.columns:
        log.error("spread_line not found in training data after merge.")
        return

    # Filter pushes
    train_df["margin"] = train_df["home_points"] - train_df["away_points"]
    train_df["cover_margin"] = train_df["margin"] + train_df["spread_line"]
    train_df = train_df[train_df["cover_margin"] != 0]

    train_df["target"] = (train_df["cover_margin"] > 0).astype(int)

    x_train = select_features(train_df, cfg)
    y_train = train_df["target"]

    log.info(f"Training on {len(train_df)} records.")

    # Initialize Model
    params = {
        "iterations": 1000,
        "learning_rate": 0.03,
        "depth": 6,
        "loss_function": "Logloss",
        "eval_metric": "Accuracy",
        "verbose": False,
        "random_seed": 42,
    }

    model = CatBoostClassifier(**params)

    with mlflow.start_run(run_name=run_id):
        mlflow.log_params(params)

        log.info("Training Classifier...")
        model.fit(x_train, y_train, verbose=False)

        # Evaluate on Test Year
        log.info("Evaluating on 2024...")
        all_test_data = []
        for week in range(1, 16):
            df = load_point_in_time_data(
                2024,
                week,
                cfg.paths.data_dir,
                adjustment_iteration=adjustment_iteration,
            )
            if df is not None:
                all_test_data.append(df)

        test_df = _concat_years(all_test_data)

        # Load 2024 lines
        try:
            records = storage.read_index("betting_lines", {"year": 2024})
            if records:
                ldf = pd.DataFrame.from_records(records)
                if "provider" in ldf.columns:
                    ldf["provider_rank"] = np.where(
                        ldf["provider"].astype(str).str.lower() == "consensus", 0, 1
                    )
                else:
                    ldf["provider_rank"] = 1
                ldf = (
                    ldf.sort_values(["game_id", "provider_rank"])
                    .groupby("game_id", as_index=False)
                    .first()
                )
                if "spread" in ldf.columns and "spread_line" not in ldf.columns:
                    ldf["spread_line"] = ldf["spread"]
                test_df = test_df.merge(
                    ldf[["game_id", "spread_line"]],
                    left_on="id",
                    right_on="game_id",
                    how="inner",
                )
        except Exception as e:
            log.warning(f"Could not load lines for 2024: {e}")

        if "spread_line" not in test_df.columns:
            log.error("spread_line not found in test data.")
            return

        test_df["margin"] = test_df["home_points"] - test_df["away_points"]
        test_df["cover_margin"] = test_df["margin"] + test_df["spread_line"]
        test_df = test_df[test_df["cover_margin"] != 0]
        test_df["target"] = (test_df["cover_margin"] > 0).astype(int)

        x_test = select_features(test_df, cfg)

        # Align features
        missing_cols = set(x_train.columns) - set(x_test.columns)
        for c in missing_cols:
            x_test[c] = 0.0
        x_test = x_test[x_train.columns]

        probs = model.predict_proba(x_test)[:, 1]  # Prob of Home Cover
        preds = model.predict(x_test)

        acc = accuracy_score(test_df["target"], preds)
        ll = log_loss(test_df["target"], probs)

        log.info(f"Accuracy: {acc:.4f}")
        log.info(f"LogLoss: {ll:.4f}")

        mlflow.log_metric("accuracy", acc)
        mlflow.log_metric("log_loss", ll)

        # Betting Analysis
        # Bet Home if Prob > Threshold
        # Bet Away if Prob < (1 - Threshold)
        thresholds = [0.524, 0.55, 0.60]

        for thresh in thresholds:
            bets = []
            for i, prob in enumerate(probs):
                actual = test_df.iloc[i]["target"]
                if prob > thresh:
                    # Bet Home
                    win = actual == 1
                    bets.append({"win": win})
                elif prob < (1 - thresh):
                    # Bet Away (Home Cover Prob is low)
                    win = actual == 0
                    bets.append({"win": win})

            if bets:
                wins = sum(b["win"] for b in bets)
                total = len(bets)
                rate = wins / total
                roi = (wins * 0.909 - (total - wins)) / (total * 1.1)
                log.info(
                    f"Threshold {thresh}: {wins}/{total} ({rate:.1%}) ROI: {roi:.1%}"
                )
                mlflow.log_metric(f"roi_{thresh}", roi)

        # Save predictions
        out_df = test_df[
            ["id", "season", "week", "home_team", "away_team", "spread_line", "target"]
        ].copy()
        out_df["home_cover_prob"] = probs
        out_path = (
            Path(cfg.paths.artifacts_dir)
            / "predictions"
            / "spread_classification"
            / f"{run_id}_predictions.csv"
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_df.to_csv(out_path, index=False)
        log.info(f"Saved predictions to {out_path}")


if __name__ == "__main__":
    main()
