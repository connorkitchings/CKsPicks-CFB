"""Pure helpers for the data-first football evidence audit.

The module has no production activation path.  It operates on caller-supplied
immutable frames and returns deterministic records suitable for research
artifacts.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict
from typing import Any

import numpy as np
import pandas as pd

from cks_picks_cfb.data.lake import DatasetRef, SourceCapture
from cks_picks_cfb.data.storage import StorageBackend, StorageError

AUDIT_SCHEMA_VERSION = "data_first_phase1_audit_v1"
DEVELOPMENT_SEASONS = (2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024, 2025)
FORBIDDEN_SEASONS = (2020,)
OUTPUT_ROOT = "artifacts/research/data-first-football-v1/phase1/"

_REF_KEYS = {"dataset", "version_id", "schema_version", "content_sha", "uri"}
_GAME_ALIASES = {
    "id": "game_id",
    "year": "season",
    "start_date": "kickoff_utc",
    "seasonType": "season_type",
    "homeClassification": "home_classification",
    "awayClassification": "away_classification",
    "homeTeam": "home_team",
    "awayTeam": "away_team",
    "homePoints": "home_points",
    "awayPoints": "away_points",
}


def canonical_json(value: Any) -> bytes:
    """Return stable JSON while refusing non-finite floating output."""

    def normalize(item: Any) -> Any:
        if isinstance(item, float):
            if not math.isfinite(item):
                raise ValueError("audit artifacts cannot contain non-finite JSON")
            return item
        if isinstance(item, np.generic):
            return normalize(item.item())
        if isinstance(item, pd.Timestamp):
            return item.isoformat()
        if isinstance(item, Mapping):
            return {str(key): normalize(val) for key, val in item.items()}
        if isinstance(item, set):
            return [normalize(val) for val in sorted(item, key=str)]
        if isinstance(item, (list, tuple)):
            return [normalize(val) for val in item]
        return item

    return json.dumps(
        normalize(value), sort_keys=True, separators=(",", ":"), default=str
    ).encode()


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def stable_issue_id(category: str, evidence: Mapping[str, Any]) -> str:
    digest = sha256(canonical_json({"category": category, "evidence": evidence}))[:12]
    return f"phase1-{category}-{digest}"


def issue(
    category: str,
    *,
    status: str,
    severity: str,
    evidence: Mapping[str, Any],
    affected_records: int | None,
    affected_descendants: Sequence[str],
    root_cause_status: str,
    certification_impact: str,
    phase2_action: str,
) -> dict[str, Any]:
    if status not in {"verified", "suspected", "accepted-limitation"}:
        raise ValueError(f"invalid issue status: {status}")
    if severity not in {"critical", "high", "medium", "low"}:
        raise ValueError(f"invalid issue severity: {severity}")
    return {
        "issue_id": stable_issue_id(category, evidence),
        "category": category,
        "status": status,
        "severity": severity,
        "evidence": dict(evidence),
        "affected_records": affected_records,
        "affected_descendants": sorted(str(value) for value in affected_descendants),
        "root_cause_status": root_cause_status,
        "certification_impact": certification_impact,
        "phase2_action": phase2_action,
    }


def extract_dataset_refs(value: Any) -> list[DatasetRef]:
    """Recursively find DatasetRef-shaped objects in JSON-compatible evidence."""
    found: dict[tuple[str, str], DatasetRef] = {}

    def visit(item: Any) -> None:
        if isinstance(item, Mapping):
            if _REF_KEYS.issubset(item):
                ref = DatasetRef(**{key: str(item[key]) for key in _REF_KEYS})
                found[(ref.dataset, ref.version_id)] = ref
            for child in item.values():
                visit(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                visit(child)

    visit(value)
    return [found[key] for key in sorted(found)]


def lineage_cycles(edges: Sequence[Mapping[str, str]]) -> list[list[str]]:
    """Return deterministic dependency cycles from child-to-parent edges."""
    graph: dict[str, set[str]] = {}
    for edge in edges:
        graph.setdefault(str(edge["child_version_id"]), set()).add(
            str(edge["parent_version_id"])
        )
    cycles: set[tuple[str, ...]] = set()

    def visit(node: str, path: list[str]) -> None:
        if node in path:
            cycle = path[path.index(node) :] + [node]
            body = cycle[:-1]
            rotations = [
                tuple(body[index:] + body[:index]) for index in range(len(body))
            ]
            cycles.add(min(rotations) + (min(rotations)[0],))
            return
        for parent in sorted(graph.get(node, ())):
            visit(parent, [*path, node])

    for node in sorted(graph):
        visit(node, [])
    return [list(cycle) for cycle in sorted(cycles)]


def validate_output_prefix(prefix: str, run_id: str) -> str:
    expected = f"{OUTPUT_ROOT}{run_id}/"
    normalized = prefix.rstrip("/") + "/"
    if (
        normalized != expected
        or not run_id
        or any(part in run_id for part in ("/", ".."))
    ):
        raise ValueError(f"output prefix must be exactly {expected}")
    return normalized


class ImmutableAuditWriter:
    """Namespace-constrained immutable artifact writer."""

    def __init__(self, storage: StorageBackend, *, run_id: str) -> None:
        self.storage = storage
        self.prefix = validate_output_prefix(f"{OUTPUT_ROOT}{run_id}/", run_id)

    def write_bytes(self, relative_path: str, payload: bytes) -> str:
        if relative_path.startswith("/") or ".." in relative_path.split("/"):
            raise ValueError("audit artifact path must be relative and traversal-free")
        uri = f"{self.prefix}{relative_path}"
        if self.storage.exists(uri):
            if self.storage.read_bytes(uri) != payload:
                raise FileExistsError(f"immutable audit artifact collision: {uri}")
            return uri
        self.storage.write_bytes(payload, uri)
        return uri

    def write_json(self, relative_path: str, value: Mapping[str, Any]) -> str:
        return self.write_bytes(relative_path, canonical_json(value))


def _classification(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    normalized = str(value).strip().casefold()
    return normalized or None


def _truthy(value: Any) -> bool:
    if value is None or pd.isna(value):
        return False
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "completed", "final"}
    return bool(value)


def _line_score_count(value: Any) -> int:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return 0
    return len(value) if isinstance(value, (list, tuple)) else 0


def _team_classification_lookup(
    teams: pd.DataFrame | None,
) -> dict[tuple[int, str], str]:
    if teams is None or teams.empty:
        return {}
    frame = teams.rename(columns={"year": "season", "school": "team"}).copy()
    required = {"season", "team", "classification"}
    if not required.issubset(frame):
        return {}
    frame["season"] = pd.to_numeric(frame["season"], errors="coerce")
    frame = frame.dropna(subset=["season", "team", "classification"])
    lookup: dict[tuple[int, str], str] = {}
    for row in frame.itertuples(index=False):
        key = (int(row.season), str(row.team))
        value = _classification(row.classification)
        if value is not None and key not in lookup:
            lookup[key] = value
    return lookup


def classify_schedule(
    games: pd.DataFrame, teams: pd.DataFrame | None = None
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Create the pre-join FBS-involved schedule denominator."""
    frame = games.rename(columns=_GAME_ALIASES).copy()
    required = {"season", "game_id", "home_team", "away_team"}
    if missing := sorted(required - set(frame)):
        raise ValueError(f"captured games missing denominator columns: {missing}")
    frame["season"] = pd.to_numeric(frame["season"], errors="coerce")
    frame["game_id"] = pd.to_numeric(frame["game_id"], errors="coerce")
    invalid_key = frame["season"].isna() | frame["game_id"].isna()
    if invalid_key.any():
        raise ValueError("captured games contain invalid season/game_id keys")
    frame["season"] = frame["season"].astype(int)
    frame["game_id"] = frame["game_id"].astype(int)
    if frame.duplicated(["season", "game_id"]).any():
        raise ValueError("captured games contain duplicate season/game_id keys")

    lookup = _team_classification_lookup(teams)
    issues: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    for source in frame.to_dict("records"):
        season = int(source["season"])
        home = str(source["home_team"])
        away = str(source["away_team"])
        home_game = _classification(source.get("home_classification"))
        away_game = _classification(source.get("away_classification"))
        home_team = lookup.get((season, home))
        away_team = lookup.get((season, away))
        if home_game and home_team and home_game != home_team:
            issues.append(
                {
                    "season": season,
                    "game_id": source["game_id"],
                    "side": "home",
                    "game": home_game,
                    "team": home_team,
                }
            )
        if away_game and away_team and away_game != away_team:
            issues.append(
                {
                    "season": season,
                    "game_id": source["game_id"],
                    "side": "away",
                    "game": away_game,
                    "team": away_team,
                }
            )
        home_class = home_game or home_team
        away_class = away_game or away_team
        known_fbs = home_class == "fbs" or away_class == "fbs"
        unresolved = home_class is None or away_class is None
        if known_fbs and home_class == away_class == "fbs":
            population = "fbs_fbs"
        elif known_fbs and not unresolved:
            population = "fbs_fcs"
        elif known_fbs or unresolved:
            population = "unresolved"
        else:
            continue

        home_points = pd.to_numeric(source.get("home_points"), errors="coerce")
        away_points = pd.to_numeric(source.get("away_points"), errors="coerce")
        completed = _truthy(source.get("completed"))
        valid_final = completed and pd.notna(home_points) and pd.notna(away_points)
        status = str(source.get("status") or "").strip().casefold()
        if status in {"cancelled", "canceled", "postponed"}:
            completion_status = "canceled" if status != "postponed" else "postponed"
        elif valid_final:
            completion_status = "completed"
        elif completed:
            completion_status = "missing_final"
        else:
            completion_status = "scheduled_or_unknown"
        line_scores = source.get("home_line_scores") or source.get("homeLineScores")
        overtime = _line_score_count(line_scores) > 4
        rows.append(
            {
                **source,
                "season": season,
                "game_id": int(source["game_id"]),
                "season_type": str(source.get("season_type") or "unknown").casefold(),
                "home_classification_resolved": home_class,
                "away_classification_resolved": away_class,
                "population": population,
                "classification_unresolved": unresolved,
                "in_target_population": known_fbs,
                "completion_status": completion_status,
                "label_eligible": valid_final,
                "overtime": overtime,
            }
        )
    result = pd.DataFrame.from_records(rows)
    if result.empty:
        raise ValueError("captured schedule has no FBS-involved or unresolved games")
    forbidden = result["season"].isin(FORBIDDEN_SEASONS)
    if forbidden.any():
        raise ValueError("captured schedule contains forbidden 2020 lineage")
    return result.sort_values(["season", "game_id"]).reset_index(drop=True), issues


