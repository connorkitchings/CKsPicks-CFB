#!/usr/bin/env python3
"""Train and save points-for models for home and away scoring."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.base import clone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cks_picks_cfb.config import MODELS_DIR
from cks_picks_cfb.models.train_model import _evaluate, points_for_models

POINTS_FOR_HOME_MODEL_NAME = "points_for_home.joblib"
POINTS_FOR_AWAY_MODEL_NAME = "points_for_away.joblib"


def _parse_weeks(raw: str | None) -> list[int]:
    if not raw:
        return []
    candidate = raw.strip()
    try:
        if candidate.startswith("["):
            return [int(x) for x in json.loads(candidate)]
        return [int(x) for x in candidate.split(",") if x.strip()]
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Unable to parse weeks from '{raw}': {exc}") from exc


def _select_features(df: pd.DataFrame, prefix: str) -> list[str]:
    cols = [c for c in df.columns if c.startswith(f"{prefix}adj_")]
    games_col = f"{prefix}games_played"
    if games_col in df.columns:
        cols.append(games_col)
    if not cols:
        raise ValueError(f"No opponent-adjusted columns found with prefix '{prefix}'.")
    return cols


def build_dataset(df: pd.DataFrame, weeks: list[int]) -> tuple[pd.DataFrame, pd.Series]:
    subset = df[df["week"].isin(weeks)] if weeks else df
    if subset.empty:
        raise ValueError("Selected weeks produced an empty dataset.")
    return subset.copy(), subset.copy()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train points-for models for home and away scoring."
    )
    parser.add_argument(
        "--slice-path", required=True, help="Path to training slice CSV"
    )
    parser.add_argument(
        "--model",
        choices=list(points_for_models.keys()),
        default="ridge",
        help="Estimator to train",
    )
    parser.add_argument(
        "--model-year", type=int, required=True, help="Model year for artifact storage"
    )
    parser.add_argument(
        "--model-dir",
        type=str,
        default=str(MODELS_DIR),
        help="Directory to save models",
    )
    parser.add_argument(
        "--train-weeks",
        type=str,
        default="[3,4,5,6,7,8,9,10]",
        help="Weeks to use for training (comma separated or JSON array)",
    )
    parser.add_argument(
        "--valid-weeks",
        type=str,
        default="[11,12,13,14,15]",
        help="Weeks to use for validation/reporting",
    )
    parser.add_argument(
        "--features-path",
        type=str,
        default=None,
        help="Path to a JSON file containing feature lists for home and away models.",
    )
    args = parser.parse_args()

    slice_path = Path(args.slice_path)
    if not slice_path.is_file():
        raise FileNotFoundError(f"Training slice not found: {slice_path}")

    df = pd.read_csv(slice_path)
    required_cols = {"home_points", "away_points", "week"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Slice missing required columns: {sorted(missing)}")

    train_weeks = _parse_weeks(args.train_weeks)
    valid_weeks = _parse_weeks(args.valid_weeks)

    if args.features_path:
        with open(args.features_path, "r") as f:
            feature_lists = json.load(f)
        feature_cols_home = feature_lists.get("home_features", [])
        feature_cols_away = feature_lists.get("away_features", [])
    else:
        feature_cols_home = _select_features(df, "home_")
        feature_cols_away = _select_features(df, "away_")

    train_df = df[df["week"].isin(train_weeks)] if train_weeks else df
    if train_df.empty:
        raise ValueError("Training dataset is empty; adjust --train-weeks.")

    x_train_home = train_df[feature_cols_home].fillna(0.0).astype("float64")
    x_train_away = train_df[feature_cols_away].fillna(0.0).astype("float64")
    y_train_home = train_df["home_points"].astype("float64")
    y_train_away = train_df["away_points"].astype("float64")

    estimator = points_for_models[args.model]
    home_model = clone(estimator)
    away_model = clone(estimator)

    home_model.fit(x_train_home, y_train_home)
    away_model.fit(x_train_away, y_train_away)

    def _evaluate_split(model, features, actual):
        preds = model.predict(features)
        metrics = _evaluate(actual.to_numpy(), preds)
        return preds, metrics

    train_preds_home, train_metrics_home = _evaluate_split(
        home_model, x_train_home, y_train_home
    )
    train_preds_away, train_metrics_away = _evaluate_split(
        away_model, x_train_away, y_train_away
    )

    if valid_weeks:
        valid_df = df[df["week"].isin(valid_weeks)]
    else:
        valid_df = pd.DataFrame()

    if not valid_df.empty:
        x_valid_home = valid_df[feature_cols_home].fillna(0.0).astype("float64")
        x_valid_away = valid_df[feature_cols_away].fillna(0.0).astype("float64")
        y_valid_home = valid_df["home_points"].astype("float64")
        y_valid_away = valid_df["away_points"].astype("float64")
        valid_preds_home, valid_metrics_home = _evaluate_split(
            home_model, x_valid_home, y_valid_home
        )
        valid_preds_away, valid_metrics_away = _evaluate_split(
            away_model, x_valid_away, y_valid_away
        )
        total_actual = y_valid_home.to_numpy() + y_valid_away.to_numpy()
        total_preds = valid_preds_home + valid_preds_away
        total_metrics = _evaluate(total_actual, total_preds)
    else:
        valid_metrics_home = valid_metrics_away = total_metrics = None
        valid_preds_home = valid_preds_away = None
        total_actual = total_preds = None

    output_dir = Path(args.model_dir) / str(args.model_year)
    output_dir.mkdir(parents=True, exist_ok=True)
    home_path = output_dir / POINTS_FOR_HOME_MODEL_NAME
    away_path = output_dir / POINTS_FOR_AWAY_MODEL_NAME
    joblib.dump(home_model, home_path)
    joblib.dump(away_model, away_path)

    print(f"Saved home model to {home_path}")
    print(f"Saved away model to {away_path}")
    print("Training metrics (home, away) RMSE/MAE:")
    print(
        f"  Home: rmse={train_metrics_home.rmse:.3f}, mae={train_metrics_home.mae:.3f}"
    )
    print(
        f"  Away: rmse={train_metrics_away.rmse:.3f}, mae={train_metrics_away.mae:.3f}"
    )
    if (
        valid_metrics_home is not None
        and valid_metrics_away is not None
        and total_metrics is not None
    ):
        print("Validation metrics (home, away, total):")
        print(
            f"  Home: rmse={valid_metrics_home.rmse:.3f}, mae={valid_metrics_home.mae:.3f}"
        )
        print(
            f"  Away: rmse={valid_metrics_away.rmse:.3f}, mae={valid_metrics_away.mae:.3f}"
        )
        print(f"  Total: rmse={total_metrics.rmse:.3f}, mae={total_metrics.mae:.3f}")

    def _residual_std(actual, preds):
        if actual is None or preds is None:
            return None
        residuals = actual - preds
        if len(residuals) < 2:
            return None
        return float(pd.Series(residuals).std(ddof=1))

    if valid_preds_home is not None and valid_preds_away is not None:
        source = "validation"
        home_actual = y_valid_home.to_numpy()
        away_actual = y_valid_away.to_numpy()
        home_std = _residual_std(home_actual, valid_preds_home)
        away_std = _residual_std(away_actual, valid_preds_away)
        total_std = _residual_std(total_actual, total_preds)
        spread_std = _residual_std(
            home_actual - away_actual, valid_preds_home - valid_preds_away
        )
    else:
        source = "training"
        home_actual = y_train_home.to_numpy()
        away_actual = y_train_away.to_numpy()
        home_std = _residual_std(home_actual, train_preds_home)
        away_std = _residual_std(away_actual, train_preds_away)
        total_actual_train = home_actual + away_actual
        total_preds_train = train_preds_home + train_preds_away
        total_std = _residual_std(total_actual_train, total_preds_train)
        spread_std = _residual_std(
            home_actual - away_actual, train_preds_home - train_preds_away
        )

    stats = {
        "variance_source": source,
        "train_weeks": train_weeks,
        "valid_weeks": valid_weeks,
        "home_points": {
            "rmse": train_metrics_home.rmse,
            "mae": train_metrics_home.mae,
            "std": home_std,
        },
        "away_points": {
            "rmse": train_metrics_away.rmse,
            "mae": train_metrics_away.mae,
            "std": away_std,
        },
        "total_points": {
            "rmse": total_metrics.rmse if total_metrics else None,
            "mae": total_metrics.mae if total_metrics else None,
            "std": total_std,
        },
        "spread_points": {"std": spread_std},
    }

    stats_path = output_dir / "points_for_stats.json"
    stats_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
