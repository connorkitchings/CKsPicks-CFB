#!/usr/bin/env python3
"""Train a point-in-time preseason spread and total model bundle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.preseason import (
    build_preseason_matchups,
    evaluate_preseason_candidate,
    save_preseason_models,
)

TRAINING_YEARS = {2019, 2021, 2022, 2023}
LOCKED_HOLDOUT_YEAR = 2024
SHADOW_YEAR = 2025


def _parse_snapshot(value: str) -> tuple[int, str]:
    year, as_of = value.split(":", 1)
    return int(year), as_of


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--snapshots",
        required=True,
        help="Comma-separated year:as_of values; historical snapshots only.",
    )
    parser.add_argument("--holdout", required=True, help="Year:as_of locked holdout.")
    parser.add_argument(
        "--shadow",
        default=None,
        help="Optional later year:as_of check; it is never used for tuning.",
    )
    parser.add_argument(
        "--blend-weights-json",
        type=Path,
        default=None,
        help="Frozen select_blend_weights output computed from training-only rows.",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--alpha", type=float, default=10.0)
    args = parser.parse_args()

    storage = get_storage()
    train_snapshots = list(map(_parse_snapshot, args.snapshots.split(",")))
    if {year for year, _ in train_snapshots} != TRAINING_YEARS:
        raise ValueError(
            f"Preseason training years must be {sorted(TRAINING_YEARS)}; "
            f"got {sorted(year for year, _ in train_snapshots)}"
        )
    holdout_year, holdout_as_of = _parse_snapshot(args.holdout)
    if holdout_year != LOCKED_HOLDOUT_YEAR:
        raise ValueError(f"Locked preseason holdout must be {LOCKED_HOLDOUT_YEAR}")
    train_frames = [
        build_preseason_matchups(storage, year=year, as_of=as_of, include_targets=True)
        for year, as_of in train_snapshots
    ]
    train = pd.concat(train_frames, ignore_index=True)
    holdout = build_preseason_matchups(
        storage, year=holdout_year, as_of=holdout_as_of, include_targets=True
    )
    shadow = None
    if args.shadow:
        shadow_year, shadow_as_of = _parse_snapshot(args.shadow)
        if shadow_year != SHADOW_YEAR:
            raise ValueError(f"Preseason shadow year must be {SHADOW_YEAR}")
        shadow = build_preseason_matchups(
            storage, year=shadow_year, as_of=shadow_as_of, include_targets=True
        )
    bundle, metrics = evaluate_preseason_candidate(
        train, holdout, shadow, alpha=args.alpha
    )
    if args.blend_weights_json:
        weights = json.loads(args.blend_weights_json.read_text(encoding="utf-8"))
        if set(map(int, weights)) != {1, 2}:
            raise ValueError("Blend weights must contain exactly keys 1 and 2")
        bundle["blend_weights"] = {
            int(key): float(value) for key, value in weights.items()
        }
    save_preseason_models(bundle, args.output)
    print(json.dumps(metrics, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
