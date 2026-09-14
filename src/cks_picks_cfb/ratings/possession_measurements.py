"""Deterministic possession and scoring ledgers for V5 research.

The old score-stream helper is deliberately not used as a numerator: it proves
only final reconciliation, while this module records the unit attribution that
PPP requires.  All ambiguous evidence is quarantined rather than inferred.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from cks_picks_cfb.data.data_first_possession_v1 import (
    COVERAGE_COLUMNS,
    HISTORY_COLUMNS,
    MEASUREMENTS,
    OBSERVATION_COLUMNS,
    POSSESSION_COLUMNS,
    SCORING_EVENT_COLUMNS,
    SNAPSHOT_COLUMNS,
    TERMINAL_COLUMNS,
)

_DEAD_MARKERS = ("timeout", "end of", "period end", "game end", "delay of game")
_NON_OFFENSE_MARKERS = (
    "interception",
    "fumble",
    "punt",
    "kickoff",
    "blocked",
    "safety",
    "return",
)
_CONVERSION_MARKERS = ("two point", "2-point", "extra point", "conversion")
_MALFORMED_SCORE_REASONS = {
    "missing_or_nonfinite_score",
    "score_regression_or_nonintegral",
    "impossible_score_increment",
}


class PossessionMeasurementError(ValueError):
    """Raised for malformed score streams or incompatible source records."""


@dataclass(frozen=True)
class PossessionMeasurementResult:
    possessions: pd.DataFrame
    scoring_events: pd.DataFrame
    observations: pd.DataFrame
    coverage: pd.DataFrame
    final_reconciliation: dict[int, dict[str, float]]


def _num(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if np.isfinite(result) else None


def _period(value: Any) -> str:
    numeric = _num(value)
    if numeric is None or numeric != int(numeric) or numeric < 1:
        return "unknown"
    return "overtime" if numeric >= 5 else "regulation"


def _dead_play(value: Any) -> bool:
    text = str(value or "").casefold()
    return any(marker in text for marker in _DEAD_MARKERS)


def _non_offense_play(value: Any) -> bool:
    text = str(value or "").casefold()
    return any(marker in text for marker in _NON_OFFENSE_MARKERS)


def _conversion_play(value: Any, twopoint: Any) -> bool:
    text = str(value or "").casefold()
    return _num(twopoint) == 1 or any(marker in text for marker in _CONVERSION_MARKERS)


def _eligible_play(row: Any) -> bool:
    return (
        _period(row.quarter) == "regulation"
        and _num(row.st) == 0
        and _num(row.penalty) == 0
        and _num(row.twopoint) == 0
        and _num(row.garbage) == 0
        and not _dead_play(row.play_type)
    )


def _source_id(row: Any) -> str:
    return f"{int(row.season)}:{int(row.game_id)}:{int(row.drive_number)}:{int(row.play_number)}"


def _required(frame: pd.DataFrame, columns: set[str], label: str) -> None:
    missing = sorted(columns - set(frame.columns))
    if missing:
        raise PossessionMeasurementError(f"{label} is missing columns: {missing}")


def build_possession_ledger(
    *, byplay: pd.DataFrame, population: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build regulation possession eligibility and score-attribution ledgers."""
    _required(
        byplay,
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
    known_games = set(
        population[["season", "game_id"]].itertuples(index=False, name=None)
    )
    plays = byplay.copy()
    for name in ("season", "week", "game_id", "drive_number", "play_number"):
        plays[name] = pd.to_numeric(plays[name], errors="raise").astype(int)
    if plays.duplicated(["season", "game_id", "drive_number", "play_number"]).any():
        raise PossessionMeasurementError("byplay has duplicate stable source play IDs")
    plays = plays.loc[
        plays.apply(
            lambda row: (int(row.season), int(row.game_id)) in known_games, axis=1
        )
    ].sort_values(
        ["season", "game_id", "quarter", "drive_number", "play_number"],
        kind="mergesort",
    )

    possession_records: list[dict[str, Any]] = []
    possession_lookup: dict[tuple[int, int, int, str], dict[str, Any]] = {}
    for key, group in plays.groupby(
        ["season", "game_id", "drive_number", "offense"], sort=False
    ):
        season, game_id, drive, offense = key
        defenses = group["defense"].dropna().astype(str).unique().tolist()
        periods = {_period(value) for value in group["quarter"]}
        period_class = periods.pop() if len(periods) == 1 else "unknown"
        eligible = [row for row in group.itertuples(index=False) if _eligible_play(row)]
        record = {
            "season": int(season),
            "week": int(group["week"].iloc[0]),
            "game_id": int(game_id),
            "drive_number": int(drive),
            "offense": str(offense),
            "defense": defenses[0] if len(defenses) == 1 else None,
            "period_class": period_class,
            "eligible_play_count": len(eligible),
            "ineligible_play_count": int(len(group) - len(eligible)),
            "mixed_eligibility": bool(eligible and len(eligible) != len(group)),
            "possession_eligible": bool(eligible),
            "source_play_ids": json.dumps(
                [_source_id(row) for row in group.itertuples(index=False)]
            ),
            "quality_reason": None
            if len(defenses) == 1 and period_class != "unknown"
            else "ambiguous_drive_identity_or_period",
            "timing_class": "historically_reconstructed",
        }
        possession_records.append(record)
        possession_lookup[(int(season), int(game_id), int(drive), str(offense))] = (
            record
        )
    possessions = pd.DataFrame.from_records(
        possession_records, columns=POSSESSION_COLUMNS
    )
    if possessions.duplicated(["season", "game_id", "drive_number", "offense"]).any():
        raise PossessionMeasurementError("possession ledger has duplicate keys")

    events: list[dict[str, Any]] = []
    active_event: dict[tuple[int, int, str], str] = {}
    prior_scores: dict[tuple[int, int, str], float] = {}
    malformed_scores: set[tuple[int, int, str]] = set()
    for row in plays.itertuples(index=False):
        event_id = _source_id(row)
        for team, score in (
            (str(row.offense), row.offense_score),
            (str(row.defense), row.defense_score),
        ):
            key = (int(row.season), int(row.game_id), team)
            if key in malformed_scores:
                continue
            current = _num(score)
            previous = prior_scores.get(key, 0.0)
            malformed_reason = (
                "missing_or_nonfinite_score"
                if current is None
                else "score_regression_or_nonintegral"
                if current < 0 or current < previous or current != int(current)
                else "impossible_score_increment"
                if current - previous > 8
                else None
            )
            if malformed_reason is not None:
                # Do not synthesize a balancing score from a malformed stream.
                # The zero-point unresolved marker makes the quarantine explicit
                # while preserving the schedule row and all independent EPA data.
                events.append(
                    {
                        "season": int(row.season),
                        "game_id": int(row.game_id),
                        "source_event_id": event_id,
                        "team": team,
                        "drive_number": int(row.drive_number),
                        "period_class": _period(row.quarter),
                        "score_increment": 0,
                        "scoring_category": "unresolved",
                        "unit_category": "unknown",
                        "associated_possession_id": None,
                        "conversion_for_event_id": None,
                        "quality_reason": malformed_reason,
                        "timing_class": "historically_reconstructed",
                    }
                )
                malformed_scores.add(key)
                continue
            prior_scores[key] = current
            increment = current - previous
            if increment == 0:
                continue
            period_class = _period(row.quarter)
            possession = possession_lookup.get(
                (
                    int(row.season),
                    int(row.game_id),
                    int(row.drive_number),
                    str(row.offense),
                )
            )
            associated = event_id if possession is not None else None
            unit = "offense"
            category = "unresolved"
            reason: str | None = None
            conversion_for = None
            if period_class == "unknown":
                unit, reason = "unknown", "unknown_period"
            elif period_class == "overtime":
                unit = (
                    "non_offense"
                    if _non_offense_play(row.play_type) or team != str(row.offense)
                    else "offense"
                )
                category = "overtime"
            elif _conversion_play(row.play_type, row.twopoint):
                previous_event = active_event.get(key)
                if previous_event is None:
                    unit, reason = "unknown", "conversion_without_origin"
                else:
                    conversion_for = previous_event
                    prior = next(
                        item
                        for item in reversed(events)
                        if item["source_event_id"] == previous_event
                    )
                    unit, category, associated = (
                        prior["unit_category"],
                        prior["scoring_category"],
                        prior["associated_possession_id"],
                    )
            elif _non_offense_play(row.play_type) or team != str(row.offense):
                unit, category = "non_offense", "regulation_non_offense"
            elif possession is None or possession["quality_reason"] is not None:
                unit, reason = "unknown", "ambiguous_possession"
            elif possession["possession_eligible"]:
                category = "eligible_regulation_offense"
            else:
                category = "excluded_regulation_offense"
            if category == "unresolved" and reason is None:
                reason = "unclassified_scoring_event"
            item = {
                "season": int(row.season),
                "game_id": int(row.game_id),
                "source_event_id": event_id,
                "team": team,
                "drive_number": int(row.drive_number),
                "period_class": period_class,
                "score_increment": int(increment),
                "scoring_category": category,
                "unit_category": unit,
                "associated_possession_id": associated,
                "conversion_for_event_id": conversion_for,
                "quality_reason": reason,
                "timing_class": "historically_reconstructed",
            }
            events.append(item)
            if category != "overtime" and category != "unresolved":
                active_event[key] = event_id
    scoring = pd.DataFrame.from_records(events, columns=SCORING_EVENT_COLUMNS)
    if scoring.duplicated(["season", "game_id", "source_event_id", "team"]).any():
        raise PossessionMeasurementError(
            "scoring ledger has duplicate stable event keys"
        )
    if (
        not scoring.empty
        and ((scoring["score_increment"] < 0) | (scoring["score_increment"] > 8)).any()
    ):
        raise PossessionMeasurementError(
            "scoring ledger has non-integral or impossible event points"
        )
    return possessions, scoring


def _observation(
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
) -> dict[str, Any]:
    value = numerator / denominator if usable and denominator > 0 else None
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
        "raw_value": value,
        "usable_exposure": float(denominator if usable else 0),
        "exposure_unit": "possessions"
        if measurement in {"ppp", "epa_per_possession", "plays_per_possession"}
        else "count",
        "coverage_status": "observed" if usable else "missing",
        "missing_reason": reason,
        "quality_flags": "|".join(sorted(set(flags))) or None,
        "timing_class": "historically_reconstructed",
    }


