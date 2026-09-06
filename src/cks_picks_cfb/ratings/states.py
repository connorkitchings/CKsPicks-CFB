"""Point-in-time empirical-Bayes team states from corrected measurements."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np
import pandas as pd

from cks_picks_cfb.data.season_lineage import load_season_lineage_policy
from cks_picks_cfb.ratings.state_contracts import (
    MEASUREMENT_STATE_COLUMNS,
    TEAM_STATE_COLUMNS,
    TeamStateConfig,
)


def _flags(*values: object) -> str | None:
    result: set[str] = set()
    for value in values:
        if value is not None and not (isinstance(value, float) and np.isnan(value)):
            result.update(item for item in str(value).split(";") if item)
    return ";".join(sorted(result)) if result else None


def _utc_text(value: object) -> str:
    return pd.Timestamp(value).tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%S.%f%z")


def _scales(
    terminal: pd.DataFrame, config: TeamStateConfig
) -> dict[tuple[str, str], tuple[float, float, str | None]]:
    output: dict[tuple[str, str], tuple[float, float, str | None]] = {}
    for component in config.components:
        for role in ("offense", "defense"):
            values = pd.to_numeric(
                terminal.loc[
                    (terminal["measurement_id"] == component.measurement_id)
                    & (terminal["unit_role"] == role)
                    & (terminal["coverage_status"] == "observed"),
                    "adjusted_value",
                ],
                errors="coerce",
            ).dropna()
            if len(values) >= 2:
                center = float(values.mean())
                scale = max(float(values.std(ddof=1)), component.scale_floor)
                flag = (
                    "standardization_scale_floored"
                    if scale == component.scale_floor
                    else None
                )
            else:
                center, scale, flag = (
                    component.fallback_center,
                    component.fallback_scale,
                    "standardization_fallback",
                )
            output[(component.measurement_id, role)] = (center, scale, flag)
    return output


def _posterior(
    *,
    prior_mean: float,
    prior_variance: float,
    observed_z: float | None,
    exposure: float,
    equivalent_exposure: float,
) -> tuple[float, float, float, float, float]:
    prior_precision = 1.0 / prior_variance
    observation_precision = (
        exposure / equivalent_exposure
        if observed_z is not None and exposure > 0
        else 0.0
    )
    total = prior_precision + observation_precision
    posterior_variance = 1.0 / total
    posterior_mean = (
        prior_precision * prior_mean + observation_precision * (observed_z or 0.0)
    ) / total
    return (
        posterior_mean,
        posterior_variance,
        prior_precision,
        observation_precision,
        observation_precision / total,
    )


def build_team_states(
    *,
    pregame_snapshots: pd.DataFrame,
    terminal_snapshots: pd.DataFrame,
    config: TeamStateConfig,
    code_sha: str,
    config_sha: str,
    parent_measurement_refs: str,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Build chronological pregame and terminal component/team states."""
    components: list[dict[str, Any]] = []
    teams: list[dict[str, Any]] = []
    terminal_states_by_season: dict[
        int, dict[tuple[str, str, str], tuple[float, float]]
    ] = {}
    seasons = sorted(
        set(pd.to_numeric(pregame_snapshots["season"]).dropna().astype(int))
    )
    lineage = (
        load_season_lineage_policy(config.season_lineage_policy_path)
        if config.is_successor_v2
        else None
    )
    if lineage is not None and tuple(seasons) != lineage.historical_development_seasons:
        raise ValueError(
            "Successor-v2 team states require the complete permitted corpus"
        )
    for season in seasons:
        transition = lineage.prior_transition_for(season) if lineage else None
        prior_source_season = transition.source_season if transition else season - 1
        annual_decay_steps = transition.annual_decay_steps if transition else 1
        prior_states = (
            terminal_states_by_season.get(prior_source_season, {})
            if transition is not None
            else terminal_states_by_season.get(season - 1, {})
        )
        previous_terminal = terminal_snapshots[
            pd.to_numeric(terminal_snapshots["season"]) == prior_source_season
        ]
        scales = (
            _scales(previous_terminal, config)
            if prior_states
            else _scales(pd.DataFrame(columns=terminal_snapshots.columns), config)
        )
        season_pregame = pregame_snapshots[
            pd.to_numeric(pregame_snapshots["season"]) == season
        ].copy()
        target_keys = ["as_of_game_id", "as_of_kickoff_utc"]
        for (game_id, as_of), target_rows in season_pregame.groupby(
            target_keys, sort=True
        ):
            state_id = f"game:{season}:{int(game_id)}"
            _append_state_group(
                component_rows=components,
                team_rows=teams,
                source_rows=target_rows,
                state_id=state_id,
                state_kind="pregame",
                season=season,
                week=int(target_rows["week"].iloc[0]),
                as_of_game_id=int(game_id),
                as_of_utc=_utc_text(as_of),
                config=config,
                scales=scales,
                prior_states=prior_states,
                prior_source_season=prior_source_season if prior_states else None,
                annual_decay_steps=annual_decay_steps,
                code_sha=code_sha,
                config_sha=config_sha,
                parent_measurement_refs=parent_measurement_refs,
            )
        season_terminal = terminal_snapshots[
            pd.to_numeric(terminal_snapshots["season"]) == season
        ].copy()
        if not season_terminal.empty:
            terminal_at = _utc_text(season_terminal["terminal_at_utc"].iloc[0])
            _append_state_group(
                component_rows=components,
                team_rows=teams,
                source_rows=season_terminal,
                state_id=f"terminal:{season}",
                state_kind="season_terminal",
                season=season,
                week=99,
                as_of_game_id=None,
                as_of_utc=terminal_at,
                config=config,
                scales=scales,
                prior_states=prior_states,
                prior_source_season=prior_source_season if prior_states else None,
                annual_decay_steps=annual_decay_steps,
                code_sha=code_sha,
                config_sha=config_sha,
                parent_measurement_refs=parent_measurement_refs,
            )
            terminal_states_by_season[season] = {
                (row["team"], row["measurement_id"], row["unit_role"]): (
                    row["posterior_mean"],
                    row["posterior_variance"],
                )
                for row in components
                if row["state_id"].startswith(f"terminal:{season}:")
            }
    measurement_frame = pd.DataFrame.from_records(
        components, columns=MEASUREMENT_STATE_COLUMNS
    )
    team_frame = pd.DataFrame.from_records(teams, columns=TEAM_STATE_COLUMNS)
    if not measurement_frame.empty:
        measurement_frame = measurement_frame.sort_values(
            ["season", "as_of_utc", "state_id", "team", "measurement_id", "unit_role"],
            kind="mergesort",
        ).reset_index(drop=True)
        team_frame = team_frame.sort_values(
            ["season", "as_of_utc", "state_id", "team"], kind="mergesort"
        ).reset_index(drop=True)
    return (
        measurement_frame,
        team_frame,
        {
            "measurement_rows": int(len(measurement_frame)),
            "team_rows": int(len(team_frame)),
            "seasons": seasons,
        },
    )


