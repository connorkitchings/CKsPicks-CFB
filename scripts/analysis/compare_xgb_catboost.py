"""
Compare XGBoost (Optimized) vs CatBoost (Baseline) using MLflow artifacts.
"""

import sys
from pathlib import Path

import mlflow
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.config import get_data_root
from src.models.features import load_point_in_time_data
from src.utils.mlflow_tracking import get_tracking_uri


def get_predictions(model_home, model_away, data_root: str):
    """Get all predictions for 2024."""
    all_preds = []

    for week in range(2, 16):
        df = load_point_in_time_data(2024, week, data_root, include_betting_lines=True)
        if df is None or df.empty:
            continue

        if hasattr(model_home, "feature_names_in_"):
            features = list(model_home.feature_names_in_)
        elif hasattr(model_home, "get_booster"):
            features = model_home.get_booster().feature_names
        else:
            from src.models.features import build_feature_list

            features = build_feature_list(df)

        features = [f for f in features if f in df.columns]
        required = features + [
            "home_points",
            "away_points",
            "spread_line",
            "total_line",
        ]
        df = df.dropna(subset=required).copy()

        if df.empty:
            continue

        x_features = df[features]
        df["pred_home"] = model_home.predict(x_features)
        df["pred_away"] = model_away.predict(x_features)
        df["pred_spread"] = df["pred_away"] - df["pred_home"]
        df["pred_total"] = df["pred_home"] + df["pred_away"]
        df["actual_spread"] = df["away_points"] - df["home_points"]
        df["actual_total"] = df["home_points"] + df["away_points"]
        df["spread_edge"] = df["pred_spread"] - df["spread_line"]
        df["total_edge"] = df["pred_total"] - df["total_line"]

        all_preds.append(df)

    return pd.concat(all_preds, ignore_index=True)


def analyze_threshold(df, market, threshold):
    """Analyze a single threshold."""
    edge_col = f"{market}_edge"
    actual_col = f"actual_{market}"
    line_col = f"{market}_line"

    bets = df[abs(df[edge_col]) >= threshold].copy()
    if len(bets) == 0:
        return None

    if market == "spread":
        bets["bet_side"] = bets[edge_col].apply(lambda x: "home" if x < 0 else "away")
        bets["win"] = bets.apply(
            lambda r: r[actual_col] < r[line_col]
            if r["bet_side"] == "home"
            else r[actual_col] > r[line_col],
            axis=1,
        )
    else:  # total
        bets["bet_side"] = bets[edge_col].apply(lambda x: "under" if x < 0 else "over")
        bets["win"] = bets.apply(
            lambda r: r[actual_col] > r[line_col]
            if r["bet_side"] == "over"
            else r[actual_col] < r[line_col],
            axis=1,
        )

    bets["push"] = bets[actual_col] == bets[line_col]

    wins = bets["win"].sum()
    pushes = bets["push"].sum()
    losses = len(bets) - wins - pushes

    if wins + losses == 0:
        return None

    hit_rate = wins / (wins + losses) * 100
    profit = (wins * 0.909) - losses
    roi = (profit / len(bets)) * 100

    return {
        "bets": len(bets),
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "hit_rate": hit_rate,
        "roi": roi,
        "profit": profit,
    }


