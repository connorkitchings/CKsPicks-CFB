#!/usr/bin/env python3
"""Window 2 Step 5A: fetch CFBD drives by (year, seasonType, week) and retain the evidence.

Each response is stored as the exact bytes received, with a manifest line holding the
request URL (never the API key), parameters, UTC capture time, HTTP status, byte count and
SHA-256. Re-running resumes: a bundle whose file and manifest line already agree is skipped,
and a stored file whose hash differs from its manifest line stops the run. The API key is read
from ``CFBD_API_KEY`` and is never printed or written. Writes only under ``--output-dir``.

    PYTHONPATH=src:. uv run python scripts/data/fetch_cfbd_drives_5a.py \\
        --bundles bundles.csv --output-dir <dir> [--limit N]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

BASE_URL = "https://api.collegefootballdata.com/drives"
RETRY_STATUSES = {429, 500, 502, 503, 504}
STOP_STATUSES = {400, 401, 403, 404}


def bundle_name(year: int, season_type: str, week: int) -> str:
    return f"drives_{year}_{season_type}_w{week:02d}.json"


def read_manifest(path: Path) -> dict[str, dict]:
    records: dict[str, dict] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                record = json.loads(line)
                records[record["file"]] = record
    return records


def fetch_one(
    session: requests.Session, key: str, year: int, season_type: str, week: int
) -> tuple[bytes, dict]:
    params = {"year": year, "seasonType": season_type, "week": week}
    last = None
    for attempt in range(1, 6):
        response = session.get(
            BASE_URL,
            params=params,
            headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
            timeout=120,
        )
        captured_at = datetime.now(timezone.utc).isoformat()
        if response.status_code in STOP_STATUSES:
            raise SystemExit(
                f"CFBD returned {response.status_code} for {response.request.url}; stopping"
            )
        if response.status_code in RETRY_STATUSES:
            last = response.status_code
            time.sleep(min(60, 2**attempt * 2))
            continue
        response.raise_for_status()
        meta = {
            "request_url": response.request.url,  # query string only; the key is in a header
            "params": params,
            "captured_at_utc": captured_at,
            "http_status": response.status_code,
            "bytes": len(response.content),
            "sha256": hashlib.sha256(response.content).hexdigest(),
            "response_date_header": response.headers.get("Date"),
            "rate_limit_remaining": response.headers.get("X-CallLimit-Remaining"),
        }
        return response.content, meta
    raise SystemExit(f"CFBD kept returning {last} for {year} {season_type} week {week}")


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bundles", type=Path, required=True, help="CSV with season, season_type, week"
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--limit", type=int, default=None, help="Fetch at most this many new bundles"
    )
    parser.add_argument(
        "--pause", type=float, default=0.5, help="Seconds between requests"
    )
    args = parser.parse_args(argv)
    key = os.environ.get("CFBD_API_KEY")
    if not key:
        raise SystemExit("CFBD_API_KEY is not set")
    raw_dir = args.output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output_dir / "manifest.jsonl"
    manifest = read_manifest(manifest_path)
    with args.bundles.open() as handle:
        bundles = [
            (int(r["season"]), r["season_type"], int(r["week"]))
            for r in csv.DictReader(handle)
        ]
    session = requests.Session()
    fetched = skipped = 0
    for year, season_type, week in bundles:
        name = bundle_name(year, season_type, week)
        path = raw_dir / name
        if name in manifest and path.exists():
            if (
                hashlib.sha256(path.read_bytes()).hexdigest()
                != manifest[name]["sha256"]
            ):
                raise SystemExit(f"{name}: stored bytes differ from the manifest hash")
            skipped += 1
            continue
        if args.limit is not None and fetched >= args.limit:
            break
        body, meta = fetch_one(session, key, year, season_type, week)
        path.write_bytes(body)
        meta["file"] = name
        meta["rows"] = len(json.loads(body))
        with manifest_path.open("a") as out:
            out.write(json.dumps(meta, sort_keys=True) + "\n")
        fetched += 1
        print(
            f"{name}: {meta['rows']} drives, {meta['bytes']} bytes",
            file=sys.stderr,
            flush=True,
        )
        time.sleep(args.pause)
    print(
        json.dumps(
            {"fetched": fetched, "already_present": skipped, "bundles": len(bundles)}
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
