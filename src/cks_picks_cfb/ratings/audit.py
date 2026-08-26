"""Coverage, redundancy, and lineage audit for the Phase 1 rating datasets."""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from cks_picks_cfb.ratings.contracts import (
    MeasurementConfig,
    market_field_conflicts,
)


def _quantiles(values: pd.Series) -> dict[str, float | None]:
    if values.empty:
        return {f"q{int(q * 100)}": None for q in (0.1, 0.25, 0.5, 0.75, 0.9)}
    finite = pd.to_numeric(values, errors="coerce").dropna()
    if finite.empty:
        return {f"q{int(q * 100)}": None for q in (0.1, 0.25, 0.5, 0.75, 0.9)}
    return {
        f"q{int(q * 100)}": float(finite.quantile(q))
        for q in (0.1, 0.25, 0.5, 0.75, 0.9)
    }


def _season_measurement_coverage(
    observations: pd.DataFrame,
) -> dict[str, Any]:
    coverage: dict[str, Any] = {}
    grouped = observations.groupby(
        ["season", "measurement_id", "unit_role"], dropna=False
    )
    for (season, measurement_id, role), rows in grouped:
        key = f"{int(season)}/{measurement_id}/{role}"
        denominator = pd.to_numeric(rows["denominator"])
        coverage[key] = {
            "rows": int(len(rows)),
            "team_games": int(rows.groupby("game_id")["team"].nunique().sum()),
            "observed_rows": int((rows["coverage_status"] == "observed").sum()),
            "missing_rows": int((rows["coverage_status"] == "missing").sum()),
            "non_null_values": int(rows["raw_value"].notna().sum()),
            "zero_exposure_rows": int((denominator == 0).sum()),
            "missing_reasons": {
                str(reason): int(count)
                for reason, count in rows["missing_reason"]
                .value_counts(dropna=True)
                .items()
            },
            "temporal_status": {
                str(status): int(count)
                for status, count in rows["temporal_status"]
                .value_counts(dropna=False)
                .items()
            },
            "exposure_min": (
                float(denominator.min()) if not denominator.empty else None
            ),
            "exposure_median": (
                float(denominator.median()) if not denominator.empty else None
            ),
            "exposure_max": float(denominator.max()) if not denominator.empty else None,
            "value_quantiles": _quantiles(rows["raw_value"]),
        }
    return coverage


def _redundancy_correlations(
    snapshots: pd.DataFrame, config: MeasurementConfig
) -> dict[str, Any]:
    adjusted_ids = [
        spec.measurement_id for spec in config.measurements if spec.is_adjusted
    ]
    correlations: dict[str, Any] = {}
    eligible = snapshots[
        (snapshots["coverage_status"] == "observed")
        & snapshots["measurement_id"].isin(adjusted_ids)
    ]
    for (season, role), rows in eligible.groupby(["season", "unit_role"]):
        pivot = rows.pivot_table(
            index=["as_of_game_id", "team"],
            columns="measurement_id",
            values="adjusted_value",
        )
        available = [column for column in adjusted_ids if column in pivot.columns]
        if len(available) < 2:
            continue
        matrix = pivot[available].corr(method="spearman")
        pairs = {}
        for i, left in enumerate(available):
            for right in available[i + 1 :]:
                value = matrix.loc[left, right]
                pairs[f"{left}|{right}"] = float(value) if pd.notna(value) else None
        correlations[f"{int(season)}/{role}"] = {
            "common_pregame_states": int(len(pivot)),
            "pairs": pairs,
        }
    return correlations


def _check_symmetry(
    observations: pd.DataFrame, games: pd.DataFrame, config: MeasurementConfig
) -> bool:
    teams_by_game = observations.groupby(["season", "game_id"])["team"].apply(set)
    schedule = games.set_index(["season", "game_id"])[["home_team", "away_team"]]
    for (season, game_id), teams in teams_by_game.items():
        try:
            row = schedule.loc[(season, game_id)]
        except KeyError:
            return False
        if teams != {row["home_team"], row["away_team"]}:
            return False
    two_role_measurements = {
        spec.measurement_id
        for spec in config.measurements
        if set(spec.roles) == {"offense", "defense"}
    }
    mirrored = observations[observations["measurement_id"].isin(two_role_measurements)]
    offense = mirrored[mirrored["unit_role"] == "offense"]
    defense = mirrored[mirrored["unit_role"] == "defense"]
    offense_keys = set(
        zip(
            offense["game_id"],
            offense["team"],
            offense["opponent"],
            offense["measurement_id"],
        )
    )
    defense_keys = set(
        zip(
            defense["game_id"],
            defense["opponent"],
            defense["team"],
            defense["measurement_id"],
        )
    )
    return offense_keys == defense_keys


