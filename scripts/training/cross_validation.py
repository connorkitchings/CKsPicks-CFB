#!/usr/bin/env python3
"""
Cross-validation runner for V2 champion model.
Implements leave-one-season-out cross-validation with parallel execution.
"""

import argparse
import json
import multiprocessing as mp
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import mlflow
import pandas as pd
from omegaconf import OmegaConf


def run_single_fold(fold_config, base_config_path, fold_index, experiment_name):
    """
    Train a single fold of cross-validation.

    Args:
        fold_config: Dictionary with train_years and test_year
        base_config_path: Path to base experiment config
        fold_index: Index of this fold (for logging)
        experiment_name: Hydra experiment name to use for training

    Returns:
        Dictionary with fold results
    """
    fold_name = fold_config["name"]
    train_years = fold_config["train_years"]
    test_year = fold_config["test_year"]

    print(f"\n{'=' * 60}")
    print(f"Starting Fold {fold_index + 1}/4: {fold_name}")
    print(f"Train: {train_years} → Test: {test_year}")
    print(f"{'=' * 60}\n")

    # Run training using Hydra overrides
    # Format: training.train_years=[2019,2021,2022] training.test_year=2023
    train_years_str = ",".join(map(str, train_years))

    cmd = [
        sys.executable,
        "src/cks_picks_cfb/train.py",
        f"experiment={experiment_name}",
        f"training.train_years=[{train_years_str}]",
        f"training.test_year={test_year}",
        f"experiment.name=crossval_{fold_name}",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600,  # 1 hour timeout
            cwd=os.getcwd(),
        )

        if result.returncode != 0:
            print(f"ERROR in {fold_name}: {result.stderr}")
            return {
                "fold": fold_name,
                "status": "failed",
                "error": result.stderr,
                "train_years": train_years,
                "test_year": test_year,
            }

        print(f"✓ Fold {fold_name} completed successfully")

        return {
            "fold": fold_name,
            "status": "success",
            "train_years": train_years,
            "test_year": test_year,
            "output": result.stdout,
        }

    except subprocess.TimeoutExpired:
        print(f"TIMEOUT in {fold_name}: Exceeded 1 hour")
        return {
            "fold": fold_name,
            "status": "timeout",
            "train_years": train_years,
            "test_year": test_year,
        }
    except Exception as e:
        print(f"EXCEPTION in {fold_name}: {e}")
        return {
            "fold": fold_name,
            "status": "error",
            "error": str(e),
            "train_years": train_years,
            "test_year": test_year,
        }


def collect_mlflow_metrics(experiment_name, fold_name):
    """
    Collect metrics from MLflow for a specific fold.

    Returns:
        Dictionary with metrics or None if not found
    """
    mlflow.set_tracking_uri(
        "file:///Users/connorkitchings/Desktop/Repositories/ckspicks-cfb/artifacts/mlruns"
    )

    try:
        # Each fold creates its own experiment
        fold_experiment_name = f"crossval_{fold_name}"
        experiment = mlflow.get_experiment_by_name(fold_experiment_name)
        if not experiment:
            return None

        # Get latest run for this fold
        runs = mlflow.search_runs(
            experiment_ids=[experiment.experiment_id],
            order_by=["start_time DESC"],
            max_results=1,
        )

        if runs.empty:
            return None

        run = runs.iloc[0]
        return {
            "rmse": run.get("metrics.rmse"),
            "mae": run.get("metrics.mae"),
            "hit_rate": run.get("metrics.hit_rate"),
            "roi": run.get("metrics.roi"),
            "n_bets": run.get("metrics.n_bets"),
            "run_id": run["run_id"],
        }
    except Exception as e:
        print(f"Error collecting metrics for {fold_name}: {e}")
        return None


def train_final_model(all_years, deploy_year, experiment_name, final_model_name):
    """
    Train final model on all training years.

    Args:
        all_years: List of years to train on
        deploy_year: Year to deploy/predict on
        experiment_name: Hydra experiment name to use
        final_model_name: Name to give the final model experiment

    Returns:
        Result from training
    """
    print(f"\n{'=' * 60}")
    print("Training Final Model")
    print(f"Train: {all_years} → Deploy: {deploy_year}")
    print(f"{'=' * 60}\n")

    train_years_str = ",".join(map(str, all_years))

    cmd = [
        sys.executable,
        "src/cks_picks_cfb/train.py",
        f"experiment={experiment_name}",
        f"training.train_years=[{train_years_str}]",
        f"training.test_year={deploy_year}",
        f"experiment.name={final_model_name}",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd())

    if result.returncode != 0:
        print(f"ERROR training final model: {result.stderr}")
        return None

    print("✓ Final model trained successfully")
    return result


