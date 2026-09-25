"""Verifier-owned reconstruction for V5 possession certification.

This module deliberately does not import the possession producer.  It expresses
the measurement and replay rules a second time so changes isolated to producer
code cannot silently certify themselves.
"""

from __future__ import annotations

import json
import runpy
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from cks_picks_cfb.data.data_first_phase2 import DEVELOPMENT_SEASONS, FORBIDDEN_SEASONS
from cks_picks_cfb.data.data_first_possession_v1 import (
    COVERAGE_COLUMNS,
    HISTORY_COLUMNS,
    MEASUREMENTS,
    OBSERVATION_COLUMNS,
    POPULATION_COLUMNS,
    POSSESSION_COLUMNS,
    SCORING_EVENT_COLUMNS,
    SNAPSHOT_COLUMNS,
    TERMINAL_COLUMNS,
)
from cks_picks_cfb.data.data_first_repair_v2 import (
    EXTENSION_2026_SEASONS,
    LIVE_TIMING,
    RECONSTRUCTED_TIMING,
)

ProgressCallback = Callable[..., None]
PartCallback = Callable[[str, dict[str, int], pd.DataFrame], None]

_NO_SCRIMMAGE = ("timeout", "end of", "period end", "game end", "delay of game")
_OTHER_UNIT = (
    "interception",
    "fumble",
    "punt",
    "kickoff",
    "blocked",
    "safety",
    "return",
)
_DEAD_MARKERS = ("timeout", "end of", "period end", "game end", "delay of game")
_TRY_MARKERS = ("two point", "2-point", "extra point", "conversion")
_BROKEN_SCORE_REASONS = {
    "missing_or_nonfinite_score",
    "score_regression_or_nonintegral",
    "impossible_score_increment",
}


class IndependentPossessionError(ValueError):
    """Raised when independently reconstructed evidence violates the contract."""


@dataclass(frozen=True)
class IndependentMeasurements:
    possessions: pd.DataFrame
    scoring_events: pd.DataFrame
    observations: pd.DataFrame
    coverage: pd.DataFrame
    final_reconciliation: dict[int, dict[str, float]]


def reconstruct_population(
    repair_population: pd.DataFrame,
    *,
    scope: str = "historical",
    expected_rows: int | None = None,
    expected_eligible: int | None = None,
) -> pd.DataFrame:
    """Reconstruct Contract 02 population membership without producer helpers."""
    if scope == "season_2026":
        allowed_seasons = tuple(EXTENSION_2026_SEASONS)
        row_timing = LIVE_TIMING
        if expected_rows is None or expected_eligible is None:
            raise IndependentPossessionError(
                "2026 population reconstruction requires pinned counts"
            )
        expected_counts = (int(expected_rows), int(expected_eligible))
    elif scope == "historical":
        allowed_seasons = tuple(DEVELOPMENT_SEASONS)
        row_timing = RECONSTRUCTED_TIMING
        expected_counts = (8936, 8935)
    else:
        raise IndependentPossessionError(f"population has unknown scope: {scope}")
    needed = {
        "season",
        "week",
        "game_id",
        "kickoff_utc",
        "home_team",
        "away_team",
        "schedule_completed",
        "outcome_valid",
        "forecast_eligible",
        "measurement_usable",
        "missing_reason",
        "disposition",
        "timing_class",
    }
    if missing := sorted(needed - set(repair_population)):
        raise IndependentPossessionError(f"Repair population lacks columns: {missing}")
    source = repair_population.copy()
    for column in ("season", "week", "game_id"):
        source[column] = pd.to_numeric(source[column], errors="raise").astype(int)
    source["kickoff_utc"] = pd.to_datetime(
        source["kickoff_utc"], utc=True, errors="raise"
    )
    if source.duplicated(["season", "game_id"]).any():
        raise IndependentPossessionError(
            "Repair population contains duplicate game keys"
        )
    if set(source["season"]) - set(allowed_seasons):
        raise IndependentPossessionError(
            "Repair population contains undeclared seasons"
        )
    if source["season"].isin(FORBIDDEN_SEASONS).any():
        raise IndependentPossessionError(
            "Repair population includes a forbidden season"
        )
    if not source["timing_class"].eq(row_timing).all():
        raise IndependentPossessionError(
            "Repair timing class differs from the contract"
        )
    result = pd.DataFrame(
        {
            "season": source["season"],
            "week": source["week"],
            "game_id": source["game_id"],
            "kickoff_utc": source["kickoff_utc"],
            "home_team": source["home_team"],
            "away_team": source["away_team"],
            "schedule_completed": source["schedule_completed"],
            "outcome_valid": source["outcome_valid"],
            "forecast_eligible": source["forecast_eligible"],
            "measurement_usable": source["measurement_usable"],
            "population_disposition": source["disposition"],
            "measurement_disposition": source["disposition"].where(
                source["measurement_usable"], "measurement_unavailable"
            ),
            "missing_reason": source["missing_reason"],
            "timing_class": source["timing_class"],
        }
    )
    result = (
        result.loc[:, POPULATION_COLUMNS]
        .sort_values(["season", "week", "game_id"], kind="mergesort")
        .reset_index(drop=True)
    )
    if (len(result), int(result["forecast_eligible"].sum())) != expected_counts:
        raise IndependentPossessionError(
            "Repair population totals differ from the 2026 extension declaration"
            if scope == "season_2026"
            else "Repair population totals differ from Contract 02"
        )
    return result