def _check_future_rows(snapshots: pd.DataFrame) -> bool:
    kickoff = pd.to_datetime(snapshots["as_of_kickoff_utc"], utc=True, errors="coerce")
    evidence = pd.to_datetime(
        snapshots["evidence_max_kickoff_utc"], utc=True, errors="coerce"
    )
    effective = pd.to_datetime(
        snapshots["evidence_max_effective_at"], utc=True, errors="coerce"
    )
    has_evidence = evidence.notna()
    if (has_evidence & (evidence >= kickoff)).any():
        return False
    flagged_effective = has_evidence & effective.notna()
    if (flagged_effective & (effective >= kickoff)).any():
        return False
    return True


def _check_no_double_counting(
    snapshots: pd.DataFrame, config: MeasurementConfig
) -> bool:
    adjusted_ids = {
        spec.measurement_id for spec in config.measurements if spec.is_adjusted
    }
    context_ids = {
        spec.measurement_id for spec in config.measurements if not spec.is_adjusted
    }
    observed = snapshots[snapshots["coverage_status"] == "observed"]
    adjusted = observed[observed["measurement_id"].isin(adjusted_ids)]
    if not adjusted.empty:
        error = (
            adjusted["raw_aggregate"].astype(float)
            - adjusted["adjusted_value"].astype(float)
            - adjusted["schedule_strength_component"].astype(float)
        ).abs()
        if (error > 1e-9).any():
            return False
    context = observed[observed["measurement_id"].isin(context_ids)]
    if not context.empty:
        if (
            context["adjusted_value"].astype(float)
            != context["raw_aggregate"].astype(float)
        ).any():
            return False
        if context["schedule_strength_component"].notna().any():
            return False
    return True


def _terminal_ppso_summary(terminal_snapshots: pd.DataFrame) -> dict[str, Any]:
    """Report and validate v3's expected terminal PPSO football-unit range."""
    rows = terminal_snapshots[
        (terminal_snapshots["measurement_id"] == "points_per_scoring_opportunity")
        & (terminal_snapshots["coverage_status"] == "observed")
    ]
    summary: dict[str, Any] = {}
    for (season, role), group in rows.groupby(["season", "unit_role"]):
        mean = float(pd.to_numeric(group["adjusted_value"], errors="coerce").mean())
        summary[f"{int(season)}/{role}"] = {"mean": mean, "in_range": 2 <= mean <= 6}
    return summary


