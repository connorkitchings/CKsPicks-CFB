#!/usr/bin/env python3
"""Independently verify corrected team-statistics release payloads and write the receipt.

Read-only. Inputs are the local before/after payload files written by
``build_corrected_publication_payloads.py`` and (for the recompute check) the published 6A
run in Preview R2. The receipt it writes is the ``v5_team_stats_release_verification_v1``
document the v2 release controller requires; it binds changed ``source_versions`` with the
digests the controller recomputes (Contract 04, Amendment 6).

Checks:

* payload signatures and raw hashes, schema, and the structural contract;
* identical complete key sets (never a silent delete or insert);
* value changes only in the EPA/PPA family that nullable PPA affects; every other metric is
  value-identical to the "before" rows;
* an independent recompute of three drive metrics from raw plays for sampled teams, using
  ``scripts/analysis/handcheck_team_stats.py`` (it does not call the statistics builder).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload  # noqa: E402
from cks_picks_cfb.data.storage import get_storage  # noqa: E402
from cks_picks_cfb.rebuild import release_payloads as rp  # noqa: E402
from cks_picks_cfb.rebuild.published_diff import MISSING_PPA  # noqa: E402
from scripts.analysis.handcheck_team_stats import build_drives, compare  # noqa: E402
from scripts.pipeline.build_corrected_publication_payloads import (  # noqa: E402
    SEASON,
    open_published_run,
)

DEFAULT_TEAMS = ("Michigan", "Oklahoma", "Vanderbilt", "Auburn")


def load_payload(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    payload = json.loads(raw)
    verify_signed_payload(payload, label=path.name)
    if payload.get("schema_version") != rp.PAYLOAD_SCHEMA:
        raise SystemExit(
            f"{path.name}: unexpected schema {payload.get('schema_version')}"
        )
    digest = hashlib.sha256(raw).hexdigest()
    if rp.payload_bytes(payload)[1] != digest:
        raise SystemExit(f"{path.name}: file is not in canonical form")
    return payload, digest


def change_gate(before_rows: list[dict], after_rows: list[dict]) -> dict[str, Any]:
    comparison = rp.compare_stats(before_rows, after_rows)
    unexpected = sorted(set(comparison["value_changed"]) - MISSING_PPA)
    return {
        "passed": comparison["same_key_set"] and not unexpected,
        "allowed_value_change_metrics": sorted(MISSING_PPA),
        "value_changed": comparison["value_changed"],
        "unexpected_value_changes": unexpected,
    }


def handcheck(
    after_rows: list[dict], teams: tuple[str, ...], as_of_week: int
) -> dict[str, Any]:
    storage = get_storage(environment="preview")
    run = open_published_run(storage)
    plays = run.dataset_frames("byplay", season_scope="2026")[SEASON]
    plays = plays[(plays["season"] == SEASON) & (plays["week"] < as_of_week)]
    published = pd.DataFrame(
        [r for r in after_rows if r["as_of_week"] == as_of_week],
        columns=list(rp.STAT_COLUMNS),
    )
    results = compare(build_drives(plays), published, list(teams), 1e-4)
    failed = [r for r in results if not r.ok]
    return {
        "passed": bool(results) and not failed,
        "teams": list(teams),
        "as_of_week": as_of_week,
        "compared": len(results),
        "differences": [
            {
                "team": r.team,
                "role": r.role,
                "metric": r.metric,
                "recomputed": r.recomputed,
                "published": r.published,
            }
            for r in failed
        ],
    }


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--decision-ref", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--teams", nargs="+", default=list(DEFAULT_TEAMS))
    parser.add_argument("--as-of-week", type=int, default=5)
    args = parser.parse_args()

    before, before_sha = load_payload(args.before)
    after, after_sha = load_payload(args.after)
    if before["scope"] != after["scope"]:
        raise SystemExit("before and after scopes differ")
    before_rows, after_rows = before["rows"], after["rows"]
    checks = {
        "structure": {
            "passed": not rp.structural_problems(before_rows)
            and not rp.structural_problems(after_rows),
        },
        "expected_change_buckets": change_gate(before_rows, after_rows),
        "independent_drive_metric_recompute": handcheck(
            after_rows, tuple(args.teams), args.as_of_week
        ),
    }
    receipt = rp.verification_receipt(
        before_sha256=before_sha,
        after_sha256=after_sha,
        before_rows=before_rows,
        after_rows=after_rows,
        decision_ref=args.decision_ref,
        checks=checks,
    )
    raw, digest = rp.payload_bytes(receipt)
    args.out.write_bytes(raw)
    print(
        json.dumps(
            {
                "state": receipt["state"],
                "receipt_raw_sha256": digest,
                "failed_checks": receipt["failed_checks"],
                "problems": receipt["problems"],
                "comparison": receipt["comparison"],
                "provenance_change": receipt.get("provenance_change"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if receipt["state"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
