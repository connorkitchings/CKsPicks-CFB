"""Read-only exact-key reconciliation and evidence for adjusted-row investigations."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from cks_picks_cfb.data import matchup_data as md

KEY = md.TABLES["team_possession_adjusted"][1]
NUMERIC = frozenset(
    {"raw_value", "adjusted_value", "opponent_adjustment", "primary_exposure"}
)
PROVENANCE = frozenset({"rating_manifest_sha256", "measurement_manifest_sha256"})


def clean(value: Any) -> Any:
    """Explicit JSON nulls and UTC timestamps; preserve names and numeric zeros."""
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, (datetime, pd.Timestamp)):
        t = pd.Timestamp(value)
        if t.tzinfo is None:
            raise ValueError("naive timestamp in evidence")
        return t.tz_convert("UTC").isoformat()
    if hasattr(value, "item"):
        return clean(value.item())
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("nonfinite evidence value")
    return value


def canonical(value: Any) -> bytes:
    return json.dumps(
        clean(value), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def index_rows(frame: pd.DataFrame) -> dict[tuple, dict]:
    indexed = {}
    for row in clean(frame.to_dict("records")):
        key = tuple(row[k] for k in KEY)
        if any(v is None for v in key) or key in indexed:
            raise ValueError(f"null or duplicate canonical key: {key}")
        indexed[key] = row
    return indexed


def same(field: str, left: Any, right: Any) -> bool:
    if left is None or right is None:
        return left is None and right is None
    if field == "as_of_cutoff" or field == "updated_at":
        a, b = pd.Timestamp(left), pd.Timestamp(right)
        if a.tzinfo is None or b.tzinfo is None:
            raise ValueError("naive comparison cutoff")
        return a.tz_convert("UTC") == b.tz_convert("UTC")
    if field in NUMERIC:
        return abs(left - right) <= 1e-9 * max(1.0, abs(left), abs(right))
    return left == right


def compare(left: pd.DataFrame, right: pd.DataFrame) -> dict:
    """Full anti-joins and every shared-key differing field, including provenance."""
    a, b = index_rows(left), index_rows(right)
    differences = []
    for key in sorted(a.keys() & b.keys()):
        for field in sorted(
            (a[key].keys() | b[key].keys()) - set(KEY) - {"updated_at"}
        ):
            if field not in a[key] or field not in b[key]:
                raise ValueError(f"incompatible snapshot field: {field}")
            x, y = a[key][field], b[key][field]
            if not same(field, x, y):
                differences.append(
                    {
                        **dict(zip(KEY, key, strict=True)),
                        "field": field,
                        "left": x,
                        "right": y,
                        "delta": y - x
                        if field in NUMERIC and x is not None and y is not None
                        else None,
                        "kind": "provenance" if field in PROVENANCE else "value",
                    }
                )
    return {
        "only_left": [a[k] for k in sorted(a.keys() - b.keys())],
        "only_right": [b[k] for k in sorted(b.keys() - a.keys())],
        "differences": differences,
        "shared_keys": len(a.keys() & b.keys()),
    }


def verified_names(
    names: set[str], game_names: set[str], aliases: dict[str, str]
) -> dict:
    result = md.resolve_game_names(names, game_names, aliases)
    inverse = {}
    for source, target in result.items():
        if target in inverse:
            raise ValueError(
                f"alias collision: {inverse[target]!r}, {source!r} -> {target!r}"
            )
        inverse[target] = source
    return result


def eligible(prepared: pd.DataFrame, week: int, cutoff: Any) -> pd.DataFrame:
    cutoff = pd.Timestamp(cutoff)
    if cutoff.tzinfo is None:
        raise ValueError("naive eligibility cutoff")
    return prepared.loc[prepared.week.lt(week) & prepared.available_utc.le(cutoff)]


def validate_population(prepared: pd.DataFrame, population: pd.DataFrame) -> dict:
    """Prove observations refer to completed, valid, uniquely identified games."""
    if population.duplicated(["season", "game_id"]).any():
        raise ValueError("duplicate source game population key")
    games = {
        (int(r["season"]), int(r["game_id"])): r
        for r in clean(population.to_dict("records"))
    }
    for r in clean(
        prepared.drop_duplicates(["season", "game_id", "team"]).to_dict("records")
    ):
        game = games.get((r["season"], r["game_id"]))
        if (
            not game
            or game["schedule_completed"] is not True
            or game["outcome_valid"] is not True
        ):
            raise ValueError("observation lacks a completed valid source game")
        if r["week"] != game["week"] or not same(
            "as_of_cutoff", r["kickoff_utc"], game["kickoff_utc"]
        ):
            raise ValueError("source game week/kickoff mismatch")
        if r["team"] not in {game["home_team"], game["away_team"]}:
            raise ValueError("observation team outside source game")
    return games


def explain_extra(
    row: dict,
    corrected: pd.DataFrame,
    legacy: pd.DataFrame,
    legacy_rebuilt: dict,
    cutoffs: dict[int, Any],
) -> dict:
    """Source-backed omission explanation, never a deletion authorization."""
    week = int(row["as_of_week"])
    cutoff = cutoffs[week]

    def filters(f):
        return (
            f.team_game.eq(row["team"])
            & f.unit_role.eq(row["role"])
            & f.measurement_id.eq(row["measurement_id"])
            & f.season.eq(row["season"])
        )

    new = eligible(corrected.loc[filters(corrected)], week, cutoff)
    old = eligible(legacy.loc[filters(legacy)], week, cutoff)

    def allowed(f):
        return f.observed & f.denominator.gt(0)

    new_used, old_used = new.loc[allowed(new)], old.loc[allowed(old)]
    key = tuple(row[k] for k in KEY)
    rebuilt = legacy_rebuilt.get(key)
    fields = set(md.ADJUSTED_COLUMNS) - set(KEY) - PROVENANCE
    reproduced = rebuilt is not None and all(
        same(f, row[f], rebuilt[f]) for f in fields
    )
    games_match = set(new.game_id) == set(old.game_id)
    missing = (
        len(new) > 0
        and new.coverage_status.eq("missing").all()
        and new.raw_value.isna().all()
        and new.missing_reason.isin(
            {"missing_ppa", "missing_or_nonfinite_eligible_ppa"}
        ).all()
    )
    supported = (
        row["measurement_id"] == "epa_per_possession"
        and missing
        and len(new_used) == 0
        and len(old_used) > 0
        and games_match
        and reproduced
    )
    source_columns = [
        "season",
        "week",
        "game_id",
        "kickoff_utc",
        "available_utc",
        "team",
        "opponent",
        "unit_role",
        "measurement_id",
        "numerator",
        "denominator",
        "raw_value",
        "usable_exposure",
        "coverage_status",
        "missing_reason",
        "observed",
    ]
    return clean(
        {
            **{k: row[k] for k in KEY},
            "cutoff": pd.Timestamp(cutoff),
            "classification": "supported_exclusion_recommendation"
            if supported
            else "unresolved",
            "reason": "Restored PPA missingness leaves no eligible observed EPA; legacy adjusted row independently reproduced. Requires separately approved scoped replacement."
            if supported
            else "Source evidence does not establish the missing-PPA hypothesis.",
            "legacy_row_reproduced": reproduced,
            "source_game_sets_match": games_match,
            "eligible_corrected": len(new_used),
            "eligible_legacy": len(old_used),
            "source_game_ids": sorted(int(g) for g in new.game_id),
            "corrected_source_sha256": sha(
                canonical(new[source_columns].to_dict("records"))
            ),
            "legacy_source_sha256": sha(
                canonical(old[source_columns].to_dict("records"))
            ),
            "corrected_observations": new[source_columns].to_dict("records"),
            "legacy_observations": old[source_columns].to_dict("records"),
            "legacy_adjusted_row": row,
            "legacy_reconstructed_row": rebuilt,
        }
    )


def fresh_output(path: Path) -> None:
    """Reserve evidence exclusively; no existing directory may be overwritten."""
    relative = (
        path.resolve().relative_to(Path.cwd())
        if path.resolve().is_relative_to(Path.cwd())
        else None
    )
    if relative is not None and relative.parts and relative.parts[0] == "data":
        raise ValueError("root data output forbidden")
    path.mkdir(parents=True, exist_ok=False)


def configure_readonly(conn: Any) -> None:
    from psycopg import IsolationLevel

    conn.isolation_level = IsolationLevel.REPEATABLE_READ
    conn.read_only = True
