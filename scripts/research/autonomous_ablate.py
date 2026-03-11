#!/usr/bin/env python3
"""
Autonomous Ablation Runner

Inspired by karpathy/autoresearch - gives AI agents a framework to
systematically test feature additions to a baseline model.

Usage:
    PYTHONPATH=. uv run python scripts/research/autonomous_ablate.py

    # Or with custom config:
    PYTHONPATH=. uv run python scripts/research/autonomous_ablate.py \
        --config conf/research/ablation_config.yaml \
        --time-budget 10
"""

import argparse
import sys
import time
from pathlib import Path

import mlflow
import pandas as pd
import yaml

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from cks_picks_cfb.features.v2_recency import load_v2_recency_data  # noqa: E402
from cks_picks_cfb.models.v2_catboost import V2CatBoostModel  # noqa: E402


def load_config(config_path: str) -> dict:
    """Load ablation configuration."""
    with open(config_path) as f:
        return yaml.safe_load(f)


def load_baseline_features(config: dict) -> list:
    """Load baseline feature list from config."""
    baseline_name = config["ablation"]["baseline_features"]
    baseline_path = PROJECT_ROOT / "conf" / "features" / f"{baseline_name}.yaml"

    with open(baseline_path) as f:
        baseline_cfg = yaml.safe_load(f)

    return baseline_cfg.get("groups", [])


def load_data_for_ablation(
    years: list, alpha: float = 0.5, iterations: int = 2
) -> pd.DataFrame:
    """Load training data for ablation experiments."""
    dfs = []
    for year in years:
        print(f"Loading data for {year}...")
        df = load_v2_recency_data(year, alpha=alpha, iterations=iterations)
        if df is not None:
            dfs.append(df)

    if not dfs:
        raise ValueError("No training data loaded")

    return pd.concat(dfs, ignore_index=True)


def evaluate_candidate(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    features: list,
    model_params: dict,
    candidate_name: str,
    mlflow_run,
    model_type: str = "catboost",
) -> dict:
    """Train and evaluate a candidate feature set."""
    print(f"\n{'=' * 60}")
    print(f"Evaluating: {candidate_name}")
    print(f"Features: {len(features)}, Model: {model_type}")
    print(f"{'=' * 60}")

    # Train model based on type
    if model_type == "xgboost":
        from cks_picks_cfb.models.v2_xgboost import V2XGBoostModel

        model = V2XGBoostModel(features=features, **model_params)
    else:
        model = V2CatBoostModel(features=features, **model_params)

    model.fit(train_df)

    # Evaluate
    metrics = model.evaluate(test_df)

    # Log to MLflow
    mlflow.log_params(
        {
            "candidate": candidate_name,
            "num_features": len(features),
            "model_type": model_type,
        }
    )
    mlflow.log_metrics(
        {
            "roi": metrics.get("roi", -100.0),
            "hit_rate": metrics.get("hit_rate", 0.0),
            "rmse": metrics.get("rmse", 999.0),
            "mae": metrics.get("mae", 999.0),
        }
    )

    print(
        f"Results - ROI: {metrics.get('roi', -100):.2f}%, Hit Rate: {metrics.get('hit_rate', 0):.1f}%"
    )

    return {
        "candidate": candidate_name,
        "features": features,
        "roi": metrics.get("roi", -100.0),
        "hit_rate": metrics.get("hit_rate", 0.0),
        "rmse": metrics.get("rmse", 999.0),
    }


