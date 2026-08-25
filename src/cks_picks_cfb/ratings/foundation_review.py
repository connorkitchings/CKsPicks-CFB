"""Independent Phase 1--2 certification checks for the rating successor."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd
import yaml

from cks_picks_cfb.data.lake import DatasetRef
from cks_picks_cfb.ratings.contracts import (
    MeasurementContractError,
    market_field_conflicts,
)
from cks_picks_cfb.ratings.state_contracts import (
    CORE_MEASUREMENTS,
    TeamStateConfig,
)

FOUNDATION_REVIEW_CONFIG_VERSION = "rating_foundation_review_v1"
FOUNDATION_REVIEW_SCHEMA_VERSION = "rating_foundation_review_v1"
_CORE_SNAPSHOT_ROLES = tuple(
    (measurement, role)
    for measurement in CORE_MEASUREMENTS
    for role in ("offense", "defense")
)


def _sha(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@dataclass(frozen=True)
class FoundationReviewConfig:
    research_prefix: str
    measurement_config_path: str
    team_state_config_path: str
    adjustment_sample_targets_per_season: int
    phase1: Mapping[str, str]
    phase2: Mapping[str, str]
    raw_config: Mapping[str, Any]

    @property
    def design_id(self) -> str:
        return _sha(self.raw_config)


def load_foundation_review_config(path: str | Path) -> FoundationReviewConfig:
    raw = yaml.safe_load(Path(path).read_text())
    if (
        not isinstance(raw, Mapping)
        or raw.get("foundation_review_config_version")
        != FOUNDATION_REVIEW_CONFIG_VERSION
    ):
        raise MeasurementContractError("Unsupported foundation review configuration")
    try:
        phase1 = raw["phase1"]
        phase2 = raw["phase2"]
        if not isinstance(phase1, Mapping) or not isinstance(phase2, Mapping):
            raise TypeError
        config = FoundationReviewConfig(
            research_prefix=str(raw["research_prefix"]).rstrip("/"),
            measurement_config_path=str(raw["measurement_config_path"]),
            team_state_config_path=str(raw["team_state_config_path"]),
            adjustment_sample_targets_per_season=int(
                raw["adjustment_sample_targets_per_season"]
            ),
            phase1={str(key): str(value) for key, value in phase1.items()},
            phase2={str(key): str(value) for key, value in phase2.items()},
            raw_config=raw,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise MeasurementContractError(
            "Incomplete foundation review configuration"
        ) from exc
    if config.adjustment_sample_targets_per_season <= 0:
        raise MeasurementContractError("Foundation review requires adjustment samples")
    return config


def ref_matches(ref: DatasetRef, *, expected_version: str, expected_sha: str) -> bool:
    return ref.version_id == expected_version and ref.content_sha == expected_sha


def _finite_close(
    actual: pd.Series, expected: pd.Series, *, atol: float = 1e-10
) -> bool:
    actual_values = pd.to_numeric(actual, errors="coerce").to_numpy(dtype=float)
    expected_values = pd.to_numeric(expected, errors="coerce").to_numpy(dtype=float)
    return bool(
        np.isfinite(actual_values).all()
        and np.isfinite(expected_values).all()
        and np.allclose(actual_values, expected_values, rtol=0.0, atol=atol)
    )


def _null_or_close(
    actual: pd.Series, expected: pd.Series, *, atol: float = 1e-10
) -> bool:
    actual_values = pd.to_numeric(actual, errors="coerce")
    expected_values = pd.to_numeric(expected, errors="coerce")
    same_missing = actual_values.isna().equals(expected_values.isna())
    present = actual_values.notna() & expected_values.notna()
    return bool(
        same_missing
        and np.allclose(
            actual_values[present].to_numpy(dtype=float),
            expected_values[present].to_numpy(dtype=float),
            rtol=0.0,
            atol=atol,
        )
    )


def _flags(value: object) -> set[str]:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return set()
    return {item for item in str(value).split(";") if item}


def _observation_checks(observations: pd.DataFrame) -> dict[str, bool]:
    denominator = pd.to_numeric(observations["denominator"], errors="coerce")
    numerator = pd.to_numeric(observations["numerator"], errors="coerce")
    raw = pd.to_numeric(observations["raw_value"], errors="coerce")
    positive = denominator > 0
    zero = denominator == 0
    expected = numerator[positive] / denominator[positive]
    return {
        "observation_unique_identity": not observations.duplicated(
            ["season", "game_id", "team", "measurement_id", "unit_role"]
        ).any(),
        "observation_ratio_and_exposure": bool(
            denominator.notna().all()
            and (denominator >= 0).all()
            and _finite_close(raw[positive], expected)
        ),
        "zero_exposure_has_null_reason": bool(
            raw[zero].isna().all()
            and observations.loc[zero, "missing_reason"].notna().all()
        ),
        "observation_temporal_status": bool(
            observations["temporal_status"].isin(("authentic", "reconstructed")).all()
            and (
                observations.loc[
                    observations["temporal_status"].eq("authentic"), "effective_at"
                ]
                .notna()
                .all()
            )
        ),
        "observation_forbidden_seasons_excluded": not set(
            pd.to_numeric(observations["season"], errors="coerce").dropna().astype(int)
        )
        & {2019, 2020},
    }


def _snapshot_checks(snapshots: pd.DataFrame) -> dict[str, bool]:
    cutoff = pd.to_datetime(snapshots["as_of_kickoff_utc"], utc=True, errors="coerce")
    max_kickoff = pd.to_datetime(
        snapshots["evidence_max_kickoff_utc"], utc=True, errors="coerce"
    )
    max_effective = pd.to_datetime(
        snapshots["evidence_max_effective_at"], utc=True, errors="coerce"
    )
    observed = snapshots["coverage_status"].eq("observed")
    missing = snapshots["coverage_status"].eq("missing")
    return {
        "snapshot_unique_identity": not snapshots.duplicated(
            ["season", "as_of_game_id", "team", "measurement_id", "unit_role"]
        ).any(),
        "snapshot_pregame_bounds": bool(
            (max_kickoff.dropna() < cutoff[max_kickoff.notna()]).all()
            and (max_effective.dropna() < cutoff[max_effective.notna()]).all()
        ),
        "snapshot_exposure_and_missingness": bool(
            (pd.to_numeric(snapshots.loc[observed, "primary_exposure"]) > 0).all()
            and snapshots.loc[observed, "adjusted_value"].notna().all()
            and snapshots.loc[missing, "adjusted_value"].isna().all()
            and snapshots.loc[missing, "missing_reason"].notna().all()
        ),
        "snapshot_forbidden_seasons_excluded": not set(
            pd.to_numeric(snapshots["season"], errors="coerce").dropna().astype(int)
        )
        & {2019, 2020},
    }


def _eligible_adjustment_rows(
    observations: pd.DataFrame, *, cutoff: pd.Timestamp, season: int, config: Any
) -> pd.DataFrame:
    """Recreate Phase 1 point-in-time eligibility without calling its builder."""
    historical = set(config.historical_development_seasons)
    authentic = observations["temporal_status"].astype(str).eq("authentic")
    reconstructed = observations["temporal_status"].astype(str).eq("reconstructed")
    eligible = observations["kickoff_ts"].lt(cutoff) & pd.to_numeric(
        observations["season"], errors="coerce"
    ).eq(season)
    eligible &= (
        authentic
        & observations["effective_ts"].notna()
        & observations["effective_ts"].lt(cutoff)
    ) | (reconstructed & (season in historical))
    return observations[eligible]


def _recompute_adjustment(
    rows: pd.DataFrame, *, iterations: int
) -> tuple[dict[str, float], dict[str, float]]:
    """Independently reproduce exposure-weighted additive opponent adjustment."""
    evidence: dict[str, dict[str, tuple[float, float]]] = {}
    raw: dict[str, dict[str, float]] = {}
    edges: dict[str, pd.DataFrame] = {}
    for role in ("offense", "defense"):
        role_rows = rows[rows["unit_role"].eq(role)]
        grouped = role_rows.groupby("team", observed=True).agg(
            numerator=("numerator", "sum"), denominator=("denominator", "sum")
        )
        evidence[role] = {
            str(team): (float(value.numerator), float(value.denominator))
            for team, value in grouped.iterrows()
        }
        raw[role] = {
            team: numerator / denominator if denominator > 0 else float("nan")
            for team, (numerator, denominator) in evidence[role].items()
        }
        edges[role] = role_rows[
            ["game_id", "team", "opponent", "denominator"]
        ].drop_duplicates()

    adjusted_offense = dict(raw["offense"])
    adjusted_defense = dict(raw["defense"])

    def center(values: Mapping[str, float], role: str) -> float:
        included = [
            (value, evidence[role][team][1])
            for team, value in values.items()
            if np.isfinite(value) and evidence[role][team][1] > 0
        ]
        if not included:
            return float("nan")
        return float(
            np.average(
                [value for value, _ in included],
                weights=[weight for _, weight in included],
            )
        )

    for _ in range(iterations):
        offense_center = center(adjusted_offense, "offense")
        defense_center = center(adjusted_defense, "defense")
        updated: dict[str, dict[str, float]] = {
            "offense": dict(raw["offense"]),
            "defense": dict(raw["defense"]),
        }
        for role, opponent_values, opponent_center in (
            ("offense", adjusted_defense, defense_center),
            ("defense", adjusted_offense, offense_center),
        ):
            values = edges[role].copy()
            values["opponent_adjusted"] = values["opponent"].map(opponent_values)
            values = values[values["opponent_adjusted"].notna()]
            if values.empty:
                continue
            values["weighted_delta"] = (
                values["opponent_adjusted"] - opponent_center
            ) * values["denominator"]
            totals = values.groupby("team", observed=True).agg(
                weighted_delta=("weighted_delta", "sum"),
                denominator=("denominator", "sum"),
            )
            for team, value in totals.iterrows():
                if float(value.denominator) > 0:
                    updated[role][str(team)] = raw[role][str(team)] - float(
                        value.weighted_delta / value.denominator
                    )
        adjusted_offense = updated["offense"]
        adjusted_defense = updated["defense"]
    return adjusted_offense, adjusted_defense


def _sample_adjustment_check(
    observations: pd.DataFrame,
    snapshots: pd.DataFrame,
    *,
    measurement_config: Any,
    targets_per_season: int,
) -> tuple[bool, int]:
    values = observations.copy()
    values["kickoff_ts"] = pd.to_datetime(values["kickoff_utc"], utc=True)
    values["effective_ts"] = pd.to_datetime(values["effective_at"], utc=True)
    values = values[values["coverage_status"].eq("observed")]
    adjusted = {
        item.measurement_id
        for item in measurement_config.measurements
        if item.is_adjusted
    }
    core = snapshots[
        snapshots["measurement_id"].isin(adjusted)
        & snapshots["unit_role"].isin(("offense", "defense"))
    ]
    targets = (
        core.loc[
            core["coverage_status"].eq("observed"),
            ["season", "as_of_game_id", "as_of_kickoff_utc"],
        ]
        .drop_duplicates()
        .sort_values(["season", "as_of_kickoff_utc", "as_of_game_id"])
        .groupby("season", sort=True)
        .head(targets_per_season)
    )
    checked = 0
    for target in targets.itertuples(index=False):
        cutoff = pd.Timestamp(target.as_of_kickoff_utc)
        eligible = _eligible_adjustment_rows(
            values, cutoff=cutoff, season=int(target.season), config=measurement_config
        )
        target_rows = core[
            (core["season"] == target.season)
            & (core["as_of_game_id"] == target.as_of_game_id)
        ]
        for measurement_id in adjusted:
            expected_offense, expected_defense = _recompute_adjustment(
                eligible[eligible["measurement_id"].eq(measurement_id)],
                iterations=measurement_config.adjustment_iterations,
            )
            for role, expected in (
                ("offense", expected_offense),
                ("defense", expected_defense),
            ):
                rows = target_rows[
                    (target_rows["measurement_id"] == measurement_id)
                    & (target_rows["unit_role"] == role)
                    & target_rows["coverage_status"].eq("observed")
                ]
                for row in rows.itertuples(index=False):
                    value = expected.get(row.team)
                    if value is None or not np.isclose(
                        float(row.adjusted_value), value, atol=1e-10, rtol=0.0
                    ):
                        return False, checked
                    checked += 1
    return checked > 0, checked


def _state_algebra_checks(measurement_states: pd.DataFrame) -> dict[str, bool]:
    rows = measurement_states.copy()
    native = pd.to_numeric(rows["native_adjusted_value"], errors="coerce")
    exposure = pd.to_numeric(rows["primary_exposure"], errors="coerce")
    center = pd.to_numeric(rows["standardization_center"], errors="coerce")
    scale = pd.to_numeric(rows["standardization_scale"], errors="coerce")
    expected_z = (native - center) / scale
    expected_z = expected_z.where(rows["unit_role"].eq("offense"), -expected_z)
    expected_z = expected_z.where(native.notna() & exposure.gt(0))
    prior_variance = pd.to_numeric(rows["prior_variance"], errors="coerce")
    prior_precision = 1.0 / prior_variance
    observation_precision = pd.to_numeric(
        rows["observation_precision"], errors="coerce"
    )
    posterior_variance = 1.0 / (prior_precision + observation_precision)
    posterior_mean = (
        prior_precision * pd.to_numeric(rows["prior_mean"], errors="coerce")
        + observation_precision * expected_z.fillna(0.0)
    ) * posterior_variance
    return {
        "component_unique_identity": not rows.duplicated(
            ["state_id", "team", "measurement_id", "unit_role"]
        ).any(),
        "component_standardization_and_direction": bool(
            (scale > 0).all() and _null_or_close(rows["observed_z"], expected_z)
        ),
        "component_posterior_algebra": bool(
            _finite_close(rows["prior_precision"], prior_precision)
            and _finite_close(rows["posterior_variance"], posterior_variance)
            and _finite_close(rows["posterior_mean"], posterior_mean)
            and _finite_close(rows["posterior_sd"], np.sqrt(posterior_variance))
            and _finite_close(
                rows["observed_weight"],
                observation_precision * posterior_variance,
            )
            and _finite_close(
                rows["prior_weight"],
                1.0 - observation_precision * posterior_variance,
            )
        ),
        "component_positive_uncertainty": bool(
            (pd.to_numeric(rows["posterior_sd"], errors="coerce") > 0).all()
        ),
    }


def _prior_carryover_check(
    measurement_states: pd.DataFrame, config: TeamStateConfig
) -> bool:
    rows = measurement_states.copy()
    terminal = rows[rows["state_kind"].eq("season_terminal")].set_index(
        ["season", "team", "measurement_id", "unit_role"]
    )
    for row in rows.itertuples(index=False):
        season = int(row.season)
        previous_key = (season - 1, row.team, row.measurement_id, row.unit_role)
        previous = (
            terminal.loc[previous_key] if previous_key in terminal.index else None
        )
        if previous is None:
            if not (
                np.isclose(float(row.prior_mean), config.neutral_mean)
                and np.isclose(float(row.prior_variance), config.neutral_variance)
                and pd.isna(row.prior_source_season)
                and "neutral_preseason_prior" in _flags(row.quality_flags)
            ):
                return False
            continue
        if isinstance(previous, pd.DataFrame):
            return False
        expected_mean = config.offseason_rho * float(previous.posterior_mean)
        expected_variance = config.offseason_rho**2 * float(
            previous.posterior_variance
        ) + (1 - config.offseason_rho**2)
        if not (
            int(row.prior_source_season) == season - 1
            and np.isclose(float(row.prior_mean), expected_mean, atol=1e-10, rtol=0.0)
            and np.isclose(
                float(row.prior_variance), expected_variance, atol=1e-10, rtol=0.0
            )
        ):
            return False
    return True


def _composite_check(
    measurement_states: pd.DataFrame, team_states: pd.DataFrame, config: TeamStateConfig
) -> bool:
    components = measurement_states.copy()
    teams = team_states.set_index(["state_id", "team"])
    for (state_id, team), rows in components.groupby(["state_id", "team"], sort=False):
        if (state_id, team) not in teams.index or len(rows) != 8:
            return False
        team_row = teams.loc[(state_id, team)]
        if isinstance(team_row, pd.DataFrame):
            return False
        expected: dict[str, float] = {}
        for role in ("offense", "defense"):
            role_rows = rows[rows["unit_role"].eq(role)]
            if set(role_rows["measurement_id"]) != set(CORE_MEASUREMENTS):
                return False
            weights = role_rows["measurement_id"].map(
                {item.measurement_id: item.weight for item in config.components}
            )
            expected[f"{role}_mean"] = float(
                (weights * pd.to_numeric(role_rows["posterior_mean"])).sum()
            )
            expected[f"{role}_sd"] = float(
                (weights * pd.to_numeric(role_rows["posterior_sd"])).sum()
            )
            expected[f"{role}_observed_weight"] = float(
                (weights * pd.to_numeric(role_rows["observed_weight"])).sum()
            )
        expected["overall_mean"] = (
            expected["offense_mean"] + expected["defense_mean"]
        ) / 2
        expected["overall_sd"] = (expected["offense_sd"] + expected["defense_sd"]) / 2
        if any(
            not np.isclose(float(team_row[key]), value, atol=1e-10, rtol=0.0)
            for key, value in expected.items()
        ):
            return False
    return True


def _coverage_check(snapshots: pd.DataFrame, team_states: pd.DataFrame) -> bool:
    expected = snapshots[
        (snapshots["measurement_id"] == "epa_per_play")
        & snapshots["unit_role"].eq("offense")
    ][["season", "as_of_game_id", "team"]].drop_duplicates()
    pregame = team_states[team_states["state_kind"].eq("pregame")]
    actual = pregame[["season", "as_of_game_id", "team"]].drop_duplicates()
    two_teams = pregame.groupby(["season", "as_of_game_id"], observed=True).size().eq(2)
    return bool(
        set(map(tuple, expected.to_numpy())) == set(map(tuple, actual.to_numpy()))
        and two_teams.all()
        and pregame[["offense_mean", "defense_mean", "overall_mean"]]
        .notna()
        .all()
        .all()
    )


def build_foundation_review(
    *,
    observations: pd.DataFrame,
    snapshots: pd.DataFrame,
    terminal_snapshots: pd.DataFrame,
    measurement_states: pd.DataFrame,
    team_states: pd.DataFrame,
    phase1_audit: Mapping[str, Any],
    phase2_audit: Mapping[str, Any],
    refs: Mapping[str, DatasetRef],
    config: FoundationReviewConfig,
    measurement_config: Any,
    team_state_config: TeamStateConfig,
    code_sha: str,
) -> dict[str, Any]:
    """Recompute the Phase 1--2 handoff without constructing predictions."""
    checks = {
        "phase1_audit_passed": bool(phase1_audit.get("all_checks_passed"))
        and phase1_audit.get("report_schema_version") == "rating_measurement_audit_v2",
        "phase2_audit_passed": bool(phase2_audit.get("all_checks_passed"))
        and phase2_audit.get("report_schema_version") == "rating_team_state_audit_v1",
        "phase1_ref_identity": all(
            ref_matches(
                refs[key],
                expected_version=config.phase1[f"expected_{key}_version"],
                expected_sha=config.phase1[f"expected_{key}_sha"],
            )
            for key in ("observations", "snapshots", "terminal")
        ),
        "phase2_ref_identity": all(
            ref_matches(
                refs[key],
                expected_version=config.phase2[f"expected_{key}_version"],
                expected_sha=config.phase2[f"expected_{key}_sha"],
            )
            for key in ("measurement_states", "team_states")
        ),
    }
    checks.update(_observation_checks(observations))
    checks.update(_snapshot_checks(snapshots))
    adjustment_ok, adjusted_rows = _sample_adjustment_check(
        observations,
        snapshots,
        measurement_config=measurement_config,
        targets_per_season=config.adjustment_sample_targets_per_season,
    )
    checks["opponent_adjustment_recomputed"] = adjustment_ok
    checks.update(_state_algebra_checks(measurement_states))
    checks["prior_carryover_recomputed"] = _prior_carryover_check(
        measurement_states, team_state_config
    )
    checks["team_composites_recomputed"] = _composite_check(
        measurement_states, team_states, team_state_config
    )
    checks["pregame_two_team_coverage"] = _coverage_check(snapshots, team_states)
    terminal = team_states[team_states["state_kind"].eq("season_terminal")]
    checks["terminal_identity"] = bool(
        terminal.apply(
            lambda row: row["state_id"]
            == f"terminal:{int(row['season'])}:{row['team']}",
            axis=1,
        ).all()
    )
    checks["phase3_pregame_handoff_only"] = bool(
        set(team_states["state_kind"].dropna()) == {"pregame", "season_terminal"}
        and team_states.loc[team_states["state_kind"].eq("pregame"), "state_id"]
        .astype(str)
        .str.startswith("game:")
        .all()
    )
    checks["market_and_forbidden_inputs_absent"] = not (
        market_field_conflicts(observations.columns)
        + market_field_conflicts(snapshots.columns)
        + market_field_conflicts(terminal_snapshots.columns)
        + market_field_conflicts(measurement_states.columns)
        + market_field_conflicts(team_states.columns)
    ) and not set(pd.to_numeric(team_states["season"]).astype(int)) & {2019, 2020}
    return {
        "report_schema_version": FOUNDATION_REVIEW_SCHEMA_VERSION,
        "foundation_review_design_id": config.design_id,
        "code_sha": code_sha,
        "input_refs": {key: ref.__dict__ for key, ref in refs.items()},
        "checks": checks,
        "diagnostics": {
            "adjustment_rows_recomputed": adjusted_rows,
            "observation_rows": int(len(observations)),
            "snapshot_rows": int(len(snapshots)),
            "terminal_snapshot_rows": int(len(terminal_snapshots)),
            "measurement_state_rows": int(len(measurement_states)),
            "team_state_rows": int(len(team_states)),
            "pregame_team_rows": int(team_states["state_kind"].eq("pregame").sum()),
            "terminal_team_rows": int(
                team_states["state_kind"].eq("season_terminal").sum()
            ),
        },
        "all_checks_passed": bool(all(checks.values())),
    }