def build_measurements(
    *,
    byplay: pd.DataFrame,
    population: pd.DataFrame,
    outcomes: pd.DataFrame | None = None,
) -> PossessionMeasurementResult:
    """Build both role measurements while preserving every scoreable game row."""
    possessions, scoring = build_possession_ledger(byplay=byplay, population=population)
    plays = byplay.copy()
    for name in ("season", "game_id", "drive_number", "play_number"):
        plays[name] = pd.to_numeric(plays[name], errors="coerce")
    eligible_play = plays.apply(lambda row: _eligible_play(row), axis=1)
    plays["eligible_for_possession"] = eligible_play
    records: list[dict[str, Any]] = []
    reconciliation: dict[int, dict[str, float]] = {}
    for game in population.itertuples(index=False):
        teams = (
            (str(game.home_team), str(game.away_team), "home"),
            (str(game.away_team), str(game.home_team), "away"),
        )
        base: dict[
            str, dict[str, tuple[float, float, bool, str | None, list[str]]]
        ] = {}
        for team, opponent, side in teams:
            team_possessions = possessions[
                (possessions["season"] == game.season)
                & (possessions["game_id"] == game.game_id)
                & (possessions["offense"] == team)
            ]
            eligible = team_possessions[team_possessions["possession_eligible"]]
            count = float(len(eligible))
            game_plays = plays[
                (plays["season"] == game.season)
                & (plays["game_id"] == game.game_id)
                & (plays["offense"] == team)
                & plays["eligible_for_possession"]
            ]
            ppa = pd.to_numeric(
                game_plays.get("ppa", pd.Series(dtype=float)), errors="coerce"
            )
            ppa_invalid = bool(ppa.isna().any() or ~np.isfinite(ppa.dropna()).all())
            events = scoring[
                (scoring["season"] == game.season)
                & (scoring["game_id"] == game.game_id)
                & (scoring["team"] == team)
            ]
            eligible_points = float(
                events.loc[
                    events["scoring_category"] == "eligible_regulation_offense",
                    "score_increment",
                ].sum()
            )
            non_offense = float(
                events.loc[
                    events["scoring_category"] == "regulation_non_offense",
                    "score_increment",
                ].sum()
            )
            unresolved = bool((events["scoring_category"] == "unresolved").any())
            flags = (
                ["mixed_eligibility_drive"]
                if bool(eligible.get("mixed_eligibility", pd.Series(dtype=bool)).any())
                else []
            )
            ppp_usable = count > 0 and not unresolved
            epa_usable = count > 0 and not ppa_invalid
            noff_usable = not unresolved
            reason = (
                "zero_eligible_possessions"
                if count == 0
                else ("unresolved_scoring_attribution" if unresolved else None)
            )
            base[team] = {
                "eligible_possessions": (count, 1.0, True, None, flags),
                "offensive_possession_points": (
                    eligible_points,
                    1.0,
                    ppp_usable,
                    reason,
                    flags,
                ),
                "ppp": (eligible_points, count, ppp_usable, reason, flags),
                "eligible_epa": (
                    float(ppa.sum()) if not ppa_invalid else 0.0,
                    1.0,
                    epa_usable,
                    "missing_or_nonfinite_eligible_ppa"
                    if ppa_invalid
                    else ("zero_eligible_possessions" if count == 0 else None),
                    flags,
                ),
                "epa_per_possession": (
                    float(ppa.sum()) if not ppa_invalid else 0.0,
                    count,
                    epa_usable,
                    "missing_or_nonfinite_eligible_ppa"
                    if ppa_invalid
                    else ("zero_eligible_possessions" if count == 0 else None),
                    flags,
                ),
                "eligible_scrimmage_plays": (
                    float(len(game_plays)),
                    1.0,
                    True,
                    None,
                    flags,
                ),
                "plays_per_possession": (
                    float(len(game_plays)),
                    count,
                    count > 0,
                    "zero_eligible_possessions" if count == 0 else None,
                    flags,
                ),
                "non_offense_points": (
                    non_offense,
                    1.0,
                    noff_usable,
                    "unresolved_scoring_attribution" if unresolved else None,
                    flags,
                ),
            }
        for team, opponent, side in teams:
            for measurement in MEASUREMENTS:
                numerator, denominator, usable, reason, flags = base[team][measurement]
                records.append(
                    _observation(
                        game=game,
                        team=team,
                        opponent=opponent,
                        side=side,
                        measurement=measurement,
                        role="offense",
                        numerator=numerator,
                        denominator=denominator,
                        usable=usable,
                        reason=reason,
                        flags=flags,
                    )
                )
                numerator, denominator, usable, reason, flags = base[opponent][
                    measurement
                ]
                records.append(
                    _observation(
                        game=game,
                        team=team,
                        opponent=opponent,
                        side=side,
                        measurement=measurement,
                        role="defense",
                        numerator=numerator,
                        denominator=denominator,
                        usable=usable,
                        reason=reason,
                        flags=flags,
                    )
                )
        events_game = scoring[
            (scoring["season"] == game.season) & (scoring["game_id"] == game.game_id)
        ]
        reconciliation[int(game.game_id)] = {
            "score_stream_points": float(events_game["score_increment"].sum()),
            "event_count": float(len(events_game)),
        }
    observations = pd.DataFrame.from_records(records, columns=OBSERVATION_COLUMNS)
    if observations.duplicated(
        ["season", "game_id", "team", "measurement_id", "unit_role"]
    ).any():
        raise PossessionMeasurementError("observation grid has duplicate keys")
    coverage_records: list[dict[str, Any]] = []
    for (season, measurement), frame in observations.groupby(
        ["season", "measurement_id"], sort=True
    ):
        for slice_name, subset in (("all", frame), ("fbs_fbs_or_fcs", frame)):
            missing = subset[subset["coverage_status"] != "observed"]
            coverage_records.append(
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
                        (subset["coverage_status"] == "observed").sum()
                    ),
                    "quarantined_team_games": int(len(missing)),
                    "reason_counts": json.dumps(
                        missing["missing_reason"]
                        .fillna("unknown")
                        .value_counts()
                        .sort_index()
                        .to_dict()
                    ),
                    "timing_class": "historically_reconstructed",
                }
            )
    if outcomes is not None:
        _required(
            outcomes, {"season", "game_id", "home_points", "away_points"}, "outcomes"
        )
        outcomes = outcomes.copy()
        outcomes["season"] = pd.to_numeric(outcomes["season"], errors="raise").astype(
            int
        )
        outcomes["game_id"] = pd.to_numeric(outcomes["game_id"], errors="raise").astype(
            int
        )
        expected_by_game = population.merge(
            outcomes[["season", "game_id", "home_points", "away_points"]],
            on=["season", "game_id"],
            how="left",
            validate="one_to_one",
        )
        for season, games in expected_by_game.groupby("season", sort=True):
            exact, expected, quarantined = 0, 0, 0
            for game in games.itertuples(index=False):
                for team, outcome_points in (
                    (game.home_team, game.home_points),
                    (game.away_team, game.away_points),
                ):
                    numeric = _num(outcome_points)
                    if numeric is None:
                        continue
                    team_events = scoring[
                        (scoring["season"] == game.season)
                        & (scoring["game_id"] == game.game_id)
                        & (scoring["team"] == team)
                    ]
                    if (
                        team_events["quality_reason"]
                        .isin(_MALFORMED_SCORE_REASONS)
                        .any()
                    ):
                        quarantined += 1
                        continue
                    expected += 1
                    actual = float(team_events["score_increment"].sum())
                    exact += int(actual == numeric)
            reconciliation[int(season)] = {
                "exact_team_scores": float(exact),
                "expected_team_scores": float(expected),
                "quarantined_team_scores": float(quarantined),
                "exact_rate": float(exact / expected) if expected else 0.0,
            }
        if any(
            values["exact_rate"] < 0.94
            for values in reconciliation.values()
            if "exact_rate" in values
        ):
            raise PossessionMeasurementError(
                "season final-score reconciliation is below 94%"
            )
    return PossessionMeasurementResult(
        possessions,
        scoring,
        observations,
        pd.DataFrame.from_records(coverage_records, columns=COVERAGE_COLUMNS),
        reconciliation,
    )


