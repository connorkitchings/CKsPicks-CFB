#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging

from cfb_model.flows.preaggregations import preaggregations_flow


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run pre-aggregations (plays → byplay → drives → team_game → team_season → adjusted)"
    )
    parser.add_argument(
        "--year", type=int, required=True, help="Season year to process"
    )
    parser.add_argument(
        "--data-root",
        type=str,
        default=None,
        help="Absolute path to the data root (parent of 'raw'/'processed')",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-partition progress logs",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    totals = preaggregations_flow(
        year=args.year, data_root=args.data_root, verbose=(not args.quiet)
    )
    logging.info("Completed pre-aggregations for %s: %s", args.year, totals)


if __name__ == "__main__":
    main()
