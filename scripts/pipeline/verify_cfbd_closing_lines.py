#!/usr/bin/env python3
"""Compare completed-game CFBD lines with immutable pre-kickoff CFBD captures."""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.ratings_lab.artifacts import canonical_json

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.pipeline.audit_corrected_replay_chain import (  # noqa: E402
    ReadOnlyEvidence,
    sha,
)


def compare_lines(stored, current, schedule):
    """Compare provider and target exactly; a missing current line is a failure."""
    lookup = {
        (int(g["id"]), line["provider"]): line for g in current for line in g["lines"]
    }
    rows = []
    kickoff = schedule.set_index("game_id")["start_date"]
    for q in stored.to_dict("records"):
        if q.get("__capture_provider") != "cfbd" or int(q["game_id"]) not in kickoff:
            continue
        if pd.Timestamp(q["captured_at"]) >= pd.Timestamp(kickoff[int(q["game_id"])]):
            continue
        live = lookup.get((int(q["game_id"]), q["provider"]), {})
        for target, column in [("spread", "spread"), ("total", "overUnder")]:
            old, new = q.get(target), live.get(column)
            if old is None or pd.isna(old):
                continue
            rows.append(
                {
                    "game_id": int(q["game_id"]),
                    "provider": q["provider"],
                    "target": target,
                    "quote_id": q["quote_id"],
                    "captured_at": pd.Timestamp(q["captured_at"]).isoformat(),
                    "stored": float(old),
                    "current": new,
                    "matches": new is not None and abs(float(old) - float(new)) < 1e-9,
                }
            )
    return rows


def main():
    load_dotenv()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--environment", choices=["preview", "production"], default="preview"
    )
    p.add_argument(
        "--source-lock",
        type=Path,
        default=Path("conf/rebuild/successor_lock_w5_v1.json"),
    )
    p.add_argument("--sample-per-week", type=int, default=3)
    p.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/audit/cfbd_closing_line_comparison_2026.json"),
    )
    args = p.parse_args()
    if os.getenv("CFB_STORAGE_BACKEND") != "r2" or not os.getenv("CFBD_API_KEY"):
        raise SystemExit("R2 backend and CFBD_API_KEY are required")
    if args.sample_per_week < 1:
        raise SystemExit("sample-per-week must be positive")
    if Path("data").resolve() in [
        args.output.resolve(),
        *args.output.resolve().parents,
    ]:
        raise SystemExit("output cannot be repository ./data")
    storage = ReadOnlyEvidence(get_storage(environment=args.environment))
    raw = args.source_lock.read_bytes()
    lock = json.loads(raw)
    schedule = pd.DataFrame(lock["games"]["rows"], columns=lock["games"]["columns"])
    rows, requests_evidence = [], []
    for week in range(6):
        ref = lock["market_sources"][str(week)]["market_quotes"]
        data = storage.read_bytes(ref["uri"])
        if sha(data) != ref["content_sha"]:
            raise ValueError("quote checksum differs")
        stored = pd.read_parquet(io.BytesIO(data))
        slate = (
            schedule[schedule.week.eq(week)]
            .sort_values("game_id")
            .head(args.sample_per_week)
        )
        for game in slate.itertuples():
            response = requests.get(
                "https://api.collegefootballdata.com/lines",
                params={"year": 2026, "gameId": int(game.game_id)},
                headers={"Authorization": "Bearer " + os.environ["CFBD_API_KEY"]},
                timeout=60,
            )
            response.raise_for_status()
            current = response.json()
            if not current or any(
                g.get("homeScore") is None or g.get("awayScore") is None
                for g in current
            ):
                raise ValueError("sample must contain completed games")
            requests_evidence.append(
                {"game_id": int(game.game_id), "response_sha256": sha(response.content)}
            )
            rows.extend(
                compare_lines(stored[stored.game_id.eq(game.game_id)], current, slate)
            )
    passed = (
        bool(rows)
        and all(row["matches"] for row in rows)
        and {row["game_id"] for row in rows}
        == {item["game_id"] for item in requests_evidence}
    )
    receipt = signed_payload(
        {
            "schema_version": "cfbd_closing_line_comparison_v1",
            "state": "passed" if passed else "failed",
            "season": 2026,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "source_lock_sha256": sha(raw),
            "requests": requests_evidence,
            "comparisons": rows,
            "matched": sum(row["matches"] for row in rows),
            "checked": len(rows),
            "objects": {uri: sha(value) for uri, value in storage.raw.items()},
            "limits": [
                "A finite sample supports an assumption; it cannot prove feed behavior.",
                "A difference may reflect legitimate pregame movement after our capture; it does not prove in-game movement. No exception is enabled on a failed comparison.",
            ],
        }
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as out:
        out.write(canonical_json(receipt))
    print(json.dumps({key: receipt[key] for key in ("state", "matched", "checked")}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
