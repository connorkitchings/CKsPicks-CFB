import logging
import sys
from pathlib import Path

import hydra
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from dotenv import load_dotenv
from omegaconf import DictConfig

load_dotenv()

# Add src to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from catboost import CatBoostRegressor  # noqa: E402

from src.features.selector import select_features  # noqa: E402
from src.models.features import load_point_in_time_data  # noqa: E402
from src.models.train_model import _concat_years  # noqa: E402

log = logging.getLogger(__name__)


@hydra.main(config_path="../conf", config_name="config", version_base="1.2")
def main(cfg: DictConfig):
    log.info("Starting feature importance analysis...")

    # Override model config if provided in command line (e.g. model=spread_catboost)
    # Hydra handles this automatically if passed via CLI, but we ensure we use the config's model params

    # We use the same training years as the baseline experiment: 2019, 2021-2023
    # We will exclude 2024 (test year) and 2020 (covid)
    train_years = [2019, 2021, 2022, 2023]

    adjustment_iteration = cfg.model.get(
        "adjustment_iteration", cfg.data.adjustment_iteration
    )
    log.info(f"Using adjustment_iteration: {adjustment_iteration}")
    log.info(f"Training years: {train_years}")

    all_train_data = []
    for t_year in train_years:
        # Load all weeks for training year
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
    train_df = train_df.dropna(subset=[cfg.model.target])

    log.info(f"Training data shape: {train_df.shape}")

    # Select features
    x_train = select_features(train_df, cfg)
    y_train = train_df[cfg.model.target]

    feature_names = x_train.columns.tolist()
    log.info(f"Number of features: {len(feature_names)}")

    # Initialize and Train Model
    if cfg.model.type == "catboost":
        model = CatBoostRegressor(**cfg.model.params)
    else:
        log.error(
            f"Model type {cfg.model.type} not supported for this script (CatBoost only)."
        )
        return

    log.info("Training model...")
    model.fit(x_train, y_train, verbose=False)

    # Compute SHAP values
    log.info("Computing SHAP values...")
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(x_train)

    # Summarize feature importance
    # Mean absolute SHAP value for each feature
    mean_abs_shap = np.abs(shap_values).mean(axis=0)
    feature_importance = pd.DataFrame(
        {"feature": feature_names, "importance": mean_abs_shap}
    ).sort_values(by="importance", ascending=False)

    # Save feature importance to CSV
    output_dir = Path(cfg.paths.artifacts_dir) / "analysis" / "feature_importance"
    output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = output_dir / f"shap_importance_{cfg.model.name}.csv"
    feature_importance.to_csv(csv_path, index=False)
    log.info(f"Saved feature importance to {csv_path}")

    # Print top 30 features
    print("\nTop 30 Features by SHAP Importance:")
    print(feature_importance.head(30))

    # Generate Summary Plot
    plt.figure(figsize=(10, 12))
    shap.summary_plot(shap_values, x_train, plot_type="bar", show=False, max_display=30)
    plot_path = output_dir / f"shap_summary_{cfg.model.name}.png"
    plt.savefig(plot_path, bbox_inches="tight")
    log.info(f"Saved SHAP summary plot to {plot_path}")

    # Also save a beeswarm plot for the top 20
    plt.figure(figsize=(10, 12))
    shap.summary_plot(shap_values, x_train, show=False, max_display=20)
    beeswarm_path = output_dir / f"shap_beeswarm_{cfg.model.name}.png"
    plt.savefig(beeswarm_path, bbox_inches="tight")
    log.info(f"Saved SHAP beeswarm plot to {beeswarm_path}")


if __name__ == "__main__":
    main()