def add_team_experience(schedule: pd.DataFrame) -> pd.DataFrame:
    """Compute each side's own completed-game count before kickoff."""
    frame = schedule.copy()
    if "kickoff_utc" not in frame:
        frame["kickoff_utc"] = pd.NaT
    frame["kickoff_utc"] = pd.to_datetime(
        frame["kickoff_utc"], utc=True, errors="coerce"
    )
    order = frame.sort_values(["season", "kickoff_utc", "game_id"], na_position="last")
    counts: dict[tuple[int, str], int] = {}
    values: dict[int, tuple[int, int]] = {}
    for row in order.itertuples(index=True):
        season = int(row.season)
        home_key = (season, str(row.home_team))
        away_key = (season, str(row.away_team))
        home_count = counts.get(home_key, 0)
        away_count = counts.get(away_key, 0)
        values[int(row.Index)] = (home_count, away_count)
        if bool(row.label_eligible):
            counts[home_key] = home_count + 1
            counts[away_key] = away_count + 1
    frame["home_completed_before"] = [values[index][0] for index in frame.index]
    frame["away_completed_before"] = [values[index][1] for index in frame.index]
    frame["first_game_involved"] = frame["home_completed_before"].eq(0) | frame[
        "away_completed_before"
    ].eq(0)
    frame["asymmetric_experience"] = frame["home_completed_before"].ne(
        frame["away_completed_before"]
    )
    frame["matchup_max_completed"] = frame[
        ["home_completed_before", "away_completed_before"]
    ].max(axis=1)
    return frame


