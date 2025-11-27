"""Walk-forward validation script for evaluating model performance over time."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import warnings

import hydra
import mlflow
import numpy as np
import pandas as pd
from omegaconf import DictConfig
from sklearn.base import clone
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler

from src.models.features import (
    build_feature_list,
    filter_features_by_pack,
    load_point_in_time_data,
)
from src.models.train_model import (
    _concat_years,
    _evaluate,
    _suppress_linear_runtime_warnings,
    points_for_models,
    spread_models,
    total_models,
)
from src.utils.mlflow_tracking import get_tracking_uri


def _compute_vif(frame: pd.DataFrame) -> pd.Series:
    """Compute variance inflation factor (VIF) per column using linear regression R^2."""

    if frame.shape[1] <= 1:
        return pd.Series([0.0] * frame.shape[1], index=frame.columns)

    x = frame.to_numpy(dtype=float)
    vif_values: list[float] = []
    for idx, col in enumerate(frame.columns):
        y = x[:, idx]
        x_other = np.delete(x, idx, axis=1)
        if x_other.shape[1] == 0 or np.allclose(y, y[0]):
            vif_values.append(0.0)
            continue
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=RuntimeWarning)
            with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
                model = LinearRegression()
                model.fit(x_other, y)
                r2 = model.score(x_other, y)
        vif = float("inf") if r2 >= 0.999999 else float(1.0 / max(1e-12, 1.0 - r2))
        vif_values.append(vif)
    return pd.Series(vif_values, index=frame.columns)


def _prune_high_vif(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    *,
    threshold: float = 50.0,
    max_iter: int = 10,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Iteratively remove columns with VIF above threshold."""
    keep_cols = list(train_df.columns)
    dropped: list[str] = []
    for _ in range(max_iter):
        if len(keep_cols) <= 1:
            break
        vif = _compute_vif(train_df[keep_cols])
        high = vif[vif > threshold]
        if high.empty:
            break
        # drop the highest VIF column
        drop_col = high.sort_values(ascending=False).index[0]
        keep_cols.remove(drop_col)
        dropped.append(drop_col)
    return train_df[keep_cols], test_df[keep_cols], dropped


