#!/usr/bin/env python3
"""Read-only compatibility probe for one planned successor R1 play week."""

from __future__ import annotations

import argparse
import json

from cks_picks_cfb.data.history_play_capture import (
    load_history_play_capture_policy,
    run_isolated_play_worker,
)
from cks_picks_cfb.data.plays import PlaysIngester
from cks_picks_cfb.data.storage import get_storage


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history-season", type=int, default=2015)
    parser.add_argument("--provider-week", type=int, default=1)
    parser.add_argument("--expected-play-count", type=int, default=15369)
    args = parser.parse_args()
    if args.history_season != 2015 or args.provider_week != 1:
        raise ValueError("the controlled compatibility probe is fixed to 2015 Week 1")
    ingester = PlaysIngester(year=args.history_season, storage=get_storage())
    request = next(
        (
            source_request.manifest()
            for source_request in ingester.source_requests()
            if int(source_request.parameters["week"]) == args.provider_week
        ),
        None,
    )
    if request is None:
        raise LookupError("2015 Week 1 is absent from the prepared games projection")
    result = run_isolated_play_worker(
        request, policy=load_history_play_capture_policy()
    )
    rows = len(result["records"])
    if rows != args.expected_play_count:
        raise RuntimeError(
            f"2015 Week 1 play compatibility mismatch: {rows} != {args.expected_play_count}"
        )
    print(
        json.dumps(
            {
                "history_season": args.history_season,
                "provider_week": args.provider_week,
                "row_count": rows,
                "returned_game_ids": result["returned_game_ids"],
                "missing_game_ids": result["missing_game_ids"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
