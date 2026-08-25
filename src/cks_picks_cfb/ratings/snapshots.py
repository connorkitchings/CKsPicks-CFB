"""Strictly pregame adjusted measurement snapshots for rating research.

The builder walks scheduled games in ``(kickoff_utc, game_id)`` order and forms
each evidence graph exclusively from observations whose kickoff and, when
authentic, effective time precede the target kickoff. Opponent adjustment is
applied exactly once, here, over that frozen history.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from cks_picks_cfb.ratings.contracts import (
    ADJUSTMENT_METHOD_ADJUSTED,
    ADJUSTMENT_METHOD_NONE,
    SNAPSHOT_COLUMNS,
    SNAPSHOT_SCHEMA_VERSION,
    TERMINAL_SNAPSHOT_COLUMNS,
    TERMINAL_SNAPSHOT_SCHEMA_VERSION,
    MeasurementConfig,
    MeasurementContractError,
    assert_no_market_fields,
)


@dataclass(frozen=True)
class SnapshotBuildResult:
    frame: pd.DataFrame
    audit: dict[str, Any]


@dataclass(frozen=True)
class _TeamEvidence:
    numerator: float
    denominator: float
    games: int
    included: int


@dataclass(frozen=True)
class _TeamAdjustment:
    raw: float
    adjusted: float
    league_center: float
    schedule_strength: float
    games: int
    primary_exposure: float
    included_observations: int


def _quality_flags(rows: pd.DataFrame) -> str | None:
    flags: set[str] = set()
    for value in rows.get("quality_flags", pd.Series(dtype=object)).dropna():
        flags.update(flag for flag in str(value).split(";") if flag)
    return ";".join(sorted(flags)) if flags else None


def _evidence_bounds(rows: pd.DataFrame) -> dict[str, pd.Timestamp] | None:
    if rows.empty:
        return None
    return {
        "max_kickoff": rows["kickoff_ts"].max(),
        "max_effective": rows["effective_ts"].max(),
    }


def _eligible_observations(
    observations: pd.DataFrame,
    cutoff: pd.Timestamp,
    season: int,
    config: MeasurementConfig,
) -> pd.DataFrame:
    kickoff = observations["kickoff_ts"]
    effective = observations["effective_ts"]
    mask = (kickoff < cutoff) & (pd.to_numeric(observations["season"]) == season)
    authentic = observations["temporal_status"].astype(str) == "authentic"
    reconstructed = observations["temporal_status"].astype(str) == "reconstructed"
    mask &= (authentic & effective.notna() & (effective < cutoff)) | (
        reconstructed & (season in config.historical_development_seasons)
    )
    return observations[mask]


def _team_evidence(rows: pd.DataFrame) -> dict[str, _TeamEvidence]:
    evidence: dict[str, _TeamEvidence] = {}
    if rows.empty:
        return evidence
    grouped = rows.groupby("team").agg(
        numerator=("numerator", "sum"),
        denominator=("denominator", "sum"),
        games=("game_id", "nunique"),
        included=("game_id", "size"),
    )
    for team, row in grouped.iterrows():
        evidence[str(team)] = _TeamEvidence(
            numerator=float(row["numerator"]),
            denominator=float(row["denominator"]),
            games=int(row["games"]),
            included=int(row["included"]),
        )
    return evidence


def _league_center(
    values: dict[str, float], evidence: dict[str, _TeamEvidence]
) -> float:
    pairs = [
        (value, evidence[team].denominator)
        for team, value in values.items()
        if not pd.isna(value) and evidence[team].denominator > 0
    ]
    if not pairs:
        return float("nan")
    return float(
        np.average(
            [value for value, _ in pairs], weights=[weight for _, weight in pairs]
        )
    )


def _adjust_measurement(
    rows: pd.DataFrame, iterations: int
) -> tuple[dict[str, _TeamAdjustment], dict[str, _TeamAdjustment]]:
    """Apply additive, league-centered opponent adjustment over frozen history."""
    offense_rows = rows[rows["unit_role"] == "offense"]
    defense_rows = rows[rows["unit_role"] == "defense"]
    off_evidence = _team_evidence(offense_rows)
    def_evidence = _team_evidence(defense_rows)
    raw_off = {
        team: (
            values.numerator / values.denominator
            if values.denominator > 0
            else float("nan")
        )
        for team, values in off_evidence.items()
    }
    raw_def = {
        team: (
            values.numerator / values.denominator
            if values.denominator > 0
            else float("nan")
        )
        for team, values in def_evidence.items()
    }
    adj_off = dict(raw_off)
    adj_def = dict(raw_def)

    off_edges = (
        offense_rows[["game_id", "team", "opponent", "denominator"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )
    def_edges = (
        defense_rows[["game_id", "team", "opponent", "denominator"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )

    league_center_off = float("nan")
    league_center_def = float("nan")
    for _ in range(iterations):
        league_center_off = _league_center(adj_off, off_evidence)
        league_center_def = _league_center(adj_def, def_evidence)
        new_adj_off = dict(raw_off)
        if not off_edges.empty:
            deltas = off_edges.merge(
                pd.Series(adj_def, name="opp_adjusted"),
                left_on="opponent",
                right_index=True,
                how="left",
            )
            deltas = deltas[deltas["opp_adjusted"].notna()].copy()
            deltas["delta"] = deltas["opp_adjusted"] - league_center_def
            deltas["weighted_delta"] = deltas["delta"] * deltas["denominator"]
            totals = deltas.groupby("team")[["weighted_delta", "denominator"]].sum()
            strength = totals["weighted_delta"] / totals["denominator"]
            for team in adj_off:
                new_adj_off[team] = raw_off[team] - float(strength.get(team, 0.0))

        new_adj_def = dict(raw_def)
        if not def_edges.empty:
            deltas = def_edges.merge(
                pd.Series(adj_off, name="opp_adjusted"),
                left_on="opponent",
                right_index=True,
                how="left",
            )
            deltas = deltas[deltas["opp_adjusted"].notna()].copy()
            deltas["delta"] = deltas["opp_adjusted"] - league_center_off
            deltas["weighted_delta"] = deltas["delta"] * deltas["denominator"]
            totals = deltas.groupby("team")[["weighted_delta", "denominator"]].sum()
            strength = totals["weighted_delta"] / totals["denominator"]
            for team in adj_def:
                new_adj_def[team] = raw_def[team] - float(strength.get(team, 0.0))
        adj_off = new_adj_off
        adj_def = new_adj_def

    offense_result = {
        team: _TeamAdjustment(
            raw=raw_off[team],
            adjusted=adj_off[team],
            league_center=league_center_def,
            schedule_strength=raw_off[team] - adj_off[team],
            games=off_evidence[team].games,
            primary_exposure=off_evidence[team].denominator,
            included_observations=off_evidence[team].included,
        )
        for team in raw_off
    }
    defense_result = {
        team: _TeamAdjustment(
            raw=raw_def[team],
            adjusted=adj_def[team],
            league_center=league_center_off,
            schedule_strength=raw_def[team] - adj_def[team],
            games=def_evidence[team].games,
            primary_exposure=def_evidence[team].denominator,
            included_observations=def_evidence[team].included,
        )
        for team in raw_def
    }
    return offense_result, defense_result


def _raw_aggregate(evidence: _TeamEvidence | None) -> tuple[float | None, bool]:
    if evidence is None:
        return None, False
    if evidence.denominator <= 0:
        return None, True
    return evidence.numerator / evidence.denominator, True


def build_pregame_snapshots(
    *,
    observations: pd.DataFrame,
    games: pd.DataFrame,
    config: MeasurementConfig,
    code_sha: str,
    config_sha: str,
    parent_observation_version_id: str,
    parent_ref_shas: str,
) -> SnapshotBuildResult:
    """Build pregame adjusted snapshots for every scheduled game in scope."""
    required = {
        "season",
        "game_id",
        "week",
        "kickoff_utc",
        "home_team",
        "away_team",
    }
    missing = sorted(required - set(games.columns))
    if missing:
        raise MeasurementContractError(f"games parent missing columns: {missing}")
    assert_no_market_fields(games.columns, context="games parent columns")

    observations = observations.copy()
    observations["kickoff_ts"] = pd.to_datetime(
        observations["kickoff_utc"], utc=True, errors="coerce"
    )
    observations["effective_ts"] = pd.to_datetime(
        observations["effective_at"], utc=True, errors="coerce"
    )
    observations["game_id"] = pd.to_numeric(
        observations["game_id"], errors="coerce"
    ).astype("Int64")
    observed = observations[observations["coverage_status"] == "observed"]
    observed = observed.sort_values(["kickoff_ts", "game_id"], kind="mergesort")

    games = games.copy()
    games["season"] = pd.to_numeric(games["season"], errors="coerce")
    games["week"] = pd.to_numeric(games["week"], errors="coerce")
    games["kickoff_ts"] = pd.to_datetime(
        games["kickoff_utc"], utc=True, errors="coerce"
    )
    status = (
        games["status"].astype(str).str.lower().str.strip()
        if "status" in games
        else pd.Series("", index=games.index)
    )
    targets = (
        games[
            games["season"].isin(config.known_seasons)
            & games["week"].notna()
            & games["kickoff_ts"].notna()
            & ~status.isin(config.excluded_statuses)
        ][["season", "week", "game_id", "kickoff_ts", "home_team", "away_team"]]
        .sort_values(["kickoff_ts", "game_id"], kind="mergesort")
        .reset_index(drop=True)
    )

    adjusted_ids = {
        spec.measurement_id for spec in config.measurements if spec.is_adjusted
    }

    records: list[dict[str, Any]] = []
    missing_counts: dict[str, int] = {}
    boundaries = 0
    for cutoff, group in targets.groupby("kickoff_ts", sort=True):
        boundaries += 1
        eligible_by_season = {
            int(season): _eligible_observations(
                observed, pd.Timestamp(cutoff), int(season), config
            )
            for season in group["season"].unique()
        }
        context_ids = {
            spec.measurement_id for spec in config.measurements if not spec.is_adjusted
        }
        for target in group.itertuples(index=False):
            eligible = eligible_by_season[int(target.season)]
            adjusted_cache = {
                measurement_id: _adjust_measurement(
                    eligible[eligible["measurement_id"] == measurement_id],
                    config.adjustment_iterations,
                )
                for measurement_id in adjusted_ids
            }
            context_cache = {
                measurement_id: (
                    _team_evidence(
                        eligible[
                            (eligible["measurement_id"] == measurement_id)
                            & (eligible["unit_role"] == "offense")
                        ]
                    ),
                    _team_evidence(
                        eligible[
                            (eligible["measurement_id"] == measurement_id)
                            & (eligible["unit_role"] == "defense")
                        ]
                    ),
                )
                for measurement_id in context_ids
            }
            for spec in config.measurements:
                for team in (target.home_team, target.away_team):
                    for role in spec.roles:
                        evidence_rows = eligible[
                            (eligible["team"] == team)
                            & (eligible["measurement_id"] == spec.measurement_id)
                            & (eligible["unit_role"] == role)
                        ]
                        bounds = _evidence_bounds(evidence_rows)
                        record = _build_row(
                            spec=spec,
                            role=role,
                            team=team,
                            target=target,
                            cutoff=pd.Timestamp(cutoff),
                            config=config,
                            code_sha=code_sha,
                            config_sha=config_sha,
                            parent_observation_version_id=parent_observation_version_id,
                            parent_ref_shas=parent_ref_shas,
                            adjusted_cache=adjusted_cache,
                            context_cache=context_cache,
                            bounds=bounds,
                            quality_flags=_quality_flags(evidence_rows),
                        )
                        records.append(record)
                        if record["coverage_status"] == "missing":
                            reason = record["missing_reason"]
                            missing_counts[reason] = missing_counts.get(reason, 0) + 1

    frame = (
        pd.DataFrame.from_records(records, columns=SNAPSHOT_COLUMNS)
        if records
        else pd.DataFrame(columns=SNAPSHOT_COLUMNS)
    )
    if records:
        frame = frame.sort_values(
            [
                "season",
                "as_of_kickoff_utc",
                "as_of_game_id",
                "team",
                "measurement_id",
                "unit_role",
            ],
            kind="mergesort",
        ).reset_index(drop=True)
    audit = {
        "target_games": int(len(targets)),
        "distinct_kickoff_boundaries": boundaries,
        "missing_rows_by_reason": missing_counts,
    }
    return SnapshotBuildResult(frame=frame, audit=audit)


def build_season_terminal_snapshots(
    *,
    observations: pd.DataFrame,
    games: pd.DataFrame,
    config: MeasurementConfig,
    code_sha: str,
    config_sha: str,
    parent_observation_version_id: str,
    parent_ref_shas: str,
) -> SnapshotBuildResult:
    """Build one adjusted terminal measurement state per historical team-season."""
    observations = observations.copy()
    observations["kickoff_ts"] = pd.to_datetime(observations["kickoff_utc"], utc=True)
    observations["effective_ts"] = pd.to_datetime(
        observations["effective_at"], utc=True, errors="coerce"
    )
    observed = observations[observations["coverage_status"] == "observed"]
    records: list[dict[str, Any]] = []
    for season in config.historical_development_seasons:
        season_rows = observed[pd.to_numeric(observed["season"]) == season]
        if season_rows.empty:
            continue
        terminal_at = season_rows["kickoff_ts"].max() + pd.Timedelta(microseconds=1)
        adjusted_ids = {
            spec.measurement_id for spec in config.measurements if spec.is_adjusted
        }
        adjusted_cache = {
            measurement_id: _adjust_measurement(
                season_rows[season_rows["measurement_id"] == measurement_id],
                config.adjustment_iterations,
            )
            for measurement_id in adjusted_ids
        }
        context_ids = {
            spec.measurement_id for spec in config.measurements if not spec.is_adjusted
        }
        context_cache = {
            measurement_id: (
                _team_evidence(
                    season_rows[
                        (season_rows["measurement_id"] == measurement_id)
                        & (season_rows["unit_role"] == "offense")
                    ]
                ),
                _team_evidence(
                    season_rows[
                        (season_rows["measurement_id"] == measurement_id)
                        & (season_rows["unit_role"] == "defense")
                    ]
                ),
            )
            for measurement_id in context_ids
        }
        teams = sorted(set(season_rows["team"].astype(str)))
        target = type("Terminal", (), {"season": season, "week": 99, "game_id": -1})()
        for spec in config.measurements:
            for team in teams:
                for role in spec.roles:
                    evidence_rows = season_rows[
                        (season_rows["team"] == team)
                        & (season_rows["measurement_id"] == spec.measurement_id)
                        & (season_rows["unit_role"] == role)
                    ]
                    record = _build_row(
                        spec=spec,
                        role=role,
                        team=team,
                        target=target,
                        cutoff=terminal_at,
                        config=config,
                        code_sha=code_sha,
                        config_sha=config_sha,
                        parent_observation_version_id=parent_observation_version_id,
                        parent_ref_shas=parent_ref_shas,
                        adjusted_cache=adjusted_cache,
                        context_cache=context_cache,
                        bounds=_evidence_bounds(evidence_rows),
                        quality_flags=_quality_flags(evidence_rows),
                    )
                    record["terminal_at_utc"] = record.pop("as_of_kickoff_utc")
                    record.pop("as_of_game_id")
                    record.pop("week")
                    record["measurement_schema_version"] = (
                        TERMINAL_SNAPSHOT_SCHEMA_VERSION
                    )
                    records.append(record)
    frame = pd.DataFrame.from_records(records, columns=TERMINAL_SNAPSHOT_COLUMNS)
    if not frame.empty:
        frame = frame.sort_values(
            ["season", "team", "measurement_id", "unit_role"], kind="mergesort"
        ).reset_index(drop=True)
    return SnapshotBuildResult(
        frame=frame,
        audit={
            "terminal_rows": int(len(frame)),
            "terminal_seasons": list(config.historical_development_seasons),
        },
    )


def _build_row(
    *,
    spec,
    role: str,
    team: str,
    target,
    cutoff: pd.Timestamp,
    config: MeasurementConfig,
    code_sha: str,
    config_sha: str,
    parent_observation_version_id: str,
    parent_ref_shas: str,
    adjusted_cache: dict[
        str, tuple[dict[str, _TeamAdjustment], dict[str, _TeamAdjustment]]
    ],
    context_cache: dict[str, tuple[dict[str, _TeamEvidence], dict[str, _TeamEvidence]]],
    bounds,
    quality_flags: str | None,
) -> dict[str, Any]:
    record = {
        "season": int(target.season),
        "week": int(target.week),
        "as_of_game_id": int(target.game_id),
        "as_of_kickoff_utc": cutoff.isoformat(),
        "team": team,
        "measurement_id": spec.measurement_id,
        "unit_role": role,
        "raw_aggregate": None,
        "adjusted_value_iter0": None,
        "adjusted_value": None,
        "games_exposure": 0,
        "primary_exposure": 0.0,
        "included_observations": 0,
        "adjustment_method": (
            ADJUSTMENT_METHOD_ADJUSTED if spec.is_adjusted else ADJUSTMENT_METHOD_NONE
        ),
        "adjustment_iteration": (
            config.adjustment_iterations if spec.is_adjusted else 0
        ),
        "league_center": None,
        "schedule_strength_component": None,
        "evidence_max_kickoff_utc": (
            bounds["max_kickoff"].isoformat()
            if bounds is not None and pd.notna(bounds["max_kickoff"])
            else None
        ),
        "evidence_max_effective_at": (
            bounds["max_effective"].isoformat()
            if bounds is not None and pd.notna(bounds["max_effective"])
            else None
        ),
        "coverage_status": "missing",
        "missing_reason": "no_eligible_evidence",
        "quality_flags": quality_flags,
        "measurement_schema_version": SNAPSHOT_SCHEMA_VERSION,
        "measurement_design_id": config.design_id,
        "parent_observation_version_id": parent_observation_version_id,
        "parent_ref_shas": parent_ref_shas,
        "code_sha": code_sha,
        "config_sha": config_sha,
    }

    if spec.is_adjusted:
        offense_result, defense_result = adjusted_cache[spec.measurement_id]
        entry = (
            offense_result.get(team) if role == "offense" else defense_result.get(team)
        )
        if entry is None or entry.primary_exposure <= 0 or pd.isna(entry.raw):
            if entry is not None:
                record["games_exposure"] = entry.games
                record["primary_exposure"] = entry.primary_exposure
                record["included_observations"] = entry.included_observations
                record["missing_reason"] = "zero_primary_exposure"
            return record
        record.update(
            {
                "coverage_status": "observed",
                "missing_reason": None,
                "raw_aggregate": float(entry.raw),
                "adjusted_value_iter0": float(entry.raw),
                "adjusted_value": float(entry.adjusted),
                "games_exposure": int(entry.games),
                "primary_exposure": float(entry.primary_exposure),
                "included_observations": int(entry.included_observations),
                "league_center": (
                    float(entry.league_center)
                    if pd.notna(entry.league_center)
                    else None
                ),
                "schedule_strength_component": float(entry.schedule_strength),
            }
        )
        return record

    offense_evidence, defense_evidence = context_cache[spec.measurement_id]
    evidence = (offense_evidence if role == "offense" else defense_evidence).get(team)
    raw, has_evidence = _raw_aggregate(evidence)
    if evidence is not None:
        record["games_exposure"] = evidence.games
        record["primary_exposure"] = evidence.denominator
        record["included_observations"] = evidence.included
    if raw is None:
        if has_evidence:
            record["missing_reason"] = "zero_primary_exposure"
        return record
    record.update(
        {
            "coverage_status": "observed",
            "missing_reason": None,
            "raw_aggregate": raw,
            "adjusted_value_iter0": raw,
            "adjusted_value": raw,
        }
    )
    return record
