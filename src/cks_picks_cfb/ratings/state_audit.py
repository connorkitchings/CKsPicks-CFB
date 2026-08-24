"""Descriptive, non-predictive audit for Phase 2 team states."""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd


def build_team_state_audit(
    *, measurement_states: pd.DataFrame, team_states: pd.DataFrame,
    measurement_refs: Mapping[str, Any], state_design_id: str,
) -> dict[str, Any]:
    pregame = team_states[team_states["state_kind"] == "pregame"]
    components = measurement_states[measurement_states["state_kind"] == "pregame"]
    correlations: dict[str, float | None] = {}
    for role, rows in components.groupby("unit_role"):
        pivot = rows.pivot_table(index=["state_id", "team"], columns="measurement_id", values="posterior_mean")
        if {"epa_per_play", "success_rate"}.issubset(pivot.columns):
            value = pivot["epa_per_play"].corr(pivot["success_rate"], method="spearman")
            correlations[str(role)] = None if pd.isna(value) else float(value)
    uncertainty_by_week = {
        str(int(week)): float(rows["overall_sd"].mean())
        for week, rows in pregame.groupby("week")
    }
    return {
        "report_schema_version": "rating_team_state_audit_v1",
        "state_design_id": state_design_id,
        "lineage": dict(measurement_refs),
        "coverage": {
            "pregame_team_rows": int(len(pregame)),
            "terminal_team_rows": int((team_states["state_kind"] == "season_terminal").sum()),
            "component_rows": int(len(measurement_states)),
            "all_pregame_nonnull": bool(not pregame.empty and pregame[["offense_mean", "offense_sd", "defense_mean", "defense_sd", "overall_mean", "overall_sd"]].notna().all().all()),
        },
        "behavior": {
            "mean_overall_sd_by_week": uncertainty_by_week,
            "epa_success_spearman": correlations,
            "largest_absolute_overall_state": float(pregame["overall_mean"].abs().max()) if not pregame.empty else None,
        },
    }
