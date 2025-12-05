#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from typing import Tuple

import numpy as np
import pandas as pd

from src.config import METRICS_SUBDIR, MODELS_DIR, REPORTS_DIR
from src.scripts.generate_weekly_bets_clean import (
    apply_betting_policy,
    build_feature_list,
    load_ensemble_models,
    load_week_dataset,
)


def _american_to_b(odds: float | int) -> float:
    odds = float(odds)
    if odds > 0:
        return odds / 100.0
    if odds < 0:
        return 100.0 / abs(odds)
    return 0.0


def _settle_spread(
    home_points: float, away_points: float, home_line: float, side: str
) -> float:
    # Returns +1 for win, 0 for push, -1 for loss (unit outcome)
    margin = float(home_points) - float(away_points)
    val = margin + float(home_line)
    if side == "home":
        return 1.0 if val > 0 else (0.0 if val == 0 else -1.0)
    elif side == "away":
        return 1.0 if val < 0 else (0.0 if val == 0 else -1.0)
    return 0.0


def _settle_total(
    home_points: float, away_points: float, total_line: float, side: str
) -> float:
    # Returns +1 for win, 0 for push, -1 for loss (unit outcome)
    total_points = float(home_points) + float(away_points)
    val = total_points - float(total_line)
    if side == "over":
        return 1.0 if val > 0 else (0.0 if val == 0 else -1.0)
    elif side == "under":
        return 1.0 if val < 0 else (0.0 if val == 0 else -1.0)
    return 0.0


