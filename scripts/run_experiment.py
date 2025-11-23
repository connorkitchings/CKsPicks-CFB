import logging
import sys
import uuid
from datetime import datetime
from pathlib import Path

import hydra
import mlflow
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from omegaconf import DictConfig, OmegaConf

load_dotenv()

# Add src to path
# Add src to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from catboost import CatBoostRegressor  # noqa: E402
from sklearn.linear_model import Ridge  # noqa: E402
from sklearn.metrics import mean_absolute_error, mean_squared_error  # noqa: E402
from sklearn.isotonic import IsotonicRegression  # noqa: E402
from sklearn.ensemble import GradientBoostingRegressor  # noqa: E402

from src.features.selector import get_feature_set_id, select_features  # noqa: E402
from src.models.features import load_point_in_time_data  # noqa: E402
from src.models.train_model import _concat_years  # noqa: E402
from src.utils.local_storage import LocalStorage  # noqa: E402

log = logging.getLogger(__name__)


def compute_ats_metrics(
    test_df: pd.DataFrame,
    predictions: np.ndarray,
    actuals: np.ndarray,
    data_root: str,
    target_type: str = "spread",  # NEW: "spread" or "total"
    edge_threshold: float = 5.0,  # Updated from 3.5 based on 2024 calibration analysis
) -> dict:
    """Compute ATS-style hit rate using actual betting lines.

    Args:
        test_df: Test dataframe with game metadata (id, season, week)
        predictions: Model predictions
        actuals: Actual outcomes
        data_root: Path to data storage
        target_type: "spread" or "total" - determines betting logic
        edge_threshold: Minimum edge (in points) to place a bet

    Returns:
        Dict with hit_rate, edge_bucket_hit_rates, num_bets, etc.
    """
    storage = LocalStorage(data_root=data_root, file_format="csv", data_type="raw")

    # Load betting lines for all games in test set
    all_lines = []
    for year in test_df["season"].unique():
        for week in test_df[test_df["season"] == year]["week"].unique():
            try:
                lines_records = storage.read_index(
                    "betting_lines", {"year": int(year), "week": int(week)}
                )
                if lines_records:
                    all_lines.extend(lines_records)
            except FileNotFoundError:
                continue

    if not all_lines:
        log.warning("No betting lines found. Skipping ATS metrics.")
        return {
            "overall_hit_rate": 0.0,
            "edge_buckets": {},
            "num_bets": 0,
            "num_wins": 0,
            "num_losses": 0,
            "num_pushes": 0,
        }

    # Convert to DataFrame and get consensus line (use DraftKings preference)
    lines_df = pd.DataFrame(all_lines)
    lines_df = lines_df.sort_values(["game_id", "provider"])
    lines_df["is_draftkings"] = lines_df["provider"] == "DraftKings"
    consensus_lines = lines_df.sort_values(
        ["game_id", "is_draftkings"], ascending=[True, False]
    ).drop_duplicates(subset="game_id", keep="first")

    # Select appropriate line column based on target type
    if target_type == "spread":
        line_col = "spread"
    elif target_type == "total":
        line_col = "over_under"
    else:
        raise ValueError(f"Unknown target_type: {target_type}")

    # Merge with test data
    test_eval_df = test_df[["id", "season", "week"]].copy()
    test_eval_df["prediction"] = predictions
    test_eval_df["actual"] = actuals
    test_eval_df = test_eval_df.merge(
        consensus_lines[["game_id", line_col, "provider"]],
        left_on="id",
        right_on="game_id",
        how="left",
    )

    # Filter to games with lines
    test_eval_df = test_eval_df.dropna(subset=[line_col])
    if len(test_eval_df) == 0:
        log.warning("No games with betting lines. Skipping ATS metrics.")
        return {
            "overall_hit_rate": 0.0,
            "edge_buckets": {},
            "num_bets": 0,
            "num_wins": 0,
            "num_losses": 0,
            "num_pushes": 0,
        }

    # Calculate edge based on target type
    if target_type == "spread":
        # For spread: compare prediction to expected margin
        test_eval_df["expected"] = -test_eval_df[line_col]  # Negate spread
        test_eval_df["edge"] = test_eval_df["prediction"] - test_eval_df["expected"]
        # Bet home if edge < -threshold, away if edge > threshold
        test_eval_df["bet_home"] = test_eval_df["edge"] < -edge_threshold
        test_eval_df["bet_away"] = test_eval_df["edge"] > edge_threshold
    elif target_type == "total":
        # For total: compare prediction directly to line
        test_eval_df["edge"] = test_eval_df["prediction"] - test_eval_df[line_col]
        # Bet over if edge > threshold, under if edge < -threshold
        test_eval_df["bet_over"] = test_eval_df["edge"] > edge_threshold
        test_eval_df["bet_under"] = test_eval_df["edge"] < -edge_threshold

    test_eval_df["bet_made"] = (
        test_eval_df["bet_home"] | test_eval_df["bet_away"]
        if target_type == "spread"
        else test_eval_df["bet_over"] | test_eval_df["bet_under"]
    )

    # Settle bets based on target type
    def settle_bet(row):
        """Settle a bet. Returns 'win', 'loss', 'push', or None."""
        if not row["bet_made"]:
            return None

        if target_type == "spread":
            # Spread betting logic
            actual_margin = row["actual"]
            expected_margin = row["expected"]

            if row["bet_home"]:
                if actual_margin > expected_margin:
                    return "win"
                elif actual_margin < expected_margin:
                    return "loss"
                else:
                    return "push"
            elif row["bet_away"]:
                if actual_margin < expected_margin:
                    return "win"
                elif actual_margin > expected_margin:
                    return "loss"
                else:
                    return "push"
        elif target_type == "total":
            # Total betting logic
            actual_total = row["actual"]
            line_total = row[line_col]

            if row["bet_over"]:
                if actual_total > line_total:
                    return "win"
                elif actual_total < line_total:
                    return "loss"
                else:
                    return "push"
            elif row["bet_under"]:
                if actual_total < line_total:
                    return "win"
                elif actual_total > line_total:
                    return "loss"
                else:
                    return "push"
        return None

    test_eval_df["bet_result"] = test_eval_df.apply(settle_bet, axis=1)

    # Calculate hit rate (only for games where we bet, excluding pushes)
    bet_games = test_eval_df[test_eval_df["bet_made"]]
    if len(bet_games) == 0:
        log.warning("No bets met edge threshold. Skipping ATS metrics.")
        return {
            "overall_hit_rate": 0.0,
            "edge_buckets": {},
            "num_bets": 0,
            "num_wins": 0,
            "num_losses": 0,
            "num_pushes": 0,
        }

    # Count wins, losses, pushes
    num_wins = (bet_games["bet_result"] == "win").sum()
    num_losses = (bet_games["bet_result"] == "loss").sum()
    num_pushes = (bet_games["bet_result"] == "push").sum()

    # Win rate = wins / (wins + losses), excluding pushes
    hit_rate = (
        num_wins / (num_wins + num_losses) if (num_wins + num_losses) > 0 else 0.0
    )

    # Edge bucket analysis (also excluding pushes from win rate)
    edge_buckets = [(3.5, 5.0), (5.0, 7.0), (7.0, 10.0), (10.0, 100.0)]
    bucket_stats = {}
    test_eval_df["abs_edge"] = test_eval_df["edge"].abs()

    for low, high in edge_buckets:
        bucket_bets = test_eval_df[
            (test_eval_df["abs_edge"] >= low)
            & (test_eval_df["abs_edge"] < high)
            & test_eval_df["bet_made"]
        ]
        if len(bucket_bets) > 0:
            bucket_wins = (bucket_bets["bet_result"] == "win").sum()
            bucket_losses = (bucket_bets["bet_result"] == "loss").sum()
            bucket_pushes = (bucket_bets["bet_result"] == "push").sum()

            # Win rate excluding pushes
            bucket_hit_rate = (
                bucket_wins / (bucket_wins + bucket_losses)
                if (bucket_wins + bucket_losses) > 0
                else 0.0
            )

            bucket_stats[f"edge_{low}_{high}"] = {
                "hit_rate": float(bucket_hit_rate),
                "count": int(len(bucket_bets)),
                "wins": int(bucket_wins),
                "losses": int(bucket_losses),
                "pushes": int(bucket_pushes),
            }

    return {
        "overall_hit_rate": float(hit_rate),
        "edge_buckets": bucket_stats,
        "num_bets": int(len(bet_games)),
        "num_wins": int(num_wins),
        "num_losses": int(num_losses),
        "num_pushes": int(num_pushes),
        "total_games": int(len(test_eval_df)),
    }