def _aliases() -> dict[str, str]:
    root = Path(__file__).resolve().parents[3]
    return dict(runpy.run_path(str(root / "contracts" / "teams.py"))["TEAM_LOGO_MAP"])


def _canonicalize_teams(frame: pd.DataFrame) -> pd.DataFrame:
    aliases = _aliases()
    result = frame.copy()
    for column in ("offense", "defense"):
        result[column] = result[column].map(
            lambda value: aliases.get(str(value).strip(), str(value).strip())
            if pd.notna(value)
            else None
        )
    return result


def _finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if np.isfinite(number) else None


def _period_class(value: Any) -> str:
    period = _finite_number(value)
    if period is None or period != int(period) or period < 1:
        return "unknown"
    return "overtime" if period >= 5 else "regulation"


def _contains(value: Any, markers: tuple[str, ...]) -> bool:
    text = str(value or "").casefold()
    return any(marker in text for marker in markers)


def _scrimmage_eligible(row: Any) -> bool:
    return (
        _period_class(row.quarter) == "regulation"
        and _finite_number(row.st) == 0
        and _finite_number(row.penalty) == 0
        and _finite_number(row.twopoint) == 0
        and _finite_number(row.garbage) == 0
        and not _contains(row.play_type, _NO_SCRIMMAGE)
    )


def _event_key(row: Any) -> str:
    return f"{int(row.season)}:{int(row.game_id)}:{int(row.drive_number)}:{int(row.play_number)}"


def _require(frame: pd.DataFrame, required: set[str], label: str) -> None:
    if missing := sorted(required - set(frame)):
        raise IndependentPossessionError(f"{label} lacks columns: {missing}")