def run_ablation(config_path: str, time_budget: int | None = None):
    """Run autonomous ablation experiments."""

    # Load config
    cfg = load_config(config_path)
    ablation_cfg = cfg["ablation"]

    # Override time budget if provided
    if time_budget:
        ablation_cfg["time_budget_minutes"] = time_budget

    print("Starting Autonomous Ablation")
    print(f"Time budget: {ablation_cfg['time_budget_minutes']} minutes per experiment")
    print(
        f"Validation: train {ablation_cfg['validation']['train_years']} -> test {ablation_cfg['validation']['test_year']}"
    )

    # Setup MLflow
    mlflow.set_experiment(
        ablation_cfg.get("mlflow", {}).get("experiment_name", "autonomous_ablation")
    )

    # Load data once (baseline uses alpha=0.5, iterations=2)
    print("\nLoading training data...")
    train_years = ablation_cfg["validation"]["train_years"]
    test_year = ablation_cfg["validation"]["test_year"]

    train_df = load_data_for_ablation(train_years, alpha=0.5, iterations=2)
    print(f"Training data: {len(train_df)} games")

    print(f"\nLoading test data ({test_year})...")
    test_df = load_data_for_ablation([test_year], alpha=0.5, iterations=2)
    print(f"Test data: {len(test_df)} games")

    # Get baseline features
    baseline_features = load_baseline_features(cfg)
    print(f"\nBaseline features ({len(baseline_features)}): {baseline_features[:4]}...")

    # Get model params
    model_params = ablation_cfg.get("model", {}).get("params", {})

    # Track results
    results = []
    start_time = time.time()
    best_roi = float("-inf")
    best_candidate = None

    # Run baseline first
    with mlflow.start_run(run_name="baseline") as run:
        baseline_result = evaluate_candidate(
            train_df, test_df, baseline_features, model_params, "baseline", run
        )
        results.append(baseline_result)
        best_roi = baseline_result["roi"]
        best_candidate = "baseline"

    # Run candidates
    candidates = ablation_cfg.get("candidates", {})

    for candidate_key, candidate_cfg in candidates.items():
        # Check time budget
        elapsed = (time.time() - start_time) / 60
        remaining = ablation_cfg["time_budget_minutes"] - elapsed

        if remaining < 2:
            print(
                f"\nTime budget nearly exhausted ({elapsed:.1f} min), stopping ablation"
            )
            break

        candidate_name = candidate_cfg["name"]

        # Determine features
        # If candidate has its own features (replace), use those; otherwise add to baseline
        if "features" in candidate_cfg:
            # Check if this is a replacement set (starts with specific features, not adding)
            cand_features = candidate_cfg["features"]
            # If fewer than baseline, assume it's a replacement/simplified set
            if len(cand_features) < len(baseline_features):
                candidate_features = cand_features
            else:
                candidate_features = baseline_features + cand_features
        else:
            candidate_features = baseline_features

        # Check if we need to reload data (alpha/iteration changes)
        alpha = candidate_cfg.get("alpha", 0.5)
        iterations = candidate_cfg.get("adjustment_iterations", 2)

        # Only reload if different from baseline
        reload_data = (alpha != 0.5) or (iterations != 2)

        if reload_data:
            print(f"\nReloading data with alpha={alpha}, iterations={iterations}...")
            train_df_cand = load_data_for_ablation(
                train_years, alpha=alpha, iterations=iterations
            )
            test_df_cand = load_data_for_ablation(
                [test_year], alpha=alpha, iterations=iterations
            )
        else:
            train_df_cand = train_df
            test_df_cand = test_df

        # Determine model type and params
        model_type = candidate_cfg.get("model_type", "catboost")

        # Merge model params with overrides
        candidate_params = dict(model_params)
        if "model_override" in candidate_cfg:
            candidate_params.update(candidate_cfg["model_override"])

        with mlflow.start_run(run_name=candidate_name) as run:
            # Log candidate config
            mlflow.log_params(
                {
                    "candidate_key": candidate_key,
                    "description": candidate_cfg.get("description", ""),
                    "alpha": alpha,
                    "adjustment_iterations": iterations,
                    "model_type": model_type,
                }
            )

            result = evaluate_candidate(
                train_df_cand,
                test_df_cand,
                candidate_features,
                candidate_params,
                candidate_name,
                run,
                model_type=model_type,
            )
            results.append(result)

            # Track best
            if result["roi"] > best_roi:
                best_roi = result["roi"]
                best_candidate = candidate_name

    # Summary
    total_time = (time.time() - start_time) / 60
    print(f"\n{'=' * 60}")
    print(f"Ablation Complete in {total_time:.1f} minutes")
    print(f"{'=' * 60}")

    # Sort by ROI
    results_df = pd.DataFrame(results).sort_values("roi", ascending=False)
    print("\nResults (sorted by ROI):")
    print(results_df.to_string(index=False))

    print(f"\nBest candidate: {best_candidate} with ROI: {best_roi:.2f}%")

    # Log summary
    with mlflow.start_run(run_name="summary") as run:
        mlflow.log_param("total_experiments", len(results))
        mlflow.log_param("total_time_minutes", total_time)
        mlflow.log_param("best_candidate", best_candidate)
        mlflow.log_metric("best_roi", best_roi)

    return results


def main():
    parser = argparse.ArgumentParser(description="Autonomous ablation runner")
    parser.add_argument(
        "--config",
        type=str,
        default="conf/research/ablation_config.yaml",
        help="Path to ablation config",
    )
    parser.add_argument(
        "--time-budget",
        type=int,
        help="Override time budget (minutes)",
    )
    args = parser.parse_args()

    # Resolve config path relative to project root
    config_path = PROJECT_ROOT / args.config
    if not config_path.exists():
        config_path = Path(args.config)

    run_ablation(str(config_path), args.time_budget)


if __name__ == "__main__":
    main()
