"""Pure diff of rebuilt statistics against published rows, with named explanation buckets.

Every differing cell is attributed to a bucket by its metric. Buckets that are *expected*
to differ (missing PPA, punt-return plays) explain a difference; a difference in any other
bucket (scoring, possessions, ratings, anything unknown) is an unexplained finding, and so is
any row present on one side only (a population difference). Nothing is redefined to make
the two sides agree.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

SCORING = {
    "ppp",
    "offensive_possession_points",
    "non_offense_points",
    "non_offense_points_per_game",
    "pts_per_scoring_opp",
}
POSSESSIONS = {"eligible_possessions", "possessions_per_game"}
MISSING_PPA = {
    "epa_per_possession",
    "eligible_epa",
    "epa_per_play",
    "ppa_per_play",
    "epa_pass",
    "epa_rush",
    "early_down_epa",
}
PUNT = {"plays_per_possession", "eligible_scrimmage_plays"}
EXPECTED_TO_DIFFER = {"missing_ppa", "punt"}


def bucket_of(metric: str | None) -> str:
    if metric == "history_correction":
        return "history_correction"
    if metric in MISSING_PPA:
        return "missing_ppa"
    if metric in PUNT:
        return "punt"
    if metric in SCORING:
        return "scoring"
    if metric in POSSESSIONS:
        return "possessions"
    return "ratings" if metric is None else f"other:{metric}"


def _same(
    left: pd.Series, right: pd.Series, *, json_column: bool, tolerance: float
) -> pd.Series:
    if json_column:

        def parse(value: Any) -> Any:
            if value is None or (isinstance(value, float) and np.isnan(value)):
                return None
            return json.loads(value) if isinstance(value, str) else value

        return pd.Series(
            [parse(a) == parse(b) for a, b in zip(left, right, strict=True)],
            index=left.index,
        )
    both_null = left.isna() & right.isna()
    if _datetime_like(left) or _datetime_like(right):
        ta = pd.to_datetime(left, utc=True, errors="coerce")
        tb = pd.to_datetime(right, utc=True, errors="coerce")
        return both_null | (ta == tb)
    a = pd.to_numeric(left, errors="coerce")
    b = pd.to_numeric(right, errors="coerce")
    if a.dtype == bool or b.dtype == bool:  # booleans compare as 0.0 / 1.0
        a, b = a.astype("float64"), b.astype("float64")
    if a.notna().sum() == left.notna().sum() and b.notna().sum() == right.notna().sum():
        close = (a - b).abs() <= tolerance * np.maximum(
            1.0, np.maximum(a.abs(), b.abs())
        )
        return both_null | close.fillna(False)
    return both_null | (left.astype(str) == right.astype(str))


def _datetime_like(series: pd.Series) -> bool:
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    present = series.dropna()
    return len(present) > 0 and isinstance(present.iloc[0], (datetime, pd.Timestamp))


def diff_frames(
    built: pd.DataFrame,
    published: pd.DataFrame,
    *,
    keys: Sequence[str],
    columns: Sequence[str],
    metric_of: Callable[[pd.Series], str | None],
    jsonb: Sequence[str] = (),
    tolerance: float = 1e-9,
    sample: int = 5,
    expected: set[str] | None = None,
    added_scope: Callable[[pd.DataFrame], pd.Series] | None = None,
    bucket_override: Callable[[pd.Series, str], str | None] | None = None,
) -> dict[str, Any]:
    """Compare ``built`` with ``published`` on ``keys``; attribute every difference.

    ``added_scope`` marks built rows that belong to scope added after the published rows
    were written (for example a newly completed week). Those rows are set aside and counted
    under ``added_scope``; a published row inside that scope is itself a finding. Everything
    else is compared as before. ``bucket_override`` may name a bucket for one differing
    cell (given the merged row and the column), for a cause proven independently.
    """
    full_built_rows = int(len(built))
    scope_report: dict[str, Any] | None = None
    scope_finding = False
    if added_scope is not None:
        in_built = added_scope(built).astype(bool)
        in_published = added_scope(published).astype(bool)
        by_metric: Counter = Counter(
            bucket_of(metric_of(row)) for _, row in built[in_built].iterrows()
        )
        scope_report = {
            "rows": int(in_built.sum()),
            "by_bucket": dict(sorted(by_metric.items())),
            "published_rows_in_scope": int(in_published.sum()),
        }
        scope_finding = bool(in_published.any())
        built = built[~in_built]
        published = published[~in_published]
    merged = built[[*keys, *columns]].merge(
        published[[*keys, *columns]],
        on=list(keys),
        how="outer",
        suffixes=("_built", "_pub"),
        indicator=True,
    )
    both = merged[merged["_merge"] == "both"]
    only_built = merged[merged["_merge"] == "left_only"]
    only_pub = merged[merged["_merge"] == "right_only"]
    differing: dict[str, Counter] = {}
    samples: dict[str, list[dict[str, Any]]] = {}
    cells = 0
    bad_rows = pd.Series(False, index=both.index)
    for column in columns:
        same = _same(
            both[f"{column}_built"],
            both[f"{column}_pub"],
            json_column=column in jsonb,
            tolerance=tolerance,
        )
        cells += len(both)
        bad = ~same
        bad_rows |= bad
        for index in both.index[bad]:
            row = both.loc[index]
            bucket = (
                bucket_override(row, column) if bucket_override is not None else None
            ) or bucket_of(metric_of(row))
            differing.setdefault(bucket, Counter())[column] += 1
            records = samples.setdefault(bucket, [])
            if len(records) < sample:
                records.append(
                    {
                        **{k: _plain(row[k]) for k in keys},
                        "column": column,
                        "built": _plain(row[f"{column}_built"]),
                        "published": _plain(row[f"{column}_pub"]),
                    }
                )
    allowed = EXPECTED_TO_DIFFER if expected is None else expected
    by_bucket = {b: dict(c) for b, c in sorted(differing.items())}
    unexplained = {b: c for b, c in by_bucket.items() if b not in allowed}
    population_buckets: dict[str, dict[str, int]] = {
        "only_built": {},
        "only_published": {},
    }
    for label, frame in (("only_built", only_built), ("only_published", only_pub)):
        for _, row in frame.iterrows():
            bucket = bucket_of(metric_of(row))
            population_buckets[label][bucket] = (
                population_buckets[label].get(bucket, 0) + 1
            )
    population = {
        "only_built": int(len(only_built)),
        "only_published": int(len(only_pub)),
        "by_bucket": population_buckets,
        "keys": {
            label: [
                {
                    **{key: _plain(row[key]) for key in keys},
                    "bucket": bucket_of(metric_of(row)),
                }
                for _, row in frame.sort_values(list(keys)).iterrows()
            ]
            for label, frame in (
                ("only_built", only_built),
                ("only_published", only_pub),
            )
        },
    }
    unexplained_population = {
        label: {b: n for b, n in buckets.items() if b not in allowed}
        for label, buckets in population_buckets.items()
    }
    return {
        "rows_built": full_built_rows,
        "rows_published": int(len(published)),
        "rows_compared": int(len(both)),
        "cells_compared": int(cells),
        "rows_with_a_difference": int(bad_rows.sum()),
        "differences_by_bucket": by_bucket,
        "samples": samples,
        "population": population,
        "unexplained_buckets": unexplained,
        "unexplained_population": unexplained_population,
        "unexplained": bool(unexplained)
        or any(unexplained_population.values())
        or scope_finding,
        **({"added_scope": scope_report} if scope_report is not None else {}),
    }


def _plain(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return None if (isinstance(value, float) and np.isnan(value)) else value


def summarize(tables: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    buckets: Counter = Counter()
    for report in tables.values():
        for bucket, columns in report["differences_by_bucket"].items():
            buckets[bucket] += sum(columns.values())
    return {
        "cells_compared": int(sum(t["cells_compared"] for t in tables.values())),
        "differing_cells_by_bucket": dict(sorted(buckets.items())),
        "added_scope_rows": {
            n: t["added_scope"]["rows"] for n, t in tables.items() if "added_scope" in t
        },
        "unexplained_tables": sorted(n for n, t in tables.items() if t["unexplained"]),
        "all_differences_explained": not any(t["unexplained"] for t in tables.values()),
    }
