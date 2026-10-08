#!/usr/bin/env python3
"""Write the historical input cache the successor bridge builder and verifier accept,
from a published corrected 6A run (hash-checked reads, local output only).

    PYTHONPATH=src:. uv run python scripts/pipeline/write_corrected_historical_cache.py \\
        --run-id 6a-rebuild-w5-20261007-r2 --root-sha256 <raw sha> --out-dir <dir>

Then, for example::

    uv run python scripts/pipeline/build_v5_intended_update_bundle.py \\
        --run-id v5-intended-update-<tag> --expected-code-sha $(git rev-parse HEAD) \\
        --local-output <bridge dir> --historical-cache <dir>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from cks_picks_cfb.data.storage import get_storage  # noqa: E402
from cks_picks_cfb.rebuild.successor_sources import write_historical_cache  # noqa: E402
from scripts.pipeline.build_corrected_publication_payloads import (  # noqa: E402
    open_published_run,
)


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--root-sha256", required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    if REPO_ROOT / "data" in [args.out_dir.resolve(), *args.out_dir.resolve().parents]:
        raise SystemExit("output cannot be the repository ./data directory")
    run = open_published_run(
        get_storage(environment="preview"), args.run_id, args.root_sha256
    )
    print(json.dumps(write_historical_cache(run, args.out_dir), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
