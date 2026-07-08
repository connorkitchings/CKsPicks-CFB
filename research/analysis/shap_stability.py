#!/usr/bin/env python3
"""
SHAP Feature Stability Analysis

For each leave-one-season-out CV fold, trains a Ridge model and computes SHAP
values. Reports which features have stable predictive importance across folds
vs. which are noise.

Usage:
    PYTHONPATH=. uv run python scripts/analysis/shap_stability.py
    PYTHONPATH=. uv run python scripts/analysis/shap_stability.py --output artifacts/analysis/shap_stability_report.md
    PYTHONPATH=. uv run python scripts/analysis/shap_stability.py --catboost  # Use CatBoost instead of Ridge
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import shap
from sklearn.linear_model import Ridge

# Add repo root to path
REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from cks_picks_cfb.features.v2_recency import load_v2_recency_data  # noqa: E402

# ── Fold configuration (matches v2_champion_crossval.yaml) ───────────────────
FOLDS = [
    {"name": "fold_2019", "train_years": [2021, 2022, 2023], "test_year": 2019},
    {"name": "fold_2021", "train_years": [2019, 2022, 2023], "test_year": 2021},
    {"name": "fold_2022", "train_years": [2019, 2021, 2023], "test_year": 2022},
    {"name": "fold_2023", "train_years": [2019, 2021, 2022], "test_year": 2023},
]

# Features used in the matchup_v1 / champion CV experiment
FEATURES = [
    "home_adj_off_epa_pp",
    "home_adj_def_epa_pp",
    "home_adj_off_sr",
    "home_adj_def_sr",
    "away_adj_off_epa_pp",
    "away_adj_def_epa_pp",
    "away_adj_off_sr",
    "away_adj_def_sr",
    "home_adj_off_rush_ypp",
    "home_adj_def_rush_ypp",
    "home_adj_off_pass_ypp",
    "home_adj_def_pass_ypp",
    "away_adj_off_rush_ypp",
    "away_adj_def_rush_ypp",
    "away_adj_off_pass_ypp",
    "away_adj_def_pass_ypp",
]

TARGET = "spread_target"
ALPHA = 0.3  # EWMA alpha from matchup_v1 config
RIDGE_ALPHA = 1.0


def load_fold_data(fold: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load train and test DataFrames for a given fold."""
    train_dfs = []
    for year in fold["train_years"]:
        df = load_v2_recency_data(year, alpha=ALPHA)
        if df is not None:
            train_dfs.append(df)

    if not train_dfs:
        raise ValueError(f"No training data for fold {fold['name']}")

    train_df = pd.concat(train_dfs, ignore_index=True)
    test_df = load_v2_recency_data(fold["test_year"], alpha=ALPHA)

    if test_df is None:
        raise ValueError(f"No test data for year {fold['test_year']}")

    return train_df, test_df


