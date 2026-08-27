#!/usr/bin/env python3
"""Private one-request CFBD worker for resumable successor R1 play capture."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cks_picks_cfb.data.plays import PlaysIngester
from cks_picks_cfb.data.sources import classify_source_exception


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        json.dump(value, handle, sort_keys=True, default=str)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True)
    parser.add_argument("--result", required=True)
    args = parser.parse_args()
    result_path = Path(args.result)
    request = json.loads(Path(args.request).read_text(encoding="utf-8"))
    try:
        parameters = dict(request["parameters"])
        ingester = PlaysIngester(
            year=int(parameters["year"]),
            classification=str(parameters["classification"]),
            season_type=str(parameters["season_type"]),
            only_week=parameters.get("canonical_week"),
        )
        raw_records = ingester.fetch_source_request(parameters)
        records = ingester.transform_data(raw_records)
        returned_game_ids = sorted(
            {int(record["game_id"]) for record in records if record.get("game_id") is not None}
        )
        expected_game_ids = sorted(int(value) for value in parameters["expected_game_ids"])
        _atomic_json(
            result_path,
            {
                "state": "succeeded",
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "records": records,
                "returned_game_ids": returned_game_ids,
                "missing_game_ids": sorted(set(expected_game_ids) - set(returned_game_ids)),
                "extra_game_ids": sorted(set(returned_game_ids) - set(expected_game_ids)),
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