def aggregate_results(fold_results, output_dir):
    """
    Aggregate cross-validation results and generate report.

    Args:
        fold_results: List of fold result dictionaries
        output_dir: Directory to save reports

    Returns:
        DataFrame with aggregated metrics
    """
    print(f"\n{'=' * 60}")
    print("Aggregating Cross-Validation Results")
    print(f"{'=' * 60}\n")

    # Create DataFrame from results
    df = pd.DataFrame(fold_results)

    # Calculate statistics
    numeric_cols = ["rmse", "mae", "hit_rate", "roi", "n_bets"]
    agg_metrics = {}

    for col in numeric_cols:
        if col in df.columns and df[col].notna().any():
            values = df[col].dropna()
            agg_metrics[f"{col}_mean"] = values.mean()
            agg_metrics[f"{col}_std"] = values.std()
            agg_metrics[f"{col}_min"] = values.min()
            agg_metrics[f"{col}_max"] = values.max()

    # Print summary
    print("Cross-Validation Summary (4 folds)")
    print("=" * 60)
    print(
        f"ROI: {agg_metrics.get('roi_mean', 0):.2%} ± {agg_metrics.get('roi_std', 0):.2%}"
    )
    print(
        f"     [Range: {agg_metrics.get('roi_min', 0):.2%} to {agg_metrics.get('roi_max', 0):.2%}]"
    )
    print()
    print(
        f"Hit Rate: {agg_metrics.get('hit_rate_mean', 0):.1%} ± {agg_metrics.get('hit_rate_std', 0):.1%}"
    )
    print(
        f"          [Range: {agg_metrics.get('hit_rate_min', 0):.1%} to {agg_metrics.get('hit_rate_max', 0):.1%}]"
    )
    print()
    print(
        f"RMSE: {agg_metrics.get('rmse_mean', 0):.2f} ± {agg_metrics.get('rmse_std', 0):.2f}"
    )
    print(
        f"MAE: {agg_metrics.get('mae_mean', 0):.2f} ± {agg_metrics.get('mae_std', 0):.2f}"
    )
    print()
    print(
        f"N Bets (avg): {agg_metrics.get('n_bets_mean', 0):.0f} ± {agg_metrics.get('n_bets_std', 0):.0f}"
    )
    print()
    print("=" * 60)

    # Per-fold breakdown
    print("\nPer-Fold Results:")
    print("-" * 60)
    for _, row in df.iterrows():
        print(
            f"{row['fold']}: "
            f"ROI={row.get('roi', 0):.2%}, "
            f"Hit={row.get('hit_rate', 0):.1%}, "
            f"RMSE={row.get('rmse', 0):.2f}, "
            f"N={row.get('n_bets', 0):.0f}"
        )
    print()

    # Save results
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save fold details
    df.to_csv(output_dir / "crossval_fold_results.csv", index=False)

    # Save aggregated metrics
    with open(output_dir / "crossval_aggregated.json", "w") as f:
        json.dump(agg_metrics, f, indent=2, default=float)

    # Save report
    report_path = output_dir / "crossval_report.txt"
    with open(report_path, "w") as f:
        f.write("V2 Champion Cross-Validation Report\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Generated: {datetime.now()}\n\n")
        f.write("Summary Statistics:\n")
        f.write(
            f"ROI: {agg_metrics.get('roi_mean', 0):.2%} ± {agg_metrics.get('roi_std', 0):.2%}\n"
        )
        f.write(
            f"Hit Rate: {agg_metrics.get('hit_rate_mean', 0):.1%} ± {agg_metrics.get('hit_rate_std', 0):.1%}\n"
        )
        f.write(
            f"RMSE: {agg_metrics.get('rmse_mean', 0):.2f} ± {agg_metrics.get('rmse_std', 0):.2f}\n"
        )
        f.write(
            f"MAE: {agg_metrics.get('mae_mean', 0):.2f} ± {agg_metrics.get('mae_std', 0):.2f}\n\n"
        )
        f.write("Per-Fold Details:\n")
        f.write(df.to_string())

    print(f"\n✓ Results saved to {output_dir}")
    print("  - crossval_fold_results.csv")
    print("  - crossval_aggregated.json")
    print("  - crossval_report.txt")

    return df, agg_metrics