def prepare_xy(
    df: pd.DataFrame, features: list[str]
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Extract feature matrix and target vector; returns (X, y, available_features)."""
    df_clean = df.dropna(subset=[TARGET])
    available = [f for f in features if f in df_clean.columns]
    missing = [f for f in features if f not in df_clean.columns]
    if missing:
        print(f"  Warning: {len(missing)} features missing: {missing}")

    X = df_clean[available].replace([np.inf, -np.inf], 0).fillna(0).values  # noqa: N806
    y = df_clean[TARGET].values
    return X, y, available


def run_fold(fold: dict, features: list[str], use_catboost: bool = False) -> dict:
    """Train model and compute SHAP values for one fold."""
    print(
        f"\n  Loading data for {fold['name']} (train={fold['train_years']}, test={fold['test_year']})..."
    )
    train_df, test_df = load_fold_data(fold)

    X_train, y_train, available_train = prepare_xy(train_df, features)  # noqa: N806
    X_test, _, available_test = prepare_xy(test_df, features)  # noqa: N806

    # Use intersection of available features
    feat_names = [f for f in features if f in available_train and f in available_test]
    feat_idx = [available_train.index(f) for f in feat_names]
    X_train = X_train[:, feat_idx]  # noqa: N806
    feat_idx_test = [available_test.index(f) for f in feat_names]
    X_test = X_test[:, feat_idx_test]  # noqa: N806

    print(f"  Train: {X_train.shape}, Test: {X_test.shape}")  # noqa: N806

    if use_catboost:
        from catboost import CatBoostRegressor

        model = CatBoostRegressor(
            iterations=1000,
            learning_rate=0.05,
            depth=6,
            verbose=0,
        )
        model.fit(X_train, y_train)
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X_test)
    else:
        # Ridge regression with LinearExplainer (exact SHAP)
        model = Ridge(alpha=RIDGE_ALPHA)
        model.fit(X_train, y_train)
        explainer = shap.LinearExplainer(
            model, X_train, feature_perturbation="correlation_dependent"
        )
        shap_values = explainer.shap_values(X_test)

    # Mean absolute SHAP per feature (feature importance)
    mean_abs_shap = np.abs(shap_values).mean(axis=0)

    # Rank features by importance (1 = most important)
    ranks = pd.Series(mean_abs_shap, index=feat_names).rank(ascending=False).astype(int)

    return {
        "fold": fold["name"],
        "test_year": fold["test_year"],
        "features": feat_names,
        "mean_abs_shap": dict(zip(feat_names, mean_abs_shap)),
        "ranks": ranks.to_dict(),
        "n_train": len(X_train),
        "n_test": len(X_test),
    }


def build_stability_report(fold_results: list[dict], use_catboost: bool) -> str:
    """Build markdown stability report from per-fold SHAP results."""
    # Aggregate: mean SHAP magnitude and rank across folds
    all_features = fold_results[0]["features"]
    n_folds = len(fold_results)

    shap_matrix = pd.DataFrame(
        {r["fold"]: pd.Series(r["mean_abs_shap"]) for r in fold_results}
    ).fillna(0)

    rank_matrix = pd.DataFrame(
        {r["fold"]: pd.Series(r["ranks"]) for r in fold_results}
    ).fillna(len(all_features) + 1)

    model_type = "CatBoost" if use_catboost else "Ridge"
    lines = [
        f"# SHAP Feature Stability Report ({model_type})",
        f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Methodology",
        f"- Model: {model_type} regression",
        "- Folds: leave-one-season-out (2019, 2021, 2022, 2023)",
        "- Stability metric: Coefficient of variation (CV) of mean-absolute SHAP across folds",
        "- Low CV = consistent importance (stable); High CV = erratic importance (noise)",
        "",
        "## Feature Stability Summary",
        "",
    ]

    # Compute stability metrics
    summary = pd.DataFrame(
        {
            "mean_shap": shap_matrix.mean(axis=1),
            "std_shap": shap_matrix.std(axis=1),
            "cv_shap": (shap_matrix.std(axis=1) / (shap_matrix.mean(axis=1) + 1e-9)),
            "mean_rank": rank_matrix.mean(axis=1),
            "std_rank": rank_matrix.std(axis=1),
        }
    ).sort_values("mean_shap", ascending=False)

    # Table header
    lines.append("| Feature | Mean SHAP | SHAP Std | SHAP CV | Mean Rank | Stability |")
    lines.append("|---------|-----------|----------|---------|-----------|-----------|")

    for feat, row in summary.iterrows():
        cv = row["cv_shap"]
        stability = (
            "✅ Stable" if cv < 0.5 else ("⚠️ Moderate" if cv < 1.0 else "❌ Unstable")
        )
        lines.append(
            f"| `{feat}` | {row['mean_shap']:.4f} | {row['std_shap']:.4f} | "
            f"{cv:.2f} | {row['mean_rank']:.1f} | {stability} |"
        )

    # Per-fold breakdown
    lines += [
        "",
        "## Per-Fold SHAP Values (Mean Absolute)",
        "",
    ]
    fold_cols = [r["fold"] for r in fold_results]
    lines.append("| Feature | " + " | ".join(fold_cols) + " |")
    lines.append("|---------|" + "|".join(["----------"] * n_folds) + "|")

    for feat in summary.index:
        vals = [
            f"{shap_matrix.loc[feat, f]:.4f}" if feat in shap_matrix.index else "N/A"
            for f in fold_cols
        ]
        lines.append(f"| `{feat}` | " + " | ".join(vals) + " |")

    # Per-fold ranks
    lines += [
        "",
        "## Per-Fold Feature Ranks (1 = most important)",
        "",
    ]
    lines.append("| Feature | " + " | ".join(fold_cols) + " | Mean Rank |")
    lines.append("|---------|" + "|".join(["----------"] * n_folds) + "|-----------|")

    for feat in summary.index:
        ranks = [
            f"{int(rank_matrix.loc[feat, f])}" if feat in rank_matrix.index else "N/A"
            for f in fold_cols
        ]
        mean_rank = summary.loc[feat, "mean_rank"]
        lines.append(f"| `{feat}` | " + " | ".join(ranks) + f" | {mean_rank:.1f} |")

    # Conclusions
    stable = summary[summary["cv_shap"] < 0.5]
    moderate = summary[(summary["cv_shap"] >= 0.5) & (summary["cv_shap"] < 1.0)]
    unstable = summary[summary["cv_shap"] >= 1.0]

    lines += [
        "",
        "## Conclusions",
        "",
        f"- **Stable features ({len(stable)}):** Consistent importance across folds — retain",
        f"- **Moderate features ({len(moderate)}):** Variable importance — investigate further",
        f"- **Unstable features ({len(unstable)}):** Noisy — candidates for removal",
        "",
        "### Stable Features",
    ]
    for feat in stable.index:
        lines.append(
            f"- `{feat}` (CV={stable.loc[feat, 'cv_shap']:.2f}, mean rank={stable.loc[feat, 'mean_rank']:.1f})"
        )

    lines += ["", "### Unstable Features (candidates for removal)"]
    for feat in unstable.index:
        lines.append(
            f"- `{feat}` (CV={unstable.loc[feat, 'cv_shap']:.2f}, mean rank={unstable.loc[feat, 'mean_rank']:.1f})"
        )

    lines += [
        "",
        "## Interpretation",
        "",
        "If **all features** have high CV (> 1.0), the current feature set lacks stable",
        "predictive signal across seasons. This confirms the hypothesis that public",
        "efficiency metrics (EPA, SR, YPP) are fully priced in by the market and that",
        "**new data sources** are needed rather than feature pruning.",
        "",
        "If **some features** are stable, a reduced model using only stable features",
        "should be retested in CV before pursuing new data sources.",
    ]

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="SHAP Feature Stability Analysis")
    parser.add_argument(
        "--output",
        type=str,
        default="artifacts/analysis/shap_stability_report.md",
        help="Output path for markdown report",
    )
    parser.add_argument(
        "--catboost",
        action="store_true",
        default=False,
        help="Use CatBoost instead of Ridge (slower but handles non-linearity)",
    )
    parser.add_argument(
        "--folds",
        nargs="+",
        type=int,
        choices=[2019, 2021, 2022, 2023],
        default=None,
        help="Run only specific folds (e.g. --folds 2022 2023)",
    )
    args = parser.parse_args()

    folds_to_run = FOLDS
    if args.folds:
        folds_to_run = [f for f in FOLDS if f["test_year"] in args.folds]

    model_type = "CatBoost" if args.catboost else "Ridge"
    print(f"\n{'=' * 60}")
    print(f"SHAP Feature Stability Analysis ({model_type})")
    print(f"{'=' * 60}")
    print(f"Folds: {[f['name'] for f in folds_to_run]}")
    print(f"Features: {len(FEATURES)}")

    fold_results = []
    for fold in folds_to_run:
        print(f"\n[{fold['name']}]")
        try:
            result = run_fold(fold, FEATURES, use_catboost=args.catboost)
            fold_results.append(result)
            print(f"  ✓ SHAP computed for {len(result['features'])} features")
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            raise

    if not fold_results:
        print("No fold results collected — exiting.")
        sys.exit(1)

    # Build report
    report = build_stability_report(fold_results, use_catboost=args.catboost)

    # Save report
    output_path = REPO_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report)

    print(f"\n{'=' * 60}")
    print(f"✓ Report saved to {output_path}")
    print(f"{'=' * 60}\n")

    # Also print summary to stdout
    print(report)


if __name__ == "__main__":
    main()
