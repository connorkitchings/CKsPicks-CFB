"""Signed team-statistic release payloads, their structural checks and the verifier receipt.

The v2 release controller validates ``v5_team_stats_release_payload_v1`` payloads and a
``v5_team_stats_release_verification_v1`` receipt but nothing built them. This module is the
pure, I/O-free part of that builder: it turns a frame of statistics into controller-format
rows, signs payloads, compares a before and an after payload, and writes the receipt that
binds changed ``source_versions`` (Contract 04, Amendment 6). Reading the published run and
the database stays in the scripts.
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import pandas as pd

from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.ops.v5_batch_selection_v2 import (
    STAT_COLUMNS,
    STAT_KEY,
    stats_provenance_digest,
)
from cks_picks_cfb.ratings_lab.artifacts import canonical_json

PAYLOAD_SCHEMA = "v5_team_stats_release_payload_v1"
VERIFICATION_SCHEMA = "v5_team_stats_release_verification_v1"
ROLES = ("offense", "defense")
VALUE_TOLERANCE = 1e-9


class PayloadError(ValueError):
    """A release payload cannot be built or is internally inconsistent."""


def _plain(value: Any) -> Any:
    """JSON-safe scalar: NaN/NaT/NA become None, numpy scalars become Python scalars."""
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        value = value.item()
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def row_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return tuple(row[column] for column in STAT_KEY)


def stat_rows(
    frame: pd.DataFrame, source_versions: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Controller-format rows (``STAT_COLUMNS``), sorted by key, with honest provenance."""
    if not source_versions:
        raise PayloadError("source_versions must name the inputs that built the rows")
    rows = []
    for record in frame.to_dict("records"):
        row: dict[str, Any] = {}
        for column in STAT_COLUMNS:
            if column == "source_versions":
                row[column] = dict(source_versions)
            elif column == "season" and column not in record:
                raise PayloadError("statistics frame lacks a season column")
            else:
                row[column] = _plain(record[column])
        for integer in ("season", "as_of_week", "n", "games"):
            row[integer] = int(row[integer])
        for optional in ("rank", "cohort_size"):
            if row[optional] is not None:
                row[optional] = int(row[optional])
        if row["value"] is not None:
            row["value"] = float(row["value"])
        rows.append(row)
    rows.sort(key=row_key)
    return rows


def database_stat_rows(
    cur: Any, scope: Sequence[Mapping[str, int]]
) -> list[dict[str, Any]]:
    """Current database rows for a snapshot scope, in the controller's column order."""
    if not scope:
        raise PayloadError("a snapshot scope is required")
    clauses, params = [], []
    for item in scope:
        clauses.append("(season = %s AND as_of_week = %s)")
        params.extend((item["season"], item["as_of_week"]))
    cur.execute(
        "SELECT season, as_of_week, team, role, metric, value, n, games, rank, "
        "cohort_size, source_versions FROM team_season_stats WHERE "
        + " OR ".join(clauses)
        + " ORDER BY season, as_of_week, team, role, metric",
        tuple(params),
    )
    return [dict(zip(STAT_COLUMNS, row, strict=True)) for row in cur.fetchall()]


def scope_of(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, int]]:
    return [
        {"season": season, "as_of_week": week}
        for season, week in sorted({(r["season"], r["as_of_week"]) for r in rows})
    ]