def main():
    mlflow.set_tracking_uri(get_tracking_uri())
    data_root = get_data_root()

    # Get recent runs
    runs = mlflow.search_runs(
        experiment_names=["CFB_Model_Training"],
        order_by=["start_time DESC"],
        max_results=10,
    )

    print("Recent runs:")
    for idx, row in runs.head(5).iterrows():
        run_name = row.get("tags.mlflow.runName", "Unknown")
        start_time = row["start_time"]
        home_rmse = row.get("metrics.home_rmse", "N/A")
        print(f"  {start_time}: {run_name} - Home RMSE: {home_rmse}")

    # Find XGBoost and CatBoost runs
    print("\nLoading models from MLflow...")

    # Get the most recent XGBoost run (should be the optimized one)
    xgb_runs = runs[runs["tags.mlflow.runName"].str.contains("PointsFor", na=False)]

    if len(xgb_runs) < 2:
        print("ERROR: Need at least 2 PointsFor runs to compare")
        print("Please ensure both XGBoost and CatBoost models have been trained")
        return

    # Most recent should be CatBoost, second should be XGBoost
    catboost_run_id = xgb_runs.iloc[0]["run_id"]
    xgboost_run_id = xgb_runs.iloc[1]["run_id"]

    print(f"\nCatBoost Run ID: {catboost_run_id}")
    print(f"XGBoost Run ID: {xgboost_run_id}")

    # Load models from MLflow
    catboost_home = mlflow.sklearn.load_model(f"runs:/{catboost_run_id}/model_home")
    catboost_away = mlflow.sklearn.load_model(f"runs:/{catboost_run_id}/model_away")

    xgboost_home = mlflow.sklearn.load_model(f"runs:/{xgboost_run_id}/model_home")
    xgboost_away = mlflow.sklearn.load_model(f"runs:/{xgboost_run_id}/model_away")

    print(f"\nCatBoost Model Type: {type(catboost_home).__name__}")
    print(f"XGBoost Model Type: {type(xgboost_home).__name__}")

    # Get predictions
    print("\nGenerating predictions...")
    catboost_preds = get_predictions(catboost_home, catboost_away, data_root)
    xgboost_preds = get_predictions(xgboost_home, xgboost_away, data_root)

    print(f"Games analyzed: {len(catboost_preds)}")

    # Compare at key thresholds
    thresholds = [3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0]

    print("\n" + "=" * 100)
    print("SPREAD COMPARISON - XGBoost (Optimized) vs CatBoost (Baseline)")
    print("=" * 100)
    print(
        f"{'Threshold':<12} {'Model':<12} {'Bets':<8} {'W-L-P':<16} {'Hit Rate':<12} {'ROI':<10} {'Profit':<10}"
    )
    print("-" * 100)

    for threshold in thresholds:
        cat_result = analyze_threshold(catboost_preds, "spread", threshold)
        xgb_result = analyze_threshold(xgboost_preds, "spread", threshold)

        if cat_result:
            wlp = f"{cat_result['wins']}-{cat_result['losses']}-{cat_result['pushes']}"
            print(
                f"{threshold:<12.1f} {'CatBoost':<12} {cat_result['bets']:<8} {wlp:<16} {cat_result['hit_rate']:>6.1f}%     {cat_result['roi']:>6.1f}%    {cat_result['profit']:>6.1f}u"
            )

        if xgb_result:
            wlp = f"{xgb_result['wins']}-{xgb_result['losses']}-{xgb_result['pushes']}"
            winner = (
                "✅"
                if xgb_result["roi"] > (cat_result["roi"] if cat_result else -100)
                else ""
            )
            print(
                f"{'':12} {'XGBoost':<12} {xgb_result['bets']:<8} {wlp:<16} {xgb_result['hit_rate']:>6.1f}%     {xgb_result['roi']:>6.1f}%    {xgb_result['profit']:>6.1f}u {winner}"
            )

        print()

    print("\n" + "=" * 100)
    print("TOTAL COMPARISON - XGBoost (Optimized) vs CatBoost (Baseline)")
    print("=" * 100)
    print(
        f"{'Threshold':<12} {'Model':<12} {'Bets':<8} {'W-L-P':<16} {'Hit Rate':<12} {'ROI':<10} {'Profit':<10}"
    )
    print("-" * 100)

    for threshold in thresholds:
        cat_result = analyze_threshold(catboost_preds, "total", threshold)
        xgb_result = analyze_threshold(xgboost_preds, "total", threshold)

        if cat_result:
            wlp = f"{cat_result['wins']}-{cat_result['losses']}-{cat_result['pushes']}"
            print(
                f"{threshold:<12.1f} {'CatBoost':<12} {cat_result['bets']:<8} {wlp:<16} {cat_result['hit_rate']:>6.1f}%     {cat_result['roi']:>6.1f}%    {cat_result['profit']:>6.1f}u"
            )

        if xgb_result:
            wlp = f"{xgb_result['wins']}-{xgb_result['losses']}-{xgb_result['pushes']}"
            winner = (
                "✅"
                if xgb_result["roi"] > (cat_result["roi"] if cat_result else -100)
                else ""
            )
            print(
                f"{'':12} {'XGBoost':<12} {xgb_result['bets']:<8} {wlp:<16} {xgb_result['hit_rate']:>6.1f}%     {xgb_result['roi']:>6.1f}%    {xgb_result['profit']:>6.1f}u {winner}"
            )

        print()

    print("\n" + "=" * 100)
    print("RECOMMENDATION")
    print("=" * 100)

    # Find best threshold for each model/market
    best_xgb_spread = max(
        [
            analyze_threshold(xgboost_preds, "spread", t)
            for t in thresholds
            if analyze_threshold(xgboost_preds, "spread", t)
            and analyze_threshold(xgboost_preds, "spread", t)["bets"] >= 50
        ],
        key=lambda x: x["roi"],
        default=None,
    )
    best_cat_spread = max(
        [
            analyze_threshold(catboost_preds, "spread", t)
            for t in thresholds
            if analyze_threshold(catboost_preds, "spread", t)
            and analyze_threshold(catboost_preds, "spread", t)["bets"] >= 50
        ],
        key=lambda x: x["roi"],
        default=None,
    )

    best_xgb_total = max(
        [
            analyze_threshold(xgboost_preds, "total", t)
            for t in thresholds
            if analyze_threshold(xgboost_preds, "total", t)
            and analyze_threshold(xgboost_preds, "total", t)["bets"] >= 50
        ],
        key=lambda x: x["roi"],
        default=None,
    )
    best_cat_total = max(
        [
            analyze_threshold(catboost_preds, "total", t)
            for t in thresholds
            if analyze_threshold(catboost_preds, "total", t)
            and analyze_threshold(catboost_preds, "total", t)["bets"] >= 50
        ],
        key=lambda x: x["roi"],
        default=None,
    )

    print("\nBest Performance (minimum 50 bets):")
    print("\nSPREAD:")
    if best_cat_spread:
        print(
            f"  CatBoost: {best_cat_spread['roi']:.1f}% ROI ({best_cat_spread['bets']} bets)"
        )
    if best_xgb_spread:
        print(
            f"  XGBoost:  {best_xgb_spread['roi']:.1f}% ROI ({best_xgb_spread['bets']} bets)"
        )

    print("\nTOTAL:")
    if best_cat_total:
        print(
            f"  CatBoost: {best_cat_total['roi']:.1f}% ROI ({best_cat_total['bets']} bets)"
        )
    if best_xgb_total:
        print(
            f"  XGBoost:  {best_xgb_total['roi']:.1f}% ROI ({best_xgb_total['bets']} bets)"
        )


if __name__ == "__main__":
    main()