def frame_audit(
    frame: pd.DataFrame, *, dataset: str, key_columns: Sequence[str]
) -> dict[str, Any]:
    missing_keys = [column for column in key_columns if column not in frame]
    duplicate_rows = None
    if key_columns and not missing_keys:
        duplicate_rows = int(frame.duplicated(list(key_columns), keep=False).sum())
    numeric = frame.select_dtypes(include=[np.number])
    infinite = (
        int(np.isinf(numeric.to_numpy(dtype=float, na_value=np.nan)).sum())
        if not numeric.empty
        else 0
    )
    seasons = []
    if "season" in frame:
        seasons = sorted(
            pd.to_numeric(frame["season"], errors="coerce")
            .dropna()
            .astype(int)
            .unique()
            .tolist()
        )
    return {
        "dataset": dataset,
        "row_count": int(len(frame)),
        "column_count": int(len(frame.columns)),
        "seasons": seasons,
        "missing_key_columns": missing_keys,
        "duplicate_key_rows": duplicate_rows,
        "infinite_numeric_values": infinite,
        "null_counts": {
            str(key): int(value) for key, value in frame.isna().sum().items() if value
        },
        "forbidden_2020": 2020 in seasons,
    }


def join_cardinality_audit(
    left: pd.DataFrame,
    right: pd.DataFrame,
    *,
    keys: Sequence[str],
) -> dict[str, Any]:
    """Report join validity without silently reducing either population."""
    missing_left = sorted(set(keys) - set(left))
    missing_right = sorted(set(keys) - set(right))
    if missing_left or missing_right or not keys:
        return {
            "keys": list(keys),
            "missing_left_keys": missing_left,
            "missing_right_keys": missing_right,
            "left_duplicate_rows": None,
            "right_duplicate_rows": None,
            "left_only_keys": None,
            "right_only_keys": None,
            "many_to_many": None,
        }
    left_keys = left[list(keys)]
    right_keys = right[list(keys)]
    left_duplicates = int(left_keys.duplicated(keep=False).sum())
    right_duplicates = int(right_keys.duplicated(keep=False).sum())
    merged = left_keys.drop_duplicates().merge(
        right_keys.drop_duplicates(), on=list(keys), how="outer", indicator=True
    )
    return {
        "keys": list(keys),
        "missing_left_keys": [],
        "missing_right_keys": [],
        "left_duplicate_rows": left_duplicates,
        "right_duplicate_rows": right_duplicates,
        "left_only_keys": int(merged["_merge"].eq("left_only").sum()),
        "right_only_keys": int(merged["_merge"].eq("right_only").sum()),
        "many_to_many": bool(left_duplicates and right_duplicates),
    }


