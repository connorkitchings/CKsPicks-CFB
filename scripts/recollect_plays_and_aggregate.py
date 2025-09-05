#!/usr/bin/env python3
"""Re-collect plays (and required dependencies) across seasons and run aggregations.

Usage examples:

  # Default years (2014-2019, 2021-2024), regular season, quiet aggregation
  ./.venv/bin/python scripts/recollect_plays_and_aggregate.py --data-root "/Volumes/CK SSD/Coding Projects/cfb_model" --quiet

  # Custom years
  ./.venv/bin/python scripts/recollect_plays_and_aggregate.py --years 2015,2016,2021 --data-root /path --quiet

Notes:
- This script ensures teams, venues, and games are present before collecting plays.
- Aggregations are run per-season after plays ingest.
"""
from __future__ import annotations

import argparse
import subprocess
import sys


def _parse_years(years_arg: str | None) -> list[int]:
    if not years_arg:
        # Default per project rules: 2014–2019, 2021–2024
        return [2014, 2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024]
    years: list[int] = []
    for part in years_arg.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            years.extend(range(int(a), int(b) + 1))
        else:
            years.append(int(part))
    # Always remove 2020 if user accidentally includes it
    years = [y for y in years if y != 2020]
    # Deduplicate while preserving order
    seen: set[int] = set()
    out: list[int] = []
    for y in years:
        if y not in seen:
            seen.add(y)
            out.append(y)
    return out


def _run(cmd: list[str]) -> None:
    print("\n$", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Recollect plays and run pre-aggregations per season")
    parser.add_argument("--years", type=str, default=None, help="Comma list and/or ranges, e.g. 2014-2019,2021-2024")
    parser.add_argument("--data-root", type=str, default=None, help="Absolute data root path (external drive)")
    parser.add_argument("--season-type", type=str, default="regular", choices=["regular", "postseason"], help="Season type")
    parser.add_argument("--quiet", action="store_true", help="Suppress per-game aggregation logs")
    args = parser.parse_args()

    years = _parse_years(args.years)
    py = sys.executable

    for year in years:
        print(f"\n=== Year {year} ===")
        # Ensure dependencies
        _run([py, "scripts/ingest_cli.py", "teams", "--year", str(year)] + (["--data-root", args.data_root] if args.data_root else []))
        _run([py, "scripts/ingest_cli.py", "venues", "--year", str(year)] + (["--data-root", args.data_root] if args.data_root else []))
        _run([py, "scripts/ingest_cli.py", "games", "--year", str(year), "--season-type", args.season_type] + (["--data-root", args.data_root] if args.data_root else []))
        # Plays re-collection (full season)
        _run([py, "scripts/ingest_cli.py", "plays", "--year", str(year), "--season-type", args.season_type] + (["--data-root", args.data_root] if args.data_root else []))
        # Aggregations
        agg_cmd = [py, "scripts/aggregations_cli.py", "preagg", "--year", str(year)]
        if args.quiet:
            agg_cmd.append("--quiet")
        _run(agg_cmd)

    print("\n✅ Recollection and aggregation complete.")


if __name__ == "__main__":
    main()

