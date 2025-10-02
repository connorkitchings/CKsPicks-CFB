#!/usr/bin/env python3
"""
Calibrate predictions by week-of-season and evaluate threshold sweeps.

Two modes:
1) Single-file mode (quick check):
   - Input: one scored season CSV (contains model predictions and final scores)
   - Output: bias, calibrated predictions, and threshold sweeps computed from that file
   - Note: this may introduce in-season leakage if used on the same season you evaluate

2) Train/Holdout mode (no in-season leakage):
   - Inputs: one or more scored season CSVs for training years, and one scored CSV for holdout year
   - Bias is computed on the training years and applied to the holdout season only

Outputs in both modes include:
- Week-of-season bias estimates for spread and total
- Calibrated predictions
- Threshold sweeps for spreads and totals (hit rate vs threshold)
"""

import argparse

# Project imports
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cfb_model.models.calibration import apply_weekly_bias, compute_weekly_bias


def _compute_actuals(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if {"home_points", "away_points"}.issubset(df.columns):
        df["actual_spread"] = df["home_points"].astype(float) - df[
            "away_points"
        ].astype(float)
        df["actual_total"] = df["home_points"].astype(float) + df["away_points"].astype(
            float
        )
    return df


def _attach_actuals_from_games(
    df: pd.DataFrame, data_root: str | None, year: int
) -> pd.DataFrame:
    """Merge actual scores from raw games for a single season."""
    try:
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
        from cfb_model.data.storage.local_storage import LocalStorage
    except Exception:
        return df

    games = LocalStorage(data_root=data_root, file_format="csv", data_type="raw")
    game_rows = games.read_index("games", {"year": year})
    if not game_rows:
        return df
    gdf = pd.DataFrame.from_records(game_rows)
    cols = [c for c in ["id", "home_points", "away_points"] if c in gdf.columns]
    if "id" not in cols:
        return df
    gdf = gdf[cols].rename(columns={"id": "game_id"})
    out = df.merge(gdf, on="game_id", how="left")
    out = _compute_actuals(out)
    return out


def _attach_actuals_multi_years(
    df: pd.DataFrame, data_root: str | None
) -> pd.DataFrame:
    """Merge actual scores from raw games across all seasons present in df."""
    if "game_id" not in df.columns or "season" not in df.columns:
        return df
    try:
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
        from cfb_model.data.storage.local_storage import LocalStorage
    except Exception:
        return df

    storage = LocalStorage(data_root=data_root, file_format="csv", data_type="raw")
    seasons = sorted(set(int(s) for s in df["season"].dropna().unique()))
    frames = []
    for y in seasons:
        rows = storage.read_index("games", {"year": y})
        if not rows:
            continue
        gdf = pd.DataFrame.from_records(rows)
        cols = [c for c in ["id", "home_points", "away_points"] if c in gdf.columns]
        if "id" not in cols:
            continue
        gdf = gdf[cols].rename(columns={"id": "game_id"})
        frames.append(gdf)
    if not frames:
        return df
    all_games = pd.concat(frames, ignore_index=True).drop_duplicates(
        subset=["game_id"], keep="last"
    )
    out = df.merge(all_games, on="game_id", how="left")
    out = _compute_actuals(out)
    return out


def _apply_policy(
    df: pd.DataFrame, spread_threshold: float, total_threshold: float
) -> pd.DataFrame:
    df = df.copy()
    # Expected home margin from line
    df["expected_home_margin"] = -df["home_team_spread_line"].astype(float)

    # Edges (abs difference)
    df["edge_spread"] = (df["model_spread_calib"] - df["expected_home_margin"]).abs()
    df["edge_total"] = (df["model_total_calib"] - df["total_line"]).abs()

    # Bets
    df["bet_spread_model"] = np.where(
        df["edge_spread"] >= spread_threshold,
        np.where(df["model_spread_calib"] > df["expected_home_margin"], "home", "away"),
        "none",
    )
    df["bet_total_model"] = np.where(
        df["edge_total"] >= total_threshold,
        np.where(df["model_total_calib"] > df["total_line"], "over", "under"),
        "none",
    )
    return df


def _sweep_thresholds_scored(
    df: pd.DataFrame, target: str, thresholds: list[float]
) -> pd.DataFrame:
    """Compute hit rates for recomputed, calibrated bets using actual outcomes.

    For spread: a 'home' bet wins if actual_spread > expected_home_margin; 'away' wins if <.
    For totals: 'over' wins if actual_total > total_line; 'under' wins if <.
    Pushes are treated as losses (strict inequality).
    """
    rows = []
    for th in thresholds:
        if target == "spread":
            sub = df[df["edge_spread"] >= th].copy()
            if sub.empty:
                rows.append(
                    {"threshold": th, "picks": 0, "wins": 0, "hit_rate": np.nan}
                )
                continue
            # Determine wins for recomputed bets
            actual_spread = sub["actual_spread"].astype(float)
            exp_margin = sub["expected_home_margin"].astype(float)
            bet_home = sub["bet_spread_model"] == "home"
            bet_away = sub["bet_spread_model"] == "away"
            wins = (
                (bet_home & (actual_spread > exp_margin))
                | (bet_away & (actual_spread < exp_margin))
            ).sum()
            rows.append(
                {
                    "threshold": th,
                    "picks": int(len(sub)),
                    "wins": int(wins),
                    "hit_rate": (wins / len(sub)) if len(sub) else np.nan,
                }
            )
        else:
            sub = df[df["edge_total"] >= th].copy()
            if sub.empty:
                rows.append(
                    {"threshold": th, "picks": 0, "wins": 0, "hit_rate": np.nan}
                )
                continue
            actual_total = sub["actual_total"].astype(float)
            bet_over = sub["bet_total_model"] == "over"
            bet_under = sub["bet_total_model"] == "under"
            wins = (
                (bet_over & (actual_total > sub["total_line"].astype(float)))
                | (bet_under & (actual_total < sub["total_line"].astype(float)))
            ).sum()
            rows.append(
                {
                    "threshold": th,
                    "picks": int(len(sub)),
                    "wins": int(wins),
                    "hit_rate": (wins / len(sub)) if len(sub) else np.nan,
                }
            )
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(
        description="Calibrate predictions and sweep thresholds"
    )

    # Mode A: Single-file (may leak in-season)
    parser.add_argument(
        "--scored-file",
        type=str,
        default=None,
        help="Single scored season CSV (quick mode; may leak in-season)",
    )

    # Mode B: Train/Holdout (no in-season leakage)
    parser.add_argument(
        "--train-scored-files",
        type=str,
        default=None,
        help="Comma-separated list of scored season CSVs for training years",
    )
    parser.add_argument(
        "--holdout-scored-file",
        type=str,
        default=None,
        help="Scored season CSV for the holdout year (bias applied here)",
    )

    parser.add_argument(
        "--out-dir",
        type=str,
        default="reports/calibration",
        help="Directory for outputs",
    )
    parser.add_argument(
        "--data-root",
        type=str,
        default=None,
        help="Data root to fetch actual scores from raw games if needed",
    )
    parser.add_argument(
        "--spread-thresholds",
        type=str,
        default="3.0,4.0,5.0,5.5,6.0,7.0",
        help="Comma-separated thresholds to sweep for spreads",
    )
    parser.add_argument(
        "--total-thresholds",
        type=str,
        default="5.0,5.5,6.0,6.5,7.0,7.5,8.0",
        help="Comma-separated thresholds to sweep for totals",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    spread_thresholds = [
        float(x.strip()) for x in args.spread_thresholds.split(",") if x.strip()
    ]
    total_thresholds = [
        float(x.strip()) for x in args.total_thresholds.split(",") if x.strip()
    ]

    if args.train_scored_files and args.holdout_scored_file:
        # Train/Holdout mode
        train_paths = [
            p.strip() for p in args.train_scored_files.split(",") if p.strip()
        ]
        train_frames = []
        for p in train_paths:
            df_tr = pd.read_csv(p)
            df_tr = _compute_actuals(df_tr)
            train_frames.append(df_tr)
        train_df = (
            pd.concat(train_frames, ignore_index=True)
            if train_frames
            else pd.DataFrame()
        )
        if train_df.empty:
            raise SystemExit("No training data loaded for calibration.")

        # Ensure actuals exist in training data (merge from raw games per season if needed)
        train_df = _compute_actuals(train_df)
        if (
            "actual_spread" not in train_df.columns
            or "actual_total" not in train_df.columns
        ):
            train_df = _attach_actuals_multi_years(train_df, args.data_root)
            train_df = _compute_actuals(train_df)

        holdout_df = pd.read_csv(args.holdout_scored_file)
        holdout_df = _compute_actuals(holdout_df)
        if (
            "actual_spread" not in holdout_df.columns
            or "actual_total" not in holdout_df.columns
        ):
            # Infer year from the file content if present
            holdout_year = (
                int(holdout_df["season"].iloc[0])
                if "season" in holdout_df.columns
                else None
            )
            if holdout_year is not None:
                holdout_df = _attach_actuals_from_games(
                    holdout_df, args.data_root, holdout_year
                )

        # Compute bias on training only
        spread_bias = compute_weekly_bias(
            train_df, target_col="actual_spread", pred_col="model_spread"
        )
        total_bias = compute_weekly_bias(
            train_df, target_col="actual_total", pred_col="model_total"
        )

        # Apply to holdout only
        holdout_df = apply_weekly_bias(
            holdout_df,
            spread_bias,
            pred_col="model_spread",
            out_col="model_spread_calib",
        )
        holdout_df = apply_weekly_bias(
            holdout_df, total_bias, pred_col="model_total", out_col="model_total_calib"
        )

        # Save bias tables
        spread_bias.to_csv(
            out_dir / "spread_weekly_bias_from_training.csv", index=False
        )
        total_bias.to_csv(out_dir / "total_weekly_bias_from_training.csv", index=False)

        # Edges + threshold sweeps on calibrated holdout
        holdout_df = _apply_policy(
            holdout_df,
            spread_threshold=min(spread_thresholds),
            total_threshold=min(total_thresholds),
        )
        spread_sweep = _sweep_thresholds_scored(holdout_df, "spread", spread_thresholds)
        total_sweep = _sweep_thresholds_scored(holdout_df, "total", total_thresholds)

        # Save outputs
        spread_sweep.to_csv(
            out_dir / "holdout_spread_threshold_sweep_calibrated.csv", index=False
        )
        total_sweep.to_csv(
            out_dir / "holdout_total_threshold_sweep_calibrated.csv", index=False
        )
        holdout_df.to_csv(
            out_dir / "holdout_season_calibrated_predictions.csv", index=False
        )
        print(f"Saved calibration outputs (train/holdout mode) to {out_dir}")

    elif args.scored_file:
        # Single-file mode (original)
        df = pd.read_csv(args.scored_file)
        df = _compute_actuals(df)
        if "actual_spread" not in df.columns or "actual_total" not in df.columns:
            # Infer year from the file content if present
            single_year = int(df["season"].iloc[0]) if "season" in df.columns else None
            if single_year is not None:
                df = _attach_actuals_from_games(df, args.data_root, single_year)

        # Compute week-of-season bias using model predictions vs actuals
        spread_bias = compute_weekly_bias(
            df, target_col="actual_spread", pred_col="model_spread"
        )
        total_bias = compute_weekly_bias(
            df, target_col="actual_total", pred_col="model_total"
        )

        # Apply calibration
        df = apply_weekly_bias(
            df, spread_bias, pred_col="model_spread", out_col="model_spread_calib"
        )
        df = apply_weekly_bias(
            df, total_bias, pred_col="model_total", out_col="model_total_calib"
        )

        # Save bias tables
        spread_bias.to_csv(out_dir / "spread_weekly_bias.csv", index=False)
        total_bias.to_csv(out_dir / "total_weekly_bias.csv", index=False)

        # Re-apply policy with default thresholds to compute edges first
        df = _apply_policy(
            df,
            spread_threshold=min(spread_thresholds),
            total_threshold=min(total_thresholds),
        )

        spread_sweep = _sweep_thresholds_scored(df, "spread", spread_thresholds)
        total_sweep = _sweep_thresholds_scored(df, "total", total_thresholds)

        # Save outputs
        spread_sweep.to_csv(
            out_dir / "spread_threshold_sweep_calibrated.csv", index=False
        )
        total_sweep.to_csv(
            out_dir / "total_threshold_sweep_calibrated.csv", index=False
        )
        df.to_csv(out_dir / "season_calibrated_predictions.csv", index=False)
        print(f"Saved calibration outputs (single-file mode) to {out_dir}")

    else:
        raise SystemExit(
            "Provide either --scored-file or both --train-scored-files and --holdout-scored-file."
        )


if __name__ == "__main__":
    main()
