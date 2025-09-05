from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error

from cfb_model.data.storage.local_storage import LocalStorage


def _prepare_team_features(team_season_adj_df: pd.DataFrame) -> pd.DataFrame:
    base_cols = ["season", "team", "games_played"]
    off_metric_cols = [
        c for c in team_season_adj_df.columns if c.startswith("adj_off_")
    ]
    for extra in [
        "off_eckel_rate",
        "off_finish_pts_per_opp",
        "stuff_rate",
        "havoc_rate",
    ]:
        if extra in team_season_adj_df.columns:
            off_metric_cols.append(extra)
    def_metric_cols = [
        c for c in team_season_adj_df.columns if c.startswith("adj_def_")
    ]
    off_df = team_season_adj_df[base_cols + off_metric_cols].copy()
    if off_metric_cols:
        off_df = off_df.dropna(subset=off_metric_cols, how="all")
    def_df = team_season_adj_df[base_cols + def_metric_cols].copy()
    if def_metric_cols:
        def_df = def_df.dropna(subset=def_metric_cols, how="all")
    combined = off_df.merge(
        def_df, on=["season", "team"], how="outer", suffixes=("", "_defside")
    )
    if "games_played_x" in combined.columns or "games_played_y" in combined.columns:
        combined["games_played"] = combined[
            [c for c in ["games_played_x", "games_played_y"] if c in combined.columns]
        ].max(axis=1, skipna=True)
        combined = combined.drop(
            columns=[
                c for c in ["games_played_x", "games_played_y"] if c in combined.columns
            ]
        )
    return combined


def _load_merged_dataset(year: int, data_root: str | None) -> pd.DataFrame:
    processed_storage = LocalStorage(
        data_root=data_root, file_format="csv", data_type="processed"
    )
    raw_storage = LocalStorage(data_root=data_root, file_format="csv", data_type="raw")

    team_season_adj_records = processed_storage.read_index(
        "team_season_adj", {"year": year}
    )
    if not team_season_adj_records:
        raise ValueError(f"No adjusted team season data found for year {year}")
    team_season_adj_df = pd.DataFrame.from_records(team_season_adj_records)
    team_features = _prepare_team_features(team_season_adj_df)

    game_records = raw_storage.read_index("games", {"year": year})
    if not game_records:
        raise ValueError(f"No raw game data found for year {year}")
    games_df = pd.DataFrame.from_records(game_records)

    home_features = team_features.add_prefix("home_")
    away_features = team_features.add_prefix("away_")
    merged_df = games_df.merge(
        home_features,
        left_on=["season", "home_team"],
        right_on=["home_season", "home_team"],
        how="left",
    )
    merged_df = merged_df.merge(
        away_features,
        left_on=["season", "away_team"],
        right_on=["away_season", "away_team"],
        how="left",
    )

    required_scores = {"home_points", "away_points"}
    if not required_scores.issubset(merged_df.columns):
        raise ValueError(
            "Games data missing required score columns: home_points, away_points"
        )

    merged_df["spread_target"] = merged_df["home_points"].astype(float) - merged_df[
        "away_points"
    ].astype(float)
    merged_df["total_target"] = merged_df["home_points"].astype(float) + merged_df[
        "away_points"
    ].astype(float)
    merged_df = merged_df.drop(columns=["home_season", "away_season"], errors="ignore")
    return merged_df


def _build_feature_list(df: pd.DataFrame) -> list[str]:
    adjusted_metrics = [
        "epa_pp",
        "sr",
        "ypp",
        "expl_rate_overall_10",
        "expl_rate_overall_20",
        "expl_rate_overall_30",
        "expl_rate_rush",
        "expl_rate_pass",
    ]
    features: list[str] = []
    for side in ["home", "away"]:
        for prefix in ["adj_off_", "adj_def_"]:
            for metric in adjusted_metrics:
                col = f"{side}_{prefix}{metric}"
                if col in df.columns:
                    features.append(col)
        for extra in [
            "off_eckel_rate",
            "off_finish_pts_per_opp",
            "stuff_rate",
            "havoc_rate",
        ]:
            col = f"{side}_{extra}"
            if col in df.columns:
                features.append(col)
    return features