def _scale_features(
    train_df: pd.DataFrame, test_df: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Scale features using StandardScaler fitted on train_df."""
    scaler = StandardScaler()
    train_scaled = pd.DataFrame(
        scaler.fit_transform(train_df),
        columns=train_df.columns,
        index=train_df.index,
    )
    test_scaled = pd.DataFrame(
        scaler.transform(test_df),
        columns=train_df.columns,
        index=test_df.index,
    )
    return train_scaled, test_scaled


def _clip_extremes(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    *,
    lower_q: float = 0.005,
    upper_q: float = 0.995,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Clip feature values using train quantiles to reduce extreme outliers."""
    bounds = {}
    for col in train_df.columns:
        series = train_df[col].astype(float)
        bounds[col] = (
            series.quantile(lower_q),
            series.quantile(upper_q),
        )
    train_clipped = train_df.copy()
    test_clipped = test_df.copy()
    for col, (lo, hi) in bounds.items():
        train_clipped[col] = train_clipped[col].clip(lo, hi)
        test_clipped[col] = test_clipped[col].clip(lo, hi)
    return train_clipped, test_clipped


@hydra.main(config_path="../../conf", config_name="config", version_base=None)
def main(cfg: DictConfig) -> None:
    """Main entrypoint for walk-forward validation."""
    mlflow.set_tracking_uri(get_tracking_uri())
    mlflow.set_experiment(cfg.mlflow.experiment_name)

    season_metric_rows: list[dict] = []
    all_season_predictions: list[pd.DataFrame] = []
    start_week = int(cfg.walk_forward.get("start_week", 1))
    end_week = int(cfg.walk_forward.get("end_week", 15))
    configured_years = cfg.walk_forward.get("years")
    configured_feature_packs = cfg.walk_forward.get("feature_packs")
    if configured_years:
        years_to_process = sorted({int(y) for y in configured_years})
    else:
        years_to_process = list(range(cfg.data.train_years[0], cfg.data.test_year + 1))

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

    def _resolve_strategy(
        prefix: str, strategy: str, best_model_key: str | None
    ) -> str:
        if strategy == "ensemble":
            return f"{prefix}_pred_ensemble"
        if strategy == "best_single":
            if best_model_key is None:
                raise ValueError(
                    "best_model_key must be provided for 'best_single' strategy"
                )
            return f"{prefix}_pred_{best_model_key}"
        if strategy == "points_for":
            return f"{prefix}_pred_points_for_ensemble"
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

    feature_packs = None
    # Prefer run-level feature packs; fall back to global features config
    if configured_feature_packs:
        feature_packs = [str(pack) for pack in configured_feature_packs]
    elif "features" in cfg and cfg.features.get("packs"):
        feature_packs = [str(pack) for pack in cfg.features.packs]

    spread_model_names = cfg.walk_forward.get("spread_models") or list(
        spread_models.keys()
    )
    active_spread_models = {
        name: model
        for name, model in spread_models.items()
        if name in spread_model_names
    }
    total_model_names = cfg.walk_forward.get("total_models") or list(
        total_models.keys()
    )
    active_total_models = {
        name: model for name, model in total_models.items() if name in total_model_names
    }
    points_for_model_names = cfg.walk_forward.get("points_for_models") or list(
        points_for_models.keys()
    )
    active_points_for_models = {
        name: model
        for name, model in points_for_models.items()
        if name in points_for_model_names
    }
    min_feature_variance = (
        float(cfg.features.get("min_variance", 0.0)) if "features" in cfg else 0.0
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
                "feature_packs": ",".join(feature_packs) if feature_packs else "all",
                "min_feature_variance": min_feature_variance,
            }
        )

        for year in years_to_process:
            print(f"--- Running walk-forward validation for year: {year} ---")
            all_predictions = []
            for week in range(start_week, end_week + 1):
                print(f"  Processing Year {year}, Week {week}")

                # --- Data Loading (now using cached features) ---
                print("    Loading training data...")
                all_training_games = []
                if configured_years:
                    candidate_train_years = [y for y in years_to_process if y <= year]
                else:
                    candidate_train_years = list(
                        range(cfg.data.train_years[0], year + 1)
                    )
                for train_year in candidate_train_years:
                    limit = (
                        end_week + 1 if train_year < year else min(week, end_week + 1)
                    )
                    for train_week in range(start_week, limit):
                        weekly_data = load_point_in_time_data(
                            train_year,
                            train_week,
                            cfg.paths.data_dir,
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
                    cfg.paths.data_dir,
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
                feature_list = filter_features_by_pack(feature_list, feature_packs)
                if not feature_list:
                    print(
                        f"    Skipping week {week}: no features available after filtering."
                    )
                    continue
                if feature_packs:
                    print(
                        f"    Feature packs {feature_packs} selected → {len(feature_list)} columns"
                    )
                target_cols = [
                    "spread_target",
                    "total_target",
                    "home_points_for",
                    "away_points_for",
                ]

                train_df = train_df.dropna(subset=feature_list + target_cols)
                test_df = test_df.dropna(subset=feature_list + target_cols)

                if train_df.empty or test_df.empty:
                    print(f"    Skipping week {week}: Empty dataframe after cleaning.")
                    continue

                x_train = train_df[feature_list]
                x_train = train_df[feature_list]
                y_train_spread = train_df["spread_target"].astype(float)
                y_train_total = train_df["total_target"].astype(float)

                x_test = test_df[feature_list]
                y_test_spread = test_df["spread_target"].astype(float)
                y_test_total = test_df["total_target"].astype(float)
                y_train_home_points = train_df["home_points_for"].astype(float)
                y_train_away_points = train_df["away_points_for"].astype(float)

                y_test_home_points = test_df["home_points_for"].astype(float)
                y_test_away_points = test_df["away_points_for"].astype(float)

                if min_feature_variance > 0:
                    variances = x_train.var(axis=0, numeric_only=True)
                    keep_cols = [
                        col
                        for col in feature_list
                        if variances.get(col, 0.0) >= min_feature_variance
                    ]
                    if not keep_cols:
                        print(
                            f"    Skipping week {week}: variance threshold removed all features."
                        )
                        continue
                    dropped = [col for col in feature_list if col not in keep_cols]
                    if dropped:
                        print(
                            f"    Dropping {len(dropped)} low-variance features (threshold={min_feature_variance})"
                        )
                    feature_list = keep_cols
                    x_train = x_train[feature_list]
                    x_test = x_test[feature_list]

                # --- Outlier handling ---
                if cfg.features.get("preprocess", True):
                    x_train, x_test = _clip_extremes(x_train, x_test)

                    # --- Stable preprocessing: VIF pruning + scaling ---
                    x_train, x_test, vif_dropped = _prune_high_vif(
                        x_train,
                        x_test,
                        threshold=float(cfg.features.get("vif_threshold", 50.0)),
                        max_iter=10,
                    )
                    if vif_dropped:
                        print(
                            f"    Dropped {len(vif_dropped)} high-VIF features: "
                            f"{', '.join(vif_dropped[:5])}"
                            + ("..." if len(vif_dropped) > 5 else "")
                        )
                    x_train, x_test = _scale_features(x_train, x_test)
                else:
                    print(
                        "    Skipping preprocessing (clipping, VIF, scaling) as configured."
                    )

                # --- Model Training and Prediction ---
                week_predictions = test_df[
                    ["season", "week", "id", "home_team", "away_team"]
                ].copy()
                week_predictions["spread_actual"] = y_test_spread
                week_predictions["total_actual"] = y_test_total
                week_predictions["home_points_actual"] = y_test_home_points
                week_predictions["away_points_actual"] = y_test_away_points

                print("    Training and predicting with spread models...")
                with _suppress_linear_runtime_warnings():
                    for model_name, model in active_spread_models.items():
                        model.fit(x_train, y_train_spread)
                        preds = model.predict(x_test)
                        week_predictions[f"spread_pred_{model_name}"] = preds
                print("    Spread models complete.")

                print("    Training and predicting with total models...")
                with _suppress_linear_runtime_warnings():
                    for model_name, model in active_total_models.items():
                        model.fit(x_train, y_train_total)
                        preds = model.predict(x_test)
                        week_predictions[f"total_pred_{model_name}"] = preds
                print("    Total models complete.")

                print("    Training and predicting with points-for models...")
                with _suppress_linear_runtime_warnings():
                    for model_name, model in active_points_for_models.items():
                        # Home points
                        home_model = clone(model)
                        home_model.fit(x_train, y_train_home_points)
                        preds_home = home_model.predict(x_test)
                        week_predictions[f"home_points_pred_{model_name}"] = preds_home

                        # Away points
                        away_model = clone(model)
                        away_model.fit(x_train, y_train_away_points)
                        preds_away = away_model.predict(x_test)
                        week_predictions[f"away_points_pred_{model_name}"] = preds_away

                # Add derived total and spread from points-for models
                for model_name in active_points_for_models:
                    week_predictions[f"total_pred_points_for_{model_name}"] = (
                        week_predictions[f"home_points_pred_{model_name}"]
                        + week_predictions[f"away_points_pred_{model_name}"]
                    )
                    week_predictions[f"spread_pred_points_for_{model_name}"] = (
                        week_predictions[f"home_points_pred_{model_name}"]
                        - week_predictions[f"away_points_pred_{model_name}"]
                    )
                print("    Points-for models complete.")

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

            # Add ensemble for points-for
            home_points_cols = [
                c
                for c in season_predictions.columns
                if c.startswith("home_points_pred_")
            ]
            away_points_cols = [
                c
                for c in season_predictions.columns
                if c.startswith("away_points_pred_")
            ]
            if home_points_cols and away_points_cols:
                season_predictions["home_points_pred_ensemble"] = season_predictions[
                    home_points_cols
                ].mean(axis=1)
                season_predictions["away_points_pred_ensemble"] = season_predictions[
                    away_points_cols
                ].mean(axis=1)
                season_predictions["total_pred_points_for_ensemble"] = (
                    season_predictions["home_points_pred_ensemble"]
                    + season_predictions["away_points_pred_ensemble"]
                )
                season_predictions["spread_pred_points_for_ensemble"] = (
                    season_predictions["home_points_pred_ensemble"]
                    - season_predictions["away_points_pred_ensemble"]
                )

            for model_name in active_spread_models:
                _evaluate_and_log(
                    season_predictions,
                    year_label=str(year),
                    target="spread",
                    model_key=model_name,
                    actual_col="spread_actual",
                    pred_col=f"spread_pred_{model_name}",
                )

            for model_name in active_total_models:
                _evaluate_and_log(
                    season_predictions,
                    year_label=str(year),
                    target="total",
                    model_key=model_name,
                    actual_col="total_actual",
                    pred_col=f"total_pred_{model_name}",
                )

            for model_name in active_points_for_models:
                _evaluate_and_log(
                    season_predictions,
                    year_label=str(year),
                    target="spread",
                    model_key=f"points_for_{model_name}",
                    actual_col="spread_actual",
                    pred_col=f"spread_pred_points_for_{model_name}",
                )
                _evaluate_and_log(
                    season_predictions,
                    year_label=str(year),
                    target="total",
                    model_key=f"points_for_{model_name}",
                    actual_col="total_actual",
                    pred_col=f"total_pred_points_for_{model_name}",
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

            if "spread_pred_points_for_ensemble" in season_predictions.columns:
                _evaluate_and_log(
                    season_predictions,
                    year_label=str(year),
                    target="spread",
                    model_key="points_for_ensemble",
                    actual_col="spread_actual",
                    pred_col="spread_pred_points_for_ensemble",
                )
                _evaluate_and_log(
                    season_predictions,
                    year_label=str(year),
                    target="total",
                    model_key="points_for_ensemble",
                    actual_col="total_actual",
                    pred_col="total_pred_points_for_ensemble",
                )

            # Log strategy selections
            spread_strategy_col = _resolve_strategy(
                "spread",
                cfg.walk_forward.spread_strategy,
                cfg.walk_forward.get("best_spread_model"),
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
                cfg.walk_forward.get("best_total_model"),
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

            for model_name in active_spread_models:
                _evaluate_and_log(
                    combined_predictions,
                    year_label="overall",
                    target="spread",
                    model_key=model_name,
                    actual_col="spread_actual",
                    pred_col=f"spread_pred_{model_name}",
                )

            for model_name in active_total_models:
                _evaluate_and_log(
                    combined_predictions,
                    year_label="overall",
                    target="total",
                    model_key=model_name,
                    actual_col="total_actual",
                    pred_col=f"total_pred_{model_name}",
                )

            for model_name in active_points_for_models:
                _evaluate_and_log(
                    combined_predictions,
                    year_label="overall",
                    target="spread",
                    model_key=f"points_for_{model_name}",
                    actual_col="spread_actual",
                    pred_col=f"spread_pred_points_for_{model_name}",
                )
                _evaluate_and_log(
                    combined_predictions,
                    year_label="overall",
                    target="total",
                    model_key=f"points_for_{model_name}",
                    actual_col="total_actual",
                    pred_col=f"total_pred_points_for_{model_name}",
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

            if "spread_pred_points_for_ensemble" in combined_predictions.columns:
                _evaluate_and_log(
                    combined_predictions,
                    year_label="overall",
                    target="spread",
                    model_key="points_for_ensemble",
                    actual_col="spread_actual",
                    pred_col="spread_pred_points_for_ensemble",
                )
                _evaluate_and_log(
                    combined_predictions,
                    year_label="overall",
                    target="total",
                    model_key="points_for_ensemble",
                    actual_col="total_actual",
                    pred_col="total_pred_points_for_ensemble",
                )

            overall_spread_strategy_col = _resolve_strategy(
                "spread",
                cfg.walk_forward.spread_strategy,
                cfg.walk_forward.get("best_spread_model"),
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
                cfg.walk_forward.get("best_total_model"),
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

    # Return the final metric for Hydra
    final_rmse = metrics_df[
        (metrics_df["year"] == "overall")
        & (metrics_df["target"] == "spread")
        & (metrics_df["model"] == f"strategy_{cfg.walk_forward.spread_strategy}")
    ]["rmse"].iloc[0]

    return float(final_rmse)


if __name__ == "__main__":
    main()