def _adjust(
    history: pd.DataFrame,
) -> tuple[dict[tuple[str, str, str], float], dict[tuple[str, str, str], float]]:
    """Return iteration-zero and four-pass league-centered values by team/role/metric."""
    raw: dict[tuple[str, str, str], float] = {}
    for key, group in history.groupby(
        ["team", "unit_role", "measurement_id"], sort=False
    ):
        denominator = float(group["denominator"].sum())
        if denominator > 0:
            raw[(str(key[0]), str(key[1]), str(key[2]))] = (
                float(group["numerator"].sum()) / denominator
            )
    # Materialize the small, cutoff-bounded source once.  The original replay
    # repeatedly filtered a full DataFrame for every team/role key and pass,
    # which grows quadratically with season history.
    rows = tuple(history.itertuples(index=False))
    adjusted = dict(raw)
    for _ in range(4):
        center_numerators: dict[tuple[str, str], float] = defaultdict(float)
        center_denominators: dict[tuple[str, str], float] = defaultdict(float)
        for row in rows:
            denominator = float(row.denominator)
            key = (str(row.team), str(row.unit_role), str(row.measurement_id))
            value = adjusted.get(key)
            if value is not None and denominator > 0:
                center_key = (str(row.unit_role), str(row.measurement_id))
                center_numerators[center_key] += value * denominator
                center_denominators[center_key] += denominator
        centers = {
            key: center_numerators[key] / denominator
            for key, denominator in center_denominators.items()
            if denominator > 0
        }
        delta_numerators: dict[tuple[str, str, str], float] = defaultdict(float)
        delta_denominators: dict[tuple[str, str, str], float] = defaultdict(float)
        for row in rows:
            denominator = float(row.denominator)
            role, metric = str(row.unit_role), str(row.measurement_id)
            opponent_role = "defense" if role == "offense" else "offense"
            center = centers.get((opponent_role, metric))
            opponent = adjusted.get((str(row.opponent), opponent_role, metric))
            key = (str(row.team), role, metric)
            if center is not None and opponent is not None and denominator > 0:
                delta_numerators[key] += (opponent - center) * denominator
                delta_denominators[key] += denominator
        next_values = dict(raw)
        for key, baseline in raw.items():
            denominator = delta_denominators[key]
            if denominator > 0:
                next_values[key] = baseline - delta_numerators[key] / denominator
        adjusted = next_values
    return raw, adjusted