def main():
    parser = argparse.ArgumentParser(
        description="Cross-validation for CFB model (supports any experiment config)"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="conf/experiment/v2_champion_crossval.yaml",
        help="Path to cross-validation config",
    )
    parser.add_argument(
        "--experiment",
        type=str,
        default=None,
        help="Hydra experiment name to use for training (defaults to config filename stem)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="artifacts/cross_validation",
        help="Output directory for results",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        default=True,
        help="Run folds in parallel",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel workers",
    )
    args = parser.parse_args()

    # Load config
    print(f"Loading config from {args.config}")
    cfg = OmegaConf.load(args.config)

    # Determine experiment name: CLI arg > config name > config filename stem
    if args.experiment:
        experiment_name = args.experiment
    else:
        experiment_name = cfg.get("experiment", {}).get("name", Path(args.config).stem)
    print(f"Using experiment: {experiment_name}")

    # Extract fold configurations
    folds = []
    for fold_name, fold_cfg in cfg.folds.items():
        folds.append(
            {
                "name": fold_cfg["name"],
                "train_years": fold_cfg["train_years"],
                "test_year": fold_cfg["test_year"],
            }
        )

    print(f"\nStarting {len(folds)}-fold cross-validation")
    print(f"Parallel execution: {args.parallel} ({args.workers} workers)")
    print(f"Output directory: {args.output_dir}\n")

    start_time = datetime.now()

    # Run folds
    if args.parallel:
        # Parallel execution
        with mp.Pool(processes=args.workers) as pool:
            fold_results = pool.starmap(
                run_single_fold,
                [
                    (fold, args.config, i, experiment_name)
                    for i, fold in enumerate(folds)
                ],
            )
    else:
        # Sequential execution
        fold_results = [
            run_single_fold(fold, args.config, i, experiment_name)
            for i, fold in enumerate(folds)
        ]

    # Collect metrics from MLflow
    print("\nCollecting metrics from MLflow...")
    for result in fold_results:
        if result["status"] == "success":
            metrics = collect_mlflow_metrics(cfg.experiment.name, result["fold"])
            if metrics:
                result.update(metrics)

    # Aggregate results
    results_df, agg_metrics = aggregate_results(fold_results, args.output_dir)

    # Train final model on all years
    final_model_name = f"{experiment_name}_final"
    train_final_model(
        cfg.final_model.train_years,
        cfg.final_model.deploy_year,
        experiment_name,
        final_model_name,
    )

    end_time = datetime.now()
    duration = end_time - start_time

    print(f"\n{'=' * 60}")
    print("Cross-Validation Complete")
    print(f"{'=' * 60}")
    print(f"Duration: {duration}")
    print(f"Results: {args.output_dir}")
    print()

    # Recommend deployment
    roi_mean = agg_metrics.get("roi_mean", 0)
    hit_rate_mean = agg_metrics.get("hit_rate_mean", 0)

    print("Deployment Recommendation:")
    print("-" * 60)
    if roi_mean > 0.005 and hit_rate_mean > 0.51:
        print("✅ SAFE TO DEPLOY")
        print(f"   ROI: {roi_mean:.2%} (positive)")
        print(f"   Hit Rate: {hit_rate_mean:.1%} (above 51%)")
    elif roi_mean > 0 and hit_rate_mean > 0.50:
        print("⚠️  DEPLOY WITH CAUTION")
        print(f"   ROI: {roi_mean:.2%} (marginal)")
        print(f"   Hit Rate: {hit_rate_mean:.1%} (at threshold)")
        print("   Recommend close monitoring")
    else:
        print("❌ DO NOT DEPLOY")
        print(f"   ROI: {roi_mean:.2%} (below target)")
        print(f"   Hit Rate: {hit_rate_mean:.1%} (below target)")
        print("   Model needs improvement")

    print()


if __name__ == "__main__":
    main()
