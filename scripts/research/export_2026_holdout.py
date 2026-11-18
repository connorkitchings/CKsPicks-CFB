"""Deterministic, read-only export manifest for the frozen 2026 holdout.

For each 2026 revision manifest the export lists every pinned input (URI and raw
SHA-256), marking the outcomes (finals) and the early-week lines the record uses.
Near-kickoff captures are listed in a separate ``analysis_only`` section and never
appear among a week's inputs. The export is canonical JSON, so two runs over the
same manifests produce identical bytes, and its SHA-256 is printed.

A manifest is rejected when it was captured after its newest pre-week cutoff, or,
when a reader is supplied, when a pinned market-quote row is stamped after the
manifest's own capture time. Run after the 2026-12-13 final close::

    uv run python scripts/research/export_2026_holdout.py --output <path>
"""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path

import pandas as pd

from cks_picks_cfb.season.inputs import read_ref
from cks_picks_cfb.season.manifest import canonical, sha, utc, validate_revision

SEASON_DIR = Path("conf/season/2026")
OUTCOMES = "finals"
EARLY_WEEK_LINES = ("market_quotes", "historical_lines")


def _entry(name: str, ref: dict, role: str) -> dict:
    return {"name": name, "role": role, "sha256": ref["sha256"], "uri": ref["uri"]}


def check_cutoff(revision: dict, reader=None) -> None:
    """Reject a manifest holding any input stamped after its week's cutoff."""
    captured = utc(revision["captured_at"])
    last = max(utc(value) for value in revision["pre_week_cutoffs"].values())
    if captured > last:
        raise ValueError(
            f"{revision['revision_id']} captured after its newest pre-week cutoff"
        )
    if reader is not None and "market_quotes" in revision["inputs"]:
        raw = read_ref(reader, revision["inputs"]["market_quotes"])
        stamps = pd.read_parquet(io.BytesIO(raw), columns=["captured_at"])
        if stamps.captured_at.map(utc).gt(captured).any():
            raise ValueError(f"{revision['revision_id']} holds a quote after capture")


def manifest_section(name: str, raw: bytes, reader=None) -> dict:
    revision = json.loads(raw)
    validate_revision(revision)
    check_cutoff(revision, reader)
    inputs = [
        _entry(
            key,
            ref,
            "outcomes"
            if key == OUTCOMES
            else "early_week_lines"
            if key in EARLY_WEEK_LINES
            else "pre_kickoff_input",
        )
        for key, ref in revision["inputs"].items()
    ]
    if "score_reconciliation_exceptions" in revision:
        inputs.append(
            _entry(
                "score_reconciliation_exceptions",
                revision["score_reconciliation_exceptions"],
                "pre_kickoff_input",
            )
        )
    return {
        "captured_at": revision["captured_at"],
        "inputs": sorted(inputs, key=lambda item: item["name"]),
        "manifest": name,
        "manifest_sha256": sha(raw),
        "pre_week_cutoffs": revision["pre_week_cutoffs"],
        "revision_id": revision["revision_id"],
    }


def build_export(
    manifests: dict[str, bytes],
    model_raw: bytes,
    near_kickoff: list[dict] = (),
    reader=None,
) -> dict:
    model = json.loads(model_raw)
    sections = [manifest_section(n, manifests[n], reader) for n in sorted(manifests)]
    pinned = {item["uri"] for s in sections for item in s["inputs"]}
    for capture in near_kickoff:
        if capture["uri"] in pinned:
            raise ValueError(
                f"near-kickoff capture is a pinned input: {capture['uri']}"
            )
    return {
        "analysis_only": {
            "near_kickoff_captures": sorted(near_kickoff, key=lambda c: c["capture_id"])
        },
        "manifests": sections,
        "model": {
            "inputs": [
                _entry(k, v, "model_input") for k, v in sorted(model["inputs"].items())
            ],
            "manifest_sha256": sha(model_raw),
            "model_id": model["model_id"],
        },
        "schema_version": "holdout_export_v1",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--season-dir", type=Path, default=SEASON_DIR)
    parser.add_argument(
        "--near-kickoff-captures",
        type=Path,
        help="JSON list of {capture_id, uri, sha256, captured_at}; analysis only",
    )
    args = parser.parse_args(argv)
    manifests = {
        p.stem.removeprefix("revision_manifest_"): p.read_bytes()
        for p in args.season_dir.glob("revision_manifest_w*_v*.json")
    }
    near = (
        json.loads(args.near_kickoff_captures.read_bytes())
        if args.near_kickoff_captures
        else []
    )
    export = build_export(
        manifests, (args.season_dir / "model_manifest_v1.json").read_bytes(), near
    )
    raw = canonical(export)
    args.output.write_bytes(raw)
    print(f"{args.output}\nsha256 {sha(raw)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
