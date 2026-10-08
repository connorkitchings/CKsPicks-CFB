#!/usr/bin/env python3
"""Derive the corrected successor source lock from the rebuild-extended lock (local output).

    PYTHONPATH=src:. uv run python scripts/pipeline/build_corrected_successor_lock.py \\
        --out conf/rebuild/successor_lock_w5_v1.json

Defaults describe the Week 5 corrected rebuild; every pin is checked against the file or
constant it names before it is written into the lock.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from cks_picks_cfb.rebuild.successor_lock import derive_successor_lock  # noqa: E402

CONF = REPO_ROOT / "conf" / "rebuild"
SERVED = {
    **{week: f"2026w{week}-v5repair-20260929-p1" for week in range(5)},
    5: "2026w5-v5repair-20260929-p2",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-lock", type=Path, default=CONF / "source_lock_2026_w5_v1.json"
    )
    parser.add_argument("--refs", type=Path, default=CONF / "6b_source_refs_w5_v1.json")
    parser.add_argument(
        "--parents", type=Path, default=CONF / "silver_2026_parents_w5_v1.json"
    )
    parser.add_argument("--bundle", type=Path, default=CONF / "bundle_b2_w5_v1.json")
    parser.add_argument("--rebuild-run-id", default="6a-rebuild-w5-20261007-r2")
    parser.add_argument(
        "--rebuild-root-sha256",
        default="7865d35336b039f8983ee235c6855d2795a9b35233a779a7a67a959aee89d9b0",
    )
    parser.add_argument("--task4-run-id", default="6a-task4-w5-r2")
    parser.add_argument(
        "--task4-root-sha256",
        default="3681c884952059bd14bd59c97b11b5afe35f4dbbdc2a7facf9379237e2a2c063",
    )
    parser.add_argument(
        "--task4-receipt-sha256",
        default="1cd439defb14b886a3850102e0ad8ef44691a51287885dbc46e748e6d00ea3e3",
    )
    parser.add_argument(
        "--week5-config",
        type=Path,
        default=REPO_ROOT / "conf/weekly_bets/v5_intended_update_2026.yaml",
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if REPO_ROOT / "data" in [args.out.resolve(), *args.out.resolve().parents]:
        raise SystemExit("output cannot be the repository ./data directory")

    base = json.loads(args.base_lock.read_text())
    refs = json.loads(args.refs.read_text())
    games_ref = next(
        p
        for p in json.loads(args.parents.read_text())["parents"]
        if p["dataset"] == "games"
    )
    config = args.week5_config
    lock = derive_successor_lock(
        base,
        refs=refs,
        served_runs={week: {"run_id": run} for week, run in SERVED.items()},
        week_configs={
            week: {
                "path": str(config.relative_to(REPO_ROOT)),
                "sha256": _sha(config),
            }
            for week in range(6)
        },
        lineage={
            "kind": "corrected_rebuild",
            "rebuild_run_id": args.rebuild_run_id,
            "rebuild_root_raw_sha256": args.rebuild_root_sha256,
            "task4_run_id": args.task4_run_id,
            "task4_root_raw_sha256": args.task4_root_sha256,
            "task4_receipt_raw_sha256": args.task4_receipt_sha256,
            "inference_bundle_raw_sha256": _sha(args.bundle),
            "base_lock_sha256": hashlib.sha256(args.base_lock.read_bytes()).hexdigest(),
            "measurement_parent_sha256": args.rebuild_root_sha256,
            "rating_parent_sha256": args.task4_receipt_sha256,
        },
        schedule_content_sha256=games_ref["content_sha"],
        schedule_uri=games_ref["uri"],
    )
    args.out.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "out": str(args.out),
                "sha256": _sha(args.out),
                "weeks": sorted(lock["market_sources"], key=int),
                "active_week": lock["active_week"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
