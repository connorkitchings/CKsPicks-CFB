#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from typing import Dict

import numpy as np
import pandas as pd

from cfb_model.scripts.generate_weekly_bets_clean import (
    apply_betting_policy,
    build_feature_list,
    generate_csv_report,
    load_ensemble_models,
    load_week_dataset,
)


def _settle_spread(home_points: float, away_points: float, home_line: float, side: str) -> int:
    margin = float(home_points) - float(away_points)
    val = margin + float(home_line)
    if side == "home":
        return 1 if val > 0 else (0 if val == 0 else 0)
    if side == "away":
        return 1 if val < 0 else (0 if val == 0 else 0)
    return 0


def _settle_total(home_points: float, away_points: float, total_line: float, side: str) -> int:
    total = float(home_points) + float(away_points)
    val = total - float(total_line)
    if side == "over":
        return 1 if val > 0 else (0 if val == 0 else 0)
    if side == "under":
        return 1 if val < 0 else (0 if val == 0 else 0)
    return 0


def process_week(
    year: int,
    week: int,
    data_root: str,
    model_dir: str,
    output_dir: str,
    *,
    spread_threshold: float,
    total_threshold: float,
    spread_std: float,
    total_std: float,
) -> Dict[str, int]:
    models = load_ensemble_models(year, model_dir)
    df = load_week_dataset(year, week, data_root)

    feature_list = build_feature_list(df)
    # Align per-model features for predictions
    spread_predictions = []
    for m in models["spread"]:
        req = list(getattr(m, "feature_names_in_", [])) or feature_list
        x_m = df.reindex(columns=req, fill_value=0.0).astype("float64")
        spread_predictions.append(pd.Series(m.predict(x_m), index=df.index))
    if not spread_predictions:
        return {"spread_bets": 0, "spread_hits": 0, "total_bets": 0, "total_hits": 0}
    df["predicted_spread"] = np.mean(spread_predictions, axis=0)
    df["predicted_spread_std_dev"] = np.std(spread_predictions, axis=0)

    total_predictions = []
    for m in models["total"]:
        req = list(getattr(m, "feature_names_in_", [])) or feature_list
        x_m = df.reindex(columns=req, fill_value=0.0).astype("float64")
        total_predictions.append(pd.Series(m.predict(x_m), index=df.index))
    if not total_predictions:
        return {"spread_bets": 0, "spread_hits": 0, "total_bets": 0, "total_hits": 0}
    df["predicted_total"] = np.mean(total_predictions, axis=0)
    df["predicted_total_std_dev"] = np.std(total_predictions, axis=0)

    df = apply_betting_policy(
        df,
        spread_edge_threshold=spread_threshold,
        total_edge_threshold=total_threshold,
        spread_std_dev_threshold=spread_std,
        total_std_dev_threshold=total_std,
        min_games_played=4,
        fractional_kelly=0.25,
        kelly_cap=0.25,
        base_unit_fraction=0.02,
        single_bet_cap=0.05,
    )

    # Save weekly report
    out_path = os.path.join(output_dir, str(year), f"CFB_week{week}_bets.csv")
    generate_csv_report(df, out_path)

    # Compute weekly spread/total hits vs bets
    spread_bets = 0
    spread_hits = 0
    total_bets = 0
    total_hits = 0
    for _, row in df.iterrows():
        # Count decided bets regardless of availability of final outcomes
        if row.get("bet_spread") in ("home", "away"):
            spread_bets += 1
            # Only count hit when scores and line exist
            if (
                not pd.isna(row.get("home_points"))
                and not pd.isna(row.get("away_points"))
                and not pd.isna(row.get("home_team_spread_line"))
            ):
                spread_hits += _settle_spread(
                    row["home_points"], row["away_points"], row["home_team_spread_line"], row["bet_spread"]
                )
        if row.get("bet_total") in ("over", "under"):
            total_bets += 1
            if (
                not pd.isna(row.get("home_points"))
                and not pd.isna(row.get("away_points"))
                and not pd.isna(row.get("total_line"))
            ):
                total_hits += _settle_total(
                    row["home_points"], row["away_points"], row["total_line"], row["bet_total"]
                )

    return {"spread_bets": spread_bets, "spread_hits": spread_hits, "total_bets": total_bets, "total_hits": total_hits}


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate weekly reports and summary for 2024 with ensemble+Kelly")
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--start-week", type=int, default=2)
    ap.add_argument("--end-week", type=int, default=17)
    ap.add_argument("--data-root", type=str, default="/Volumes/CK SSD/Coding Projects/cfb_model/data")
    ap.add_argument("--model-dir", type=str, default="./models/ridge_baseline")
    ap.add_argument("--output-dir", type=str, default="./reports")
    ap.add_argument("--spread-threshold", type=float, default=6.0)
    ap.add_argument("--total-threshold", type=float, default=6.0)
    ap.add_argument("--spread-std", type=float, default=3.0)
    ap.add_argument("--total-std", type=float, default=1.5)

    args = ap.parse_args()

    os.makedirs(os.path.join(args.output_dir, str(args.year)), exist_ok=True)

    rows = []
    for w in range(args.start_week, args.end_week + 1):
        try:
            stats = process_week(
                args.year,
                w,
                args.data_root,
                args.model_dir,
                args.output_dir,
                spread_threshold=args.spread_threshold,
                total_threshold=args.total_threshold,
                spread_std=args.spread_std,
                total_std=args.total_std,
            )
            rows.append({"week": w, **stats})
        except Exception as e:
            rows.append({"week": w, "spread_bets": 0, "spread_hits": 0, "total_bets": 0, "total_hits": 0, "error": str(e)})

    summary = pd.DataFrame(rows)
    out_path = os.path.join(args.output_dir, str(args.year), f"weekly_hit_summary_{args.year}.csv")
    summary.to_csv(out_path, index=False)
    print(summary)
    print(f"Saved weekly summary to {out_path}")


if __name__ == "__main__":
    main()
