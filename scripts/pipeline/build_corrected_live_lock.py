#!/usr/bin/env python3
"""Extend the corrected replay lock with one live week taken from the pinned Silver games.

    PYTHONPATH=src:. uv run python scripts/pipeline/build_corrected_live_lock.py \\
        --week 6 --out conf/rebuild/successor_lock_w6live_v1.json

Local output only. The live week's games enter without finals; every pin is read from the
files named by the arguments.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from cks_picks_cfb.data.storage import get_storage  # noqa: E402
from cks_picks_cfb.rebuild.successor_lock import derive_live_lock  # noqa: E402

CONF = REPO_ROOT / "conf" / "rebuild"


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument(
        "--base-lock", type=Path, default=CONF / "successor_lock_w5_v1.json"
    )
    parser.add_argument(
        "--parents", type=Path, default=CONF / "silver_2026_parents_w5_v1.json"
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if REPO_ROOT / "data" in [args.out.resolve(), *args.out.resolve().parents]:
        raise SystemExit("output cannot be the repository ./data directory")
    games_ref = next(
        p
        for p in json.loads(args.parents.read_text())["parents"]
        if p["dataset"] == "games"
    )
    raw = get_storage(environment="preview").read_bytes(games_ref["uri"])
    if hashlib.sha256(raw).hexdigest() != games_ref["content_sha"]:
        raise SystemExit("pinned games dataset changed")
    frame = pd.read_parquet(io.BytesIO(raw))
    frame = frame[
        (frame["season"].astype(int) == 2026) & (frame["week"].astype(int) == args.week)
    ]
    frame = frame[
        frame["home_classification"].eq("fbs") & frame["away_classification"].eq("fbs")
    ]
    games = [
        {
            "game_id": int(row.game_id),
            "start_date": pd.Timestamp(row.kickoff_utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "home_team": row.home_team,
            "away_team": row.away_team,
        }
        for row in frame.itertuples(index=False)
    ]
    lock = derive_live_lock(
        json.loads(args.base_lock.read_text()),
        week=args.week,
        games=games,
        games_source={
            "dataset": "games",
            "version_id": games_ref["version_id"],
            "content_sha": games_ref["content_sha"],
            "uri": games_ref["uri"],
        },
    )
    args.out.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "out": str(args.out),
                "sha256": hashlib.sha256(args.out.read_bytes()).hexdigest(),
                "live_games": len(games),
                "first_kickoff": min(g["start_date"] for g in games),
                "last_kickoff": max(g["start_date"] for g in games),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
