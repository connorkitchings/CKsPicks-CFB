#!/usr/bin/env python3
"""Distill the frozen V4 tournament reports into the web accuracy panel JSON.

The deployed bundle manifest embeds the immutable predictive routing report
(selection OOF 2022-2024 + locked 2025). This script distills that report into
``web/src/data/model-accuracy.json`` for the site's backtest accuracy panel:

- Per route (game_1..game_4) x target (spread, total): the champion candidate's
  official pooled MAE + per-season MAE + sample count from the selection
  report, and the locked-2025 MAE where available.
- Champion decisions come from the report's routing table (never hardcoded).
- Baseline-champion routes have no locked report block; their locked-2025 MAE
  is computed from the frozen locked-candidates CSV (baseline_prediction vs
  actual, deduplicated to one row per game).

All displayed numbers are outcome-based (points off the final result). No
market-line grading exists historically (legacy lines are quarantined).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import pandas as pd
import yaml

from cks_picks_cfb.data.storage import get_storage

EARLY_REGIMES = ("game_1", "game_2", "game_3", "game_4")
ROUTE_LABELS = {
    "game_1": "First game of the season",
    "game_2": "Second game of the season",
    "game_3": "Third game of the season",
    "game_4": "Fourth game of the season",
}
METHODOLOGY = (
    "Backtest accuracy is the average points between the prediction and the "
    "final result (mean absolute error) for each in-season route. 2022-2024 "
    "pooled out-of-sample selection; 2025 is a held-out season checked once. "
    "Evaluation predates the final 2021-2025 refit. Not betting results."
)
SCHEMA_VERSION = "model_accuracy_v1"


def champion_selection_metrics(
    selection_reports: Mapping[str, Any], target: str, regime: str, champion: str
) -> dict[str, Any] | None:
    """Official pooled + seasonal selection metrics for a route champion.

    ``selection_reports[target][regime]`` maps candidate name -> entry. For a
    baseline champion, the route's baseline metrics are identical in every
    candidate entry, so the first available entry is used.
    """
    route = (selection_reports.get(target) or {}).get(regime) or {}
    if champion != "baseline":
        entry = route.get(champion)
        if entry is None:
            return None
        metrics = entry["metrics"]
        return _selection_block(metrics, candidate=True)
    for entry in route.values():
        metrics = entry["metrics"]
        if metrics.get("baseline_mae") is not None:
            return _selection_block(metrics, candidate=False)
    return None


def _selection_block(metrics: Mapping[str, Any], *, candidate: bool) -> dict[str, Any]:
    prefix = "candidate" if candidate else "baseline"
    seasons = {
        str(item["season"]): round(float(item[f"{prefix}_mae"]), 2)
        for item in metrics.get("seasonal") or ()
    }
    return {
        "mae": round(float(metrics[f"{prefix}_mae"]), 2),
        "n": int(metrics["sample_count"]),
        "seasons": seasons,
    }


def locked_metrics(
    locked_reports: Mapping[str, Any], target: str, regime: str, champion: str
) -> dict[str, Any] | None:
    """Locked-2025 metrics for a champion, from the report when present."""
    entry = (locked_reports.get(target) or {}).get(regime) or {}
    report = entry.get("report")
    if not report:
        return None
    metrics = report["metrics"]
    prefix = "candidate" if champion != "baseline" else "baseline"
    if metrics.get(f"{prefix}_mae") is None:
        return None
    return {
        "mae": round(float(metrics[f"{prefix}_mae"]), 2),
        "n": int(metrics["sample_count"]),
    }


def locked_baseline_metrics_from_csv(
    frame: pd.DataFrame, target: str, regime: str
) -> dict[str, Any] | None:
    """Locked-2025 MAE for a baseline champion from the frozen candidates CSV.

    Rows are deduplicated to one per game; the baseline prediction must be
    unique within each game or the data is not trustworthy.
    """
    rows = frame[
        (frame["target"] == target)
        & (frame["regime"] == regime)
        & (frame["baseline_prediction"].notna())
        & (frame["actual"].notna())
    ]
    if rows.empty:
        return None
    grouped = rows.groupby(["season", "game_id"], sort=False)
    if (grouped["baseline_prediction"].nunique() > 1).any():
        raise ValueError(
            f"Inconsistent baseline predictions for locked {target}/{regime}"
        )
    deduped = grouped.first().reset_index()
    return {
        "mae": round(
            float((deduped["baseline_prediction"] - deduped["actual"]).abs().mean()), 2
        ),
        "n": int(len(deduped)),
    }


def distill(
    manifest: Mapping[str, Any],
    routing_report: Mapping[str, Any],
    locked_frame: pd.DataFrame | None,
    *,
    manifest_sha256: str,
) -> dict[str, Any]:
    """Build the accuracy JSON payload from the frozen reports."""
    routing = routing_report["routing"]
    selection_reports = routing_report["selection_report"]["reports"]
    locked_reports = routing_report.get("locked_2025_reports") or {}

    routes: dict[str, Any] = {}
    for regime in EARLY_REGIMES:
        route_block: dict[str, Any] = {"label": ROUTE_LABELS[regime]}
        for target in ("spread", "total"):
            champion = routing[target][regime]
            selection = champion_selection_metrics(
                selection_reports, target, regime, champion
            )
            locked = locked_metrics(locked_reports, target, regime, champion)
            if locked is None and champion == "baseline" and locked_frame is not None:
                locked = locked_baseline_metrics_from_csv(locked_frame, target, regime)
            route_block[target] = {
                "champion": champion,
                "selection": selection,
                "locked_2025": locked,
            }
        routes[regime] = route_block

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "bundle_id": manifest["bundle_id"],
        "manifest_sha256": manifest_sha256,
        "routing_report_uri": manifest["promotion_reports"][
            "game_ordinal_predictive_routing"
        ],
        "selection_design_sha": routing_report["selection_report"][
            "selection_design_sha"
        ],
        "methodology": METHODOLOGY,
        "routes": routes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("conf/weekly_bets/v4_2026.yaml"),
        help="Weekly config carrying the model_bundle_v3 spec",
    )
    parser.add_argument(
        "--locked-csv",
        type=Path,
        default=Path("artifacts/preview/training/v4/locked-candidates-20260818.csv"),
        help="Frozen locked-2025 candidates CSV (baseline-champion metrics)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("web/src/data/model-accuracy.json"),
    )
    args = parser.parse_args()

    spec = yaml.safe_load(args.config.read_text())["model_bundle_v3"]
    store = get_storage()
    manifest_payload = store.read_bytes(spec["artifact_uri"])
    manifest_sha = hashlib.sha256(manifest_payload).hexdigest()
    if manifest_sha != spec["sha256"]:
        raise ValueError("model bundle manifest checksum mismatch")
    manifest = json.loads(manifest_payload.decode("utf-8"))

    report_uri = manifest["promotion_reports"]["game_ordinal_predictive_routing"]
    routing_report = json.loads(store.read_bytes(report_uri).decode("utf-8"))

    locked_frame = None
    if args.locked_csv and args.locked_csv.exists():
        locked_frame = pd.read_csv(args.locked_csv)
        locked_frame = locked_frame[locked_frame["candidate_stage"] == "locked"]

    payload = distill(
        manifest, routing_report, locked_frame, manifest_sha256=manifest_sha
    )
    if any(
        route[target]["selection"] is None
        for route in payload["routes"].values()
        for target in ("spread", "total")
    ):
        raise ValueError("Selection metrics missing for at least one route")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {args.output}")
    for regime, route in payload["routes"].items():
        for target in ("spread", "total"):
            block = route[target]
            sel = block["selection"]
            lk = block["locked_2025"]
            locked_txt = "-" if lk is None else f"{lk['mae']:.2f} n={lk['n']}"
            print(
                f"  {target:6s} {regime:7s} champion={block['champion']:15s} "
                f"OOF mae={sel['mae']:5.2f} n={sel['n']:3d} "
                f"locked2025={locked_txt}"
            )


if __name__ == "__main__":
    main()