def numeric_semantics_audit(
    frame: pd.DataFrame,
    *,
    exposures: Sequence[str] = (),
    bounded: Mapping[str, tuple[float, float]] | None = None,
) -> dict[str, Any]:
    """Expose zero/null exposure, range failures, and unstable numeric designs."""
    bounded = bounded or {}
    missing_exposures = sorted(set(exposures) - set(frame))
    null_exposure = {
        column: int(frame[column].isna().sum())
        for column in exposures
        if column in frame
    }
    zero_exposure = {
        column: int(pd.to_numeric(frame[column], errors="coerce").eq(0).sum())
        for column in exposures
        if column in frame
    }
    range_failures = {}
    for column, (lower, upper) in bounded.items():
        if column not in frame:
            range_failures[column] = None
            continue
        values = pd.to_numeric(frame[column], errors="coerce")
        range_failures[column] = int(((values < lower) | (values > upper)).sum())
    numeric = frame.select_dtypes(include=[np.number]).replace(
        [np.inf, -np.inf], np.nan
    )
    complete = numeric.dropna(axis=0, how="any")
    condition_number = None
    if complete.shape[0] >= 2 and complete.shape[1] >= 2:
        matrix = complete.to_numpy(dtype=float)
        scaled = matrix - matrix.mean(axis=0)
        scales = scaled.std(axis=0)
        scaled = scaled[:, scales > 0]
        if scaled.shape[1] >= 2:
            condition_number = float(np.linalg.cond(scaled / scales[scales > 0]))
    return {
        "missing_exposure_columns": missing_exposures,
        "null_exposure_rows": null_exposure,
        "zero_exposure_rows": zero_exposure,
        "range_failure_rows": range_failures,
        "max_absolute_numeric_value": (
            float(numeric.abs().max().max())
            if not numeric.empty and numeric.notna().any().any()
            else None
        ),
        "condition_number": condition_number,
    }