def build_rating_audit_report(
    *,
    observations: pd.DataFrame,
    snapshots: pd.DataFrame,
    terminal_snapshots: pd.DataFrame,
    games: pd.DataFrame,
    reconciled_team_game: pd.DataFrame | None,
    config: MeasurementConfig,
    observations_ref: Mapping[str, Any],
    snapshots_ref: Mapping[str, Any],
    terminal_snapshots_ref: Mapping[str, Any],
    parent_refs: tuple[Mapping[str, Any], ...] = (),
    cutoff: str | None = None,
    code_sha: str | None = None,
    build_audit: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble the immutable Phase 1 coverage, redundancy, and lineage report."""
    seasons = (
        sorted(
            int(season)
            for season in pd.to_numeric(observations["season"], errors="coerce")
            .dropna()
            .unique()
        )
        if not observations.empty
        else []
    )
    temporal_counts = (
        observations["temporal_status"].value_counts(dropna=False).to_dict()
    )
    eligible_historical = int(
        (observations["temporal_status"] == "reconstructed").sum()
    )
    eligible_protected = int((observations["temporal_status"] == "authentic").sum())

    observation_keys = ["season", "game_id", "team", "measurement_id", "unit_role"]
    snapshot_keys = ["season", "as_of_game_id", "team", "measurement_id", "unit_role"]
    terminal_keys = ["season", "team", "measurement_id", "unit_role"]
    observation_games = set(
        zip(
            pd.to_numeric(observations["season"], errors="coerce"),
            pd.to_numeric(observations["game_id"], errors="coerce"),
        )
    )
    if reconciled_team_game is not None and not reconciled_team_game.empty:
        reconciled_pairs = set(
            zip(
                pd.to_numeric(reconciled_team_game["season"], errors="coerce"),
                pd.to_numeric(reconciled_team_game["game_id"], errors="coerce"),
            )
        )
        source_reconciliation_ok = observation_games.issubset(reconciled_pairs)
    else:
        source_reconciliation_ok = True

    market_conflicts = (
        market_field_conflicts(observations.columns)
        + market_field_conflicts(snapshots.columns)
        + market_field_conflicts(terminal_snapshots.columns)
    )
    observed = observations["coverage_status"].eq("observed")
    denominator = pd.to_numeric(observations["denominator"], errors="coerce")
    expected_raw = pd.to_numeric(
        observations["numerator"], errors="coerce"
    ) / denominator.replace(0, float("nan"))
    ratios_ok = bool(
        (
            ~observed
            | (pd.to_numeric(observations["raw_value"], errors="coerce") - expected_raw)
            .abs()
            .lt(1e-9)
        ).all()
    )
    zero_exposure_ok = bool(
        (denominator.ne(0) | observations["raw_value"].isna()).all()
    )
    authentic_ok = bool(
        (
            ~observations["temporal_status"].eq("authentic")
            | (
                observations["effective_at"].notna()
                & observations["eligible_after"].notna()
            )
        ).all()
    )
    terminal_seasons = set(
        pd.to_numeric(terminal_snapshots["season"], errors="coerce")
        .dropna()
        .astype(int)
    )
    terminal_ppso = _terminal_ppso_summary(terminal_snapshots)
    reconciliation = build_audit.get("score_reconciliation", {}) if build_audit else {}
    score_stream_reconciliation_ok = all(
        float(values.get("exact_rate", 0.0)) >= 0.94
        for season, values in reconciliation.items()
        if int(season) in config.historical_development_seasons
    )

    report = {
        "report_schema_version": "rating_measurement_audit_v2",
        "measurement_design_id": config.design_id,
        "seasons": seasons,
        "lineage": {
            "observations_ref": dict(observations_ref),
            "snapshots_ref": dict(snapshots_ref),
            "terminal_snapshots_ref": dict(terminal_snapshots_ref),
            "measurement_config_version": config.config_version,
            "parent_refs": [dict(ref) for ref in parent_refs],
            "cutoff": cutoff,
            "code_sha": code_sha,
        },
        "observations": {
            "total_rows": int(len(observations)),
            "coverage_by_season_measurement_role": _season_measurement_coverage(
                observations
            ),
            "temporal_status_counts": {
                str(key): int(value) for key, value in temporal_counts.items()
            },
            "rows_eligible_for_historical_development": eligible_historical,
            "rows_eligible_for_protected_use": eligible_protected,
            "quality_flag_counts": (
                build_audit.get("quality_flag_counts", {}) if build_audit else {}
            ),
            "score_reconciliation": reconciliation,
            "excluded_games": (
                build_audit.get("excluded_games", []) if build_audit else []
            ),
            "out_of_scope_season_games": (
                build_audit.get("out_of_scope_season_games", {}) if build_audit else {}
            ),
        },
        "snapshots": {
            "total_rows": int(len(snapshots)),
            "missing_rows_by_reason": (
                snapshots["missing_reason"].value_counts(dropna=True).to_dict()
            ),
        },
        "terminal_snapshots": {
            "total_rows": int(len(terminal_snapshots)),
            "seasons": sorted(terminal_seasons),
            "ppso_terminal_means": terminal_ppso,
        },
        "redundancy": {
            "spearman_adjusted_pregame_snapshots": _redundancy_correlations(
                snapshots, config
            ),
        },
        "checks": {
            "uniqueness_ok": not (
                observations.duplicated(observation_keys).any()
                or snapshots.duplicated(snapshot_keys).any()
                or terminal_snapshots.duplicated(terminal_keys).any()
            ),
            "two_team_symmetry_ok": _check_symmetry(observations, games, config),
            "source_reconciliation_ok": source_reconciliation_ok,
            "score_stream_reconciliation_ok": score_stream_reconciliation_ok,
            "ppso_terminal_means_ok": all(
                bool(values["in_range"]) for values in terminal_ppso.values()
            )
            if config.uses_true_ppso
            else True,
            "no_2020_ok": 2020 not in seasons
            and not (
                snapshots.empty
                or 2020
                in set(
                    pd.to_numeric(snapshots["season"], errors="coerce")
                    .dropna()
                    .astype(int)
                )
            ),
            "no_2019_ok": 2019 not in seasons
            and not (
                snapshots.empty
                or 2019
                in set(
                    pd.to_numeric(snapshots["season"], errors="coerce")
                    .dropna()
                    .astype(int)
                )
            ),
            "future_rows_ok": _check_future_rows(snapshots),
            "authentic_timing_ok": authentic_ok,
            "measurement_ratio_ok": ratios_ok,
            "zero_exposure_null_ok": zero_exposure_ok,
            "terminal_coverage_ok": bool(terminal_seasons)
            and terminal_seasons.issubset(set(config.historical_development_seasons)),
            "no_double_counting_ok": _check_no_double_counting(snapshots, config),
            "market_free_ok": not market_conflicts,
            "market_field_conflicts": market_conflicts,
            "v1_inputs_superseded_ok": not bool(
                {
                    str(observations_ref.get("version_id")),
                    str(snapshots_ref.get("version_id")),
                }
                & {"b1da5e85a0438fab109937bf", "312917237b7b60cb10d61150"}
            ),
        },
    }
    report["all_checks_passed"] = all(
        value for key, value in report["checks"].items() if key.endswith("_ok")
    )
    return report
