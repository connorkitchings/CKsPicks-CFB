#!/usr/bin/env python3
"""Select frozen Week 2-3 preseason blend weights from training-only rows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from cks_picks_cfb.preseason import select_blend_weights


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--validation-csv",
        type=Path,
        required=True,
        help="Training-only rows with targets and precomputed preseason/recency predictions.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON destination. Otherwise prints weights for config entry.",
    )
    args = parser.parse_args()
    weights = select_blend_weights(pd.read_csv(args.validation_csv))
    output = json.dumps(weights, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
