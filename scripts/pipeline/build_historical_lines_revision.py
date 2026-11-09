"""Pin explicit CFBD retrospective lines for named games into a revision manifest.

Reads one already-registered CFBD betting-lines capture (never queries a provider),
keeps only the named games, tags every row ``source_provider = cfbd`` and registers
the rows as a new immutable ``market_quotes`` Silver version. The new manifest equals
its base except for the revision id and the ``historical_lines`` input, so the games
are graded ``cfbd_retrospective``: recorded separately from retained pre-kickoff
captures and never evidence of a pre-kickoff line.

Usage: python -m scripts.pipeline.build_historical_lines_revision \
    --from-manifest <src> --to-manifest <dst> --revision-id <id> \
    --capture-id <registered cfbd betting_lines capture> --game-id <id> [--game-id ...] \
    --target-week <N>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

from cks_picks_cfb.data.catalog import register_dataset_version, source_capture_by_id
from cks_picks_cfb.data.silver import build_silver_version
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.season.inputs import frame
from scripts.pipeline.build_market_revision import derive_manifest
from scripts.pipeline.build_week_market_snapshot import capture_records

SOURCE_PROVIDER = "cfbd"
CONFIG = b"season-historical-lines:cfbd_retrospective_v1"


def select_rows(records: list[dict], game_ids: set[int], capture_id: str) -> list[dict]:
    """The named games' rows, CFBD-tagged; refuses a game the capture lacks."""
    rows = [
        {**row, "source_provider": SOURCE_PROVIDER}
        for row in records
        if int(row["game_id"]) in game_ids
    ]
    if missing := game_ids - {int(row["game_id"]) for row in rows}:
        raise ValueError(
            f"capture {capture_id} has no lines for games {sorted(missing)}"
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-manifest", type=Path, required=True)
    parser.add_argument("--to-manifest", type=Path, required=True)
    parser.add_argument("--revision-id", required=True)
    parser.add_argument("--capture-id", required=True)
    parser.add_argument("--game-id", type=int, action="append", required=True)
    parser.add_argument("--target-week", type=int, required=True)
    parser.add_argument("--environment", default="preview")
    args = parser.parse_args(argv)

    if args.to_manifest.exists():
        raise SystemExit(f"Refusing to overwrite {args.to_manifest}")
    database_url = os.environ["DATABASE_URL"]
    old = json.loads(args.from_manifest.read_text())

    capture = source_capture_by_id(database_url, args.capture_id)
    if (capture.provider, capture.entity, capture.state) != (
        "cfbd",
        "betting_lines",
        "registered",
    ):
        raise SystemExit(
            f"{args.capture_id} is not a registered CFBD betting-lines capture"
        )

    store = get_storage(environment=args.environment)
    games = frame(store, old["inputs"]["schedule"])
    try:
        rows = select_rows(
            capture_records(store, [capture]), set(args.game_id), args.capture_id
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    code_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    ref, manifest = build_silver_version(
        store,
        dataset="market_quotes",
        records=rows,
        source_captures=[capture],
        as_of=capture.captured_at,
        code_sha=code_sha,
        config_sha=hashlib.sha256(CONFIG).hexdigest(),
        context={"games": games},
    )
    # The base manifest's own captured_at and cutoff already bound every football
    # and live-week input, and the capture predates them, so both stay as they are.
    new = derive_manifest(
        old,
        revision_id=args.revision_id,
        historical_lines={"uri": ref.uri, "sha256": ref.content_sha},
        captured_at=old["captured_at"],
        target_week=str(args.target_week),
        cutoff=old["pre_week_cutoffs"][str(args.target_week)],
    )
    register_dataset_version(database_url, ref, manifest)
    args.to_manifest.write_text(json.dumps(new, indent=2) + "\n")
    print(
        f"Wrote {args.to_manifest}: only the revision id and historical_lines "
        f"({len(rows)} rows, games {sorted(args.game_id)}) changed. No provider calls."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