def pregame_timing_audit(
    frame: pd.DataFrame,
    *,
    kickoff_by_game: Mapping[int, Any],
    timestamp_columns: Sequence[str] = (
        "effective_at",
        "captured_at",
        "observed_at",
        "__captured_at",
    ),
) -> dict[str, Any]:
    """Classify evidence timing without manufacturing unavailable timestamps."""
    available = [column for column in timestamp_columns if column in frame]
    if "game_id" not in frame or not available:
        return {
            "rows": int(len(frame)),
            "timestamp_columns": available,
            "pregame_rows": 0,
            "postgame_or_reconstructed_rows": 0,
            "unresolved_rows": int(len(frame)),
        }
    pregame = postgame = unresolved = 0
    for row in frame.to_dict("records"):
        game_id = pd.to_numeric(row.get("game_id"), errors="coerce")
        kickoff = kickoff_by_game.get(int(game_id)) if pd.notna(game_id) else None
        if kickoff is None or pd.isna(kickoff):
            unresolved += 1
            continue
        evidence_times = [
            pd.to_datetime(row.get(column), utc=True, errors="coerce")
            for column in available
            if row.get(column) is not None
        ]
        evidence_times = [value for value in evidence_times if pd.notna(value)]
        if not evidence_times:
            unresolved += 1
        elif all(value < pd.Timestamp(kickoff) for value in evidence_times):
            pregame += 1
        else:
            postgame += 1
    return {
        "rows": int(len(frame)),
        "timestamp_columns": available,
        "pregame_rows": pregame,
        "postgame_or_reconstructed_rows": postgame,
        "unresolved_rows": unresolved,
    }


