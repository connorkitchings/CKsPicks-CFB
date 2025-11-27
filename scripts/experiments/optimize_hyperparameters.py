"""Hydra-based hyperparameter optimization CLI."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


import hydra
import mlflow
import pandas as pd
from omegaconf import DictConfig
from sklearn.base import clone
from sklearn.preprocessing import StandardScaler

from src.models.features import filter_features_by_pack, load_point_in_time_data
from src.models.train_model import (
    _build_feature_list,
    _concat_years,
    _evaluate,
    _suppress_linear_runtime_warnings,
    points_for_models,
    spread_models,
    total_models,
)
from src.utils.mlflow_tracking import get_tracking_uri


@hydra.main(config_path="../../conf", config_name="config", version_base=None)
def main(cfg: DictConfig) -> float:
    """Main entrypoint for hyperparameter optimization."""
    mlflow.set_tracking_uri(get_tracking_uri())
    mlflow.set_experiment(cfg.mlflow.experiment_name)

    with mlflow.start_run(nested=True, run_name=f"{cfg.model.name}_trial") as run:
        run_id = run.info.run_id
        experiment_id = run.info.experiment_id
        print(f"run_id: {run_id}")
        print(f"experiment_id: {experiment_id}")

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
        mlflow.log_param("off_adjustment_iteration", resolved_offense_iteration)
        mlflow.log_param("def_adjustment_iteration", resolved_defense_iteration)
        mlflow.log_param("model_name", cfg.model.name)
        mlflow.log_param("model_type", cfg.model.type)

        # --- Data Loading ---
        all_training_games = []
        for year in cfg.data.train_years:
            for week in range(1, 16):
                weekly_features = load_point_in_time_data(
                    year,
                    week,
                    cfg.data.data_root,
                    adjustment_iteration=cfg.data.adjustment_iteration,
                    adjustment_iteration_offense=cfg.data.adjustment_iteration_offense,
                    adjustment_iteration_defense=cfg.data.adjustment_iteration_defense,
                )
                if weekly_features is not None:
                    all_training_games.append(weekly_features)
        train_df = _concat_years(all_training_games)

        all_test_games = []
        for week in range(1, 16):
            weekly_features = load_point_in_time_data(
                cfg.data.test_year,
                week,
                cfg.data.data_root,
                adjustment_iteration=cfg.data.adjustment_iteration,
                adjustment_iteration_offense=cfg.data.adjustment_iteration_offense,
                adjustment_iteration_defense=cfg.data.adjustment_iteration_defense,
            )
            if weekly_features is not None:
                all_test_games.append(weekly_features)
        test_df = _concat_years(all_test_games)

        # Ensure target column exists (compute on the fly if needed)
        target_col = cfg.model.target
        for frame_name, frame in {"train_df": train_df, "test_df": test_df}.items():
            if target_col not in frame.columns:
                if {"home_points", "away_points"}.issubset(frame.columns):
                    if target_col == "spread_target":
                        frame[target_col] = frame["home_points"].astype(float) - frame[
                            "away_points"
                        ].astype(float)
                    elif target_col == "total_target":
                        frame[target_col] = frame["home_points"].astype(float) + frame[
                            "away_points"
                        ].astype(float)
                    else:
                        raise KeyError(
                            f"{frame_name} is missing target '{target_col}' and the script "
                            "does not know how to derive it from scores."
                        )
                else:
                    available_cols = ", ".join(sorted(frame.columns))
                    raise KeyError(
                        f"{frame_name} is missing required target column '{target_col}' "
                        "and does not contain home_points/away_points to derive it. "
                        f"Columns present: [{available_cols}]"
                    )

        # --- Feature Preparation ---
        feature_list = _build_feature_list(train_df)
        feature_list = [c for c in feature_list if c in test_df.columns]
        feature_packs = None
        if "features" in cfg and cfg.features.get("packs"):
            feature_packs = [str(pack) for pack in cfg.features.packs]
        min_feature_variance = (
            float(cfg.features.min_variance) if "features" in cfg else 0.0
        )
        feature_list = filter_features_by_pack(feature_list, feature_packs)
        if not feature_list:
            raise ValueError(
                "No features available after applying feature pack filters."
            )
        if feature_packs:
            mlflow.log_param("feature_packs", ",".join(feature_packs))
        else:
            mlflow.log_param("feature_packs", "all")
        mlflow.log_param("min_feature_variance", min_feature_variance)

        # Drop rows lacking model features or targets
        train_df = train_df.dropna(subset=feature_list + [target_col])
        test_df = test_df.dropna(subset=feature_list + [target_col])
        if train_df.empty or test_df.empty:
            raise ValueError(
                "Train or test split is empty after filtering required features/targets. "
                "Verify cached features and raw game scores for the configured years."
            )

        x_train = train_df[feature_list]
        y_train = train_df[target_col].astype(float)
        x_test = test_df[feature_list]
        y_test = test_df[target_col].astype(float)

        if min_feature_variance > 0:
            variances = x_train.var(axis=0, numeric_only=True)
            keep_cols = [
                col
                for col in feature_list
                if variances.get(col, 0.0) >= min_feature_variance
            ]
            if not keep_cols:
                raise ValueError(
                    "All features were removed by the variance threshold. Lower features.min_variance."
                )
            dropped = [col for col in feature_list if col not in keep_cols]
            if dropped:
                print(
                    f"Dropping {len(dropped)} low-variance features (threshold={min_feature_variance})"
                )
            feature_list = keep_cols
            x_train = x_train[feature_list]
            x_test = x_test[feature_list]

        scaler = None
        if bool(cfg.model.get("use_standard_scaler", False)):
            scaler = StandardScaler()
            x_train = pd.DataFrame(
                scaler.fit_transform(x_train),
                columns=x_train.columns,
                index=x_train.index,
            )
            x_test = pd.DataFrame(
                scaler.transform(x_test),
                columns=x_test.columns,
                index=x_test.index,
            )
            mlflow.log_param("feature_scaler", "standard")
        else:
            mlflow.log_param("feature_scaler", "none")

        # --- Model Training ---
        models_to_train = spread_models if cfg.model.type == "spread" else total_models
        base_model = models_to_train[cfg.model.name]
        model = clone(base_model)

        # Override model parameters with the ones from the trial
        params = {k: v for k, v in cfg.model.params.items() if k in model.get_params()}
        model.set_params(**params)
        mlflow.log_params(params)

        with _suppress_linear_runtime_warnings():
            model.fit(x_train, y_train)
        with _suppress_linear_runtime_warnings():
            preds = model.predict(x_test)
        metrics = _evaluate(y_test.to_numpy(), preds)

        mlflow.log_metrics({"test_rmse": metrics.rmse, "test_mae": metrics.mae})
        mlflow.sklearn.log_model(model, "model")

        return metrics.rmse


def _run_points_for_optimization(cfg: DictConfig) -> float:
    slice_path = Path(cfg.data.slice_path)
    if not slice_path.is_file():
        raise FileNotFoundError(
            f"Points-for slice not found at {slice_path}. Generate it via "
            "`python scripts/build_points_for_slice.py --season 2023` or adjust the path."
        )

    df = pd.read_csv(slice_path)
    if "week" not in df.columns:
        raise ValueError(
            f"Slice at {slice_path} missing 'week' column required for splitting."
        )
    if {"home_points", "away_points"}.difference(df.columns):
        raise ValueError(
            "Slice does not contain both home_points and away_points targets."
        )

    feature_cols = sorted(
        [
            col
            for col in df.columns
            if col.startswith(("home_adj_", "away_adj_"))
            or col in ("home_games_played", "away_games_played")
        ]
    )
    if not feature_cols:
        raise ValueError("No features found in points-for slice.")

    train_weeks = set(cfg.data.train_weeks or [])
    test_weeks = set(cfg.data.test_weeks or [])
    if not train_weeks or not test_weeks:
        raise ValueError(
            "Points-for configuration must specify non-empty train_weeks and test_weeks."
        )

    train_df = df[df["week"].isin(train_weeks)].dropna(
        subset=feature_cols + ["home_points", "away_points"]
    )
    test_df = df[df["week"].isin(test_weeks)].dropna(
        subset=feature_cols + ["home_points", "away_points"]
    )
    if train_df.empty or test_df.empty:
        raise ValueError(
            "Train or test split is empty after filtering. Check train_weeks/test_weeks configuration."
        )

    x_train = train_df[feature_cols].astype(float)
    x_test = test_df[feature_cols].astype(float)
    y_train_home = train_df["home_points"].astype(float)
    y_train_away = train_df["away_points"].astype(float)
    y_test_home = test_df["home_points"].astype(float)
    y_test_away = test_df["away_points"].astype(float)

    models_to_train = points_for_models
    base_model = models_to_train[cfg.model.name]
    params = {k: v for k, v in cfg.model.params.items() if k in base_model.get_params()}

    home_model = clone(base_model)
    away_model = clone(base_model)
    home_model.set_params(**params)
    away_model.set_params(**params)

    mlflow.log_params(params)
    mlflow.log_param("train_weeks", sorted(train_weeks))
    mlflow.log_param("test_weeks", sorted(test_weeks))
    mlflow.log_param("feature_count", len(feature_cols))

    with _suppress_linear_runtime_warnings():
        home_model.fit(x_train, y_train_home)
        away_model.fit(x_train, y_train_away)

    with _suppress_linear_runtime_warnings():
        preds_home = home_model.predict(x_test)
        preds_away = away_model.predict(x_test)

    home_metrics = _evaluate(y_test_home.to_numpy(), preds_home)
    away_metrics = _evaluate(y_test_away.to_numpy(), preds_away)
    actual_total = y_test_home.to_numpy() + y_test_away.to_numpy()
    pred_total = preds_home + preds_away
    actual_spread = y_test_home.to_numpy() - y_test_away.to_numpy()
    pred_spread = preds_home - preds_away

    total_metrics = _evaluate(actual_total, pred_total)
    spread_metrics = _evaluate(actual_spread, pred_spread)

    mlflow.log_metrics(
        {
            "test_rmse_home": home_metrics.rmse,
            "test_mae_home": home_metrics.mae,
            "test_rmse_away": away_metrics.rmse,
            "test_mae_away": away_metrics.mae,
            "test_rmse_total": total_metrics.rmse,
            "test_mae_total": total_metrics.mae,
            "test_rmse_spread": spread_metrics.rmse,
            "test_mae_spread": spread_metrics.mae,
        }
    )

    # Optimize for total RMSE to capture both outputs in a single scalar objective.
    return total_metrics.rmse


if __name__ == "__main__":
    main()
