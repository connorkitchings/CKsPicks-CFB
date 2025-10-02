#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List

from cfb_model.data.storage.local_storage import LocalStorage
from cfb_model.data.validation import validate_adjusted_consistency


def validate_adjusted(data_root: str, years: List[int]) -> Dict[int, Dict[str, Any]]:
    summary: Dict[int, Dict[str, Any]] = {}
    for year in years:
        proc = LocalStorage(
            data_root=data_root, file_format="csv", data_type="processed"
        )
        issues = validate_adjusted_consistency(proc, year)
        errs = [i for i in issues if i.level == "ERROR"]
        warns = [i for i in issues if i.level == "WARN"]
        info = [i for i in issues if i.level == "INFO"]
        summary[year] = {
            "errors": len(errs),
            "warnings": len(warns),
            "info": len(info),
        }
    return summary


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--data-root", required=True)
    p.add_argument(
        "--years",
        type=str,
        default="2014,2015,2016,2017,2018,2019,2021,2022,2023,2024",
        help="Comma-separated list of seasons",
    )
    args = p.parse_args()
    years = [int(y.strip()) for y in args.years.split(",") if y.strip()]
    res = validate_adjusted(args.data_root, years)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