def simulate_week(
    year: int,
    week: int,
    data_root: str,
    model_dir: str,
    bankroll: float,
    *,
    spread_threshold: float = 6.0,
    total_threshold: float = 6.0,
    spread_std: float = 3.0,
    total_std: float = 1.5,
    fractional_kelly: float = 0.25,
    kelly_cap: float = 0.25,
    base_unit_fraction: float = 0.02,
    default_price: int = -110,
    single_bet_cap: float = 0.05,
    weekly_exposure_cap: float = 0.15,
    max_weekly_bets: int = 12,
) -> Tuple[pd.DataFrame, float, dict]:
    models = load_ensemble_models(year, model_dir)
    df = load_week_dataset(year, week, data_root)

    features = build_feature_list(df)
    if not features:
        return df.assign(pnl=0.0), bankroll, {"bets": 0, "stake": 0.0, "pnl": 0.0}

    # Predictions (align features to each model's training features when available)
    spread_preds = []
    for m in models["spread"]:
        req = list(getattr(m, "feature_names_in_", [])) or features
        x_m = df.reindex(columns=req, fill_value=0.0).astype("float64")
        spread_preds.append(pd.Series(m.predict(x_m), index=df.index))
    if not spread_preds:
        raise ValueError("No valid spread predictions (feature mismatch)")
    df["predicted_spread"] = np.mean(spread_preds, axis=0)
    df["predicted_spread_std_dev"] = np.std(spread_preds, axis=0)

    total_preds = []
    for m in models["total"]:
        req = list(getattr(m, "feature_names_in_", [])) or features
        x_m = df.reindex(columns=req, fill_value=0.0).astype("float64")
        total_preds.append(pd.Series(m.predict(x_m), index=df.index))
    if not total_preds:
        raise ValueError("No valid total predictions (feature mismatch)")
    df["predicted_total"] = np.mean(total_preds, axis=0)
    df["predicted_total_std_dev"] = np.std(total_preds, axis=0)

    # Policy & sizing
    df = apply_betting_policy(
        df,
        spread_edge_threshold=spread_threshold,
        total_edge_threshold=total_threshold,
        spread_std_dev_threshold=spread_std,
        total_std_dev_threshold=total_std,
        min_games_played=4,
        fractional_kelly=fractional_kelly,
        kelly_cap=kelly_cap,
        base_unit_fraction=base_unit_fraction,
        default_american_price=default_price,
        single_bet_cap=single_bet_cap,
        bankroll=bankroll,
        max_weekly_exposure_fraction=weekly_exposure_cap,
        max_weekly_bets=max_weekly_bets,
    )

    # Settle using raw outcomes present in the dataset
    n_bets = 0
    total_stake = 0.0
    pnl = 0.0
    for _, row in df.iterrows():
        # Spread
        if (
            row.get("bet_spread") in ("home", "away")
            and not pd.isna(row.get("home_points"))
            and not pd.isna(row.get("away_points"))
            and not pd.isna(row.get("home_team_spread_line"))
        ):
            f = float(row.get("kelly_fraction_spread", 0.0))
            stake = min(bankroll * f, bankroll * single_bet_cap)
            b = _american_to_b(default_price)
            outcome = _settle_spread(
                row["home_points"],
                row["away_points"],
                row["home_team_spread_line"],
                row["bet_spread"],
            )
            if outcome > 0:
                pnl += stake * b
            elif outcome < 0:
                pnl -= stake
            total_stake += stake
            n_bets += 1
        # Total
        if (
            row.get("bet_total") in ("over", "under")
            and not pd.isna(row.get("home_points"))
            and not pd.isna(row.get("away_points"))
            and not pd.isna(row.get("total_line"))
        ):
            f = float(row.get("kelly_fraction_total", 0.0))
            stake = min(bankroll * f, bankroll * single_bet_cap)
            b = _american_to_b(default_price)
            outcome = _settle_total(
                row["home_points"],
                row["away_points"],
                row["total_line"],
                row["bet_total"],
            )
            if outcome > 0:
                pnl += stake * b
            elif outcome < 0:
                pnl -= stake
            total_stake += stake
            n_bets += 1

    bankroll_out = bankroll + pnl
    meta = {"bets": n_bets, "stake": total_stake, "pnl": pnl}
    return df, bankroll_out, meta


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Simulate 2024 season bankroll week-by-week using Kelly sizing."
    )
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--start-week", type=int, default=2)
    ap.add_argument("--end-week", type=int, default=17)
    ap.add_argument(
        "--data-root", type=str, default="/Volumes/CK SSD/Coding Projects/cfb_model"
    )
    ap.add_argument("--model-dir", type=str, default=str(MODELS_DIR))
    ap.add_argument("--start-bankroll", type=float, default=100.0)
    ap.add_argument("--report-dir", type=str, default=str(REPORTS_DIR))

    ap.add_argument("--spread-threshold", type=float, default=6.0)
    ap.add_argument("--total-threshold", type=float, default=6.0)
    ap.add_argument("--spread-std", type=float, default=3.0)
    ap.add_argument("--total-std", type=float, default=1.5)
    ap.add_argument("--kelly-fraction", type=float, default=0.25)
    ap.add_argument("--kelly-cap", type=float, default=0.25)
    ap.add_argument("--base-unit-fraction", type=float, default=0.02)
    ap.add_argument("--default-price", type=int, default=-110)
    ap.add_argument("--single-bet-cap", type=float, default=0.05)
    ap.add_argument("--weekly-exposure-cap", type=float, default=0.15)
    ap.add_argument("--max-weekly-bets", type=int, default=12)

    args = ap.parse_args()

    metrics_dir = os.path.join(args.report_dir, METRICS_SUBDIR, str(args.year))
    os.makedirs(metrics_dir, exist_ok=True)

    bankroll = float(args.start_bankroll)
    summary_rows = []

    for week in range(args.start_week, args.end_week + 1):
        try:
            week_df, bankroll, meta = simulate_week(
                args.year,
                week,
                args.data_root,
                args.model_dir,
                bankroll,
                spread_threshold=args.spread_threshold,
                total_threshold=args.total_threshold,
                spread_std=args.spread_std,
                total_std=args.total_std,
                fractional_kelly=args.kelly_fraction,
                kelly_cap=args.kelly_cap,
                base_unit_fraction=args.base_unit_fraction,
                default_price=args.default_price,
                single_bet_cap=args.single_bet_cap,
                weekly_exposure_cap=args.weekly_exposure_cap,
                max_weekly_bets=args.max_weekly_bets,
            )
            summary_rows.append(
                {
                    "week": week,
                    "bets": meta["bets"],
                    "stake": round(meta["stake"], 2),
                    "pnl": round(meta["pnl"], 2),
                    "bankroll": round(bankroll, 2),
                }
            )
        except Exception as e:
            summary_rows.append(
                {
                    "week": week,
                    "bets": 0,
                    "stake": 0.0,
                    "pnl": 0.0,
                    "bankroll": round(bankroll, 2),
                    "error": str(e),
                }
            )
            continue

    summary = pd.DataFrame(summary_rows)
    out_path = os.path.join(metrics_dir, f"bankroll_sim_{args.year}.csv")
    summary.to_csv(out_path, index=False)
    print(summary)
    print(f"Saved bankroll simulation to {out_path}")


if __name__ == "__main__":
    main()
