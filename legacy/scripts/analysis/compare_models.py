"""
Compare XGBoost vs CatBoost Champion Models - Side by Side Analysis
"""

import sys
from pathlib import Path

import joblib
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.config import get_data_root
from src.models.features import load_point_in_time_data


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
    data_root = get_data_root()

    # Load models
    print("Loading models...")

    # Find the two most recent model sets
    model_dir = Path("artifacts/models/2024")

    # Get modification times of home models
    home_files = sorted(
        model_dir.glob("home_*.joblib"), key=lambda p: p.stat().st_mtime, reverse=True
    )

    if len(home_files) < 2:
        print("ERROR: Need at least 2 model runs to compare")
        return

    # Most recent should be CatBoost, second most recent should be XGBoost
    catboost_home = joblib.load(home_files[0])
    catboost_away = joblib.load(
        model_dir / home_files[0].name.replace("home_", "away_")
    )

    xgboost_home = joblib.load(home_files[1])
    xgboost_away = joblib.load(model_dir / home_files[1].name.replace("home_", "away_"))

    print(f"CatBoost: {type(catboost_home).__name__}")
    print(f"XGBoost: {type(xgboost_home).__name__}")

    # Get predictions
    print("\nGenerating predictions...")
    catboost_preds = get_predictions(catboost_home, catboost_away, data_root)
    xgboost_preds = get_predictions(xgboost_home, xgboost_away, data_root)

    print(f"\nGames analyzed: {len(catboost_preds)}")

    # Compare at key thresholds
    thresholds = [3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0]

    print("\n" + "=" * 100)
    print("SPREAD COMPARISON")
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
            print(
                f"{'':12} {'XGBoost':<12} {xgb_result['bets']:<8} {wlp:<16} {xgb_result['hit_rate']:>6.1f}%     {xgb_result['roi']:>6.1f}%    {xgb_result['profit']:>6.1f}u"
            )

        print()

    print("\n" + "=" * 100)
    print("TOTAL COMPARISON")
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
            print(
                f"{'':12} {'XGBoost':<12} {xgb_result['bets']:<8} {wlp:<16} {xgb_result['hit_rate']:>6.1f}%     {xgb_result['roi']:>6.1f}%    {xgb_result['profit']:>6.1f}u"
            )

        print()


if __name__ == "__main__":
    main()