def _reconstruct_ledgers(
    *,
    byplay: pd.DataFrame,
    population: pd.DataFrame,
    outcomes: pd.DataFrame | None = None,
    progress: ProgressCallback | None = None,
    scope: str = "historical",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if scope not in ("historical", "season_2026"):
        raise IndependentPossessionError(
            f"ledger reconstruction has unknown scope: {scope}"
        )
    row_timing = LIVE_TIMING if scope == "season_2026" else RECONSTRUCTED_TIMING
    plays = _canonicalize_teams(byplay)
    _require(
        plays,
        {
            "season",
            "week",
            "game_id",
            "drive_number",
            "play_number",
            "offense",
            "defense",
            "st",
            "penalty",
            "twopoint",
            "play_type",
            "garbage",
            "ppa",
            "quarter",
            "offense_score",
            "defense_score",
        },
        "byplay",
    )
    for column in ("season", "week", "game_id", "drive_number", "play_number"):
        plays[column] = pd.to_numeric(plays[column], errors="raise").astype(int)
    if plays.duplicated(["season", "game_id", "drive_number", "play_number"]).any():
        raise IndependentPossessionError("byplay contains duplicate stable play keys")
    membership = set(
        population[["season", "game_id"]].itertuples(index=False, name=None)
    )
    plays = plays.loc[
        plays[["season", "game_id"]].apply(tuple, axis=1).isin(membership)
    ].sort_values(
        ["season", "game_id", "quarter", "drive_number", "play_number"],
        kind="mergesort",
    )
    grouped_drives = plays.groupby(
        ["season", "game_id", "drive_number", "offense"], sort=False
    )
    drive_total = grouped_drives.ngroups
    if progress is not None:
        progress(
            "ledger_drive_index",
            force=True,
            completed=0,
            total=drive_total,
            rows=0,
        )

    possession_rows: list[dict[str, Any]] = []
    drive_by_key: dict[tuple[int, int, int, str], dict[str, Any]] = {}
    for drive_index, (key, drive_frame) in enumerate(grouped_drives, start=1):
        if progress is not None and drive_index % 1_000 == 0:
            progress(
                "ledger_drive_index",
                completed=drive_index,
                total=drive_total,
                rows=len(possession_rows),
            )
        season, game_id, drive_number, offense = key
        defenses = drive_frame["defense"].dropna().astype(str).unique().tolist()
        periods = {_period_class(value) for value in drive_frame["quarter"]}
        period = next(iter(periods)) if len(periods) == 1 else "unknown"
        drive_plays = tuple(drive_frame.itertuples(index=False))
        eligible_count = sum(_scrimmage_eligible(row) for row in drive_plays)
        row = {
            "season": int(season),
            "week": int(drive_frame["week"].iloc[0]),
            "game_id": int(game_id),
            "drive_number": int(drive_number),
            "offense": str(offense),
            "defense": defenses[0] if len(defenses) == 1 else None,
            "period_class": period,
            "eligible_play_count": int(eligible_count),
            "ineligible_play_count": int(len(drive_frame) - eligible_count),
            "mixed_eligibility": bool(
                eligible_count and eligible_count != len(drive_frame)
            ),
            "possession_eligible": bool(eligible_count),
            "source_play_ids": json.dumps([_event_key(play) for play in drive_plays]),
            "quality_reason": None
            if len(defenses) == 1 and period != "unknown"
            else "ambiguous_drive_identity_or_period",
            "timing_class": row_timing,
        }
        possession_rows.append(row)
        drive_by_key[(int(season), int(game_id), int(drive_number), str(offense))] = row
    if progress is not None:
        progress(
            "ledger_drive_index",
            force=True,
            completed=drive_total,
            total=drive_total,
            rows=len(possession_rows),
        )
    possessions = pd.DataFrame.from_records(possession_rows, columns=POSSESSION_COLUMNS)
    if possessions.duplicated(["season", "game_id", "drive_number", "offense"]).any():
        raise IndependentPossessionError(
            "independent possession ledger has duplicate keys"
        )
    if progress is not None:
        progress(
            "ledger_scoring_events",
            force=True,
            completed=0,
            total=len(plays),
            rows=len(possessions),
        )

    final_score_lookup: dict[tuple[int, int, str], float] = {}
    pop_scores = population
    if outcomes is not None and "home_points" not in population.columns:
        score_cols = [
            c
            for c in ("season", "game_id", "home_points", "away_points")
            if c in outcomes.columns
        ]
        if "home_points" in score_cols and "away_points" in score_cols:
            pop_scores = population.merge(
                outcomes[score_cols].drop_duplicates(["season", "game_id"]),
                on=["season", "game_id"],
                how="left",
            )
    for prow in pop_scores.itertuples(index=False):
        if getattr(prow, "outcome_valid", False):
            s = int(prow.season)
            g = int(prow.game_id)
            if hasattr(prow, "home_team") and hasattr(prow, "home_points"):
                if pd.notna(prow.home_points):
                    final_score_lookup[(s, g, str(prow.home_team))] = float(
                        prow.home_points
                    )
            if hasattr(prow, "away_team") and hasattr(prow, "away_points"):
                if pd.notna(prow.away_points):
                    final_score_lookup[(s, g, str(prow.away_team))] = float(
                        prow.away_points
                    )

    event_rows: list[dict[str, Any]] = []
    score_state: dict[tuple[int, int, str], float] = {}
    last_scoring_event: dict[tuple[int, int, str], str] = {}
    broken_streams: set[tuple[int, int, str]] = set()
    total = len(plays)
    for index, play in enumerate(plays.itertuples(index=False), start=1):
        if progress is not None and index % 10_000 == 0:
            progress("ledger_reconstruction", completed=index, total=total, rows=index)
        if _contains(play.play_type, _DEAD_MARKERS):
            continue
        source_event_id = _event_key(play)
        for team, reported_score in (
            (str(play.offense), play.offense_score),
            (str(play.defense), play.defense_score),
        ):
            stream_key = (int(play.season), int(play.game_id), team)
            if stream_key in broken_streams:
                continue
            score = _finite_number(reported_score)
            prior_score = score_state.get(stream_key, 0.0)

            # Score regression handling
            if (
                score is not None
                and score >= 0
                and score == int(score)
                and score < prior_score
            ):
                excess = int(prior_score - score)
                for item in reversed(event_rows):
                    if (
                        item["season"],
                        item["game_id"],
                        item["team"],
                    ) == stream_key and item["score_increment"] > 0:
                        inc = item["score_increment"]
                        if inc <= excess:
                            excess -= inc
                            item["score_increment"] = 0
                            item["quality_reason"] = "score_regression_rollback"
                        else:
                            item["score_increment"] -= excess
                            excess = 0
                        if excess == 0:
                            break
                score_state[stream_key] = score
                continue

            reason = (
                "missing_or_nonfinite_score"
                if score is None
                else "score_regression_or_nonintegral"
                if score < 0 or score != int(score)
                else "impossible_score_increment"
                if score - prior_score > 8
                else None
            )
            if reason is not None:
                event_rows.append(
                    {
                        "season": int(play.season),
                        "game_id": int(play.game_id),
                        "source_event_id": source_event_id,
                        "team": team,
                        "drive_number": int(play.drive_number),
                        "period_class": _period_class(play.quarter),
                        "score_increment": 0,
                        "scoring_category": "unresolved",
                        "unit_category": "unknown",
                        "associated_possession_id": None,
                        "conversion_for_event_id": None,
                        "quality_reason": reason,
                        "timing_class": row_timing,
                    }
                )
                broken_streams.add(stream_key)
                continue

            increment = score - prior_score
            if increment == 0:
                continue

            final_score = final_score_lookup.get(stream_key)
            if final_score is not None and prior_score + increment > final_score:
                rem = max(0.0, final_score - prior_score)
                if rem == 0.0:
                    event_rows.append(
                        {
                            "season": int(play.season),
                            "game_id": int(play.game_id),
                            "source_event_id": source_event_id,
                            "team": team,
                            "drive_number": int(play.drive_number),
                            "period_class": _period_class(play.quarter),
                            "score_increment": 0,
                            "scoring_category": "unresolved",
                            "unit_category": "unknown",
                            "associated_possession_id": None,
                            "conversion_for_event_id": None,
                            "quality_reason": "exceeds_repaired_final",
                            "timing_class": row_timing,
                        }
                    )
                    continue
                increment = rem
                score = prior_score + increment

            score_state[stream_key] = score
            if increment == 0:
                continue
            period = _period_class(play.quarter)
            possession = drive_by_key.get(
                (
                    int(play.season),
                    int(play.game_id),
                    int(play.drive_number),
                    str(play.offense),
                )
            )
            associated = source_event_id if possession is not None else None
            unit = "offense"
            category = "unresolved"
            quality_reason: str | None = None
            conversion_for = None
            if period == "unknown":
                unit, quality_reason = "unknown", "unknown_period"
            elif period == "overtime":
                unit = (
                    "non_offense"
                    if _contains(play.play_type, _OTHER_UNIT)
                    or team != str(play.offense)
                    else "offense"
                )
                category = "overtime"
            elif _finite_number(play.twopoint) == 1 or _contains(
                play.play_type, _TRY_MARKERS
            ):
                conversion_for = last_scoring_event.get(stream_key)
                if conversion_for is None:
                    unit, quality_reason = "unknown", "conversion_without_origin"
                else:
                    origin = next(
                        item
                        for item in reversed(event_rows)
                        if item["source_event_id"] == conversion_for
                    )
                    unit = str(origin["unit_category"])
                    category = str(origin["scoring_category"])
                    associated = origin["associated_possession_id"]
            elif _contains(play.play_type, _OTHER_UNIT) or team != str(play.offense):
                unit, category = "non_offense", "regulation_non_offense"
            elif possession is None or possession["quality_reason"] is not None:
                unit, quality_reason = "unknown", "ambiguous_possession"
            elif possession["possession_eligible"]:
                category = "eligible_regulation_offense"
            else:
                category = "excluded_regulation_offense"
            if category == "unresolved" and quality_reason is None:
                quality_reason = "unclassified_scoring_event"
            event_rows.append(
                {
                    "season": int(play.season),
                    "game_id": int(play.game_id),
                    "source_event_id": source_event_id,
                    "team": team,
                    "drive_number": int(play.drive_number),
                    "period_class": period,
                    "score_increment": int(increment),
                    "scoring_category": category,
                    "unit_category": unit,
                    "associated_possession_id": associated,
                    "conversion_for_event_id": conversion_for,
                    "quality_reason": quality_reason,
                    "timing_class": row_timing,
                }
            )
            if category not in {"overtime", "unresolved"}:
                last_scoring_event[stream_key] = source_event_id
    scoring = pd.DataFrame.from_records(event_rows, columns=SCORING_EVENT_COLUMNS)
    if scoring.duplicated(["season", "game_id", "source_event_id", "team"]).any():
        raise IndependentPossessionError(
            "independent scoring ledger has duplicate keys"
        )
    return plays, possessions, scoring


def _observation_row(
    *,
    game: Any,
    team: str,
    opponent: str,
    side: str,
    measurement: str,
    role: str,
    numerator: float,
    denominator: float,
    usable: bool,
    reason: str | None,
    flags: list[str],
    scope: str = "historical",
) -> dict[str, Any]:
    if scope not in ("historical", "season_2026"):
        raise IndependentPossessionError(f"observation row has unknown scope: {scope}")
    row_timing = LIVE_TIMING if scope == "season_2026" else RECONSTRUCTED_TIMING
    return {
        "season": int(game.season),
        "week": int(game.week),
        "game_id": int(game.game_id),
        "kickoff_utc": game.kickoff_utc,
        "team": team,
        "opponent": opponent,
        "side": side,
        "measurement_id": measurement,
        "unit_role": role,
        "numerator": float(numerator),
        "denominator": float(denominator),
        "raw_value": numerator / denominator if usable and denominator > 0 else None,
        "usable_exposure": float(denominator if usable else 0),
        "exposure_unit": "possessions"
        if measurement in {"ppp", "epa_per_possession", "plays_per_possession"}
        else "count",
        "coverage_status": "observed" if usable else "missing",
        "missing_reason": reason,
        "quality_flags": "|".join(sorted(set(flags))) or None,
        "timing_class": row_timing,
    }


def _reconstructed_team_game_aggregates(
    *,
    possessions: pd.DataFrame,
    plays: pd.DataFrame,
    scoring: pd.DataFrame,
) -> tuple[
    dict[tuple[int, int, str], tuple[float, bool]],
    dict[tuple[int, int, str], tuple[float, bool, float]],
    dict[tuple[int, int, str], tuple[float, float, bool, bool, float]],
    dict[tuple[int, int], tuple[float, float]],
]:
    """Independently index the team-game inputs used by the verifier grid.

    This deliberately mirrors the contract's aggregate meaning without calling
    producer code.  The observation loop retains population-major ordering.
    """
    drive_keys = ["season", "game_id", "offense"]
    qualifying_drives = possessions[possessions["possession_eligible"]]
    drive_values = {
        (int(season), int(game_id), str(team)): (
            float(len(frame)),
            bool(frame["mixed_eligibility"].any()),
        )
        for (season, game_id, team), frame in qualifying_drives.groupby(
            drive_keys, sort=False
        )
    }

    qualifying_plays = plays[plays["eligible_for_possession"]].copy()
    qualifying_plays["_reconstructed_ppa"] = pd.to_numeric(
        qualifying_plays["ppa"], errors="coerce"
    )
    play_values = {
        (int(season), int(game_id), str(team)): (
            float(len(frame)),
            bool(
                frame["_reconstructed_ppa"].isna().any()
                or ~np.isfinite(frame["_reconstructed_ppa"].dropna()).all()
            ),
            float(frame["_reconstructed_ppa"].sum()),
        )
        for (season, game_id, team), frame in qualifying_plays.groupby(
            drive_keys, sort=False
        )
    }

    event_values: dict[
        tuple[int, int, str], tuple[float, float, bool, bool, float]
    ] = {}
    for (season, game_id, team), frame in scoring.groupby(
        ["season", "game_id", "team"], sort=False
    ):
        event_values[(int(season), int(game_id), str(team))] = (
            float(
                frame.loc[
                    frame["scoring_category"] == "eligible_regulation_offense",
                    "score_increment",
                ].sum()
            ),
            float(
                frame.loc[
                    frame["scoring_category"] == "regulation_non_offense",
                    "score_increment",
                ].sum()
            ),
            bool(frame["scoring_category"].eq("unresolved").any()),
            bool(frame["quality_reason"].isin(_BROKEN_SCORE_REASONS).any()),
            float(frame["score_increment"].sum()),
        )
    game_values = {
        (int(season), int(game_id)): (
            float(frame["score_increment"].sum()),
            float(len(frame)),
        )
        for (season, game_id), frame in scoring.groupby(
            ["season", "game_id"], sort=False
        )
    }
    return drive_values, play_values, event_values, game_values


def reconstruct_measurements(
    *,
    byplay: pd.DataFrame,
    outcomes: pd.DataFrame,
    population: pd.DataFrame,
    progress: ProgressCallback | None = None,
    scope: str = "historical",
) -> IndependentMeasurements:
    """Independently derive team-game possession measurements and paired defense."""
    if scope not in ("historical", "season_2026"):
        raise IndependentPossessionError(f"reconstruction has unknown scope: {scope}")
    row_timing = LIVE_TIMING if scope == "season_2026" else RECONSTRUCTED_TIMING
    plays, possessions, scoring = _reconstruct_ledgers(
        byplay=byplay,
        population=population,
        outcomes=outcomes,
        progress=progress,
        scope=scope,
    )
    if progress is not None:
        progress(
            "team_game_measurements",
            force=True,
            completed=0,
            total=len(population),
            rows=0,
        )
    plays["eligible_for_possession"] = plays.apply(_scrimmage_eligible, axis=1)
    drive_values, play_values, event_values, game_values = (
        _reconstructed_team_game_aggregates(
            possessions=possessions, plays=plays, scoring=scoring
        )
    )
    observations: list[dict[str, Any]] = []
    reconciliation: dict[int, dict[str, float]] = {}
    for index, game in enumerate(population.itertuples(index=False), start=1):
        if progress is not None and index % 50 == 0:
            progress(
                "measurement_reconstruction",
                completed=index,
                total=len(population),
                rows=len(observations),
            )
        teams = (
            (str(game.home_team), str(game.away_team), "home"),
            (str(game.away_team), str(game.home_team), "away"),
        )
        measures: dict[
            str, dict[str, tuple[float, float, bool, str | None, list[str]]]
        ] = {}
        for team, _, _ in teams:
            key = (int(game.season), int(game.game_id), team)
            drive_count, mixed = drive_values.get(key, (0.0, False))
            eligible_play_count, bad_ppa, ppa_sum = play_values.get(
                key, (0.0, False, 0.0)
            )
            possession_points, other_points, unresolved, _, _ = event_values.get(
                key, (0.0, 0.0, False, False, 0.0)
            )
            flags = ["mixed_eligibility_drive"] if mixed else []
            points_ok = drive_count > 0 and not unresolved
            epa_ok = drive_count > 0 and not bad_ppa
            points_reason = (
                "zero_eligible_possessions"
                if drive_count == 0
                else ("unresolved_scoring_attribution" if unresolved else None)
            )
            ppa_reason = (
                "missing_or_nonfinite_eligible_ppa"
                if bad_ppa
                else ("zero_eligible_possessions" if drive_count == 0 else None)
            )
            epa_sum = ppa_sum if not bad_ppa else 0.0
            measures[team] = {
                "eligible_possessions": (drive_count, 1.0, True, None, flags),
                "offensive_possession_points": (
                    possession_points,
                    1.0,
                    points_ok,
                    points_reason,
                    flags,
                ),
                "ppp": (
                    possession_points,
                    drive_count,
                    points_ok,
                    points_reason,
                    flags,
                ),
                "eligible_epa": (epa_sum, 1.0, epa_ok, ppa_reason, flags),
                "epa_per_possession": (epa_sum, drive_count, epa_ok, ppa_reason, flags),
                "eligible_scrimmage_plays": (
                    eligible_play_count,
                    1.0,
                    True,
                    None,
                    flags,
                ),
                "plays_per_possession": (
                    eligible_play_count,
                    drive_count,
                    drive_count > 0,
                    "zero_eligible_possessions" if drive_count == 0 else None,
                    flags,
                ),
                "non_offense_points": (
                    other_points,
                    1.0,
                    not unresolved,
                    "unresolved_scoring_attribution" if unresolved else None,
                    flags,
                ),
            }
        for team, opponent, side in teams:
            for measurement in MEASUREMENTS:
                values = measures[team][measurement]
                observations.append(
                    _observation_row(
                        game=game,
                        team=team,
                        opponent=opponent,
                        side=side,
                        measurement=measurement,
                        role="offense",
                        numerator=values[0],
                        denominator=values[1],
                        usable=values[2],
                        reason=values[3],
                        flags=values[4],
                        scope=scope,
                    )
                )
                paired = measures[opponent][measurement]
                observations.append(
                    _observation_row(
                        game=game,
                        team=team,
                        opponent=opponent,
                        side=side,
                        measurement=measurement,
                        role="defense",
                        numerator=paired[0],
                        denominator=paired[1],
                        usable=paired[2],
                        reason=paired[3],
                        flags=paired[4],
                        scope=scope,
                    )
                )
        score_stream_points, event_count = game_values.get(
            (int(game.season), int(game.game_id)), (0.0, 0.0)
        )
        reconciliation[int(game.game_id)] = {
            "score_stream_points": score_stream_points,
            "event_count": event_count,
        }
    observation_frame = pd.DataFrame.from_records(
        observations, columns=OBSERVATION_COLUMNS
    )
    if observation_frame.duplicated(
        ["season", "game_id", "team", "measurement_id", "unit_role"]
    ).any():
        raise IndependentPossessionError(
            "independent observations contain duplicate keys"
        )
    coverage_rows: list[dict[str, Any]] = []
    for (season, measurement), frame in observation_frame.groupby(
        ["season", "measurement_id"], sort=True
    ):
        for slice_name in ("all", "fbs_fbs_or_fcs"):
            missing = frame[frame["coverage_status"] != "observed"]
            coverage_rows.append(
                {
                    "season": int(season),
                    "slice": slice_name,
                    "measurement_id": measurement,
                    "schedule_games": int(
                        population.loc[
                            population["season"] == season, "game_id"
                        ].nunique()
                    ),
                    "scoreable_games": int(
                        population.loc[
                            (population["season"] == season)
                            & population["forecast_eligible"],
                            "game_id",
                        ].nunique()
                    ),
                    "usable_team_games": int(
                        frame["coverage_status"].eq("observed").sum()
                    ),
                    "quarantined_team_games": int(len(missing)),
                    "reason_counts": json.dumps(
                        missing["missing_reason"]
                        .fillna("unknown")
                        .value_counts()
                        .sort_index()
                        .to_dict()
                    ),
                    "timing_class": row_timing,
                }
            )
    _require(outcomes, {"season", "game_id", "home_points", "away_points"}, "outcomes")
    outcomes = outcomes.copy()
    for column in ("season", "game_id"):
        outcomes[column] = pd.to_numeric(outcomes[column], errors="raise").astype(int)
    game_outcomes = population.merge(
        outcomes[["season", "game_id", "home_points", "away_points"]],
        on=["season", "game_id"],
        how="left",
        validate="one_to_one",
    )
    for season, games in game_outcomes.groupby("season", sort=True):
        exact = expected = quarantined = 0
        for game in games.itertuples(index=False):
            for team, points in (
                (game.home_team, game.home_points),
                (game.away_team, game.away_points),
            ):
                target = _finite_number(points)
                if target is None:
                    continue
                _, _, _, broken, actual = event_values.get(
                    (int(game.season), int(game.game_id), str(team)),
                    (0.0, 0.0, False, False, 0.0),
                )
                if broken:
                    quarantined += 1
                    continue
                expected += 1
                exact += int(actual == target)
        reconciliation[int(season)] = {
            "exact_team_scores": float(exact),
            "expected_team_scores": float(expected),
            "quarantined_team_scores": float(quarantined),
            "exact_rate": float(exact / expected) if expected else 0.0,
        }
    if any(
        value["exact_rate"] < 0.94
        for value in reconciliation.values()
        if "exact_rate" in value
    ):
        raise IndependentPossessionError(
            "independent final-score reconciliation is below 94%"
        )
    if progress is not None:
        progress(
            "measurement_reconstruction_complete",
            force=True,
            completed=len(population),
            total=len(population),
            rows=len(observations),
        )
    return IndependentMeasurements(
        possessions=possessions,
        scoring_events=scoring,
        observations=observation_frame,
        coverage=pd.DataFrame.from_records(coverage_rows, columns=COVERAGE_COLUMNS),
        final_reconciliation=reconciliation,
    )


def _four_pass_values(
    observations: pd.DataFrame,
) -> tuple[dict[tuple[str, str, str], float], dict[tuple[str, str, str], float]]:
    raw: dict[tuple[str, str, str], float] = {}
    for key, rows in observations.groupby(
        ["team", "unit_role", "measurement_id"], sort=False
    ):
        exposure = float(rows["denominator"].sum())
        if exposure > 0:
            raw[(str(key[0]), str(key[1]), str(key[2]))] = (
                float(rows["numerator"].sum()) / exposure
            )
    records = tuple(observations.itertuples(index=False))
    adjusted = dict(raw)
    for _pass in range(4):
        center_numerators: dict[tuple[str, str], float] = defaultdict(float)
        center_exposure: dict[tuple[str, str], float] = defaultdict(float)
        for record in records:
            exposure = float(record.denominator)
            key = (str(record.team), str(record.unit_role), str(record.measurement_id))
            if key in adjusted and exposure > 0:
                center_key = (key[1], key[2])
                center_numerators[center_key] += adjusted[key] * exposure
                center_exposure[center_key] += exposure
        centers = {
            key: center_numerators[key] / value
            for key, value in center_exposure.items()
            if value > 0
        }
        deltas: dict[tuple[str, str, str], float] = defaultdict(float)
        delta_exposure: dict[tuple[str, str, str], float] = defaultdict(float)
        for record in records:
            exposure = float(record.denominator)
            role = str(record.unit_role)
            metric = str(record.measurement_id)
            opponent_role = "defense" if role == "offense" else "offense"
            opponent_key = (str(record.opponent), opponent_role, metric)
            center_key = (opponent_role, metric)
            own_key = (str(record.team), role, metric)
            if opponent_key in adjusted and center_key in centers and exposure > 0:
                deltas[own_key] += (
                    adjusted[opponent_key] - centers[center_key]
                ) * exposure
                delta_exposure[own_key] += exposure
        updated = dict(raw)
        for key, baseline in raw.items():
            if delta_exposure[key] > 0:
                updated[key] = baseline - deltas[key] / delta_exposure[key]
        adjusted = updated
    return raw, adjusted


def reconstruct_replay_partitions(
    *,
    population: pd.DataFrame,
    observations: pd.DataFrame,
    emit: PartCallback,
    progress: ProgressCallback | None = None,
    scope: str = "historical",
) -> dict[str, Any]:
    """Reconstruct replay one season/week partition at a time."""
    if scope not in ("historical", "season_2026"):
        raise IndependentPossessionError(
            f"replay reconstruction has unknown scope: {scope}"
        )
    row_timing = LIVE_TIMING if scope == "season_2026" else RECONSTRUCTED_TIMING
    maximum_history_rows = 0
    for season in sorted(population["season"].astype(int).unique()):
        games = population[
            (population["season"] == season) & population["forecast_eligible"]
        ].sort_values(["week", "kickoff_utc", "game_id"], kind="mergesort")
        season_observations = observations[
            (observations["season"] == season)
            & observations["measurement_id"].isin({"ppp", "epa_per_possession"})
        ].copy()
        season_observations["kickoff_utc"] = pd.to_datetime(
            season_observations["kickoff_utc"], utc=True
        )
        season_observations["_available_utc"] = season_observations[
            "kickoff_utc"
        ] + pd.Timedelta(hours=6)
        usable = season_observations[
            season_observations["coverage_status"].eq("observed")
            & (season_observations["denominator"].astype(float) > 0)
        ]
        for week, target_games in games.groupby("week", sort=True):
            if progress is not None:
                progress("replay_reconstruction", season=int(season), week=int(week))
            candidates = usable[usable["week"].astype(int) < int(week)].sort_values(
                ["_available_utc", "game_id"], kind="mergesort"
            )
            source = candidates.iloc[0:0].copy()
            source_end = 0
            raw: dict[tuple[str, str, str], float] = {}
            adjusted: dict[tuple[str, str, str], float] = {}
            summaries: dict[tuple[str, str, str], tuple[float, float, int, int]] = {}
            snapshot_rows: list[dict[str, Any]] = []
            history_rows: list[dict[str, Any]] = []
            for game_index, game in enumerate(
                target_games.itertuples(index=False), start=1
            ):
                if progress is not None:
                    progress(
                        "replay_reconstruction",
                        season=int(season),
                        week=int(week),
                        completed=game_index,
                        total=len(target_games),
                        rows=len(history_rows),
                    )
                cutoff = pd.Timestamp(game.kickoff_utc)
                while (
                    source_end < len(candidates)
                    and candidates.iloc[source_end]["_available_utc"] <= cutoff
                ):
                    source_end += 1
                if source_end and source_end != len(source):
                    source = candidates.iloc[:source_end].copy()
                    raw, adjusted = _four_pass_values(source)
                    summaries = {
                        (str(key[0]), str(key[1]), str(key[2])): (
                            float(rows["numerator"].sum()),
                            float(rows["denominator"].sum()),
                            int(rows["game_id"].nunique()),
                            int(len(rows)),
                        )
                        for key, rows in source.groupby(
                            ["team", "unit_role", "measurement_id"], sort=False
                        )
                    }
                maximum_history_rows = max(maximum_history_rows, len(source))
                for record in source.itertuples(index=False):
                    key = (
                        str(record.team),
                        str(record.unit_role),
                        str(record.measurement_id),
                    )
                    history_rows.append(
                        {
                            "season": season,
                            "week": int(game.week),
                            "as_of_game_id": int(game.game_id),
                            "target_week_cutoff_utc": cutoff,
                            "source_season": int(record.season),
                            "source_week": int(record.week),
                            "source_game_id": int(record.game_id),
                            "source_kickoff_utc": record.kickoff_utc,
                            "source_available_utc": pd.Timestamp(record.kickoff_utc)
                            + pd.Timedelta(hours=6),
                            "team": record.team,
                            "opponent": record.opponent,
                            "measurement_id": record.measurement_id,
                            "unit_role": record.unit_role,
                            "adjustment_iteration": 4,
                            "numerator": float(record.numerator),
                            "denominator": float(record.denominator),
                            "iteration_zero_value": raw.get(key),
                            "iteration_four_value": adjusted.get(key),
                            "included": True,
                            "missing_reason": None,
                            "timing_class": row_timing,
                        }
                    )
                for team in (str(game.home_team), str(game.away_team)):
                    for role in ("offense", "defense"):
                        for metric in ("ppp", "epa_per_possession"):
                            key = (team, role, metric)
                            numerator, exposure, games_exposure, source_count = (
                                summaries.get(key, (0.0, 0.0, 0, 0))
                            )
                            for iteration, value in (
                                (0, raw.get(key)),
                                (4, adjusted.get(key)),
                            ):
                                snapshot_rows.append(
                                    {
                                        "season": season,
                                        "week": int(game.week),
                                        "as_of_game_id": int(game.game_id),
                                        "as_of_kickoff_utc": cutoff,
                                        "target_week_cutoff_utc": cutoff,
                                        "team": team,
                                        "measurement_id": metric,
                                        "unit_role": role,
                                        "adjustment_iteration": iteration,
                                        "raw_value": numerator / exposure
                                        if exposure
                                        else None,
                                        "adjusted_value": value,
                                        "primary_exposure": exposure,
                                        "games_exposure": games_exposure,
                                        "source_game_count": source_count,
                                        "timing_class": row_timing,
                                        "availability_policy": "prior_week_and_source_kickoff_plus_6h",
                                    }
                                )
            emit(
                "snapshots",
                {"season": int(season), "week": int(week)},
                pd.DataFrame.from_records(snapshot_rows, columns=SNAPSHOT_COLUMNS),
            )
            if history_rows:
                emit(
                    "adjusted_history",
                    {"season": int(season), "week": int(week)},
                    pd.DataFrame.from_records(history_rows, columns=HISTORY_COLUMNS),
                )
        observed = season_observations[
            season_observations["coverage_status"].eq("observed")
            & (season_observations["denominator"].astype(float) > 0)
        ]
        raw, adjusted = _four_pass_values(observed)
        terminal_rows: list[dict[str, Any]] = []
        for key, value in adjusted.items():
            team, role, metric = key
            rows = observed[
                (observed["team"] == team)
                & (observed["unit_role"] == role)
                & (observed["measurement_id"] == metric)
            ]
            terminal_rows.append(
                {
                    "season": season,
                    "team": team,
                    "measurement_id": metric,
                    "unit_role": role,
                    "adjustment_iteration": 4,
                    "raw_value": raw.get(key),
                    "adjusted_value": value,
                    "primary_exposure": float(rows["denominator"].sum()),
                    "games_exposure": int(rows["game_id"].nunique()),
                    "source_game_count": int(len(rows)),
                    "timing_class": row_timing,
                }
            )
        emit(
            "terminal",
            {"season": int(season)},
            pd.DataFrame.from_records(terminal_rows, columns=TERMINAL_COLUMNS),
        )
    return {
        "max_history_partition_rows": maximum_history_rows,
        "iterations": [0, 4],
        "adjustment_method": "iterative_additive_league_centered",
    }
