"""Build a market-only revision manifest from a certified source manifest.

Mid-week line refresh: reuses every certified football input, completed-week
cutoff and score exception, and replaces only the cumulative market quotes, the
target-week pre-week cutoff and the revision identity. Never queries a provider;
it reads captures already stored in the database.

Usage: python -m scripts.pipeline.build_market_revision --from-manifest <src> \
    --to-manifest <dst> --revision-id <id> --cutoff <ISO-8601 UTC> --target-week <N>

``--target-week`` must be the upcoming (highest) week in the source manifest.
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


def parse_cutoff(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("--cutoff must include a timezone, e.g. 2026-10-20T16:00:00Z")
    return parsed


def check_target(old: dict[str, Any], target_week: str, cutoff: str) -> None:
    """Refuse a target week that is not the upcoming one or a cutoff moved back."""
    cutoffs = old["pre_week_cutoffs"]
    if target_week not in cutoffs:
        raise ValueError(f"Week {target_week} is not in the source pre_week_cutoffs")
    upcoming = max(cutoffs, key=int)
    if target_week != upcoming:
        raise ValueError(
            f"--target-week {target_week} is not the source manifest's upcoming "
            f"week {upcoming}; a refresh may only move the upcoming week's cutoff"
        )
    if parse_cutoff(cutoff) < parse_cutoff(cutoffs[target_week]):
        raise ValueError(
            f"Week {target_week} cutoff {cutoff} is earlier than the source "
            f"manifest's {cutoffs[target_week]}; a refresh never moves it back"
        )


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
    check_target(old, target_week, cutoff)
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
    parser.add_argument(
        "--target-week",
        type=int,
        required=True,
        help="Upcoming week being refreshed; must be the highest week in the source",
    )
    parser.add_argument("--environment", default="preview")
    args = parser.parse_args(argv)

    if args.to_manifest.exists():
        raise SystemExit(f"Refusing to overwrite {args.to_manifest}")
    cutoff = parse_cutoff(args.cutoff)
    database_url = os.environ["DATABASE_URL"]
    old = json.loads(args.from_manifest.read_text())
    try:
        check_target(old, str(args.target_week), args.cutoff)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    store = get_storage(environment=args.environment)
    games = frame(store, old["inputs"]["schedule"])
    target_week = args.target_week
    if games.loc[(games.season == SEASON) & (games.week == target_week)].empty:
        raise SystemExit(f"Week {target_week} has no games in the schedule")

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
        target_week=str(target_week),
        cutoff=cutoff.isoformat().replace("+00:00", "Z"),
    )
    register_dataset_version(database_url, ref, quotes_manifest)
    args.to_manifest.write_text(json.dumps(new, indent=2) + "\n")
    print(
        f"Wrote {args.to_manifest}: only quotes, Week {target_week} cutoff and revision "
        "identity changed. No provider calls."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