ReplayPartSink = Callable[[str, dict[str, int], pd.DataFrame], None]


def replay_partitions(
    *,
    population: pd.DataFrame,
    observations: pd.DataFrame,
    emit: ReplayPartSink,
) -> dict[str, Any]:
    """Emit replay records one declared season/week partition at a time.

    Producers and verifiers use this streaming path so cutoff history is never
    retained beyond a single logical partition.  ``build_replay`` remains a
    small-fixture convenience wrapper for focused unit tests.
    """
    max_history = 0
    for season in sorted(population["season"].astype(int).unique()):
        games = population[
            (population["season"] == season) & population["forecast_eligible"]
        ].sort_values(["week", "kickoff_utc", "game_id"], kind="mergesort")
        season_obs = observations[
            (observations["season"] == season)
            & observations["measurement_id"].isin({"ppp", "epa_per_possession"})
        ].copy()
        season_obs["kickoff_utc"] = pd.to_datetime(season_obs["kickoff_utc"], utc=True)
        season_obs["_available_utc"] = season_obs["kickoff_utc"] + pd.Timedelta(hours=6)
        eligible_obs = season_obs[
            (season_obs["coverage_status"] == "observed")
            & (season_obs["denominator"].astype(float) > 0)
        ].copy()
        for week, games_in_week in games.groupby("week", sort=True):
            snapshots: list[dict[str, Any]] = []
            histories: list[dict[str, Any]] = []
            candidates = eligible_obs[
                eligible_obs["week"].astype(int) < int(week)
            ].sort_values(["_available_utc", "game_id"], kind="mergesort")
            source = candidates.iloc[0:0].copy()
            source_end = 0
            raw: dict[tuple[str, str, str], float] = {}
            adjusted: dict[tuple[str, str, str], float] = {}
            summaries: dict[tuple[str, str, str], tuple[float, float, int, int]] = {}
            for game in games_in_week.itertuples(index=False):
                cutoff = pd.Timestamp(game.kickoff_utc)
                while (
                    source_end < len(candidates)
                    and candidates.iloc[source_end]["_available_utc"] <= cutoff
                ):
                    source_end += 1
                if source_end and source_end != len(source):
                    # A source game has role rows for each side; calculate the
                    # four-pass adjustment once per distinct prior source set,
                    # then reuse it for all same-week target games that have
                    # the identical availability boundary.
                    source = candidates.iloc[:source_end].copy()
                    raw, adjusted = _adjust(source)
                    grouped = source.groupby(
                        ["team", "unit_role", "measurement_id"], sort=False
                    )
                    summaries = {
                        (str(key[0]), str(key[1]), str(key[2])): (
                            float(rows["numerator"].sum()),
                            float(rows["denominator"].sum()),
                            int(rows["game_id"].nunique()),
                            int(len(rows)),
                        )
                        for key, rows in grouped
                    }
                max_history = max(max_history, len(source))
                for row in source.itertuples(index=False):
                    key = (str(row.team), str(row.unit_role), str(row.measurement_id))
                    histories.append(
                        {
                            "season": season,
                            "week": int(game.week),
                            "as_of_game_id": int(game.game_id),
                            "target_week_cutoff_utc": cutoff,
                            "source_season": int(row.season),
                            "source_week": int(row.week),
                            "source_game_id": int(row.game_id),
                            "source_kickoff_utc": row.kickoff_utc,
                            "source_available_utc": pd.Timestamp(row.kickoff_utc)
                            + pd.Timedelta(hours=6),
                            "team": row.team,
                            "opponent": row.opponent,
                            "measurement_id": row.measurement_id,
                            "unit_role": row.unit_role,
                            "adjustment_iteration": 4,
                            "numerator": float(row.numerator),
                            "denominator": float(row.denominator),
                            "iteration_zero_value": raw.get(key),
                            "iteration_four_value": adjusted.get(key),
                            "included": True,
                            "missing_reason": None,
                            "timing_class": "historically_reconstructed",
                        }
                    )
                for team in (str(game.home_team), str(game.away_team)):
                    for role in ("offense", "defense"):
                        for measurement in ("ppp", "epa_per_possession"):
                            key = (team, role, measurement)
                            numerator, denom, games_exposure, source_game_count = (
                                summaries.get(key, (0.0, 0.0, 0, 0))
                            )
                            for iteration, value in (
                                (0, raw.get(key)),
                                (4, adjusted.get(key)),
                            ):
                                snapshots.append(
                                    {
                                        "season": season,
                                        "week": int(game.week),
                                        "as_of_game_id": int(game.game_id),
                                        "as_of_kickoff_utc": cutoff,
                                        "target_week_cutoff_utc": cutoff,
                                        "team": team,
                                        "measurement_id": measurement,
                                        "unit_role": role,
                                        "adjustment_iteration": iteration,
                                        "raw_value": numerator / denom
                                        if denom
                                        else None,
                                        "adjusted_value": value,
                                        "primary_exposure": denom,
                                        "games_exposure": games_exposure,
                                        "source_game_count": source_game_count,
                                        "timing_class": "historically_reconstructed",
                                        "availability_policy": "prior_week_and_source_kickoff_plus_6h",
                                    }
                                )
            emit(
                "snapshots",
                {"season": int(season), "week": int(week)},
                pd.DataFrame.from_records(snapshots, columns=SNAPSHOT_COLUMNS),
            )
            if histories:
                emit(
                    "adjusted_history",
                    {"season": int(season), "week": int(week)},
                    pd.DataFrame.from_records(histories, columns=HISTORY_COLUMNS),
                )
        observed = season_obs[
            (season_obs["coverage_status"] == "observed")
            & (season_obs["denominator"].astype(float) > 0)
        ]
        raw, adjusted = _adjust(observed)
        terminal: list[dict[str, Any]] = []
        for key, value in adjusted.items():
            team, role, measurement = key
            rows = observed[
                (observed["team"] == team)
                & (observed["unit_role"] == role)
                & (observed["measurement_id"] == measurement)
            ]
            terminal.append(
                {
                    "season": season,
                    "team": team,
                    "measurement_id": measurement,
                    "unit_role": role,
                    "adjustment_iteration": 4,
                    "raw_value": raw.get(key),
                    "adjusted_value": value,
                    "primary_exposure": float(rows["denominator"].sum()),
                    "games_exposure": int(rows["game_id"].nunique()),
                    "source_game_count": int(len(rows)),
                    "timing_class": "historically_reconstructed",
                }
            )
        emit(
            "terminal",
            {"season": int(season)},
            pd.DataFrame.from_records(terminal, columns=TERMINAL_COLUMNS),
        )
    return {
        "max_history_partition_rows": max_history,
        "iterations": [0, 4],
        "adjustment_method": "iterative_additive_league_centered",
    }


def build_replay(
    *, population: pd.DataFrame, observations: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Build replay frames for small fixtures; production callers stream parts."""
    parts: dict[str, list[pd.DataFrame]] = defaultdict(list)

    def collect(_: str, __: dict[str, int], frame: pd.DataFrame) -> None:
        parts[_].append(frame)

    evidence = replay_partitions(
        population=population,
        observations=observations,
        emit=collect,
    )

    def frame_for(name: str, columns: tuple[str, ...]) -> pd.DataFrame:
        return pd.DataFrame.from_records(
            [record for frame in parts[name] for record in frame.to_dict("records")],
            columns=columns,
        )

    return (
        frame_for("snapshots", SNAPSHOT_COLUMNS),
        frame_for("adjusted_history", HISTORY_COLUMNS),
        frame_for("terminal", TERMINAL_COLUMNS),
        evidence,
    )
