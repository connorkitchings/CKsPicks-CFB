import logging
import sys
from pathlib import Path

import hydra
import pandas as pd
from omegaconf import DictConfig, OmegaConf

from src.features.selector import select_features
from src.models.train_model import _evaluate, load_data, train_model

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

log = logging.getLogger(__name__)


@hydra.main(config_path="../../conf", config_name="config", version_base="1.2")
def main(cfg: DictConfig):
    # Force 2024 as test year for this study
    cfg.data.test_year = 2024
    cfg.data.train_years = [2019, 2021, 2022, 2023]

    # Define variants
    variants = [
        {"name": "Baseline (With Weather)", "feature_set": "ppr_v1"},
        {"name": "No Weather", "feature_set": "ppr_v1_no_weather"},
    ]

    results = []

    # Load Data once
    log.info("Loading data...")
    train_df_raw, test_df_raw = load_data(cfg)

    for variant in variants:
        log.info(f"Running variant: {variant['name']}")

        # Override feature set
        cfg.features = OmegaConf.load(
            project_root / f"conf/features/{variant['feature_set']}.yaml"
        )

        # Use select_features to respect 'groups' in config
        # select_features returns a dataframe with only the selected columns
        # We need to ensure target columns are kept or handled separately

        # Get feature columns only
        x_train_selected = select_features(train_df_raw, cfg)
        x_test_selected = select_features(test_df_raw, cfg)

        feature_list = list(x_train_selected.columns)
        log.info(f"Selected {len(feature_list)} features.")

        x_train = x_train_selected
        x_test = x_test_selected

        # Targets (Points-For)
        # We need to get targets from the raw dataframes
        targets = {
            "home": (
                "home_points",
                train_df_raw["home_points"],
                test_df_raw["home_points"],
            ),
            "away": (
                "away_points",
                train_df_raw["away_points"],
                test_df_raw["away_points"],
            ),
        }

        variant_metrics = {}

        for target_name, (_, y_train, y_test) in targets.items():
            # Align indices just in case (though load_data returns aligned dfs)
            # Drop rows where target is NaN
            valid_train = ~y_train.isna()
            valid_test = ~y_test.isna()

            x_train_curr = x_train[valid_train]
            y_train_curr = y_train[valid_train]
            x_test_curr = x_test[valid_test]
            y_test_curr = y_test[valid_test]

            params = OmegaConf.to_container(cfg.model.params, resolve=True)

            model, preds = train_model(
                x_train_curr,
                y_train_curr,
                x_test_curr,
                y_test_curr,
                params,
                model_type=cfg.model.type,
            )
            metrics = _evaluate(y_test_curr, preds)
            variant_metrics[f"{target_name}_rmse"] = metrics["rmse"]
            variant_metrics[f"{target_name}_mae"] = metrics["mae"]

        res = {
            "Variant": variant["name"],
            "Feature Set": variant["feature_set"],
            "Home RMSE": variant_metrics["home_rmse"],
            "Away RMSE": variant_metrics["away_rmse"],
            "Avg RMSE": (variant_metrics["home_rmse"] + variant_metrics["away_rmse"])
            / 2,
        }
        results.append(res)

    # Create DataFrame
    df = pd.DataFrame(results)
    print("\n=== Weather Ablation Study Results (2024 Test Set) ===")
    print(df.to_markdown(index=False))

    # Save to reports
    report_path = project_root / "artifacts/reports/weather_ablation_results.csv"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(report_path, index=False)
    log.info(f"Saved results to {report_path}")


if __name__ == "__main__":
    main()
