"""Pure contracts and normalizers for Phase 2e auxiliary research evidence."""

from __future__ import annotations

import ast
import hashlib
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd

from cks_picks_cfb.data.data_first_phase2 import DEVELOPMENT_SEASONS, FORBIDDEN_SEASONS
from cks_picks_cfb.data.data_first_phase2d import (
    canonical_bytes,
    signed_payload,
    verify_signed_payload,
)
from cks_picks_cfb.data.lake import canonicalize_market_quotes_frame
from cks_picks_cfb.preseason_features import canonical_team

PHASE2E_CAPTURE_SET_SCHEMA = "data_first_phase2e_capture_set_v1"
PHASE2E_ELIGIBILITY_SCHEMA = "data_first_phase2e_eligibility_v1"
RECONSTRUCTED_TIMING = "historically_reconstructed"
CONTEXT_FAMILIES = (
    "recruiting",
    "returning_production",
    "coaching",
    "roster_continuity",
    "lagged_rankings",
)
SOURCE_ENTITY_COUNTS = {
    "betting_lines": 10,
    "coaches": 10,
    "rankings": 10,
    "rosters": 10,
    "returning_production": 10,
    "recruiting": 13,
}
RECRUITING_SEASONS = tuple(range(2012, 2020)) + tuple(range(2021, 2026))


class Phase2eError(ValueError):
    """Raised when auxiliary evidence cannot be safely admitted."""


def sha256(value: Any) -> str:
    payload = value if isinstance(value, bytes) else canonical_bytes(value)
    return hashlib.sha256(payload).hexdigest()


def expected_capture_keys() -> set[tuple[str, int]]:
    keys = {
        (entity, season)
        for entity, count in SOURCE_ENTITY_COUNTS.items()
        for season in (
            RECRUITING_SEASONS if entity == "recruiting" else DEVELOPMENT_SEASONS
        )
    }
    if len(keys) != sum(SOURCE_ENTITY_COUNTS.values()):
        raise AssertionError("Phase 2e capture set is not unique")
    return keys


def validate_capture_inventory(captures: Sequence[Mapping[str, Any]]) -> None:
    """Require the exact backfill matrix and reconstructed source timing."""
    actual: set[tuple[str, int]] = set()
    capture_ids: set[str] = set()
    for row in captures:
        entity = str(row.get("entity") or "")
        season = int(row.get("season", -1))
        key = (entity, season)
        if key in actual:
            raise Phase2eError(f"duplicate auxiliary capture: {key}")
        actual.add(key)
        capture_id = str(row.get("capture_id") or "")
        if not capture_id or capture_id in capture_ids:
            raise Phase2eError("auxiliary captures require unique nonempty IDs")
        capture_ids.add(capture_id)
        if row.get("provider") != "cfbd" or row.get("state") != "registered":
            raise Phase2eError(f"auxiliary capture is not a registered CFBD row: {key}")
        if row.get("effective_at") is not None:
            raise Phase2eError(
                f"auxiliary capture has unsupported effective time: {key}"
            )
        if row.get("timing_class") != RECONSTRUCTED_TIMING:
            raise Phase2eError(f"auxiliary capture has invalid timing class: {key}")
        if int(row.get("row_count", 0)) <= 0:
            raise Phase2eError(f"auxiliary capture is empty: {key}")
        if (
            len(str(row.get("content_sha") or "")) != 64
            or len(str(row.get("object_sha") or "")) != 64
        ):
            raise Phase2eError(f"auxiliary capture checksum is malformed: {key}")
    expected = expected_capture_keys()
    if actual != expected:
        raise Phase2eError(
            f"auxiliary capture matrix mismatch: missing={sorted(expected - actual)[:3]}, "
            f"extra={sorted(actual - expected)[:3]}"
        )


