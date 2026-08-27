#!/usr/bin/env python3
"""Private capture-only CFBD worker for one successor R1 source request."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cks_picks_cfb.data.base import BaseIngester
from cks_picks_cfb.data.game_stats import GameStatsIngester
from cks_picks_cfb.data.games import GamesIngester
from cks_picks_cfb.data.sources import classify_source_exception
from cks_picks_cfb.data.teams import TeamsIngester
from cks_picks_cfb.data.venues import VenuesIngester

INGESTERS = {
    "teams": TeamsIngester,
    "games": GamesIngester,
    "game_stats": GameStatsIngester,
    "venues": VenuesIngester,
}


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        json.dump(value, handle, sort_keys=True, default=str)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    temporary.replace(path)


def _game_ids(records: list[dict[str, Any]]) -> list[int]:
    values = {
        int(record["game_id"])
        for record in records
        if record.get("game_id") is not None
    }
    return sorted(values)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entity", choices=sorted(INGESTERS), required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--request", required=True)
    parser.add_argument("--result", required=True)
    args = parser.parse_args()
    result_path = Path(args.result)
    request = json.loads(Path(args.request).read_text(encoding="utf-8"))
    try:
        ingester = INGESTERS[args.entity](year=args.year)
        raw_records = ingester.fetch_source_request(dict(request["parameters"]))
        records = [BaseIngester.provider_value(record) for record in raw_records]
        if not records:
            raise ValueError(f"CFBD returned no {args.entity} records")
        _atomic_json(
            result_path,
            {
                "state": "succeeded",
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "records": records,
                "returned_game_ids": _game_ids(records),
            },
        )
    except Exception as exc:
        error = classify_source_exception(exc)
        _atomic_json(
            result_path,
            {
                "state": "failed",
                "error_category": str(error.category),
                "error_detail": str(exc)[-4000:],
                "retryable": bool(error.retryable),
                "status": getattr(exc, "status", getattr(exc, "status_code", None)),
            },
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
