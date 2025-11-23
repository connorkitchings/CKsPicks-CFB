import logging
import sys
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor, Pool
from dotenv import load_dotenv
from hydra import compose, initialize_config_dir
from omegaconf import DictConfig, OmegaConf

project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from src.features.selector import select_features  # noqa: E402
from src.models.features import load_point_in_time_data  # noqa: E402
from src.models.train_model import _concat_years  # noqa: E402


log = logging.getLogger(__name__)


def _compose_config(model_name: str) -> DictConfig:
    """Load the Hydra config for a specific model without changing cwd."""
    project_root = Path(__file__).resolve().parents[1]
    with initialize_config_dir(
        config_dir=str(project_root / "conf"), version_base="1.2"
    ):
        cfg = compose(config_name="config", overrides=[f"model={model_name}"])

    # Keep top-level target aligned with the model file.
    if "target" in cfg.model:
        cfg.target = cfg.model.target

    # Use the model's adjustment iteration for both train and test splits.
    model_iteration = cfg.model.get("adjustment_iteration", None)
    if model_iteration is not None:
        cfg.data.adjustment_iteration = model_iteration

    return cfg


def _load_season_weeks(
    years: Iterable[int], cfg: DictConfig, *, adjustment_iteration: int
) -> pd.DataFrame:
    """Load point-in-time data for a list of seasons and all weeks."""
    frames = []
    for year in years:
        if year == 2020:
            continue  # avoid pandemic year noise
        for week in range(1, 16):
            df = load_point_in_time_data(
                year,
                week,
                cfg.paths.data_dir,
                adjustment_iteration=adjustment_iteration,
            )
            if df is not None:
                frames.append(df)
    return _concat_years(frames)


def _train_and_explain(cfg: DictConfig, model_name: str) -> dict:
    """Train a CatBoost model and compute SHAP importances on the holdout year."""
    test_years = cfg.get("test_years", [2024])
    test_year = max(test_years)  # use the most recent holdout
    train_years = [y for y in range(cfg.get("start_train_year", 2019), test_year)]

    log.info(
        "Model %s | train years %s | test year %s | iteration %s",
        model_name,
        train_years,
        test_year,
        cfg.data.adjustment_iteration,
    )

    train_df = _load_season_weeks(
        train_years, cfg, adjustment_iteration=cfg.data.adjustment_iteration
    )
    test_df = _load_season_weeks(
        [test_year], cfg, adjustment_iteration=cfg.data.adjustment_iteration
    )
    if train_df.empty or test_df.empty:
        raise RuntimeError("Training or test data frame is empty; check data availability.")

    train_df = train_df.dropna(subset=[cfg.target])
    test_df = test_df.dropna(subset=[cfg.target])

    x_train_full = select_features(train_df, cfg)
    x_test_full = select_features(test_df, cfg)

    common_features = sorted(set(x_train_full.columns) & set(x_test_full.columns))
    if not common_features:
        raise RuntimeError("No overlapping features found between train and test splits.")

    x_train = x_train_full[common_features].astype(float)
    y_train = train_df[cfg.target]
    x_test = x_test_full[common_features].astype(float)
    y_test = test_df[cfg.target]

    model_params = OmegaConf.to_container(cfg.model.params, resolve=True)
    # Quiet default CatBoost logging for script use.
    model_params.setdefault("verbose", False)
    model = CatBoostRegressor(**model_params)
    model.fit(x_train, y_train)

    preds = model.predict(x_test)
    rmse = float(np.sqrt(np.mean((preds - y_test.values) ** 2)))
    mae = float(np.mean(np.abs(preds - y_test.values)))

    test_pool = Pool(x_test, label=y_test)
    shap_values = model.get_feature_importance(test_pool, type="ShapValues")
    mean_abs_shap = np.abs(shap_values[:, :-1]).mean(axis=0)

    importance_df = (
        pd.DataFrame({"feature": common_features, "mean_abs_shap": mean_abs_shap})
        .sort_values("mean_abs_shap", ascending=False)
        .reset_index(drop=True)
    )
    importance_df["rank"] = importance_df.index + 1

    out_dir = (
        Path(cfg.paths.reports_dir)
        / "shap"
        / f"{model_name}_iter{cfg.data.adjustment_iteration}"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{test_year}_importance.csv"
    importance_df.to_csv(out_path, index=False)

    log.info(
        "Saved %s SHAP importances (%d features) to %s", model_name, len(importance_df), out_path
    )
    return {
        "model": model_name,
        "test_year": test_year,
        "rmse": rmse,
        "mae": mae,
        "top_features": importance_df.head(20),
        "output_path": out_path,
    }


def main() -> None:
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )

    model_names = ["spread_catboost", "total_catboost"]
    summaries = []
    for model_name in model_names:
        cfg = _compose_config(model_name)
        summaries.append(_train_and_explain(cfg, model_name))

    # Emit a concise summary to stdout for quick inspection.
    for summary in summaries:
        print(
            f"\n=== {summary['model']} | Test {summary['test_year']} | "
            f"RMSE {summary['rmse']:.2f} | MAE {summary['mae']:.2f} ==="
        )
        print(summary["top_features"][["rank", "feature", "mean_abs_shap"]].to_string(index=False))
        print(f"Saved: {summary['output_path']}")


if __name__ == "__main__":
    main()
