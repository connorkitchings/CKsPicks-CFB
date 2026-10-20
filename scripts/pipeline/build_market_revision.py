"""Build a market-only revision manifest from a certified source manifest.

Mid-week line refresh: reuses every certified football input, completed-week
cutoff and score exception, and replaces only the cumulative market quotes, the
target-week pre-week cutoff and the revision identity. Never queries a provider;
it reads captures already stored in the database.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from cks_picks_cfb.data.catalog import register_dataset_version
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.season.inputs import frame
from cks_picks_cfb.season.manifest import validate_revision
from scripts.pipeline.build_season_revision import (
    build_market_quotes,
    season_market_capture_ids,
)
from scripts.pipeline.build_week_market_snapshot import market_captures

SEASON = 2026
TARGET_WEEK = 8
EXPECTED_TARGET_GAMES = 56


def parse_cutoff(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("--cutoff must include a timezone, e.g. 2026-10-20T16:00:00Z")
    return parsed


def derive_manifest(
    old: dict[str, Any],
    *,
    revision_id: str,
    quotes_input: dict[str, str],
    captured_at: str,
    target_week: str,
    cutoff: str,
) -> dict[str, Any]:
    """Return ``old`` with only market identity changed; assert nothing else moved."""
    new = copy.deepcopy(old)
    new["revision_id"] = revision_id
    new["inputs"]["market_quotes"] = quotes_input
    new["captured_at"] = captured_at
    new["pre_week_cutoffs"][target_week] = cutoff

    def without(mapping: dict[str, Any], key: str) -> dict[str, Any]:
        return {k: v for k, v in mapping.items() if k != key}

    if without(new["inputs"], "market_quotes") != without(
        old["inputs"], "market_quotes"
    ):
        raise ValueError("football inputs differ from the source manifest")
    if new["post_week_cutoffs"] != old["post_week_cutoffs"]:
        raise ValueError("post-week cutoffs differ from the source manifest")
    if new["score_reconciliation_exceptions"] != old["score_reconciliation_exceptions"]:
        raise ValueError("score exceptions differ from the source manifest")
    if without(new["pre_week_cutoffs"], target_week) != without(
        old["pre_week_cutoffs"], target_week
    ):
        raise ValueError(
            "earlier-week pre-week cutoffs differ from the source manifest"
        )
    validate_revision(new)
    return new


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-manifest", type=Path, required=True)
    parser.add_argument("--to-manifest", type=Path, required=True)
    parser.add_argument("--revision-id", required=True)
    parser.add_argument(
        "--cutoff", required=True, help="ISO-8601 UTC, last capture + ~5 min"
    )
    parser.add_argument("--environment", default="preview")
    args = parser.parse_args(argv)

    if args.to_manifest.exists():
        raise SystemExit(f"Refusing to overwrite {args.to_manifest}")
    cutoff = parse_cutoff(args.cutoff)
    database_url = os.environ["DATABASE_URL"]
    old = json.loads(args.from_manifest.read_text())

    store = get_storage(environment=args.environment)
    games = frame(store, old["inputs"]["schedule"])
    if len(games.loc[(games.season == SEASON) & (games.week == TARGET_WEEK)]) != (
        EXPECTED_TARGET_GAMES
    ):
        raise SystemExit(
            f"Week {TARGET_WEEK} schedule is not {EXPECTED_TARGET_GAMES} games"
        )

    captures = market_captures(
        database_url, season_market_capture_ids(database_url, SEASON, cutoff)
    )
    last_capture = max(x.captured_at for x in captures)
    if last_capture > cutoff:
        raise SystemExit("A capture is later than --cutoff")
    code_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    ref, quotes_manifest = build_market_quotes(
        store, store, captures=captures, games=games, code_sha=code_sha
    )
    new = derive_manifest(
        old,
        revision_id=args.revision_id,
        quotes_input={"uri": ref.uri, "sha256": ref.content_sha},
        captured_at=last_capture.isoformat().replace("+00:00", "Z"),
        target_week=str(TARGET_WEEK),
        cutoff=cutoff.isoformat().replace("+00:00", "Z"),
    )
    register_dataset_version(database_url, ref, quotes_manifest)
    args.to_manifest.write_text(json.dumps(new, indent=2) + "\n")
    print(
        f"Wrote {args.to_manifest}: only quotes, Week {TARGET_WEEK} cutoff and revision "
        "identity changed. No provider calls."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
