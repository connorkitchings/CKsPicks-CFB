"""Walk-forward validation script for evaluating model performance over time."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import hydra
import mlflow
import pandas as pd
from omegaconf import DictConfig

from src.models.features import (
    build_feature_list,
    load_point_in_time_data,
)
from src.models.train_model import (
    _concat_years,
    _evaluate,
    _suppress_linear_runtime_warnings,
    spread_models,
    total_models,
)


@hydra.main(config_path="../conf", config_name="config", version_base=None)
def main(cfg: DictConfig) -> None:
    """Main entrypoint for walk-forward validation."""
    mlflow.set_tracking_uri("file:./artifacts/mlruns")
    mlflow.set_experiment(cfg.mlflow.experiment_name)

    season_metric_rows: list[dict] = []
    all_season_predictions: list[pd.DataFrame] = []

    def _evaluate_and_log(
        df: pd.DataFrame,
        *,
        year_label: str,
        target: str,
        model_key: str,
        actual_col: str,
        pred_col: str,
    ) -> None:
        """Evaluate predictions, log metrics, and capture summary rows."""
        if pred_col not in df.columns:
            print(
                f"    Skipping {target} model '{model_key}': column '{pred_col}' missing."
            )
            return

        valid = df[[actual_col, pred_col]].dropna()
        if valid.empty:
            print(
                f"    Skipping {target} model '{model_key}': no rows after dropping NA."
            )
            return

        metrics = _evaluate(valid[actual_col].to_numpy(), valid[pred_col].to_numpy())
        mlflow.log_metrics(
            {
                f"{year_label}_{model_key}_{target}_rmse": metrics.rmse,
                f"{year_label}_{model_key}_{target}_mae": metrics.mae,
            }
        )
        season_metric_rows.append(
            {
                "year": year_label,
                "target": target,
                "model": model_key,
                "rmse": metrics.rmse,
                "mae": metrics.mae,
            }
        )

    def _resolve_strategy(prefix: str, strategy: str, best_model_key: str) -> str:
        if strategy == "ensemble":
            return f"{prefix}_pred_ensemble"
        if strategy == "best_single":
            return f"{prefix}_pred_{best_model_key}"
        raise ValueError(
            f"Unknown {prefix} strategy '{strategy}'. Expected 'ensemble' or 'best_single'."
        )

    if (
        cfg.walk_forward.spread_strategy == "best_single"
        and cfg.walk_forward.best_spread_model not in spread_models
    ):
        raise ValueError(
            f"Configured best_spread_model '{cfg.walk_forward.best_spread_model}' "
            f"is not one of the available spread models: {list(spread_models.keys())}"
        )
    if (
        cfg.walk_forward.total_strategy == "best_single"
        and cfg.walk_forward.best_total_model not in total_models
    ):
        raise ValueError(
            f"Configured best_total_model '{cfg.walk_forward.best_total_model}' "
            f"is not one of the available total models: {list(total_models.keys())}"
        )

    with mlflow.start_run(run_name="Walk_Forward_Validation_All_Models"):
        resolved_offense_iteration = (
            cfg.data.adjustment_iteration_offense
            if cfg.data.adjustment_iteration_offense is not None
            else cfg.data.adjustment_iteration
        )
        resolved_defense_iteration = (
            cfg.data.adjustment_iteration_defense
            if cfg.data.adjustment_iteration_defense is not None
            else cfg.data.adjustment_iteration
        )
        mlflow.log_params(
            {
                "train_years": str(cfg.data.train_years),
                "test_year": cfg.data.test_year,
                "off_adjustment_iteration": resolved_offense_iteration,
                "def_adjustment_iteration": resolved_defense_iteration,
            }
        )

        for year in range(cfg.data.train_years[0], cfg.data.test_year + 1):
            print(f"--- Running walk-forward validation for year: {year} ---")
            all_predictions = []
            for week in range(1, 16):
                print(f"  Processing Year {year}, Week {week}")

                # --- Data Loading (now using cached features) ---
                print("    Loading training data...")
                all_training_games = []
                for train_year in range(cfg.data.train_years[0], year + 1):
                    for train_week in range(1, 16 if train_year < year else week):
                        weekly_data = load_point_in_time_data(
                            train_year,
                            train_week,
                            cfg.data.data_root,
                            adjustment_iteration=cfg.data.adjustment_iteration,
                            adjustment_iteration_offense=cfg.data.adjustment_iteration_offense,
                            adjustment_iteration_defense=cfg.data.adjustment_iteration_defense,
                        )
                        if weekly_data is not None:
                            all_training_games.append(weekly_data)

                if not all_training_games:
                    print(f"    Skipping week {week}: No training data available.")
                    continue
                train_df = _concat_years(all_training_games)
                print(f"    Training data loaded: {len(train_df)} games.")

                print("    Loading test data...")
                test_df = load_point_in_time_data(
                    year,
                    week,
                    cfg.data.data_root,
                    adjustment_iteration=cfg.data.adjustment_iteration,
                    adjustment_iteration_offense=cfg.data.adjustment_iteration_offense,
                    adjustment_iteration_defense=cfg.data.adjustment_iteration_defense,
                )
                if test_df is None:
                    print(f"    Skipping week {week}: No test data available.")
                    continue
                print(f"    Test data loaded: {len(test_df)} games.")

                # --- Feature Preparation ---
                feature_list = build_feature_list(train_df)
                feature_list = [c for c in feature_list if c in test_df.columns]
                target_cols = ["spread_target", "total_target"]

                train_df = train_df.dropna(subset=feature_list + target_cols)
                test_df = test_df.dropna(subset=feature_list + target_cols)

                if train_df.empty or test_df.empty:
                    print(f"    Skipping week {week}: Empty dataframe after cleaning.")
                    continue

                x_train = train_df[feature_list]
                y_train_spread = train_df["spread_target"].astype(float)
                y_train_total = train_df["total_target"].astype(float)

                x_test = test_df[feature_list]
                y_test_spread = test_df["spread_target"].astype(float)
                y_test_total = test_df["total_target"].astype(float)

                # --- Model Training and Prediction ---
                week_predictions = test_df[
                    ["season", "week", "id", "home_team", "away_team"]
                ].copy()
                week_predictions["spread_actual"] = y_test_spread
                week_predictions["total_actual"] = y_test_total

                print("    Training and predicting with spread models...")
                with _suppress_linear_runtime_warnings():
                    for model_name, model in spread_models.items():
                        model.fit(x_train, y_train_spread)
                        preds = model.predict(x_test)
                        week_predictions[f"spread_pred_{model_name}"] = preds
                print("    Spread models complete.")

                print("    Training and predicting with total models...")
                with _suppress_linear_runtime_warnings():
                    for model_name, model in total_models.items():
                        model.fit(x_train, y_train_total)
                        preds = model.predict(x_test)
                        week_predictions[f"total_pred_{model_name}"] = preds
                print("    Total models complete.")

                all_predictions.append(week_predictions)

            if not all_predictions:
                print(f"No predictions generated for year {year}.")
                continue

            # --- Evaluate and Log Metrics ---
            print(f"  Evaluating performance for year {year}...")
            season_predictions = pd.concat(all_predictions, ignore_index=True)

            spread_pred_cols = [
                col
                for col in season_predictions.columns
                if col.startswith("spread_pred_")
            ]
            total_pred_cols = [
                col
                for col in season_predictions.columns
                if col.startswith("total_pred_")
            ]

            if spread_pred_cols:
                season_predictions["spread_pred_ensemble"] = season_predictions[
                    spread_pred_cols
                ].mean(axis=1)
            if total_pred_cols:
                season_predictions["total_pred_ensemble"] = season_predictions[
                    total_pred_cols
                ].mean(axis=1)

            for model_name in spread_models:
                _evaluate_and_log(
                    season_predictions,
                    year_label=str(year),
                    target="spread",
                    model_key=model_name,
                    actual_col="spread_actual",
                    pred_col=f"spread_pred_{model_name}",
                )

            for model_name in total_models:
                _evaluate_and_log(
                    season_predictions,
                    year_label=str(year),
                    target="total",
                    model_key=model_name,
                    actual_col="total_actual",
                    pred_col=f"total_pred_{model_name}",
                )

            if "spread_pred_ensemble" in season_predictions.columns:
                _evaluate_and_log(
                    season_predictions,
                    year_label=str(year),
                    target="spread",
                    model_key="ensemble",
                    actual_col="spread_actual",
                    pred_col="spread_pred_ensemble",
                )

            if "total_pred_ensemble" in season_predictions.columns:
                _evaluate_and_log(
                    season_predictions,
                    year_label=str(year),
                    target="total",
                    model_key="ensemble",
                    actual_col="total_actual",
                    pred_col="total_pred_ensemble",
                )

            # Log strategy selections
            spread_strategy_col = _resolve_strategy(
                "spread",
                cfg.walk_forward.spread_strategy,
                cfg.walk_forward.best_spread_model,
            )
            _evaluate_and_log(
                season_predictions,
                year_label=str(year),
                target="spread",
                model_key=f"strategy_{cfg.walk_forward.spread_strategy}",
                actual_col="spread_actual",
                pred_col=spread_strategy_col,
            )

            total_strategy_col = _resolve_strategy(
                "total",
                cfg.walk_forward.total_strategy,
                cfg.walk_forward.best_total_model,
            )
            _evaluate_and_log(
                season_predictions,
                year_label=str(year),
                target="total",
                model_key=f"strategy_{cfg.walk_forward.total_strategy}",
                actual_col="total_actual",
                pred_col=total_strategy_col,
            )

            print(f"  Metrics for {year} logged to MLflow.")

            # Save predictions
            output_dir = Path("./artifacts/validation/walk_forward")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{year}_predictions.csv"
            season_predictions.to_csv(output_path, index=False)
            print(f"  Saved consolidated predictions for {year} to {output_path}")
            all_season_predictions.append(
                season_predictions.assign(validation_year=year)
            )

        if all_season_predictions:
            print("Computing aggregate metrics across all seasons...")
            combined_predictions = pd.concat(all_season_predictions, ignore_index=True)

            # Ensure ensemble columns exist if possible
            spread_cols = [
                col
                for col in combined_predictions.columns
                if col.startswith("spread_pred_")
            ]
            total_cols = [
                col
                for col in combined_predictions.columns
                if col.startswith("total_pred_")
            ]
            if "spread_pred_ensemble" not in combined_predictions and spread_cols:
                combined_predictions["spread_pred_ensemble"] = combined_predictions[
                    spread_cols
                ].mean(axis=1)
            if "total_pred_ensemble" not in combined_predictions and total_cols:
                combined_predictions["total_pred_ensemble"] = combined_predictions[
                    total_cols
                ].mean(axis=1)

            for model_name in spread_models:
                _evaluate_and_log(
                    combined_predictions,
                    year_label="overall",
                    target="spread",
                    model_key=model_name,
                    actual_col="spread_actual",
                    pred_col=f"spread_pred_{model_name}",
                )

            for model_name in total_models:
                _evaluate_and_log(
                    combined_predictions,
                    year_label="overall",
                    target="total",
                    model_key=model_name,
                    actual_col="total_actual",
                    pred_col=f"total_pred_{model_name}",
                )

            if "spread_pred_ensemble" in combined_predictions.columns:
                _evaluate_and_log(
                    combined_predictions,
                    year_label="overall",
                    target="spread",
                    model_key="ensemble",
                    actual_col="spread_actual",
                    pred_col="spread_pred_ensemble",
                )
            if "total_pred_ensemble" in combined_predictions.columns:
                _evaluate_and_log(
                    combined_predictions,
                    year_label="overall",
                    target="total",
                    model_key="ensemble",
                    actual_col="total_actual",
                    pred_col="total_pred_ensemble",
                )

            overall_spread_strategy_col = _resolve_strategy(
                "spread",
                cfg.walk_forward.spread_strategy,
                cfg.walk_forward.best_spread_model,
            )
            _evaluate_and_log(
                combined_predictions,
                year_label="overall",
                target="spread",
                model_key=f"strategy_{cfg.walk_forward.spread_strategy}",
                actual_col="spread_actual",
                pred_col=overall_spread_strategy_col,
            )

            overall_total_strategy_col = _resolve_strategy(
                "total",
                cfg.walk_forward.total_strategy,
                cfg.walk_forward.best_total_model,
            )
            _evaluate_and_log(
                combined_predictions,
                year_label="overall",
                target="total",
                model_key=f"strategy_{cfg.walk_forward.total_strategy}",
                actual_col="total_actual",
                pred_col=overall_total_strategy_col,
            )

            # Persist metrics summary
            metrics_df = pd.DataFrame(season_metric_rows)
            metrics_output = Path(
                "./artifacts/validation/walk_forward/metrics_summary.csv"
            )
            metrics_output.parent.mkdir(parents=True, exist_ok=True)
            metrics_df.sort_values(["target", "model", "year"]).to_csv(
                metrics_output, index=False
            )
            print(f"Saved aggregated metrics summary to {metrics_output}")

    print("Walk-forward validation complete.")


if __name__ == "__main__":
    main()
