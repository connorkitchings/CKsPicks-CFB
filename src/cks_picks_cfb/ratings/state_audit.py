"""Descriptive, fail-closed audit for Phase 2 team states."""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from cks_picks_cfb.ratings.contracts import market_field_conflicts
from cks_picks_cfb.ratings.state_contracts import TeamStateConfig


def _location_stability(
    team_states: pd.DataFrame, config: TeamStateConfig
) -> tuple[bool, dict[str, object]]:
    """Audit representative state populations without postseason-selection bias."""
    gate = config.location_gate
    if gate is None:
        return True, {"enabled": False}
    historical = set(range(2021, 2026))
    terminal = team_states[
        (team_states["state_kind"] == "season_terminal")
        & (team_states["season"].astype(int).isin(historical))
    ].copy()
    population = terminal.groupby("season")["team"].nunique().to_dict()
    rows: list[dict[str, object]] = []
    pregame = team_states[
        (team_states["state_kind"] == "pregame")
        & (team_states["season"].astype(int).isin(historical))
    ]
    fraction = float(gate["minimum_terminal_population_fraction"])
    maximum = float(gate["maximum_abs_population_mean"])
    for (season, ordinal), values in pregame.groupby(["season", "completed_games"]):
        teams = int(values["team"].nunique())
        season_population = int(population.get(int(season), 0))
        qualifies = season_population > 0 and teams >= fraction * season_population
        offense = float(values["offense_mean"].mean())
        defense = float(values["defense_mean"].mean())
        rows.append(
            {
                "state_kind": "pregame",
                "season": int(season),
                "completed_games": int(ordinal),
                "team_count": teams,
                "terminal_population": season_population,
                "qualifies": qualifies,
                "offense_mean": offense,
                "defense_mean": defense,
                "max_abs_mean": max(abs(offense), abs(defense)),
                "passes": (max(abs(offense), abs(defense)) <= maximum)
                if qualifies
                else None,
            }
        )
    for season, values in terminal.groupby("season"):
        offense = float(values["offense_mean"].mean())
        defense = float(values["defense_mean"].mean())
        rows.append(
            {
                "state_kind": "season_terminal",
                "season": int(season),
                "completed_games": None,
                "team_count": int(values["team"].nunique()),
                "terminal_population": int(population.get(int(season), 0)),
                "qualifies": True,
                "offense_mean": offense,
                "defense_mean": defense,
                "max_abs_mean": max(abs(offense), abs(defense)),
                "passes": max(abs(offense), abs(defense)) <= maximum,
            }
        )
    qualifying = [row for row in rows if row["qualifies"]]
    return bool(qualifying) and all(bool(row["passes"]) for row in qualifying), {
        "enabled": True,
        "minimum_terminal_population_fraction": fraction,
        "maximum_abs_population_mean": maximum,
        "groups": rows,
    }


def build_team_state_audit(
    *,
    measurement_states: pd.DataFrame,
    team_states: pd.DataFrame,
    measurement_refs: Mapping[str, Any],
    state_design_id: str,
    config: TeamStateConfig,
    pregame_snapshots: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Build the Phase 2 structural and behavioral exit-gate report."""
    pregame = team_states[team_states["state_kind"] == "pregame"].copy()
    components = measurement_states[measurement_states["state_kind"] == "pregame"]
    correlations: dict[str, float | None] = {}
    for role, rows in components.groupby("unit_role"):
        pivot = rows.pivot_table(
            index=["state_id", "team"],
            columns="measurement_id",
            values="posterior_mean",
        )
        if {"epa_per_play", "success_rate"}.issubset(pivot.columns):
            value = pivot["epa_per_play"].corr(pivot["success_rate"], method="spearman")
            correlations[str(role)] = None if pd.isna(value) else float(value)
    weights = {
        str(int(n)): float(rows["offense_observed_weight"].mean())
        for n, rows in pregame.groupby("completed_games")
    }
    uncertainty = {
        str(int(n)): float(rows["overall_sd"].mean())
        for n, rows in pregame.groupby("completed_games")
    }
    expected = set()
    if pregame_snapshots is not None:
        expected = set(
            zip(
                pregame_snapshots["season"],
                pregame_snapshots["as_of_game_id"],
                pregame_snapshots["team"],
            )
        )
    actual = set(zip(pregame["season"], pregame["as_of_game_id"], pregame["team"]))
    terminal = team_states[team_states["state_kind"] == "season_terminal"]
    location_ok, location = _location_stability(team_states, config)
    checks = {
        "schedule_coverage_ok": expected == actual if expected else True,
        "nonnull_states_ok": bool(
            not pregame.empty
            and pregame[
                [
                    "offense_mean",
                    "offense_sd",
                    "defense_mean",
                    "defense_sd",
                    "overall_mean",
                    "overall_sd",
                ]
            ]
            .notna()
            .all()
            .all()
        ),
        "component_attribution_ok": bool((pregame["component_count"] == 8).all()),
        "positive_uncertainty_ok": bool(
            (measurement_states["posterior_sd"] > 0).all()
            and (team_states[["offense_sd", "defense_sd", "overall_sd"]] > 0)
            .all()
            .all()
        ),
        "terminal_identity_ok": bool(
            (
                terminal.apply(
                    lambda r: r["state_id"]
                    == f"terminal:{int(r['season'])}:{r['team']}",
                    axis=1,
                )
            ).all()
        ),
        "market_free_ok": not (
            market_field_conflicts(measurement_states.columns)
            + market_field_conflicts(team_states.columns)
        ),
        "forbidden_seasons_ok": not set(
            pd.to_numeric(team_states["season"], errors="coerce").dropna().astype(int)
        )
        & {2019, 2020},
        "location_stability_ok": location_ok,
    }
    report = {
        "report_schema_version": "rating_team_state_audit_v1",
        "state_design_id": state_design_id,
        "lineage": dict(measurement_refs),
        "coverage": {
            "pregame_team_rows": int(len(pregame)),
            "terminal_team_rows": int(len(terminal)),
            "component_rows": int(len(measurement_states)),
            "all_pregame_nonnull": checks["nonnull_states_ok"],
        },
        "behavior": {
            "mean_overall_sd_by_completed_games": uncertainty,
            "mean_observed_weight_by_completed_games": weights,
            "epa_success_spearman": correlations,
            "largest_absolute_overall_state": float(pregame["overall_mean"].abs().max())
            if not pregame.empty
            else None,
            "quality_flag_counts": team_states["quality_flags"]
            .value_counts(dropna=True)
            .to_dict(),
        },
        "location_stability": location,
        "checks": checks,
    }
    report["all_checks_passed"] = all(checks.values())
    return report