def _train_and_save(X: pd.DataFrame, y: pd.Series, out_dir: str, name: str) -> None:  # noqa: N803
    os.makedirs(out_dir, exist_ok=True)
    model = Ridge(alpha=1.0)
    model.fit(X, y)
    joblib.dump(model, os.path.join(out_dir, f"{name}.joblib"))


@dataclass
class Metrics:
    rmse: float
    mae: float


def _evaluate(y_true: np.ndarray, y_pred: np.ndarray) -> Metrics:
    return Metrics(
        rmse=float(np.sqrt(mean_squared_error(y_true, y_pred))),
        mae=float(mean_absolute_error(y_true, y_pred)),
    )


def _concat_years(dfs: Iterable[pd.DataFrame]) -> pd.DataFrame:
    frames = [df for df in dfs if df is not None and not df.empty]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Train ridge baseline on multiple years and evaluate on a test year."
    )
    parser.add_argument(
        "--train-years",
        type=str,
        default="2019,2021,2022,2023",
        help="Comma-separated training years",
    )
    parser.add_argument("--test-year", type=int, default=2024, help="Holdout test year")
    parser.add_argument("--data-root", type=str, default=None, help="Data root path")
    parser.add_argument(
        "--model-dir",
        type=str,
        default="./models/ridge_baseline",
        help="Output dir for models",
    )
    parser.add_argument(
        "--metrics-dir",
        type=str,
        default="./reports/metrics",
        help="Output dir for metrics CSV",
    )
    args = parser.parse_args()

    train_years = [int(y.strip()) for y in args.train_years.split(",") if y.strip()]
    test_year = int(args.test_year)

    print(f"Loading training years: {train_years}")
    train_dfs = [_load_merged_dataset(y, args.data_root) for y in train_years]
    train_df = _concat_years(train_dfs)

    print(f"Loading test year: {test_year}")
    test_df = _load_merged_dataset(test_year, args.data_root)

    # Build feature list present in both train and test
    feature_list = _build_feature_list(train_df)
    feature_list = [c for c in feature_list if c in test_df.columns]

    # Filter rows with complete features/targets
    target_cols = ["spread_target", "total_target"]
    train_df = train_df.dropna(subset=feature_list + target_cols)
    test_df = test_df.dropna(subset=feature_list + target_cols)

    X_train = train_df[feature_list]  # noqa: N806
    y_spread_train = train_df["spread_target"].astype(float)
    y_total_train = train_df["total_target"].astype(float)

    X_test = test_df[feature_list]  # noqa: N806
    y_spread_test = test_df["spread_target"].astype(float)
    y_total_test = test_df["total_target"].astype(float)

    out_dir = os.path.join(args.model_dir, str(test_year))
    print("Training spread model...")
    _train_and_save(X_train, y_spread_train, out_dir, name="ridge_spread")
    print("Training total model...")
    _train_and_save(X_train, y_total_train, out_dir, name="ridge_total")

    # Load back and evaluate on test
    spread_model = joblib.load(os.path.join(out_dir, "ridge_spread.joblib"))
    total_model = joblib.load(os.path.join(out_dir, "ridge_total.joblib"))
    spread_pred = spread_model.predict(X_test)
    total_pred = total_model.predict(X_test)

    spread_metrics = _evaluate(y_spread_test.to_numpy(), spread_pred)
    total_metrics = _evaluate(y_total_test.to_numpy(), total_pred)

    # Persist metrics
    os.makedirs(args.metrics_dir, exist_ok=True)
    metrics_path = os.path.join(
        args.metrics_dir, f"ridge_baseline_eval_{test_year}.csv"
    )
    pd.DataFrame(
        [
            {
                "target": "spread",
                "rmse": spread_metrics.rmse,
                "mae": spread_metrics.mae,
            },
            {"target": "total", "rmse": total_metrics.rmse, "mae": total_metrics.mae},
        ]
    ).to_csv(metrics_path, index=False)
    print(f"Saved evaluation metrics to {metrics_path}")


if __name__ == "__main__":
    main()
