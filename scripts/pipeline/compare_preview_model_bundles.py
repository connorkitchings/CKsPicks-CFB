#!/usr/bin/env python3
"""Produce a private, game-level V2/V3/V4 prediction comparison CSV."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v2-csv", type=Path, required=True)
    parser.add_argument("--v3-csv", type=Path, required=True)
    parser.add_argument("--v4-csv", type=Path)
    parser.add_argument("--output-csv", type=Path, required=True)
    args = parser.parse_args()
    columns = [
        "game_id",
        "Game",
        "prediction_regime",
        "Spread Prediction",
        "Total Prediction",
        "edge_spread",
        "edge_total",
        "Spread Bet",
        "Total Bet",
        "high_confidence_eligible",
        "spread_model_version",
        "total_model_version",
    ]
    v2 = pd.read_csv(args.v2_csv)
    frames = {"v2": v2, "v3": pd.read_csv(args.v3_csv)}
    if args.v4_csv:
        frames["v4"] = pd.read_csv(args.v4_csv)
    for name, frame in frames.items():
        missing = sorted(set(columns) - set(frame.columns))
        if missing:
            raise ValueError(f"{name} predictions are missing columns: {missing}")
        if frame["game_id"].duplicated().any():
            raise ValueError(f"{name} predictions have duplicate game IDs")
    comparison = v2[columns].merge(
        frames["v3"][columns],
        on="game_id",
        suffixes=("_v2", "_v3"),
        validate="one_to_one",
    )
    comparison["spread_prediction_delta"] = comparison["Spread Prediction_v3"] - comparison["Spread Prediction_v2"]
    comparison["total_prediction_delta"] = comparison["Total Prediction_v3"] - comparison["Total Prediction_v2"]
    comparison["spread_edge_delta"] = comparison["edge_spread_v3"] - comparison["edge_spread_v2"]
    comparison["total_edge_delta"] = comparison["edge_total_v3"] - comparison["edge_total_v2"]
    comparison["spread_lean_changed"] = comparison["Spread Bet_v2"] != comparison["Spread Bet_v3"]
    comparison["total_lean_changed"] = comparison["Total Bet_v2"] != comparison["Total Bet_v3"]
    if "v4" in frames:
        comparison = comparison.merge(
            frames["v4"][columns], on="game_id", validate="one_to_one"
        )
        comparison["spread_prediction_delta_v4_vs_v2"] = (
            comparison["Spread Prediction"] - comparison["Spread Prediction_v2"]
        )
        comparison["total_prediction_delta_v4_vs_v2"] = (
            comparison["Total Prediction"] - comparison["Total Prediction_v2"]
        )
        comparison["spread_prediction_delta_v4_vs_v3"] = (
            comparison["Spread Prediction"] - comparison["Spread Prediction_v3"]
        )
        comparison["total_prediction_delta_v4_vs_v3"] = (
            comparison["Total Prediction"] - comparison["Total Prediction_v3"]
        )
        comparison["spread_lean_changed_v4_vs_v2"] = (
            comparison["Spread Bet"] != comparison["Spread Bet_v2"]
        )
        comparison["total_lean_changed_v4_vs_v2"] = (
            comparison["Total Bet"] != comparison["Total Bet_v2"]
        )
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    comparison.sort_values("game_id").to_csv(args.output_csv, index=False)
    print({"games": len(comparison), "output": str(args.output_csv)})


if __name__ == "__main__":
    main()
