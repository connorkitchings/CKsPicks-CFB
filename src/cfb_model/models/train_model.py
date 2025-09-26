"""Training helpers for baseline models.

Provides utilities to load/merge features and targets and to train and persist
ridge models for spread and total tasks.
"""

import os

import joblib
import pandas as pd
from sklearn.linear_model import Ridge

from cfb_model.data.storage.local_storage import LocalStorage
from cfb_model.models.features import load_merged_dataset, prepare_team_features


def _prepare_team_features(team_season_adj_df: pd.DataFrame) -> pd.DataFrame:
    # Backward-compat shim: delegate to shared helper
    return prepare_team_features(team_season_adj_df)
    """Prepare one-row-per-team features combining offense and defense.

    Keeps adjusted offense/defense metrics and selected unadjusted offense rates.

    Args:
        team_season_adj_df: DataFrame returned from processed/team_season_adj read.

    Returns:
        DataFrame with columns: season, team, games_played, adj_off_*, adj_def_*,
        and selected unadjusted offense metrics (off_eckel_rate, off_finish_pts_per_opp,
        stuff_rate, havoc_rate) when available.
    """
    base_cols = ["season", "team", "games_played"]

    off_metric_cols = [
        c for c in team_season_adj_df.columns if c.startswith("adj_off_")
    ]
    # Include selected unadjusted offense metrics if present
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
    # Require at least one adjusted offense metric to be non-null to keep the row
    if off_metric_cols:
        off_df = off_df.dropna(subset=off_metric_cols, how="all")

    def_df = team_season_adj_df[base_cols + def_metric_cols].copy()
    if def_metric_cols:
        def_df = def_df.dropna(subset=def_metric_cols, how="all")

    combined = off_df.merge(
        def_df,
        on=["season", "team"],
        how="outer",
        suffixes=("", "_defside"),
    )

    # Consolidate games_played if present from both sides
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


def load_features_and_targets(year: int, data_root: str | None) -> pd.DataFrame:
    # Delegate to shared loader to avoid drift
    return load_merged_dataset(year, data_root)
    """Load adjusted team-season features and compute training targets for a season.

    Args:
        year: Season year to load.
        data_root: Optional absolute data root; falls back to CFB_MODEL_DATA_ROOT or cwd/data.

    Returns:
        Merged DataFrame with home/away features and spread/total targets.
    """
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

    # Prepare combined per-team features
    team_features = _prepare_team_features(team_season_adj_df)

    # Load raw games
    game_records = raw_storage.read_index("games", {"year": year})
    if not game_records:
        raise ValueError(f"No raw game data found for year {year}")
    games_df = pd.DataFrame.from_records(game_records)

    # Merge home/away team features
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

    # Targets from final scores
    if not {"home_points", "away_points"}.issubset(merged_df.columns):
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


def train_ridge_model(
    x: pd.DataFrame, y: pd.Series, model_type: str, year: int, model_dir: str
) -> None:
    """Train a Ridge Regression model and persist it to disk.

    Args:
        X: Feature matrix.
        y: Target vector.
        model_type: "spread" or "total".
        year: Season year.
        model_dir: Output directory for model artifacts.
    """
    model = Ridge(alpha=1.0)
    model.fit(x, y)

    os.makedirs(os.path.join(model_dir, str(year)), exist_ok=True)
    model_path = os.path.join(model_dir, str(year), f"ridge_{model_type}.joblib")
    joblib.dump(model, model_path)
    print(f"Saved {model_type} model for {year} to {model_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Train Ridge Regression models for CFB betting."
    )
    parser.add_argument(
        "--year", type=int, required=True, help="Season year to train the model for."
    )
    parser.add_argument(
        "--data-root",
        type=str,
        default=None,
        help="Absolute path to the data root directory.",
    )
    parser.add_argument(
        "--model-dir",
        type=str,
        default="./models",
        help="Directory to save trained models.",
    )

    args = parser.parse_args()

    try:
        print(f"Loading data for year {args.year}...")
        df = load_features_and_targets(args.year, args.data_root)

        # Build feature list from available adjusted metrics and selected extras
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

        feature_candidates: list[str] = []
        for side in ["home", "away"]:
            for prefix in ["adj_off_", "adj_def_"]:
                for metric in adjusted_metrics:
                    col = f"{side}_{prefix}{metric}"
                    if col in df.columns:
                        feature_candidates.append(col)
            # Selected unadjusted offense extras if present
            for extra in [
                "off_eckel_rate",
                "off_finish_pts_per_opp",
                "stuff_rate",
                "havoc_rate",
            ]:
                col = f"{side}_{extra}"
                if col in df.columns:
                    feature_candidates.append(col)

        # Drop rows with missing features or targets
        df_cleaned = df.dropna(
            subset=feature_candidates + ["spread_target", "total_target"]
        )

        X = df_cleaned[feature_candidates]
        y_spread = df_cleaned["spread_target"].astype(float)
        y_total = df_cleaned["total_target"].astype(float)

        print(f"Training spread model for year {args.year}...")
        train_ridge_model(X, y_spread, "spread", args.year, args.model_dir)

        print(f"Training total model for year {args.year}...")
        train_ridge_model(X, y_total, "total", args.year, args.model_dir)

        print(f"Model training for year {args.year} completed successfully.")

    except Exception as e:
        print(f"Error during model training for year {args.year}: {e}")
        import traceback

        traceback.print_exc()