def structural_problems(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    """Contract checks on the rows themselves; an empty list means they pass."""
    problems: list[str] = []
    seen: set[tuple[Any, ...]] = set()
    for row in rows:
        missing = set(STAT_COLUMNS) - set(row)
        if missing:
            problems.append(f"row lacks columns {sorted(missing)}")
            continue
        key = row_key(row)
        if key in seen:
            problems.append(f"duplicate key {key}")
        seen.add(key)
        if row["role"] not in ROLES:
            problems.append(f"{key}: unknown role {row['role']!r}")
        value = row["value"]
        if value is not None and not math.isfinite(value):
            problems.append(f"{key}: non-finite value")
        if row["n"] < 0 or row["games"] < 0:
            problems.append(f"{key}: negative count")
        rank, cohort = row["rank"], row["cohort_size"]
        if rank is not None and (
            cohort is None or cohort <= 0 or not 1 <= rank <= cohort
        ):
            problems.append(f"{key}: rank {rank} outside cohort {cohort}")
        if value is None and rank is not None:
            problems.append(f"{key}: ranked row has no value")
        versions = row["source_versions"]
        if not isinstance(versions, Mapping) or not versions:
            problems.append(f"{key}: source_versions must be a nonempty mapping")
    return problems


def team_stats_payload(
    rows: Sequence[Mapping[str, Any]],
    *,
    environment: str,
    season: int,
    parents: Mapping[str, Any],
    label: str,
) -> dict[str, Any]:
    """A signed payload in the exact shape ``validate_v2_packet`` reads."""
    if environment not in {"preview", "production"}:
        raise PayloadError("invalid environment")
    problems = structural_problems(rows)
    if problems:
        raise PayloadError("; ".join(problems[:5]))
    return signed_payload(
        {
            "schema_version": PAYLOAD_SCHEMA,
            "environment": environment,
            "season": season,
            "label": label,
            "scope": scope_of(rows),
            "parents": dict(parents),
            "row_count": len(rows),
            "provenance_sha256": stats_provenance_digest(list(rows)),
            "rows": list(rows),
        }
    )


def payload_bytes(payload: Mapping[str, Any]) -> tuple[bytes, str]:
    """Canonical bytes of a signed payload and their raw SHA-256 (what a packet refs)."""
    raw = canonical_json(payload)
    return raw, hashlib.sha256(raw).hexdigest()


def compare_stats(
    before: Sequence[Mapping[str, Any]], after: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Key-set, value, rank, count and provenance differences between two row sets."""
    b = {row_key(r): r for r in before}
    a = {row_key(r): r for r in after}
    only_before = sorted(set(b) - set(a))
    only_after = sorted(set(a) - set(b))
    value_changed: Counter[str] = Counter()
    rank_only: Counter[str] = Counter()
    count_only: Counter[str] = Counter()
    provenance_changed = 0
    for key in set(b) & set(a):
        x, y = b[key], a[key]
        metric = key[STAT_KEY.index("metric")]
        if x["source_versions"] != y["source_versions"]:
            provenance_changed += 1
        xv, yv = x["value"], y["value"]
        if (xv is None) != (yv is None) or (
            xv is not None and abs(xv - yv) > VALUE_TOLERANCE
        ):
            value_changed[metric] += 1
        elif x["rank"] != y["rank"]:
            rank_only[metric] += 1
        elif (x["n"], x["games"], x["cohort_size"]) != (
            y["n"],
            y["games"],
            y["cohort_size"],
        ):
            count_only[metric] += 1
    return {
        "rows_before": len(b),
        "rows_after": len(a),
        "only_before": len(only_before),
        "only_after": len(only_after),
        "same_key_set": not only_before and not only_after,
        "value_changed": dict(sorted(value_changed.items())),
        "rank_only_changed": dict(sorted(rank_only.items())),
        "count_only_changed": dict(sorted(count_only.items())),
        "provenance_changed_keys": provenance_changed,
    }


def verification_receipt(
    *,
    before_sha256: str,
    after_sha256: str,
    before_rows: Sequence[Mapping[str, Any]],
    after_rows: Sequence[Mapping[str, Any]],
    decision_ref: str,
    checks: Mapping[str, Any],
) -> dict[str, Any]:
    """The signed receipt the controller requires; ``verified`` only if every check passes.

    ``checks`` must hold the independent checks run by the verifier script (for example the
    recompute of sampled values). A changed provenance is bound with the digests the
    controller recomputes (Contract 04, Amendment 6).
    """
    if not decision_ref.strip():
        raise PayloadError("a decision reference is required")
    comparison = compare_stats(before_rows, after_rows)
    problems = structural_problems(before_rows) + structural_problems(after_rows)
    if not comparison["same_key_set"]:
        problems.append("before and after payloads do not have identical keys")
    failed = [name for name, result in checks.items() if not result.get("passed")]
    body: dict[str, Any] = {
        "schema_version": VERIFICATION_SCHEMA,
        "state": "verified" if not problems and not failed else "failed",
        "before_sha256": before_sha256,
        "after_sha256": after_sha256,
        "decision_ref": decision_ref,
        "comparison": comparison,
        "checks": {name: dict(result) for name, result in checks.items()},
        "problems": problems[:20],
        "failed_checks": failed,
    }
    if comparison["provenance_changed_keys"]:
        body["provenance_change"] = {
            "keys_changed": comparison["provenance_changed_keys"],
            "before_provenance_sha256": stats_provenance_digest(list(before_rows)),
            "after_provenance_sha256": stats_provenance_digest(list(after_rows)),
        }
    return signed_payload(body)