@hydra.main(config_path="../conf", config_name="config", version_base="1.2")
def main(cfg: DictConfig):
    run_id = str(uuid.uuid4())
    log.info(f"Starting experiment run: {run_id}")
    log.info(f"Config:\n{OmegaConf.to_yaml(cfg)}")

    # Setup MLflow
    mlflow_tracking_uri = f"file://{cfg.paths.artifacts_dir}/mlruns"
    mlflow.set_tracking_uri(mlflow_tracking_uri)
    experiment_name = (
        cfg.experiment.name if "experiment" in cfg and cfg.experiment else "default"
    )
    mlflow.set_experiment(experiment_name)

    # Define WFV years
    # Default to 2023, 2024 if not specified
    test_years = cfg.get("test_years", [2023, 2024])
    start_train_year = cfg.get("start_train_year", 2019)

    start_train_year = cfg.get("start_train_year", 2019)

    # Determine adjustment iteration: prefer model config, fallback to data config
    adjustment_iteration = cfg.model.get(
        "adjustment_iteration", cfg.data.adjustment_iteration
    )
    log.info(f"Using adjustment_iteration: {adjustment_iteration}")

    metrics = []

    with mlflow.start_run(run_name=run_id):
        # Log params
        mlflow.log_params(OmegaConf.to_container(cfg.model.params, resolve=True))
        mlflow.log_param("features", cfg.features.name)
        mlflow.log_param("target", cfg.target)
        mlflow.log_param("feature_set_id", get_feature_set_id(cfg))
        mlflow.log_param("calibration_type", cfg.model.get("calibration_type", None))

        for year in test_years:
            log.info(f"--- Processing Test Year: {year} ---")

            # Load Training Data
            train_years = list(range(start_train_year, year))
            log.info(f"Loading training data for years: {train_years}")

            all_train_data = []
            # We load week-by-week to ensure point-in-time correctness if needed,
            # but for training set (past years), we can load all weeks.
            # However, load_point_in_time_data is designed for specific weeks.
            # To be safe and consistent with WFV script, we iterate.

            # Optimization: For past years, we can load the full season if available,
            # but load_point_in_time_data might be safer.
            # Let's stick to the pattern in walk_forward_validation.py for now.

            for t_year in train_years:
                if t_year == 2020:
                    continue
                # Load all weeks for training year
                # Assuming 15 weeks max
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
                log.warning(f"No training data found for year {year}. Skipping.")
                continue

            train_df = _concat_years(all_train_data)

            # Load Test Data
            # For test year, we validate week by week?
            # Or just train once on T-1 and predict T?
            # The plan says "Train on seasons [Start, T-1], Validate on Season T".
            # Usually this implies retraining every week (expanding window) OR training once per season.
            # For simplicity and speed in this refactor, let's do ONCE per season first (Train on <T, Test on T).
            # But strictly speaking, for betting, we retrain every week.
            # Let's do week-by-week evaluation to be accurate.

            # We need to retrain every week to be truly point-in-time correct?
            # Actually, if we train on [2019-2022], we can predict ALL of 2023 without leakage
            # IF we don't use 2023 data in training.
            # So we can train ONCE on [2019-2022] and predict 2023.
            # This is the "Season-Holdout" approach.
            # The "Walk-Forward" approach usually adds Week 1 of 2023 to train Week 2.
            # Let's stick to Season-Holdout for this baseline to match "Train on seasons [Start, T-1]".

            log.info(f"Training model on {len(train_df)} records...")
            train_df = train_df.dropna(subset=[cfg.target])
            X_train_full = select_features(train_df, cfg)  # noqa: N806

            # Collect features from all test years to ensure consistency
            # (Some features may not exist in all years due to data availability)
            log.info("Checking feature consistency across test years...")
            test_feature_sets = []
            for test_year in test_years:
                test_sample = load_point_in_time_data(
                    test_year,
                    2,
                    cfg.paths.data_dir,
                    adjustment_iteration=cfg.data.adjustment_iteration,
                )
                if test_sample is not None:
                    test_sample = test_sample.dropna(subset=[cfg.target])
                    x_test_sample = select_features(test_sample, cfg)
                    test_feature_sets.append(set(x_test_sample.columns))

            # Find common features across train and all test years
            common_features = set(X_train_full.columns)
            for test_feats in test_feature_sets:
                common_features = common_features.intersection(test_feats)

            common_features = sorted(list(common_features))
            log.info(
                f"Using {len(common_features)} common features "
                f"(reduced from {len(X_train_full.columns)})"
            )

            X_train = X_train_full[common_features]  # noqa: N806
            y_train = train_df[cfg.target]

            # Split out a calibration slice if requested
            calibration_model = None
            residual_model = None
            calibration_type = cfg.model.get("calibration_type")
            calibrate_on_year = cfg.model.get(
                "calibration_year", max(train_df["season"].unique())
            )
            if calibration_type == "residual_tree":
                calibration_mask = train_df["season"] == calibrate_on_year
                base_train_mask = train_df["season"] < calibrate_on_year
                if base_train_mask.sum() == 0 or calibration_mask.sum() == 0:
                    log.warning(
                        "Calibration split failed (insufficient data); "
                        "falling back to full training without residual calibration."
                    )
                else:
                    X_calib = X_train[calibration_mask]
                    y_calib = y_train[calibration_mask]
                    X_train = X_train[base_train_mask]
                    y_train = y_train[base_train_mask]

            # Initialize Model
            if cfg.model.type == "catboost":
                model = CatBoostRegressor(**cfg.model.params)
            elif cfg.model.type == "ridge":
                model = Ridge(**cfg.model.params)
            else:
                raise ValueError(f"Unknown model type: {cfg.model.type}")

            model.fit(X_train, y_train)

            # Optional isotonic calibration on training predictions (prototype)
            calibration_model = None
            if cfg.model.get("calibration_type") == "isotonic":
                train_preds_for_cal = model.predict(X_train)
                calibration_model = IsotonicRegression(out_of_bounds="clip")
                calibration_model.fit(train_preds_for_cal, y_train)
                log.info("Fitted isotonic calibration model on training predictions")
            elif calibration_type == "residual_tree" and calibration_mask.sum() > 0:
                base_preds_for_cal = model.predict(X_calib)
                calibration_bias = cfg.model.get("calibration_bias", 0.0)
                if calibration_bias != 0.0:
                    base_preds_for_cal = base_preds_for_cal - calibration_bias
                residuals = y_calib.values - base_preds_for_cal
                residual_model = GradientBoostingRegressor(
                    n_estimators=200,
                    learning_rate=0.05,
                    max_depth=3,
                    random_state=cfg.random_seed,
                )
                residual_model.fit(base_preds_for_cal.reshape(-1, 1), residuals)
                log.info(
                    "Fitted residual tree calibration on year %s (%d rows)",
                    calibrate_on_year,
                    len(residuals),
                )

            # Evaluate on Test Year
            log.info(f"Evaluating on {year}...")
            all_test_data = []
            for week in range(1, 16):
                df = load_point_in_time_data(
                    year,
                    week,
                    cfg.paths.data_dir,
                    adjustment_iteration=cfg.data.adjustment_iteration,
                )
                if df is not None:
                    all_test_data.append(df)

            if not all_test_data:
                log.warning(f"No test data found for year {year}.")
                continue

            test_df = _concat_years(all_test_data)
            test_df = test_df.dropna(subset=[cfg.target])
            X_test_full = select_features(test_df, cfg)  # noqa: N806
            x_test = X_test_full[common_features]  # Use only common features
            y_test = test_df[cfg.target]

            preds = model.predict(x_test)

            # Apply calibration correction if configured
            preds_raw = preds.copy()  # Save raw predictions
            calibration_bias = cfg.model.get("calibration_bias", 0.0)
            if calibration_bias != 0.0:
                log.info(f"Applying calibration bias correction: {calibration_bias}")
                preds = preds - calibration_bias
            if calibration_model is not None:
                preds = calibration_model.predict(preds)
                log.info("Applied isotonic calibration to predictions")
            if residual_model is not None:
                preds = preds + residual_model.predict(preds.reshape(-1, 1))
                log.info("Applied residual-tree calibration to predictions")

            # TODO: Compute prediction intervals (std dev) for uncertainty quantification
            # For CatBoost, could use ensemble variance or bootstrap methods

            rmse = np.sqrt(mean_squared_error(y_test, preds))
            mae = mean_absolute_error(y_test, preds)

            # Compute ATS metrics with actual betting lines
            target_type = "spread" if "spread" in cfg.target else "total"
            ats_metrics = compute_ats_metrics(
                test_df,
                preds,
                y_test.values,
                cfg.paths.data_dir,
                target_type=target_type,
            )

            log.info(
                f"Year {year} RMSE: {rmse:.4f}, MAE: {mae:.4f}, "
                f"Hit Rate: {ats_metrics['overall_hit_rate']:.1%} "
                f"({ats_metrics['num_wins']}-{ats_metrics['num_losses']}-{ats_metrics['num_pushes']} "
                f"W-L-P, {ats_metrics['num_bets']}/{ats_metrics['total_games']} bet)"
            )
            metrics.append(
                {
                    "year": year,
                    "rmse": rmse,
                    "mae": mae,
                    "hit_rate": ats_metrics["overall_hit_rate"],
                    "num_bets": ats_metrics["num_bets"],
                }
            )

            # Save predictions
            pred_df = test_df[["id", "season", "week", "home_team", "away_team"]].copy()
            pred_df["prediction"] = preds
            pred_df["prediction_raw"] = preds_raw  # Save uncalibrated predictions
            pred_df["actual"] = y_test
            pred_df["residual"] = y_test.values - preds
            if calibration_bias != 0.0:
                pred_df["calibration_bias"] = calibration_bias

            out_path = (
                Path(cfg.paths.artifacts_dir)
                / "predictions"
                / experiment_name
                / run_id
                / f"{year}_predictions.csv"
            )
            out_path.parent.mkdir(parents=True, exist_ok=True)
            pred_df.to_csv(out_path, index=False)

        # Aggregate Metrics
        if metrics:
            avg_rmse = np.mean([m["rmse"] for m in metrics])
            avg_mae = np.mean([m["mae"] for m in metrics])
            avg_hit_rate = np.mean(
                [m.get("hit_rate", 0) for m in metrics if "hit_rate" in m]
            )

            mlflow.log_metric("rmse_test", avg_rmse)
            mlflow.log_metric("mae_test", avg_mae)
            mlflow.log_metric("hit_rate_test", avg_hit_rate)
            log.info(
                f"Run complete. Avg RMSE: {avg_rmse:.4f}, Avg MAE: {avg_mae:.4f}, "
                f"Avg Hit Rate: {avg_hit_rate:.1%}"
            )

            # Log to experiment_log.csv
            log_entry = {
                "run_id": run_id,
                "timestamp": datetime.utcnow().isoformat(),
                "experiment_name": experiment_name,
                "model_type": cfg.model.type,
                "target": cfg.target,
                "rmse_test": avg_rmse,
                "mae_test": avg_mae,
                "hit_rate_test": avg_hit_rate,
                "config_path": "conf/config.yaml",
            }
            log_path = Path(cfg.paths.artifacts_dir) / "experiment_log.csv"
            pd.DataFrame([log_entry]).to_csv(
                log_path, mode="a", header=not log_path.exists(), index=False
            )
        else:
            log.warning("No metrics computed.")


if __name__ == "__main__":
    main()