def stage_coverage(
    schedule: pd.DataFrame, stage_game_ids: Mapping[str, Iterable[int]]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Measure every downstream game set against the independent schedule."""
    groups = ["season", "season_type", "population", "completion_status"]
    coverage_rows: list[dict[str, Any]] = []
    exclusion_rows: list[dict[str, Any]] = []
    for group_values, games in schedule.groupby(groups, dropna=False):
        denominator_ids = set(games["game_id"].astype(int))
        base = dict(zip(groups, group_values, strict=True))
        for stage, raw_ids in stage_game_ids.items():
            ids = {int(value) for value in raw_ids}
            admitted_ids = denominator_ids & ids
            missing_ids = denominator_ids - ids
            unresolved = int(
                games.loc[games["classification_unresolved"], "game_id"].nunique()
            )
            coverage_rows.append(
                {
                    **base,
                    "stage": stage,
                    "denominator_count": len(denominator_ids),
                    "admitted_count": len(admitted_ids),
                    "excluded_count": len(missing_ids),
                    "unresolved_count": unresolved,
                    "coverage_rate": len(admitted_ids) / len(denominator_ids),
                }
            )
            for game_id in sorted(missing_ids):
                game = games.loc[games["game_id"].eq(game_id)].iloc[0]
                if game["completion_status"] != "completed":
                    reason = str(game["completion_status"])
                elif bool(game["classification_unresolved"]):
                    reason = "classification_unresolved"
                else:
                    reason = f"missing_from_{stage}"
                exclusion_rows.append(
                    {**base, "stage": stage, "game_id": game_id, "reason_code": reason}
                )
    return pd.DataFrame(coverage_rows), pd.DataFrame(exclusion_rows)


def recompute_prediction_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    """Recompute unique-game MAE and bias from long or wide prediction rows."""
    long_rows: list[pd.DataFrame] = []
    identity = [
        column
        for column in ("candidate_id", "family", "design_id", "season", "fold")
        if column in frame
    ]
    if {"target", "prediction", "actual"}.issubset(frame):
        long_rows.append(
            frame[[*identity, "game_id", "target", "prediction", "actual"]]
        )
    for target in ("margin", "spread", "total"):
        pred = next(
            (
                name
                for name in (f"predicted_{target}", f"{target}_prediction")
                if name in frame
            ),
            None,
        )
        actual = next(
            (
                name
                for name in (f"actual_{target}", f"{target}_target")
                if name in frame
            ),
            None,
        )
        if pred and actual:
            part = frame[[*identity, "game_id", pred, actual]].rename(
                columns={pred: "prediction", actual: "actual"}
            )
            part["target"] = "margin" if target == "spread" else target
            long_rows.append(part)
    if not long_rows:
        return pd.DataFrame(
            columns=[
                *identity,
                "target",
                "candidate_rows",
                "unique_games",
                "mae",
                "bias",
            ]
        )
    long = pd.concat(long_rows, ignore_index=True)
    long["prediction"] = pd.to_numeric(long["prediction"], errors="coerce")
    long["actual"] = pd.to_numeric(long["actual"], errors="coerce")
    long["finite"] = np.isfinite(long["prediction"]) & np.isfinite(long["actual"])
    groups = [*identity, "target"]
    rows = []
    for key, values in long.groupby(groups, dropna=False):
        key_tuple = key if isinstance(key, tuple) else (key,)
        finite = values[values["finite"]].drop_duplicates(["game_id"], keep=False)
        errors = finite["prediction"] - finite["actual"]
        rows.append(
            {
                **dict(zip(groups, key_tuple, strict=True)),
                "candidate_rows": int(len(values)),
                "unique_games": int(values["game_id"].nunique()),
                "finite_unique_games": int(len(finite)),
                "nonfinite_rows": int((~values["finite"]).sum()),
                "duplicate_game_rows": int(
                    values.duplicated(["game_id"], keep=False).sum()
                ),
                "mae": float(errors.abs().mean()) if not finite.empty else None,
                "bias": float(errors.mean()) if not finite.empty else None,
            }
        )
    return pd.DataFrame(rows)


def metrics_match(
    reported: float, recomputed: float, *, rounded_digits: int | None = None
) -> bool:
    tolerance = (
        1e-9 if rounded_digits is None else max(1e-9, 0.5 * 10 ** (-rounded_digits))
    )
    return math.isclose(
        float(reported), float(recomputed), rel_tol=1e-9, abs_tol=tolerance
    )


def result_disposition(
    *,
    result_id: str,
    lineage_resolved: bool,
    evidence_readable: bool,
    counts_match: bool,
    metrics_match_report: bool,
    correctness_defect: bool,
    modeling_status: str,
    reasons: Sequence[str] = (),
) -> dict[str, Any]:
    allowed_modeling = {
        "historical-only",
        "diagnostic-only",
        "blocked-pending-repair",
        "eligible-for-phase2-review",
    }
    if modeling_status not in allowed_modeling:
        raise ValueError(f"invalid modeling status: {modeling_status}")
    if not lineage_resolved or not evidence_readable:
        evidence_status = "unsupported"
    elif correctness_defect or not counts_match or not metrics_match_report:
        evidence_status = "requires-correction"
    else:
        evidence_status = "reproducible"
    return {
        "result_id": result_id,
        "evidence_status": evidence_status,
        "modeling_status": modeling_status,
        "lineage_resolved": lineage_resolved,
        "evidence_readable": evidence_readable,
        "counts_match": counts_match,
        "metrics_match": metrics_match_report,
        "correctness_defect": correctness_defect,
        "reasons": sorted(set(str(reason) for reason in reasons)),
    }


def source_capture_json(capture: SourceCapture) -> dict[str, Any]:
    value = asdict(capture)
    value["captured_at"] = capture.captured_at.isoformat()
    value["effective_at"] = (
        capture.effective_at.isoformat() if capture.effective_at else None
    )
    return value


def require_resolved_manifest(payload: Mapping[str, Any]) -> None:
    if payload.get("schema_version") != AUDIT_SCHEMA_VERSION:
        raise ValueError("resolved evidence manifest has the wrong schema version")
    expected = payload.get("manifest_sha256")
    unsigned = dict(payload)
    unsigned.pop("manifest_sha256", None)
    if expected != sha256(canonical_json(unsigned)):
        raise StorageError("resolved evidence manifest identity mismatch")
    if payload.get("state") not in {"resolved", "resolved_with_blockers"}:
        raise ValueError("resolved evidence manifest is not sealed")
