#!/usr/bin/env python3
"""Window 2 Step 5A: upload the retained CFBD drive responses to Preview R2, immutably.

Copies each raw response byte for byte to ``raw/cfbd/drives/<file>`` plus a checksum
manifest (``raw/cfbd/drives/manifest.jsonl``, the same lines the fetcher wrote). An object
that already exists is never overwritten: identical bytes are skipped, different bytes stop
the run. Every uploaded object is read back and hash-checked. Without ``--apply`` it only
reports what it would do and writes nothing.

    PYTHONPATH=src:. uv run python scripts/data/upload_cfbd_drives_5a.py \\
        --source-dir artifacts/research/window2_5a_cfbd_drives [--apply]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from cks_picks_cfb.data.storage import get_storage

PREFIX = "raw/cfbd/drives"


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    manifest_path = args.source_dir / "manifest.jsonl"
    records = [
        json.loads(line)
        for line in manifest_path.read_text().splitlines()
        if line.strip()
    ]
    storage = get_storage(environment="preview")
    plan = {"write": [], "identical": [], "conflict": []}
    for record in records:
        local = (args.source_dir / "raw" / record["file"]).read_bytes()
        if hashlib.sha256(local).hexdigest() != record["sha256"]:
            raise SystemExit(
                f"{record['file']}: local bytes differ from the manifest hash"
            )
        uri = f"{PREFIX}/{record['file']}"
        if storage.exists(uri):
            same = (
                hashlib.sha256(storage.read_bytes(uri)).hexdigest() == record["sha256"]
            )
            plan["identical" if same else "conflict"].append(uri)
        else:
            plan["write"].append(uri)
    manifest_uri = f"{PREFIX}/manifest.jsonl"
    manifest_bytes = manifest_path.read_bytes()
    manifest_state = "write"
    if storage.exists(manifest_uri):
        manifest_state = (
            "identical"
            if storage.read_bytes(manifest_uri) == manifest_bytes
            else "conflict"
        )
    summary = {k: len(v) for k, v in plan.items()} | {
        "manifest": manifest_state,
        "apply": args.apply,
    }
    print(json.dumps(summary, sort_keys=True))
    if plan["conflict"] or manifest_state == "conflict":
        raise SystemExit(
            "an existing object differs from the retained bytes; refusing to overwrite"
        )
    if not args.apply:
        return 0
    for record in records:
        uri = f"{PREFIX}/{record['file']}"
        if uri in plan["write"]:
            storage.write_bytes(
                (args.source_dir / "raw" / record["file"]).read_bytes(), uri
            )
        if hashlib.sha256(storage.read_bytes(uri)).hexdigest() != record["sha256"]:
            raise SystemExit(f"{uri}: read-back hash differs after upload")
    if manifest_state == "write":
        storage.write_bytes(manifest_bytes, manifest_uri)
    if storage.read_bytes(manifest_uri) != manifest_bytes:
        raise SystemExit("manifest read-back differs after upload")
    print(
        json.dumps(
            {"uploaded": len(plan["write"]), "verified": len(records), "prefix": PREFIX}
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
