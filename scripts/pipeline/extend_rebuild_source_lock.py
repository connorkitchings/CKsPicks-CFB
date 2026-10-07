#!/usr/bin/env python3
"""Extend the pinned 2026 rebuild source lock by one completed week.

Read-only against Preview R2; the extended lock is written to ``--out`` only. The base lock
is verified against its pinned SHA-256, the new finals come from a Silver ``game_outcomes``
dataset named by a pipeline ref file, and nothing already recorded may change (see
``cks_picks_cfb.rebuild.lock_extension``).

    PYTHONPATH=src:. uv run python scripts/pipeline/extend_rebuild_source_lock.py \\
        --outcomes-ref-uri artifacts/preview/pipeline-runs/<run>/game_outcomes_ref.json \\
        --new-cutoff 2026-10-05T00:00:00Z --out conf/rebuild/source_lock_2026_w5_v1.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from cks_picks_cfb.data.lake import DatasetRef, read_dataset  # noqa: E402
from cks_picks_cfb.data.storage import get_storage  # noqa: E402
from cks_picks_cfb.rebuild.lock_extension import extend_lock  # noqa: E402

BASE_LOCK = REPO_ROOT / "docs/plans/2026-09-29/v5-repair-2026-source-lock.json"
BASE_SHA256 = "eaecabecfd85f463f76858feda46fb8a927b4a7d534be856155b21ccec919227"


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-lock", type=Path, default=BASE_LOCK)
    parser.add_argument("--base-sha256", default=BASE_SHA256)
    parser.add_argument("--outcomes-ref-uri", required=True)
    parser.add_argument("--new-cutoff", required=True)
    parser.add_argument(
        "--games-ref-uri",
        help="games_ref.json of the new Silver games; every locked kickoff is checked",
    )
    parser.add_argument(
        "--accept-kickoff-revision",
        type=int,
        action="append",
        default=[],
        help="game id whose provider-revised kickoff is recorded in the lock",
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if REPO_ROOT / "data" in [args.out.resolve(), *args.out.resolve().parents]:
        raise SystemExit("output cannot be the repository ./data directory")

    raw = args.base_lock.read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.base_sha256:
        raise SystemExit("base lock does not match its pinned SHA-256")
    storage = get_storage(environment="preview")
    ref = DatasetRef(**json.loads(storage.read_bytes(args.outcomes_ref_uri)))
    if ref.dataset != "game_outcomes":
        raise SystemExit(f"ref names {ref.dataset}, expected game_outcomes")
    outcomes = read_dataset(storage, ref)
    finals = outcomes[
        (outcomes["season"].astype(int) == 2026) & outcomes["completed"].astype(bool)
    ]
    schedule = schedule_ref = None
    if args.games_ref_uri:
        games_ref = DatasetRef(**json.loads(storage.read_bytes(args.games_ref_uri)))
        if games_ref.dataset != "games":
            raise SystemExit(f"ref names {games_ref.dataset}, expected games")
        schedule = read_dataset(storage, games_ref)
        schedule_ref = {
            "dataset": games_ref.dataset,
            "version_id": games_ref.version_id,
            "content_sha": games_ref.content_sha,
            "uri": games_ref.uri,
        }
    elif args.accept_kickoff_revision:
        raise SystemExit("--accept-kickoff-revision needs --games-ref-uri")
    lock = extend_lock(
        json.loads(raw),
        base_sha256=args.base_sha256,
        finals=finals,
        new_cutoff=args.new_cutoff,
        outcomes_ref={
            "dataset": ref.dataset,
            "version_id": ref.version_id,
            "content_sha": ref.content_sha,
            "uri": ref.uri,
        },
        schedule=schedule,
        schedule_ref=schedule_ref,
        accepted_kickoff_revisions=args.accept_kickoff_revision,
    )
    args.out.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")
    print(json.dumps(lock["extends"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