def capture_set_manifest(captures: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    validate_capture_inventory(captures)
    return signed_payload(
        {
            "schema_version": PHASE2E_CAPTURE_SET_SCHEMA,
            "state": "complete",
            "development_seasons": list(DEVELOPMENT_SEASONS),
            "forbidden_seasons": list(FORBIDDEN_SEASONS),
            "timing_class": RECONSTRUCTED_TIMING,
            "captures": sorted(
                (dict(row) for row in captures),
                key=lambda row: (str(row["entity"]), int(row["season"])),
            ),
        }
    )


def validate_capture_set_manifest(value: Mapping[str, Any]) -> list[dict[str, Any]]:
    if value.get("schema_version") != PHASE2E_CAPTURE_SET_SCHEMA:
        raise Phase2eError("Phase 2e capture set has the wrong schema")
    if value.get("state") != "complete":
        raise Phase2eError("Phase 2e capture set is not complete")
    verify_signed_payload(value, label="Phase 2e capture set")
    if tuple(value.get("development_seasons") or ()) != DEVELOPMENT_SEASONS:
        raise Phase2eError("Phase 2e capture set has the wrong development seasons")
    if tuple(value.get("forbidden_seasons") or ()) != FORBIDDEN_SEASONS:
        raise Phase2eError("Phase 2e capture set has the wrong forbidden seasons")
    captures = [dict(row) for row in value.get("captures") or []]
    validate_capture_inventory(captures)
    return captures


def _universe(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"season", "team"}
    if missing := sorted(required - set(frame)):
        raise Phase2eError(f"team universe is missing columns: {missing}")
    result = frame.loc[:, ["season", "team"]].copy()
    result["season"] = pd.to_numeric(result["season"], errors="raise").astype(int)
    result["team"] = result["team"].map(canonical_team)
    if result["team"].isna().any() or result.duplicated().any():
        raise Phase2eError("team universe has invalid or duplicate team-season keys")
    if set(result["season"]) - set(DEVELOPMENT_SEASONS):
        raise Phase2eError("team universe contains forbidden seasons")
    return result.sort_values(["season", "team"]).reset_index(drop=True)


def _numeric(frame: pd.DataFrame, *names: str) -> pd.Series:
    for name in names:
        if name in frame:
            return pd.to_numeric(frame[name], errors="coerce")
    return pd.Series(np.nan, index=frame.index, dtype=float)


def _one_row_per_team(frame: pd.DataFrame, *, family: str) -> pd.DataFrame:
    result = frame.copy()
    result["team"] = result["team"].map(canonical_team)
    result = result[result["team"].notna()].copy()
    if result.duplicated(["season", "team"]).any():
        raise Phase2eError(f"{family} has duplicate team-season rows")
    return result


def normalize_recruiting(raw: pd.DataFrame, universe: pd.DataFrame) -> pd.DataFrame:
    required = {"year", "team", "points"}
    if missing := sorted(required - set(raw)):
        raise Phase2eError(f"recruiting source is missing columns: {missing}")
    source = raw.loc[:, ["year", "team", "points"]].copy()
    source["year"] = pd.to_numeric(source["year"], errors="raise").astype(int)
    source["season"] = source["year"]
    source = _one_row_per_team(source, family="recruiting")
    source["points"] = _numeric(source, "points")
    rows = []
    for row in _universe(universe).itertuples(index=False):
        window = source[
            (source["year"] >= row.season - 3) & (source["year"] <= row.season)
        ]
        values = window[window["team"] == row.team]
        current = values[values["year"] == row.season]["points"]
        mean = values["points"].mean() if len(values) == 4 else np.nan
        current_value = current.iloc[0] if len(current) == 1 else np.nan
        rows.append(
            {
                "season": row.season,
                "team": row.team,
                "recruiting_4yr": mean,
                "recruiting_current": current_value,
                "recruiting_trend": current_value - mean
                if pd.notna(current_value) and pd.notna(mean)
                else np.nan,
                "missing_reason": None
                if pd.notna(current_value) and pd.notna(mean)
                else "incomplete_four_class_history",
                "timing_class": RECONSTRUCTED_TIMING,
            }
        )
    return pd.DataFrame(rows)


def normalize_returning_production(
    raw: pd.DataFrame, universe: pd.DataFrame
) -> pd.DataFrame:
    required = {"season", "team"}
    if missing := sorted(required - set(raw)):
        raise Phase2eError(f"returning-production source is missing columns: {missing}")
    columns = {
        "return_total_ppa": ("totalPPA", "total_ppa"),
        "return_passing_ppa": ("totalPassingPPA", "total_passing_ppa"),
        "return_rushing_ppa": ("totalRushingPPA", "total_rushing_ppa"),
        "return_receiving_ppa": ("totalReceivingPPA", "total_receiving_ppa"),
        "return_percent_ppa": ("percentPPA", "percent_ppa"),
        "return_passing_usage": ("passingUsage", "passing_usage"),
        "return_rushing_usage": ("rushingUsage", "rushing_usage"),
    }
    source = raw.copy()
    source["season"] = pd.to_numeric(source["season"], errors="raise").astype(int)
    source = _one_row_per_team(source, family="returning_production")
    for target, aliases in columns.items():
        source[target] = _numeric(source, *aliases)
    joined = _universe(universe).merge(
        source[["season", "team", *columns]], on=["season", "team"], how="left"
    )
    values = joined[list(columns)]
    joined["missing_reason"] = np.where(
        values.notna().all(axis=1), None, "missing_or_incomplete_source_row"
    )
    joined["timing_class"] = RECONSTRUCTED_TIMING
    return joined


def _season_records(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, str):
        try:
            value = ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return []
    return [item for item in value or [] if isinstance(item, Mapping)]


def normalize_coaching(raw: pd.DataFrame, universe: pd.DataFrame) -> pd.DataFrame:
    if "seasons" not in raw:
        raise Phase2eError("coaching source is missing seasons")
    rows = []
    for coach in raw.to_dict("records"):
        records = _season_records(coach.get("seasons"))
        capture_season = int(coach.get("season"))
        for record in records:
            year = pd.to_numeric(record.get("year"), errors="coerce")
            team = canonical_team(record.get("school"))
            if pd.isna(year) or int(year) != capture_season or team is None:
                continue
            rows.append(
                {
                    "season": int(year),
                    "team": team,
                    "hire_date": coach.get("hireDate", coach.get("hire_date")),
                    "history": records,
                }
            )
    source = pd.DataFrame(rows)
    if source.empty:
        source = pd.DataFrame(columns=["season", "team", "hire_date", "history"])
    source = source[source["season"].isin(DEVELOPMENT_SEASONS)].copy()
    output = []
    for unit in _universe(universe).itertuples(index=False):
        candidates = source[
            (source["season"] == unit.season) & (source["team"] == unit.team)
        ]
        if len(candidates) != 1:
            output.append(
                {
                    "season": unit.season,
                    "team": unit.team,
                    "coach_tenure": np.nan,
                    "coach_new": np.nan,
                    "missing_reason": "ambiguous_coach_assignment"
                    if len(candidates) > 1
                    else "missing_coach_assignment",
                    "timing_class": RECONSTRUCTED_TIMING,
                }
            )
            continue
        history = candidates.iloc[0]["history"]
        years = sorted(
            int(item["year"])
            for item in history
            if canonical_team(item.get("school")) == unit.team
            and pd.notna(pd.to_numeric(item.get("year"), errors="coerce"))
        )
        tenure, expected = 0, unit.season
        for year in reversed(years):
            if year != expected:
                break
            tenure += 1
            expected -= 1
        output.append(
            {
                "season": unit.season,
                "team": unit.team,
                "coach_tenure": tenure,
                "coach_new": int(tenure == 1),
                "missing_reason": None,
                "timing_class": RECONSTRUCTED_TIMING,
            }
        )
    return pd.DataFrame(output)


def normalize_roster_continuity(
    raw: pd.DataFrame, universe: pd.DataFrame
) -> pd.DataFrame:
    required = {"id", "team", "position"}
    if missing := sorted(required - set(raw)):
        raise Phase2eError(f"roster source is missing columns: {missing}")
    source = raw.copy()
    if "season" not in source:
        raise Phase2eError("roster source requires capture-derived season")
    source["season"] = pd.to_numeric(source["season"], errors="raise").astype(int)
    source["team"] = source["team"].map(canonical_team)
    source = source[source["team"].notna() & source["id"].notna()].copy()
    source["id"] = source["id"].astype(str)
    team_counts = source.groupby(["season", "id"], observed=True)["team"].nunique()
    ambiguous_ids = set(team_counts[team_counts > 1].index)
    ambiguous = source.set_index(["season", "id"]).index.isin(ambiguous_ids)
    exclusions = source.loc[ambiguous].groupby(["season", "team"], observed=True).size()
    # A player appearing for two teams in the same season has no stable
    # continuity identity. Exclude that player from the derived numerator and
    # preserve the count on each affected team row instead of choosing a team.
    source = source.loc[~ambiguous].drop_duplicates(["season", "team", "id"])
    rows = []
    for unit in _universe(universe).itertuples(index=False):
        current = source[
            (source["season"] == unit.season) & (source["team"] == unit.team)
        ]
        previous_season = unit.season - 1
        if unit.season in {2015, 2021}:
            rows.append(
                {
                    "season": unit.season,
                    "team": unit.team,
                    "roster_size": np.nan,
                    "roster_returning_share": np.nan,
                    "roster_returning_qb_count": np.nan,
                    "identity_exclusion_count": int(
                        exclusions.get((unit.season, unit.team), 0)
                    ),
                    "missing_reason": "prior_roster_outside_lineage",
                    "timing_class": RECONSTRUCTED_TIMING,
                }
            )
            continue
        prior_ids = set(source[source["season"] == previous_season]["id"])
        ids = set(current["id"])
        returning = ids & prior_ids
        rows.append(
            {
                "season": unit.season,
                "team": unit.team,
                "roster_size": len(ids) if ids else np.nan,
                "roster_returning_share": len(returning) / len(ids) if ids else np.nan,
                "roster_returning_qb_count": int(
                    current[current["position"].astype(str).str.upper().eq("QB")]["id"]
                    .isin(returning)
                    .sum()
                )
                if ids
                else np.nan,
                "identity_exclusion_count": int(
                    exclusions.get((unit.season, unit.team), 0)
                ),
                "missing_reason": None if ids else "missing_current_roster",
                "timing_class": RECONSTRUCTED_TIMING,
            }
        )
    return pd.DataFrame(rows)


def _ranking_rows(
    raw: pd.DataFrame,
) -> tuple[pd.DataFrame, set[tuple[int, int, str, str]]]:
    rows = []
    for item in raw.to_dict("records"):
        season = item.get("season")
        week = item.get("week")
        polls = item.get("polls")
        if isinstance(polls, str):
            try:
                polls = ast.literal_eval(polls)
            except (SyntaxError, ValueError):
                polls = []
        for poll in polls or []:
            if not isinstance(poll, Mapping) or poll.get("poll") not in {
                "AP Top 25",
                "Coaches Poll",
            }:
                continue
            for rank in poll.get("ranks") or []:
                if not isinstance(rank, Mapping):
                    continue
                team = canonical_team(rank.get("school"))
                if team is not None:
                    rows.append(
                        {
                            "season": int(season),
                            "poll_week": int(week),
                            "poll": poll["poll"],
                            "team": team,
                            "rank": rank.get("rank"),
                        }
                    )
    result = pd.DataFrame(rows)
    if result.empty:
        return (
            pd.DataFrame(columns=["season", "poll_week", "poll", "team", "rank"]),
            set(),
        )
    result["rank"] = pd.to_numeric(result["rank"], errors="raise").astype(int)
    keys = ["season", "poll_week", "poll", "team"]
    conflicts = {
        tuple(key)
        for key, values in result.groupby(keys, observed=True)
        if values["rank"].nunique() > 1
    }
    if conflicts:
        conflict_index = result.set_index(keys).index.isin(conflicts)
        result = result.loc[~conflict_index].copy()
    return result.drop_duplicates(keys), conflicts


def normalize_lagged_rankings(
    raw: pd.DataFrame, game_sides: pd.DataFrame
) -> pd.DataFrame:
    required = {"season", "week", "game_id", "team"}
    if missing := sorted(required - set(game_sides)):
        raise Phase2eError(f"ranking game sides are missing columns: {missing}")
    rankings, conflicts = _ranking_rows(raw)
    rows = []
    for game in game_sides.loc[:, ["season", "week", "game_id", "team"]].itertuples(
        index=False
    ):
        season, week, team = int(game.season), int(game.week), canonical_team(game.team)
        prior = rankings[
            (rankings["season"] == season) & (rankings["poll_week"] < week)
        ]
        values: dict[str, Any] = {}
        missing = []
        for poll, target in (
            ("AP Top 25", "lagged_ap_rank"),
            ("Coaches Poll", "lagged_coaches_rank"),
        ):
            available = prior[prior["poll"] == poll]
            if available.empty:
                values[target] = np.nan
                missing.append(poll)
                continue
            latest = int(available["poll_week"].max())
            rank = available[
                (available["poll_week"] == latest) & (available["team"] == team)
            ]["rank"]
            if (season, latest, poll, team) in conflicts:
                values[target] = np.nan
                missing.append(f"ambiguous_{poll}")
            else:
                values[target] = int(rank.iloc[0]) if len(rank) == 1 else 26
        rows.append(
            {
                "season": season,
                "week": week,
                "game_id": int(game.game_id),
                "team": team,
                **values,
                "lagged_ranked_either": int(
                    any(values[key] < 26 for key in values if pd.notna(values[key]))
                )
                if not missing
                else np.nan,
                "missing_reason": "no_prior_poll" if missing else None,
                "timing_class": RECONSTRUCTED_TIMING,
            }
        )
    result = pd.DataFrame(rows)
    if result.duplicated(["season", "game_id", "team"]).any():
        raise Phase2eError("lagged rankings has duplicate game-team rows")
    return result


def normalize_market_references(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return canonical reconstructed references and every excluded raw quote."""
    records = []
    for row in raw.to_dict("records"):
        value = dict(row)
        value["__capture_id"] = str(value.pop("source_capture_id"))
        value["__captured_at"] = value.pop("captured_at")
        value["__capture_provider"] = "cfbd"
        records.append(value)
    quotes = []
    excluded = []
    for record in records:
        try:
            frame = pd.DataFrame.from_records([record])
            from cks_picks_cfb.data.silver.builders import normalize_market_quotes

            normalized = normalize_market_quotes(frame.to_dict("records"))
            quotes.extend(normalized.to_dict("records"))
        except Exception as exc:  # exact source exclusion is preserved for review
            excluded.append(
                {
                    "source_capture_id": record["__capture_id"],
                    "reason": type(exc).__name__,
                }
            )
    quote_frame = pd.DataFrame.from_records(quotes)
    if quote_frame.empty:
        return quote_frame, pd.DataFrame.from_records(excluded)
    snapshots = canonicalize_market_quotes_frame(quote_frame)
    snapshots["timing_class"] = RECONSTRUCTED_TIMING
    snapshots["usage"] = "post_phase5_diagnostic_only"
    return snapshots, pd.DataFrame.from_records(excluded)


def family_coverage(frame: pd.DataFrame, features: Sequence[str]) -> dict[str, Any]:
    complete = frame[list(features)].notna().all(axis=1)
    per_season = {
        str(int(season)): {
            "required_rows": int(len(values)),
            "covered_rows": int(complete.loc[values.index].sum()),
            "coverage_fraction": float(complete.loc[values.index].mean()),
        }
        for season, values in frame.groupby("season", observed=True)
    }
    return {
        "coverage": per_season,
        "complete_rows": int(complete.sum()),
        "required_rows": int(len(frame)),
    }


def auxiliary_eligibility_manifest(
    *,
    capture_set: Mapping[str, Any],
    refs: Mapping[str, Mapping[str, Any]],
    coverage: Mapping[str, Mapping[str, Any]],
    exclusions: Mapping[str, Sequence[Mapping[str, Any]]],
    code_sha: str,
    as_of: str,
) -> dict[str, Any]:
    validate_capture_set_manifest(capture_set)
    if set(refs) != set((*CONTEXT_FAMILIES, "market_references")):
        raise Phase2eError("Phase 2e eligibility has the wrong output references")
    for family in CONTEXT_FAMILIES:
        if float(coverage[family]["minimum_coverage"]) < 0.90:
            raise Phase2eError(f"{family} did not meet the 90% coverage gate")
    payload = {
        "schema_version": PHASE2E_ELIGIBILITY_SCHEMA,
        "state": "eligible_reconstructed_only",
        "capture_set_sha256": capture_set["manifest_sha256"],
        "development_seasons": list(DEVELOPMENT_SEASONS),
        "forbidden_seasons": list(FORBIDDEN_SEASONS),
        "timing_class": RECONSTRUCTED_TIMING,
        "activation_eligible": False,
        "production_activation_authorized": False,
        "model_selection_authorized": False,
        "code_sha": code_sha,
        "as_of": as_of,
        "inputs": {name: dict(ref) for name, ref in refs.items()},
        "coverage": {name: dict(value) for name, value in coverage.items()},
        "exclusions": {
            name: [dict(row) for row in rows] for name, rows in exclusions.items()
        },
        "permitted_uses": {
            **{name: ["phase3_context_research_only"] for name in CONTEXT_FAMILIES},
            "market_references": ["post_phase5_diagnostic_only"],
        },
    }
    return signed_payload(payload)
