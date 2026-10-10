#!/usr/bin/env python3
"""Lock the market sources of an unserved week and list its verified quote gaps.

The corrected replay of a week that was never served as a real run (Week 6: only the
display-only run existed) has no original market snapshots to pin. This reads the Silver
games, market snapshots and market quotes the operator names, classifies every game and
target (see ``cks_picks_cfb.rebuild.market_sources_lock``) and writes the reconstruction
source refs extended by that week. A game whose only quotes were captured at or after
kickoff is recorded as a verified gap: no selection, no grade.

Read-only against Preview R2; nothing is written except ``--out`` and ``--report``::

    PYTHONPATH=src:. uv run python scripts/pipeline/build_week_market_sources_lock.py \\
        --week 6 --as-of 2026-10-08T16:20:00Z \\
        --games-ref-uri artifacts/preview/pipeline-runs/<run>/games_ref.json \\
        --market-quotes-ref-uri artifacts/preview/pipeline-runs/<run>/market_quotes_ref.json \\
        --market-snapshots-ref-uri artifacts/preview/pipeline-runs/<run>/market_snapshots_ref.json \\
        --source-manifest artifacts/preview/predictions/year=2026/week=6/run_id=<d2>/manifest.json \\
        --cutoff-source <serving manifest path> --expected-games 58 \\
        --out conf/rebuild/6b_source_refs_w6_v1.json --report <coverage report.json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from cks_picks_cfb.data.lake import DatasetRef, read_dataset  # noqa: E402
from cks_picks_cfb.data.storage import get_storage  # noqa: E402
from cks_picks_cfb.rebuild import market_sources_lock as lock  # noqa: E402

REF_KEYS = (
    "content_sha",
    "dataset",
    "entity",
    "schema_version",
    "uri",
    "version_id",
    "year",
)
BASE_REFS = REPO_ROOT / "conf/rebuild/6b_source_refs_w5_v1.json"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _load(storage: Any, ref_uri: str, dataset: str):
    ref = json.loads(storage.read_bytes(ref_uri))
    if ref.get("dataset") != dataset:
        raise SystemExit(f"{ref_uri} is not a Silver {dataset} DatasetRef")
    frame = read_dataset(
        storage,
        DatasetRef(
            **{
                key: ref[key]
                for key in (
                    "dataset",
                    "version_id",
                    "schema_version",
                    "content_sha",
                    "uri",
                )
            }
        ),
    )
    return frame, {key: ref[key] for key in REF_KEYS if key in ref}


def _object_ref(storage: Any, uri: str) -> dict[str, str]:
    return {"uri": uri, "sha256": _sha(storage.read_bytes(uri))}


def week_schedule(games, *, week: int, expected: int | None):
    """The week's FBS-versus-FBS games with a ``kickoff_utc`` column."""
    frame = games.copy()
    if "season" in frame.columns:
        frame = frame[frame["season"].eq(2026)]
    frame = frame[frame["week"].eq(week)]
    for column in ("home_classification", "away_classification"):
        if column in frame.columns:
            frame = frame[frame[column].eq("fbs")]
    if "kickoff_utc" not in frame.columns:
        if "start_date" not in frame.columns:
            raise SystemExit("games dataset has no kickoff_utc or start_date column")
        frame = frame.assign(kickoff_utc=frame["start_date"])
    frame = frame[["game_id", "kickoff_utc"]].reset_index(drop=True)
    if expected is not None and len(frame) != expected:
        raise SystemExit(f"week {week} has {len(frame)} games, expected {expected}")
    return frame


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--accepted-late-quotes", type=Path, help="JSON exact quote declarations"
    )
    parser.add_argument("--cfbd-comparison-receipt", type=Path)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--as-of", required=True, help="forecast cutoff, ISO UTC")
    parser.add_argument("--games-ref-uri", required=True)
    parser.add_argument("--market-quotes-ref-uri", required=True)
    parser.add_argument("--market-snapshots-ref-uri", required=True)
    parser.add_argument("--source-manifest", required=True, help="run manifest path")
    parser.add_argument("--cutoff-source", required=True, help="serving manifest path")
    parser.add_argument("--expected-games", type=int)
    parser.add_argument("--base-refs", type=Path, default=BASE_REFS)
    parser.add_argument(
        "--environment", choices=("preview", "production"), default="preview"
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.out, args.report):
        if REPO_ROOT / "data" in [path.resolve(), *path.resolve().parents]:
            raise SystemExit("output cannot be the repository ./data directory")

    storage = get_storage(environment=args.environment)
    games, games_ref = _load(storage, args.games_ref_uri, "games")
    quotes, quotes_ref = _load(storage, args.market_quotes_ref_uri, "market_quotes")
    snapshots, snapshots_ref = _load(
        storage, args.market_snapshots_ref_uri, "market_snapshots"
    )
    schedule = week_schedule(games, week=args.week, expected=args.expected_games)
    snapshots = snapshots[snapshots["game_id"].isin(schedule["game_id"])]
    declarations = (
        json.loads(args.accepted_late_quotes.read_bytes())
        if args.accepted_late_quotes
        else []
    )
    comparison = (
        json.loads(args.cfbd_comparison_receipt.read_bytes())
        if args.cfbd_comparison_receipt
        else None
    )
    rows = lock.classify_week_markets(
        snapshots,
        quotes,
        schedule,
        as_of=args.as_of,
        accepted_late_quotes=declarations,
        cfbd_comparison_receipt=comparison,
    )
    entry = lock.week_entry(
        as_of=args.as_of,
        cutoff_source=_object_ref(storage, args.cutoff_source),
        source_manifest=_object_ref(storage, args.source_manifest),
        games=games_ref,
        market_quotes=quotes_ref,
        market_snapshots=snapshots_ref,
        rows=rows,
        accepted_late_quotes=declarations,
        cfbd_comparison_receipt=comparison,
        week=args.week,
    )
    base_raw = args.base_refs.read_bytes()
    refs = lock.extend_source_refs(json.loads(base_raw), week=args.week, entry=entry)
    refs["extends"] = {
        "base_refs": str(args.base_refs.relative_to(REPO_ROOT)),
        "base_refs_sha256": _sha(base_raw),
        "added_week": args.week,
    }
    args.out.write_text(json.dumps(refs, indent=2, sort_keys=True) + "\n")
    report = {
        "schema_version": lock.SCHEMA,
        "week": args.week,
        "as_of": args.as_of,
        "coverage": entry["market_coverage"],
        "rows": rows,
    }
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "out": str(args.out),
                "out_sha256": _sha(args.out.read_bytes()),
                "coverage": entry["market_coverage"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