def _append_state_group(
    *,
    component_rows: list[dict[str, Any]],
    team_rows: list[dict[str, Any]],
    source_rows: pd.DataFrame,
    state_id: str,
    state_kind: str,
    season: int,
    week: int,
    as_of_game_id: int | None,
    as_of_utc: str,
    config: TeamStateConfig,
    scales: dict[tuple[str, str], tuple[float, float, str | None]],
    prior_states: dict[tuple[str, str, str], tuple[float, float]],
    prior_source_season: int | None,
    annual_decay_steps: int,
    code_sha: str,
    config_sha: str,
    parent_measurement_refs: str,
) -> None:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in source_rows.to_dict("records"):
        if row["measurement_id"] not in {
            item.measurement_id for item in config.components
        }:
            continue
        component = config.component(row["measurement_id"])
        center, scale, scale_flag = scales[(component.measurement_id, row["unit_role"])]
        terminal = prior_states.get(
            (row["team"], component.measurement_id, row["unit_role"])
        )
        if terminal is None:
            prior_mean, prior_variance, prior_source, prior_flag = (
                config.neutral_mean,
                config.neutral_variance,
                None,
                "neutral_preseason_prior",
            )
        else:
            terminal_mean, terminal_variance = terminal
            decay = config.offseason_rho**annual_decay_steps
            prior_mean = decay * terminal_mean
            prior_variance = decay**2 * terminal_variance + (1 - decay**2)
            prior_source, prior_flag = prior_source_season, None
        native = pd.to_numeric(
            pd.Series([row.get("adjusted_value")]), errors="coerce"
        ).iloc[0]
        exposure = float(
            pd.to_numeric(pd.Series([row.get("primary_exposure")]), errors="coerce")
            .fillna(0)
            .iloc[0]
        )
        observed_z = (
            None
            if pd.isna(native) or exposure <= 0
            else float((native - center) / scale)
        )
        if row["unit_role"] == "defense" and observed_z is not None:
            observed_z *= -1
        mean, variance, prior_precision, observation_precision, observed_weight = (
            _posterior(
                prior_mean=prior_mean,
                prior_variance=prior_variance,
                observed_z=observed_z,
                exposure=exposure,
                equivalent_exposure=component.equivalent_prior_exposure,
            )
        )
        record = {
            "state_id": (
                f"terminal:{season}:{row['team']}"
                if state_kind == "season_terminal"
                else state_id
            ),
            "state_kind": state_kind,
            "season": season,
            "week": week,
            "as_of_game_id": as_of_game_id,
            "as_of_utc": as_of_utc,
            "team": row["team"],
            "measurement_id": component.measurement_id,
            "unit_role": row["unit_role"],
            "prior_source_season": prior_source,
            "standardization_center": center,
            "standardization_scale": scale,
            "native_adjusted_value": None if pd.isna(native) else float(native),
            "observed_z": observed_z,
            "primary_exposure": exposure,
            "completed_games": int(row.get("games_exposure", 0)),
            "prior_mean": prior_mean,
            "prior_variance": prior_variance,
            "prior_precision": prior_precision,
            "observation_precision": observation_precision,
            "prior_weight": 1 - observed_weight,
            "observed_weight": observed_weight,
            "posterior_mean": mean,
            "posterior_variance": variance,
            "posterior_sd": float(np.sqrt(variance)),
            "quality_flags": _flags(row.get("quality_flags"), scale_flag, prior_flag),
            "state_schema_version": config.measurement_state_schema_version,
            "state_design_id": config.design_id,
            "parent_measurement_refs": parent_measurement_refs,
            "code_sha": code_sha,
            "config_sha": config_sha,
        }
        component_rows.append(record)
        grouped[row["team"]].append(record)
    for team, records in grouped.items():
        by_role = {
            role: [item for item in records if item["unit_role"] == role]
            for role in ("offense", "defense")
        }
        if any(len(by_role[role]) != len(config.components) for role in by_role):
            raise ValueError(f"Incomplete component coverage for {state_id}/{team}")

        def composite(role: str) -> tuple[float, float, float]:
            values = by_role[role]
            mean = sum(
                config.component(item["measurement_id"]).weight * item["posterior_mean"]
                for item in values
            )
            sd = sum(
                config.component(item["measurement_id"]).weight * item["posterior_sd"]
                for item in values
            )
            weight = sum(
                config.component(item["measurement_id"]).weight
                * item["observed_weight"]
                for item in values
            )
            return float(mean), float(sd), float(weight)

        offense_mean, offense_sd, offense_weight = composite("offense")
        defense_mean, defense_sd, defense_weight = composite("defense")
        team_rows.append(
            {
                "state_id": (
                    f"terminal:{season}:{team}"
                    if state_kind == "season_terminal"
                    else state_id
                ),
                "state_kind": state_kind,
                "season": season,
                "week": week,
                "as_of_game_id": as_of_game_id,
                "as_of_utc": as_of_utc,
                "team": team,
                "offense_mean": offense_mean,
                "offense_sd": offense_sd,
                "defense_mean": defense_mean,
                "defense_sd": defense_sd,
                "overall_mean": (offense_mean + defense_mean) / 2,
                "overall_sd": (offense_sd + defense_sd) / 2,
                "completed_games": max(item["completed_games"] for item in records),
                "offense_observed_weight": offense_weight,
                "defense_observed_weight": defense_weight,
                "component_count": len(records),
                "quality_flags": _flags(*(item["quality_flags"] for item in records)),
                "state_schema_version": config.team_state_schema_version,
                "state_design_id": config.design_id,
                "parent_measurement_refs": parent_measurement_refs,
                "code_sha": code_sha,
                "config_sha": config_sha,
            }
        )
