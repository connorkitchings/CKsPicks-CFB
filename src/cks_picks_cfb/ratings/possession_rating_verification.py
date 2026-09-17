"""Verifier-owned V5-03 rating reconstruction and artifact verification.

This module is deliberately independent of the producer: it must not import
``possession_ratings``, ``possession_rating_tournament``,
``possession_rating_materializer``, or either research runner.  It may share
only generic storage readers, schema contracts, and signing utilities.  Every
prior, state, bridge, bootstrap, and selection value is re-derived here from
the certified R6 and Repair v2 parents so a producer defect cannot mirror
itself into agreement.
"""

from __future__ import annotations

import hashlib
import json
import warnings
from collections.abc import Mapping
from dataclasses import dataclass, field
from math import isfinite
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.linear_model import Ridge

from cks_picks_cfb.data.data_first_phase2 import (
    DEVELOPMENT_SEASONS,
    FORBIDDEN_SEASONS,
)
from cks_picks_cfb.data.data_first_phase2d import (
    PHASE3_DATASETS,
    REPLACEMENT_ELIGIBILITY_SCHEMA,
    signed_payload,
    verify_signed_payload,
)
from cks_picks_cfb.data.data_first_possession_rating_v1 import (
    ATTRIBUTION_COLUMNS,
    DEFINITIONS,
    OUTER_SEASONS,
    PRIOR_FAMILIES,
    RATING_DATASETS,
    UPDATERS,
    candidate_id,
    candidate_registry,
)
from cks_picks_cfb.data.data_first_possession_v1 import (
    ADJUSTED_MEASUREMENTS,
    POPULATION_COLUMNS,
    POSSESSION_DATASETS,
    ROLES,
)
from cks_picks_cfb.data.lake import (
    PARTITIONED_DATASET_KIND,
    DatasetRef,
    PartitionedDatasetRef,
    canonical_frame_digest,
    partition_order_key,
    partitioned_records_sha,
    read_dataset,
)
from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame
from cks_picks_cfb.preseason_features import canonical_team

VERIFICATION_MANIFEST_SCHEMA = "data_first_possession_rating_verification_v1"

_RHO = 0.60
_K_BY_DEFINITION = {"ppp": 8.0, "epa_per_possession": 20.0}
_HALF_LIFE: dict[str, float | None] = {
    "exposure": None,
    "half_life_2": 2.0,
    "half_life_4": 4.0,
    "half_life_8": 8.0,
}
_FBS_MINIMUM_SCHEDULED_GAMES = 8
_NOISE_FIT_MINIMUM_ROWS = 8
_NOISE_FIT_MINIMUM_SEASONS = 2
_EMPTY_DATASET_SALT = "data_first_possession_rating_empty_v1"

_CONTEXT_BLOCKS: dict[str, tuple[str, ...]] = {
    "recruiting_ridge": (
        "recruiting_current",
        "recruiting_4yr",
        "recruiting_trend",
    ),
    "returning_production_ridge": (
        "return_total_ppa",
        "return_passing_ppa",
        "return_rushing_ppa",
        "return_receiving_ppa",
        "return_percent_ppa",
        "return_passing_usage",
        "return_rushing_usage",
    ),
    "continuity_ridge": (
        "coach_tenure_lower_bound",
        "coach_tenure_censored",
        "coach_new",
        "roster_same_team_return_share",
        "roster_same_team_return_qb_count",
    ),
}
_CONTEXT_BLOCKS["all_context_ridge"] = tuple(
    column for values in _CONTEXT_BLOCKS.values() for column in values
)
_CONTEXT_ALIASES = {
    "recruiting_current": "recruiting_current_points",
    "recruiting_4yr": "recruiting_strict_four_class_average_points",
    "recruiting_trend": "recruiting_current_minus_available_average",
}


class IndependentRatingError(ValueError):
    """Raised when independent reconstruction disagrees with stored evidence."""


def _json_sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str).encode()
    ).hexdigest()


def _utc_timestamp(value: Any) -> pd.Timestamp:
    return pd.Timestamp(value)


# --------------------------------------------------------------------------
# Generic parent readers (shared lake utilities only)
# --------------------------------------------------------------------------


def _part_ref(value: Mapping[str, Any], *, name: str) -> PartitionedDatasetRef:
    try:
        return PartitionedDatasetRef(
            artifact_kind=str(value["artifact_kind"]),
            dataset=str(value["dataset"]),
            version_id=str(value["version_id"]),
            schema_version=str(value["schema_version"]),
            content_sha=str(value["content_sha"]),
            records_sha=str(value["records_sha"]),
            uri=str(value["uri"]),
            row_count=int(value["row_count"]),
            partition_keys=tuple(value["partition_keys"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise IndependentRatingError(f"stored reference is malformed: {name}") from exc


def _ds_ref(value: Mapping[str, Any], *, name: str) -> DatasetRef:
    fields = ("dataset", "version_id", "schema_version", "content_sha", "uri")
    if missing := [item for item in fields if not value.get(item)]:
        raise IndependentRatingError(
            f"stored dataset reference is malformed: {name} {missing}"
        )
    return DatasetRef(**{item: value[item] for item in fields})


def _stored_parts(
    storage: Any, ref: PartitionedDatasetRef
) -> tuple[list[dict[str, Any]], list[tuple[dict[str, Any], pd.DataFrame]]]:
    """Read every stored partition with full checksum and schema validation."""
    raw = storage.read_bytes(ref.uri)
    if hashlib.sha256(raw).hexdigest() != ref.content_sha:
        raise IndependentRatingError(
            f"stored manifest checksum mismatch: {ref.dataset}"
        )
    manifest = json.loads(raw)
    if (
        manifest.get("artifact_kind") != PARTITIONED_DATASET_KIND
        or manifest.get("dataset") != ref.dataset
        or manifest.get("schema_version") != ref.schema_version
        or tuple(manifest.get("partition_keys") or ()) != ref.partition_keys
    ):
        raise IndependentRatingError(
            f"stored manifest identity mismatch: {ref.dataset}"
        )
    parts = list(manifest.get("parts") or [])
    if partitioned_records_sha(parts, ref.partition_keys) != ref.records_sha:
        raise IndependentRatingError(f"stored logical digest mismatch: {ref.dataset}")
    if sum(int(part["row_count"]) for part in parts) != ref.row_count:
        raise IndependentRatingError(f"stored row-count mismatch: {ref.dataset}")
    schema = schema_for(ref.dataset, ref.schema_version)
    frames: list[tuple[dict[str, Any], pd.DataFrame]] = []
    previous: tuple[tuple[str, int, Any], ...] | None = None
    for part in parts:
        partition = dict(part["partition"])
        order_key = partition_order_key(partition)
        if tuple(partition) != ref.partition_keys or (
            previous is not None and order_key <= previous
        ):
            raise IndependentRatingError(
                f"stored parts are malformed or unordered: {ref.dataset}"
            )
        previous = order_key
        child = part.get("ref")
        if child is None:
            if int(part["row_count"]) != 0:
                raise IndependentRatingError(
                    f"stored nonempty partition lacks a child: {ref.dataset}"
                )
            frames.append((partition, pd.DataFrame(columns=list(schema.required))))
            continue
        try:
            frame = read_dataset(storage, _ds_ref(child, name=f"{ref.dataset}:child"))
        except Exception as exc:
            raise IndependentRatingError(
                f"stored child is unreadable: {ref.dataset} {partition}"
            ) from exc
        validate_frame(frame, schema)
        if canonical_frame_digest(frame, columns=schema.required) != str(
            part["records_sha"]
        ):
            raise IndependentRatingError(
                f"stored child digest mismatch: {ref.dataset} {partition}"
            )
        frames.append((partition, frame))
    return parts, frames


def _concat_stored(frames: list[pd.DataFrame], *, columns: list[str]) -> pd.DataFrame:
    if not frames:
        return pd.DataFrame(columns=columns)
    normalized = [frame.loc[:, columns].copy() for frame in frames]
    for column in columns:
        if any(frame[column].isna().all() for frame in normalized) and any(
            frame[column].notna().any() for frame in normalized
        ):
            for frame in normalized:
                frame[column] = frame[column].astype(object)
    return pd.concat(normalized, ignore_index=True, sort=False)


def _stream_parent(
    storage: Any, *, name: str, value: Mapping[str, Any]
) -> pd.DataFrame:
    ref = _part_ref(value, name=name)
    expected_dataset, expected_schema = POSSESSION_DATASETS[name]
    if (
        ref.artifact_kind != PARTITIONED_DATASET_KIND
        or ref.dataset != expected_dataset
        or ref.schema_version != expected_schema
    ):
        raise IndependentRatingError(f"parent output identity mismatch: {name}")
    _, stored = _stored_parts(storage, ref)
    schema = schema_for(expected_dataset, expected_schema)
    frames = [frame for _, frame in stored if not frame.empty]
    if not frames:
        return pd.DataFrame(columns=list(schema.required))
    return _concat_stored(frames, columns=list(schema.required))


# --------------------------------------------------------------------------
# Parent loading (independent re-implementation of the sealed input contract)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class VerifierParents:
    population: pd.DataFrame
    observations: pd.DataFrame
    snapshots: pd.DataFrame
    terminal: pd.DataFrame
    outcomes: pd.DataFrame
    context: dict[str, pd.DataFrame]
    history_audit: dict[str, int]


def _v_context_blocks(auxiliary: pd.DataFrame) -> dict[str, pd.DataFrame]:
    required = {"family", "season", "team", "historical_eligible"}
    if not required.issubset(auxiliary.columns):
        raise IndependentRatingError("auxiliary source lacks contract columns")
    eligible = auxiliary[auxiliary["historical_eligible"].eq(True)].copy()
    eligible["team"] = eligible["team"].map(canonical_team)
    eligible["season"] = pd.to_numeric(eligible["season"], errors="raise").astype(int)
    if eligible["team"].isna().any():
        raise IndependentRatingError("auxiliary team identity is unresolved")
    blocks: dict[str, pd.DataFrame] = {}
    for family, columns in _CONTEXT_BLOCKS.items():
        source_columns = [_CONTEXT_ALIASES.get(column, column) for column in columns]
        missing = [
            column for column in source_columns if column not in eligible.columns
        ]
        if missing:
            raise IndependentRatingError(
                f"auxiliary source lacks admitted columns: {family} {missing}"
            )
        subset = eligible.loc[:, ["family", "season", "team", *source_columns]].copy()
        subset = subset[subset["family"].eq(family)]
        subset = subset.rename(columns=dict(zip(source_columns, list(columns))))
        subset = subset.drop_duplicates(["season", "team"], keep=False)
        blocks[family] = subset.loc[:, ["season", "team", *columns]].sort_values(
            ["season", "team"], kind="mergesort"
        )
    return blocks


def _v_core_refs(
    storage: Any, repair: Mapping[str, Any]
) -> dict[int, dict[str, DatasetRef]]:
    uri = ((repair.get("parents") or {}).get("core_eligibility") or {}).get("uri")
    if not uri:
        raise IndependentRatingError("Repair parent lacks core eligibility lineage")
    payload = json.loads(storage.read_bytes(str(uri)))
    if payload.get("schema_version") != REPLACEMENT_ELIGIBILITY_SCHEMA:
        raise IndependentRatingError("core eligibility schema mismatch")
    verify_signed_payload(payload, label="core eligibility")
    if (
        payload.get("state") != "eligible"
        or payload.get("production_activation_authorized") is not False
        or tuple(payload.get("development_seasons") or ()) != DEVELOPMENT_SEASONS
        or tuple(payload.get("forbidden_seasons") or ()) != FORBIDDEN_SEASONS
    ):
        raise IndependentRatingError("core eligibility is not sealed Preview evidence")
    result: dict[int, dict[str, DatasetRef]] = {}
    for value in payload.get("phase3_input_refs") or []:
        key = (int(value.get("season", -1)), str(value.get("dataset")))
        if value.get("eligible") is not True or key[1] not in PHASE3_DATASETS:
            raise IndependentRatingError(f"core eligibility rejects source {key}")
        result.setdefault(key[0], {})[key[1]] = _ds_ref(
            value, name=f"core:{key[0]}:{key[1]}"
        )
    seen = {
        (season, dataset) for season, values in result.items() for dataset in values
    }
    expected = {
        (season, dataset)
        for season in DEVELOPMENT_SEASONS
        for dataset in PHASE3_DATASETS
    }
    if seen != expected or any(
        {"byplay", "game_outcomes"} - set(values) for values in result.values()
    ):
        raise IndependentRatingError("core eligibility must provide the 70-ref set")
    return result


def _v_history_audit(
    storage: Any,
    *,
    value: Mapping[str, Any],
    snapshots: pd.DataFrame,
    progress: Any,
) -> dict[str, int]:
    ref = _part_ref(value, name="adjusted_history")
    boundary_values = {
        (
            int(row.season),
            int(row.week),
            int(row.as_of_game_id),
            str(row.team),
            str(row.unit_role),
            str(row.measurement_id),
        ): float(row.adjusted_value)
        for row in snapshots.itertuples(index=False)
        if pd.notna(row.adjusted_value)
    }
    parts_meta, stored_frames = _stored_parts(storage, ref)
    rows_seen = 0
    violations = 0
    value_mismatches = 0
    for index, (partition, frame) in enumerate(stored_frames, start=1):
        if frame.empty:
            continue
        available = pd.to_datetime(frame["source_available_utc"], utc=True)
        cutoff = pd.to_datetime(frame["target_week_cutoff_utc"], utc=True)
        strictly_later = (available <= cutoff) & frame["source_week"].astype(int).lt(
            frame["week"].astype(int)
        )
        violations += int((~strictly_later).sum())
        expected = pd.Series(
            [
                boundary_values.get(key)
                for key in zip(
                    frame["season"].astype(int),
                    frame["week"].astype(int),
                    frame["as_of_game_id"].astype(int),
                    frame["team"].astype(str),
                    frame["unit_role"].astype(str),
                    frame["measurement_id"].astype(str),
                    strict=True,
                )
            ],
            index=frame.index,
        )
        history_values = pd.to_numeric(frame["iteration_four_value"], errors="coerce")
        comparable = expected.notna() & history_values.notna()
        value_mismatches += int(
            (history_values[comparable] != expected[comparable]).sum()
        )
        rows_seen += len(frame)
        progress(
            "history_audit_part",
            dataset="adjusted_history",
            completed=index,
            total=len(parts_meta),
            rows=rows_seen,
            partition=partition,
        )
    if rows_seen != ref.row_count:
        raise IndependentRatingError("adjusted history row counts differ from manifest")
    if violations or value_mismatches:
        raise IndependentRatingError(
            "adjusted history violates cutoff chronology or snapshot consistency"
        )
    return {
        "history_parts": len(parts_meta),
        "history_rows": rows_seen,
        "availability_violations": violations,
        "snapshot_value_mismatches": value_mismatches,
    }


def load_verifier_parents(
    *,
    storage: Any,
    measurement: Mapping[str, Any],
    repair: Mapping[str, Any],
    progress: Any,
) -> VerifierParents:
    output_refs = measurement.get("output_refs") or {}
    if set(output_refs) != set(POSSESSION_DATASETS):
        raise IndependentRatingError("R6 manifest output set changed")
    population = _stream_parent(
        storage, name="population", value=output_refs["population"]
    ).loc[:, list(POPULATION_COLUMNS)]
    if len(population) != 8936 or int(population["forecast_eligible"].sum()) != 8935:
        raise IndependentRatingError("R6 population reconciliation changed")
    if population["season"].isin(FORBIDDEN_SEASONS).any():
        raise IndependentRatingError("R6 population contains a forbidden season")

    observations = _stream_parent(
        storage, name="observations", value=output_refs["observations"]
    )
    observations = observations[
        observations["measurement_id"].isin(ADJUSTED_MEASUREMENTS)
    ].reset_index(drop=True)

    terminal = _stream_parent(storage, name="terminal", value=output_refs["terminal"])

    snapshots = _stream_parent(
        storage, name="snapshots", value=output_refs["snapshots"]
    )
    snapshots = snapshots[
        snapshots["adjustment_iteration"].eq(4)
        & snapshots["measurement_id"].isin(ADJUSTED_MEASUREMENTS)
    ].reset_index(drop=True)

    auxiliary_ref = (repair.get("output_refs") or {}).get("auxiliary") or {}
    try:
        auxiliary = read_dataset(
            storage, _ds_ref(auxiliary_ref, name="repair:auxiliary")
        )
    except Exception as exc:
        raise IndependentRatingError("Repair auxiliary parent is unreadable") from exc
    context = _v_context_blocks(auxiliary)

    refs = _v_core_refs(storage, repair)
    try:
        outcome_frames = [
            read_dataset(storage, refs[season]["game_outcomes"])
            for season in sorted(refs)
        ]
    except Exception as exc:
        raise IndependentRatingError(
            "core-eligible game outcomes are unreadable"
        ) from exc
    outcomes = pd.concat(outcome_frames, ignore_index=True, sort=False).loc[
        :, ["season", "game_id", "completed", "home_points", "away_points"]
    ]
    for name in ("season", "game_id"):
        outcomes[name] = pd.to_numeric(outcomes[name], errors="raise").astype(int)

    history_audit = _v_history_audit(
        storage,
        value=output_refs["adjusted_history"],
        snapshots=snapshots,
        progress=progress,
    )
    return VerifierParents(
        population=population,
        observations=observations,
        snapshots=snapshots,
        terminal=terminal,
        outcomes=outcomes,
        context=context,
        history_audit=history_audit,
    )


# --------------------------------------------------------------------------
# Independent mathematics (re-derived from the sealed contract)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class _VPrior:
    mean: float
    variance: float
    source: str
    source_season: int | None
    fallback_reason: str | None = None


def _v_standardization(
    terminal: pd.DataFrame, *, season: int, definition: str, role: str
) -> tuple[float, float]:
    source = terminal[
        (terminal["season"] < season)
        & terminal["measurement_id"].eq(definition)
        & terminal["unit_role"].eq(role)
    ]
    if source.empty:
        return 0.0, 1.0 if definition == "ppp" else 1.5
    prior_season = int(source["season"].max())
    values = pd.to_numeric(
        source[source["season"].eq(prior_season)]["adjusted_value"], errors="coerce"
    ).dropna()
    floor = 0.30 if definition == "ppp" else 0.50
    fallback = 1.00 if definition == "ppp" else 1.50
    if values.empty:
        return 0.0, fallback
    scale = max(float(values.std(ddof=0)), floor)
    return float(values.mean()), scale if isfinite(scale) and scale > 0 else fallback


def _v_carryover(previous: _VPrior | None, *, gap: int) -> _VPrior:
    if previous is None:
        return _VPrior(0.0, 1.0, "neutral", None, "no_predecessor")
    decay = _RHO**gap
    return _VPrior(
        decay * previous.mean,
        decay**2 * previous.variance + 1 - decay**2,
        "rho_0_60",
        previous.source_season,
    )


def _v_learned_prior(
    *,
    family: str,
    carryover: _VPrior,
    training: pd.DataFrame,
    context: pd.DataFrame | None,
    target_season: int,
    team: str,
    role: str,
) -> _VPrior:
    if family == "neutral":
        return _VPrior(0.0, 1.0, "neutral", None)
    if family == "rho_0_60":
        return carryover
    if family not in PRIOR_FAMILIES:
        raise IndependentRatingError("unknown prior family")
    if context is None:
        return _VPrior(
            carryover.mean,
            carryover.variance,
            carryover.source,
            carryover.source_season,
            "context_unavailable",
        )
    columns = _CONTEXT_BLOCKS[family]
    context_row = context[
        (context["season"].eq(target_season)) & context["team"].eq(team)
    ]
    if len(context_row) != 1 or context_row.loc[:, list(columns)].isna().any(axis=None):
        return _VPrior(
            carryover.mean,
            carryover.variance,
            carryover.source,
            carryover.source_season,
            "context_missing_or_ambiguous",
        )
    fitted = training[
        (training["season"] < target_season) & training["unit_role"].eq(role)
    ].merge(context[["season", "team", *columns]], on=["season", "team"], how="inner")
    fitted = fitted.dropna(subset=["terminal_z", "carryover_mean", *columns])
    if fitted["season"].nunique() < 2:
        return _VPrior(
            carryover.mean,
            carryover.variance,
            carryover.source,
            carryover.source_season,
            "insufficient_prior_history",
        )
    feature_columns = [
        column for column in columns if fitted[column].nunique(dropna=True) > 1
    ]
    if not feature_columns:
        return _VPrior(
            carryover.mean,
            carryover.variance,
            carryover.source,
            carryover.source_season,
            "constant_context",
        )
    candidates: list[tuple[float, float]] = []
    for alpha in (0.1, 1.0, 10.0, 100.0):
        errors = []
        for season in sorted(fitted["season"].unique())[1:]:
            train = fitted[fitted["season"] < season]
            test = fitted[fitted["season"] == season]
            if train["season"].nunique() < 2 or test.empty:
                continue
            model = Ridge(alpha=alpha).fit(
                train[feature_columns], train["terminal_z"] - train["carryover_mean"]
            )
            errors.extend(
                np.abs(
                    model.predict(test[feature_columns])
                    - (test["terminal_z"] - test["carryover_mean"])
                )
            )
        if errors:
            candidates.append((float(np.mean(errors)), alpha))
    if not candidates:
        return _VPrior(
            carryover.mean,
            carryover.variance,
            carryover.source,
            carryover.source_season,
            "insufficient_inner_fold",
        )
    best_error = min(error for error, _ in candidates)
    alpha = max(value for error, value in candidates if error <= best_error * 1.005)
    model = Ridge(alpha=alpha).fit(
        fitted[feature_columns], fitted["terminal_z"] - fitted["carryover_mean"]
    )
    residuals = (
        fitted["terminal_z"]
        - fitted["carryover_mean"]
        - model.predict(fitted[feature_columns])
    )
    predicted = float(model.predict(context_row[feature_columns])[0])
    return _VPrior(
        carryover.mean + predicted,
        max(float(np.mean(np.square(residuals))), 1e-6),
        family,
        carryover.source_season,
    )


def _v_fit_noise(
    rows: list[tuple[float, float, float]],
) -> tuple[float, float, float, bool]:
    if len(rows) < _NOISE_FIT_MINIMUM_ROWS:
        return 0.0, 1.0, float("nan"), False

    def objective(values: np.ndarray) -> float:
        q, r = values
        mean, variance, total = 0.0, 1.0, 0.0
        for z, n, days in rows:
            predicted = variance + q * days / 7.0
            residual_variance = predicted + r / n
            total += 0.5 * (
                np.log(residual_variance) + (z - mean) ** 2 / residual_variance
            )
            gain = predicted / residual_variance
            mean, variance = mean + gain * (z - mean), (1 - gain) * predicted
        return float(total)

    fits = [
        minimize(
            objective,
            start,
            method="L-BFGS-B",
            bounds=((0, 1), (1e-6, 100)),
            options={"maxiter": 1000, "ftol": 1e-9},
        )
        for start in ((0.0, 1.0), (0.01, 1.0), (0.1, 1.0))
    ]
    valid = [fit for fit in fits if bool(fit.success) and isfinite(float(fit.fun))]
    if not valid:
        return 0.0, 1.0, float("nan"), False
    best = min(valid, key=lambda fit: (float(fit.fun), tuple(float(x) for x in fit.x)))
    return float(best.x[0]), float(best.x[1]), float(best.fun), True


class _VIncremental:
    """Verifier-owned incremental replay of the sealed update equations."""

    __slots__ = (
        "prior",
        "kalman_mode",
        "half_life",
        "k",
        "q",
        "r",
        "weighted_value",
        "weighted_exposure",
        "completed_games",
        "kalman_mean",
        "kalman_variance",
        "kalman_initialized",
        "last_kickoff",
    )

    def __init__(
        self,
        *,
        prior: _VPrior,
        k: float,
        half_life: float | None,
        q: float,
        r: float,
        kalman_mode: bool,
    ) -> None:
        self.prior = prior
        self.kalman_mode = kalman_mode
        self.k = k
        self.half_life = half_life
        self.q = q
        self.r = r
        self.weighted_value = 0.0
        self.weighted_exposure = 0.0
        self.completed_games = 0
        self.kalman_mean = prior.mean
        self.kalman_variance = prior.variance
        self.kalman_initialized = False
        self.last_kickoff: Any = None

    def assimilate(self, kickoff: Any, z: float | None, exposure: float) -> None:
        if not self.kalman_mode:
            usable = z is not None and np.isfinite(z) and exposure > 0
            if usable:
                factor = (
                    1.0 if self.half_life is None else 0.5 ** (1.0 / self.half_life)
                )
                self.weighted_value *= factor
                self.weighted_exposure *= factor
                self.weighted_value += exposure * z
                self.weighted_exposure += exposure
            self.completed_games += 1
            return
        if not self.kalman_initialized:
            self.kalman_initialized = True
            self.last_kickoff = kickoff
        days = max(
            (
                _utc_timestamp(kickoff) - _utc_timestamp(self.last_kickoff)
            ).total_seconds()
            / 86400.0,
            0.0,
        )
        observation = (
            float(z) if z is not None and np.isfinite(z) and exposure > 0 else None
        )
        prior_variance = self.kalman_variance + self.q * days / 7.0
        if observation is None:
            self.kalman_variance = prior_variance
        else:
            measurement_variance = self.r / exposure
            gain = prior_variance / (prior_variance + measurement_variance)
            self.kalman_mean = self.kalman_mean + gain * (
                observation - self.kalman_mean
            )
            self.kalman_variance = (1 - gain) * prior_variance
        self.completed_games += 1
        self.last_kickoff = kickoff

    def state(self, cutoff: Any) -> tuple[float, float, float, float, float, int]:
        if not self.kalman_mode:
            observation = (
                self.weighted_value / self.weighted_exposure
                if self.weighted_exposure > 0
                else None
            )
            exposure = self.weighted_exposure
            if observation is None:
                return (
                    self.prior.mean,
                    self.prior.variance,
                    0.0,
                    0.0,
                    0.0,
                    self.completed_games,
                )
            information = exposure / self.k
            variance = 1.0 / (1.0 / self.prior.variance + information)
            mean = variance * (
                self.prior.mean / self.prior.variance + information * observation
            )
            weight = information / (1.0 / self.prior.variance + information)
            return (
                mean,
                variance,
                weight,
                0.0,
                exposure,
                self.completed_games,
            )
        if not self.kalman_initialized:
            return (
                self.prior.mean,
                self.prior.variance,
                0.0,
                0.0,
                0.0,
                self.completed_games,
            )
        days = max(
            (_utc_timestamp(cutoff) - _utc_timestamp(self.last_kickoff)).total_seconds()
            / 86400.0,
            0.0,
        )
        variance = self.kalman_variance + self.q * days / 7.0
        return (
            self.kalman_mean,
            variance,
            0.0,
            variance - self.kalman_variance,
            0.0,
            self.completed_games,
        )


def _v_fcs_partial_pool(
    history: list[tuple[Any, float, float]], cutoff: Any
) -> tuple[float, float, str]:
    values = [
        (mean, variance)
        for kickoff, mean, variance in history
        if pd.Timestamp(kickoff) < pd.Timestamp(cutoff)
    ]
    if not values:
        return 0.0, 1.0, "neutral_no_preceding_fcs_cohort"
    means = [mean for mean, _ in values]
    variance = 1.0 / (1.0 + len(means) * 100.0 / 1.0)
    mean = variance * float(np.mean(means))
    conservative = max(
        float(np.sqrt(variance)), max(float(np.sqrt(v)) for _, v in values)
    )
    return mean, conservative**2, "preceding_fcs_partial_pool"


def _v_boundary_table(population: pd.DataFrame) -> pd.DataFrame:
    eligible = population[population["forecast_eligible"]].copy()
    eligible["kickoff_utc"] = pd.to_datetime(eligible["kickoff_utc"], utc=True)
    eligible["available_utc"] = eligible["kickoff_utc"] + pd.Timedelta(hours=6)
    records: list[dict[str, Any]] = []
    for season in DEVELOPMENT_SEASONS:
        season_games = eligible[eligible["season"].eq(season)]
        if season_games.empty:
            continue
        ordered = season_games.sort_values(["kickoff_utc", "game_id"], kind="mergesort")
        kickoffs = ordered["kickoff_utc"].astype("int64").to_numpy()
        weeks = ordered["week"].astype(int).to_numpy()
        game_ids = ordered["game_id"].astype(int).to_numpy()
        for week in sorted(set(weeks.tolist())):
            future = weeks > week
            future_kickoffs = kickoffs[future]
            future_games = game_ids[future]
            same_week = ordered[weeks == week].sort_values(
                ["kickoff_utc", "game_id"], kind="mergesort"
            )
            positions = np.searchsorted(
                future_kickoffs,
                same_week["available_utc"].astype("int64").to_numpy(),
                side="left",
            )
            for row, position in zip(
                same_week.itertuples(index=False), positions, strict=True
            ):
                if int(position) >= len(future_games):
                    continue
                boundary_game = int(future_games[int(position)])
                boundary_kickoff = pd.Timestamp(
                    ordered.loc[
                        ordered["game_id"].eq(boundary_game), "kickoff_utc"
                    ].iloc[0]
                )
                records.append(
                    {
                        "season": int(season),
                        "week": int(week),
                        "game_id": int(row.game_id),
                        "kickoff_utc": row.kickoff_utc,
                        "boundary_game_id": boundary_game,
                        "boundary_cutoff_utc": boundary_kickoff,
                    }
                )
    result = pd.DataFrame.from_records(records)
    if result.empty or result.duplicated(["season", "game_id"]).any():
        raise IndependentRatingError("independent boundary table is malformed")
    return result.sort_values(["season", "week", "game_id"], kind="mergesort")


def _v_fbs_universe(population: pd.DataFrame) -> set[tuple[int, str]]:
    sides = pd.concat(
        [
            population.loc[:, ["season", "home_team"]].rename(
                columns={"home_team": "team"}
            ),
            population.loc[:, ["season", "away_team"]].rename(
                columns={"away_team": "team"}
            ),
        ],
        ignore_index=True,
    )
    counts = sides.groupby(["season", "team"]).size()
    return {
        (int(season), str(team))
        for (season, team), count in counts.items()
        if count >= _FBS_MINIMUM_SCHEDULED_GAMES
    }


def _v_completed_counts(
    population: pd.DataFrame,
) -> dict[tuple[int, int], dict[str, int]]:
    eligible = population[population["forecast_eligible"]].copy()
    eligible["kickoff_utc"] = pd.to_datetime(eligible["kickoff_utc"], utc=True)
    completed = eligible[
        eligible["schedule_completed"].eq(True) & eligible["outcome_valid"].eq(True)
    ]
    result: dict[tuple[int, int], dict[str, int]] = {}
    for season in DEVELOPMENT_SEASONS:
        season_games = eligible[eligible["season"].eq(season)].sort_values(
            ["kickoff_utc", "game_id"], kind="mergesort"
        )
        completed_rows = list(
            completed[completed["season"].eq(season)]
            .sort_values(["kickoff_utc", "game_id"], kind="mergesort")
            .itertuples(index=False)
        )
        counters: dict[str, int] = {}
        index = 0
        for row in season_games.itertuples(index=False):
            while (
                index < len(completed_rows)
                and completed_rows[index].kickoff_utc < row.kickoff_utc
            ):
                finished = completed_rows[index]
                for team in (str(finished.home_team), str(finished.away_team)):
                    counters[team] = counters.get(team, 0) + 1
                index += 1
            result[(int(season), int(row.game_id))] = dict(counters)
    return result


def _v_scoreable_games(
    *,
    population: pd.DataFrame,
    outcomes: pd.DataFrame,
    completed: Mapping[tuple[int, int], Mapping[str, int]],
) -> pd.DataFrame:
    games = population[
        population["forecast_eligible"].eq(True) & population["outcome_valid"].eq(True)
    ].copy()
    games["kickoff_utc"] = pd.to_datetime(games["kickoff_utc"], utc=True)
    games = games.merge(
        outcomes.loc[:, ["season", "game_id", "home_points", "away_points"]],
        on=["season", "game_id"],
        how="inner",
        validate="one_to_one",
    )
    games["home_host"] = 1.0
    games["venue_unknown"] = True
    stages = []
    for row in games.itertuples(index=False):
        counts = completed.get((int(row.season), int(row.game_id)), {})
        stages.append(
            min(
                counts.get(str(row.home_team), 0),
                counts.get(str(row.away_team), 0),
                4,
            )
        )
    games["completed_game_stage"] = stages
    return games


def _v_bridge_predictions(
    states: pd.DataFrame,
    games: pd.DataFrame,
    outcomes: pd.DataFrame,
    *,
    candidate: str,
    alpha: float = 10.0,
) -> pd.DataFrame:
    current = states[states["candidate_id"].eq(candidate)]
    home = current.rename(
        columns={
            "team": "home_team",
            "offense_rating": "home_offense",
            "defense_rating": "home_defense",
        }
    )
    away = current.rename(
        columns={
            "team": "away_team",
            "offense_rating": "away_offense",
            "defense_rating": "away_defense",
        }
    )
    frame = (
        games.merge(
            home[["season", "game_id", "home_team", "home_offense", "home_defense"]],
            on=["season", "game_id", "home_team"],
            how="left",
        )
        .merge(
            away[["season", "game_id", "away_team", "away_offense", "away_defense"]],
            on=["season", "game_id", "away_team"],
            how="left",
        )
        .merge(outcomes, on=["season", "game_id"], how="inner")
    )
    features = ["home_offense", "home_defense", "away_offense", "away_defense"]
    if "home_host" not in frame:
        frame["home_host"] = 1.0
    if "venue_unknown" not in frame:
        frame["venue_unknown"] = False
    frame["home_host"] = frame["home_host"].fillna(0).astype(float)
    frame["venue_unknown"] = frame["venue_unknown"].fillna(True).astype(float)
    features += ["home_host", "venue_unknown"]
    frame = frame.replace([float("inf"), float("-inf")], float("nan"))
    frame = frame.dropna(subset=[*features, "home_points", "away_points"])
    rows: list[dict[str, Any]] = []
    for season in OUTER_SEASONS:
        test = frame[frame["season"].eq(season)]
        train = frame[frame["season"] < season]
        if test.empty or train.empty:
            continue
        center, scale = (
            train[features].mean(),
            train[features].std(ddof=0).clip(lower=0.05),
        )
        x_train, x_test = (
            (train[features] - center) / scale,
            (test[features] - center) / scale,
        )
        varying = [col for col in features if x_train[col].nunique(dropna=False) > 1]
        if not varying:
            continue
        x_train_v = x_train[varying]
        x_test_v = x_test[varying]
        targets = {
            "margin": train["home_points"] - train["away_points"],
            "total": train["home_points"] + train["away_points"],
        }
        actuals = {
            "margin": test["home_points"] - test["away_points"],
            "total": test["home_points"] + test["away_points"],
        }
        for target, y in targets.items():
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=RuntimeWarning)
                model = Ridge(alpha=alpha).fit(x_train_v, y)
                prediction = model.predict(x_test_v)
            for row, value, actual in zip(
                test.itertuples(index=False),
                prediction,
                actuals[target].to_numpy(float),
                strict=True,
            ):
                rows.append(
                    {
                        "candidate_id": candidate,
                        "definition": candidate.split("__", 1)[0],
                        "season": int(season),
                        "week": int(getattr(row, "week", 0)),
                        "game_id": int(row.game_id),
                        "target": target,
                        "actual": float(actual),
                        "prediction": float(value),
                        "absolute_error": abs(float(value) - float(actual)),
                        "training_seasons": ",".join(
                            map(str, sorted(train["season"].unique()))
                        ),
                        "venue_unknown": bool(row.venue_unknown),
                        "completed_game_stage": int(
                            getattr(row, "completed_game_stage", 0)
                        ),
                    }
                )
    return pd.DataFrame(rows)


def _v_bootstrap(
    candidate: pd.DataFrame,
    reference: pd.DataFrame,
    *,
    seed: int = 20260908,
    samples: int = 2000,
) -> tuple[float, float, float]:
    merged = candidate.merge(
        reference,
        on=["season", "week", "game_id", "target"],
        suffixes=("_candidate", "_reference"),
        validate="one_to_one",
    )
    if merged.empty:
        raise IndependentRatingError("paired bootstrap requires common predictions")
    differences = merged["absolute_error_reference"].to_numpy(float) - merged[
        "absolute_error_candidate"
    ].to_numpy(float)
    rng = np.random.default_rng(seed)
    seasons = sorted(merged["season"].unique())
    grouped = {
        int(season): [
            group["absolute_error_reference"].to_numpy(float)
            - group["absolute_error_candidate"].to_numpy(float)
            for _, group in season_rows.groupby("week", sort=True)
        ]
        for season, season_rows in merged.groupby("season", sort=True)
    }
    if set(grouped) != set(seasons) or any(not values for values in grouped.values()):
        raise IndependentRatingError("paired bootstrap has an empty season/week")
    season_choices = rng.integers(0, len(seasons), size=(samples, len(seasons)))
    sums = np.zeros(samples, dtype=float)
    counts = np.zeros(samples, dtype=np.int64)
    for season_index, season in enumerate(seasons):
        replica_indices, _ = np.where(season_choices == season_index)
        week_values = grouped[int(season)]
        selected_weeks = rng.integers(
            0, len(week_values), size=(len(replica_indices), len(week_values))
        )
        for week_index, values in enumerate(week_values):
            occurrences, _ = np.where(selected_weeks == week_index)
            if not len(occurrences):
                continue
            replicas = replica_indices[occurrences]
            sampled = values[
                rng.integers(0, len(values), size=(len(replicas), len(values)))
            ].mean(axis=1)
            np.add.at(sums, replicas, sampled * len(values))
            np.add.at(counts, replicas, len(values))
    if (counts == 0).any():
        raise IndependentRatingError("paired bootstrap generated an empty replica")
    means = sums / counts
    return (
        float(differences.mean()),
        float(np.quantile(means, 0.05)),
        float(np.quantile(means, 0.95)),
    )


def _v_selection(
    predictions: pd.DataFrame,
    validity: Mapping[str, str | None] | None = None,
) -> pd.DataFrame:
    if predictions.empty and not validity:
        raise IndependentRatingError("selection needs bridge predictions")
    expected = {
        candidate_id(d, p, u)
        for d in DEFINITIONS
        for p in PRIOR_FAMILIES
        for u in UPDATERS
    }
    failures = {key: value for key, value in (validity or {}).items() if value}
    represented = set(predictions["candidate_id"]) | set(failures)
    if represented != expected:
        raise IndependentRatingError("selection requires all 60 candidates")
    records: list[dict[str, Any]] = []
    retained: dict[str, str] = {}
    for definition in DEFINITIONS:
        subset = predictions[predictions["definition"].eq(definition)]
        reference_id = candidate_id(definition, "rho_0_60", "exposure")
        if reference_id in failures or reference_id not in set(subset["candidate_id"]):
            raise IndependentRatingError(
                f"invalid or missing reference blocks definition: {reference_id}"
            )
        reference = subset[subset["candidate_id"].eq(reference_id)]
        reference_mae = float(reference["absolute_error"].mean())
        reference_stages = set(reference["completed_game_stage"])
        reference_seasons = set(reference["season"])
        passing = [reference_id]
        for candidate in sorted(expected):
            if not candidate.startswith(f"{definition}__"):
                continue
            if candidate in failures:
                records.append(
                    {
                        "candidate_id": candidate,
                        "definition": definition,
                        "prior_family": candidate.split("__")[1],
                        "updater": candidate.split("__")[2],
                        "reference_candidate": reference_id,
                        "pooled_mae": -1.0,
                        "reference_mae": reference_mae,
                        "improvement_pct": -100.0,
                        "bootstrap_90_lower": -1.0,
                        "bootstrap_90_upper": -1.0,
                        "full_gate": False,
                        "early_gate": False,
                        "regression_gate": False,
                        "valid": False,
                        "selected": False,
                        "selection_reason": f"validity_failure: {failures[candidate]}",
                    }
                )
                continue
            values = subset[subset["candidate_id"].eq(candidate)]
            if len(values) != len(reference):
                raise IndependentRatingError(
                    "candidate population differs from reference"
                )
            mae = float(values["absolute_error"].mean())
            improvement, lower, upper = _v_bootstrap(values, reference)
            percent = 100 * (reference_mae - mae) / reference_mae
            candidate_stages = set(values["completed_game_stage"])
            candidate_seasons = set(values["season"])
            if not candidate_stages <= reference_stages:
                stage_regression = False
            else:
                stage_ratio = (
                    values.groupby("completed_game_stage")["absolute_error"].mean()
                    / reference.groupby("completed_game_stage")["absolute_error"].mean()
                )
                stage_regression = bool((stage_ratio <= 1.05).all())
            if not candidate_seasons <= reference_seasons:
                season_regression = False
            else:
                season_ratio = (
                    values.groupby("season")["absolute_error"].mean()
                    / reference.groupby("season")["absolute_error"].mean()
                )
                season_regression = bool((season_ratio <= 1.05).all())
            regression = stage_regression and season_regression
            full = percent >= 0.5 and lower > 0
            early_values, early_reference = (
                values[values["completed_game_stage"].le(3)],
                reference[reference["completed_game_stage"].le(3)],
            )
            early = False
            if not early_values.empty:
                early_mean, early_lower, _ = _v_bootstrap(early_values, early_reference)
                early = (
                    100
                    * early_mean
                    / max(float(early_reference["absolute_error"].mean()), 1e-12)
                    >= 0.5
                    and early_lower > 0
                    and mae <= reference_mae * 1.01
                )
            valid = candidate == reference_id or ((full or early) and regression)
            if valid:
                passing.append(candidate)
            records.append(
                {
                    "candidate_id": candidate,
                    "definition": definition,
                    "prior_family": candidate.split("__")[1],
                    "updater": candidate.split("__")[2],
                    "reference_candidate": reference_id,
                    "pooled_mae": mae,
                    "reference_mae": reference_mae,
                    "improvement_pct": percent,
                    "bootstrap_90_lower": lower,
                    "bootstrap_90_upper": upper,
                    "full_gate": full,
                    "early_gate": early,
                    "regression_gate": regression,
                    "valid": valid,
                    "selected": False,
                    "selection_reason": "reference"
                    if candidate == reference_id
                    else "failed",
                }
            )
        complexity = {
            "neutral": 0,
            "rho_0_60": 0,
            "recruiting_ridge": 1,
            "returning_production_ridge": 1,
            "continuity_ridge": 1,
            "all_context_ridge": 3,
        }
        order = {
            "exposure": 0,
            "half_life_8": 1,
            "half_life_4": 2,
            "half_life_2": 3,
            "kalman": 4,
        }
        candidate_metrics = {
            record["candidate_id"]: record
            for record in records
            if record["definition"] == definition
        }
        best = min(candidate_metrics[item]["pooled_mae"] for item in passing)
        retained[definition] = min(
            (
                item
                for item in passing
                if candidate_metrics[item]["pooled_mae"] <= best * 1.005
            ),
            key=lambda item: (
                complexity[item.split("__")[1]],
                order[item.split("__")[2]],
                item,
            ),
        )
    selected = retained["ppp"]
    ppp_record = next(
        record for record in records if record["candidate_id"] == retained["ppp"]
    )
    epa_record = next(
        record
        for record in records
        if record["candidate_id"] == retained["epa_per_possession"]
    )
    if (
        epa_record["valid"]
        and epa_record["pooled_mae"] < ppp_record["pooled_mae"] * 0.995
        and epa_record["bootstrap_90_lower"] > 0
    ):
        selected = retained["epa_per_possession"]
    for record in records:
        record["selected"] = record["candidate_id"] == selected
        if record["selected"]:
            record["selection_reason"] = "cross_definition_winner"
    return pd.DataFrame(records)


# --------------------------------------------------------------------------
# Full tournament reconstruction
# --------------------------------------------------------------------------


@dataclass
class ReconstructedRating:
    candidate_status: dict[str, str]
    selected_candidate: str
    selection_records: list[dict[str, Any]] = field(default_factory=list)
    selection_sha256: str = ""
    parts: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    row_counts: dict[str, int] = field(default_factory=dict)
    records_shas: dict[str, str] = field(default_factory=dict)


def _partition_schemas() -> dict[str, tuple[str, str, tuple[str, ...]]]:
    keys = {
        "rating_registry": (),
        "attribution": (),
        "priors": ("season",),
        "noise_fits": ("season",),
        "rating_states": ("season", "week"),
        "team_states": ("season", "week"),
        "bridge_predictions": ("season", "week"),
    }
    return {
        name: (RATING_DATASETS[name][0], RATING_DATASETS[name][1], keys[name])
        for name in RATING_DATASETS
    }


def _canonical_parts(
    name: str,
    partitions: Mapping[tuple[int, ...], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    dataset, schema_version, partition_keys = _partition_schemas()[name]
    schema = schema_for(dataset, schema_version)
    parts: list[dict[str, Any]] = []
    for key in sorted(partitions, key=lambda item: tuple(item)):
        frame = pd.DataFrame.from_records(partitions[key], columns=schema.required)
        if frame.empty:
            continue
        validate_frame(frame, schema)
        partition = {partition_keys[i]: int(key[i]) for i in range(len(partition_keys))}
        parts.append(
            {
                "partition": partition,
                "row_count": int(len(frame)),
                "records_sha": canonical_frame_digest(frame, columns=schema.required),
            }
        )
    return parts


def reconstruct_tournament(
    *,
    parents: VerifierParents,
    progress: Any,
) -> ReconstructedRating:
    """Independently rebuild every sealed output from the certified parents."""
    population = parents.population
    observations = parents.observations

    boundaries = _v_boundary_table(population)

    terminal_tables: dict[tuple[str, str, int], dict[str, Any]] = {}
    for definition in DEFINITIONS:
        for role in ROLES:
            for season in DEVELOPMENT_SEASONS:
                center, scale = _v_standardization(
                    parents.terminal, season=season, definition=definition, role=role
                )
                rows = parents.terminal[
                    parents.terminal["season"].eq(season)
                    & parents.terminal["measurement_id"].eq(definition)
                    & parents.terminal["unit_role"].eq(role)
                ]
                sign = -1.0 if role == "defense" else 1.0
                teams: dict[str, tuple[float, float]] = {}
                for row in rows.itertuples(index=False):
                    value = float(row.adjusted_value)
                    exposure = float(row.primary_exposure)
                    if not np.isfinite(value) or not np.isfinite(exposure):
                        continue
                    if exposure <= 0:
                        continue
                    teams[str(row.team)] = (sign * (value - center) / scale, exposure)
                terminal_tables[(definition, role, season)] = {
                    "center": center,
                    "scale": scale,
                    "sign": sign,
                    "teams": teams,
                }

    observed = observations[
        observations["coverage_status"].eq("observed")
        & pd.to_numeric(observations["denominator"], errors="coerce").gt(0)
    ].copy()
    observed["kickoff_utc"] = pd.to_datetime(observed["kickoff_utc"], utc=True)
    boundary_by_game = boundaries.set_index("game_id").loc[
        :, ["boundary_game_id", "boundary_cutoff_utc"]
    ]
    snapshot_values = {
        (
            int(row.as_of_game_id),
            str(row.team),
            str(row.measurement_id),
            str(row.unit_role),
        ): float(row.adjusted_value)
        for row in parents.snapshots.itertuples(index=False)
        if pd.notna(row.adjusted_value)
    }
    streams: dict[tuple[str, str], pd.DataFrame] = {}
    for definition in DEFINITIONS:
        subset = observed[observed["measurement_id"].eq(definition)].merge(
            boundary_by_game,
            left_on="game_id",
            right_index=True,
            how="inner",
            validate="many_to_one",
        )
        for role in ROLES:
            role_rows = subset[subset["unit_role"].eq(role)].copy()
            z_values: list[float] = []
            for row in role_rows.itertuples(index=False):
                table = terminal_tables[(definition, role, int(row.season))]
                value = snapshot_values.get(
                    (int(row.boundary_game_id), str(row.team), definition, role)
                )
                if value is None or not np.isfinite(value):
                    z_values.append(float("nan"))
                    continue
                z_values.append(
                    float(table["sign"] * (value - table["center"]) / table["scale"])
                )
            role_rows["adjusted_z"] = z_values
            role_rows = role_rows.dropna(subset=["adjusted_z"]).reset_index(drop=True)
            role_rows["usable_exposure"] = pd.to_numeric(
                role_rows["denominator"], errors="coerce"
            )
            streams[(definition, role)] = role_rows.sort_values(
                ["kickoff_utc", "game_id"], kind="mergesort"
            ).reset_index(drop=True)

    def previous_season(season: int) -> int | None:
        earlier = [value for value in DEVELOPMENT_SEASONS if value < season]
        return earlier[-1] if earlier else None

    labels: dict[tuple[str, str], list[dict[str, Any]]] = {
        (definition, role): [] for definition in DEFINITIONS for role in ROLES
    }
    for definition in DEFINITIONS:
        for role in ROLES:
            for season in DEVELOPMENT_SEASONS:
                table = terminal_tables[(definition, role, season)]
                prev = (
                    terminal_tables[(definition, role, previous_season(season))][
                        "teams"
                    ]
                    if previous_season(season) is not None
                    else {}
                )
                gap = season - previous_season(season) if prev else 0
                for team, (terminal_z, _) in table["teams"].items():
                    prior_z = prev.get(team)
                    labels[(definition, role)].append(
                        {
                            "season": season,
                            "team": team,
                            "unit_role": role,
                            "terminal_z": terminal_z,
                            "carryover_mean": (
                                (_RHO**gap) * prior_z[0] if prior_z else np.nan
                            ),
                        }
                    )
    training_labels = {key: pd.DataFrame(rows) for key, rows in labels.items() if rows}

    priors: dict[tuple[str, str], pd.DataFrame] = {}
    prior_columns = [
        "season",
        "team",
        "unit_role",
        "prior_mean",
        "prior_variance",
        "prior_source",
        "prior_source_season",
        "annual_decay_steps",
        "fallback_reason",
    ]
    for definition in DEFINITIONS:
        k = _K_BY_DEFINITION[definition]
        for family in PRIOR_FAMILIES:
            records: list[dict[str, Any]] = []
            for role in ROLES:
                training = training_labels.get((definition, role))
                context_frame = parents.context.get(family)
                for season in DEVELOPMENT_SEASONS:
                    context_at_season = None
                    if context_frame is not None:
                        available = context_frame[
                            context_frame["season"].astype(int).le(season)
                        ]
                        if not available.empty:
                            context_at_season = available
                    source_season = previous_season(season)
                    previous = (
                        terminal_tables[(definition, role, source_season)]["teams"]
                        if source_season is not None
                        else {}
                    )
                    gap = season - source_season if source_season else 0
                    teams = sorted(
                        set(terminal_tables[(definition, role, season)]["teams"])
                        | set(previous)
                    )
                    for team in teams:
                        previous_terminal = previous.get(team)
                        if previous_terminal is None:
                            carry = _VPrior(0.0, 1.0, "neutral", None, "no_predecessor")
                        else:
                            prev_z, prev_exposure = previous_terminal
                            prev_variance = 1.0 / (1.0 + prev_exposure / k)
                            carry = _v_carryover(
                                _VPrior(
                                    prev_z, prev_variance, "terminal", source_season
                                ),
                                gap=gap,
                            )
                        if family == "neutral":
                            prior = _VPrior(0.0, 1.0, "neutral", None)
                        elif family == "rho_0_60":
                            prior = carry
                        else:
                            prior = _v_learned_prior(
                                family=family,
                                carryover=carry,
                                training=training,
                                context=context_at_season,
                                target_season=season,
                                team=team,
                                role=role,
                            )
                        records.append(
                            {
                                "season": season,
                                "team": team,
                                "unit_role": role,
                                "prior_mean": float(prior.mean),
                                "prior_variance": float(prior.variance),
                                "prior_source": prior.source,
                                "prior_source_season": prior.source_season,
                                "annual_decay_steps": int(gap),
                                "fallback_reason": prior.fallback_reason,
                            }
                        )
            priors[(definition, family)] = pd.DataFrame.from_records(
                records, columns=prior_columns
            )

    noise: dict[tuple[str, str, str, int], dict[str, Any]] = {}
    for definition in DEFINITIONS:
        for role in ROLES:
            stream = streams[(definition, role)]
            for family in PRIOR_FAMILIES:
                prior_rows = priors[(definition, family)]
                prior_lookup = {
                    (int(row.season), str(row.team)): float(row.prior_mean)
                    for row in prior_rows.itertuples(index=False)
                    if row.unit_role == role
                }
                for season in DEVELOPMENT_SEASONS:
                    earlier = [value for value in DEVELOPMENT_SEASONS if value < season]
                    rows = [
                        (
                            float(row.adjusted_z)
                            - prior_lookup.get((int(row.season), str(row.team)), 0.0),
                            float(row.usable_exposure),
                            7.0,
                        )
                        for row in stream.itertuples(index=False)
                        if int(row.season) in set(earlier)
                        and pd.notna(row.adjusted_z)
                        and float(row.usable_exposure) > 0
                    ]
                    if len(rows) < _NOISE_FIT_MINIMUM_ROWS:
                        noise[(definition, family, role, season)] = {
                            "q": 0.0,
                            "r": 1.0,
                            "objective": -1.0,
                            "converged": False,
                            "cold_start": True,
                            "training_seasons": earlier,
                            "disqualifies": False,
                        }
                        continue
                    q, r, objective, converged = _v_fit_noise(rows)
                    noise[(definition, family, role, season)] = {
                        "q": q,
                        "r": r,
                        "objective": objective if converged else -1.0,
                        "converged": converged,
                        "cold_start": not converged,
                        "training_seasons": earlier,
                        "disqualifies": (
                            not converged and len(earlier) >= _NOISE_FIT_MINIMUM_SEASONS
                        ),
                    }

    fbs = _v_fbs_universe(population)
    completed = _v_completed_counts(population)
    games = _v_scoreable_games(
        population=population, outcomes=parents.outcomes, completed=completed
    )
    eligible = population[population["forecast_eligible"]].copy()
    eligible["kickoff_utc"] = pd.to_datetime(eligible["kickoff_utc"], utc=True)

    partitions: dict[str, dict[tuple[int, ...], list[dict[str, Any]]]] = {
        name: {} for name in RATING_DATASETS
    }

    def append(name: str, key: tuple[int, ...], rows: list[dict[str, Any]]) -> None:
        partitions[name].setdefault(key, []).extend(rows)

    registry_rows = [
        {
            "candidate_id": entry["candidate_id"],
            "definition": entry["definition"],
            "prior_family": entry["prior_family"],
            "updater": entry["updater"],
            "reference_candidate": entry["reference_candidate"],
            "prior_feature_count": entry["prior_feature_count"],
        }
        for entry in candidate_registry()
    ]
    append("rating_registry", (), registry_rows)

    candidate_status: dict[str, str] = {}
    prediction_frames: list[pd.DataFrame] = []
    progress("tournament_started", completed=0, total=len(candidate_registry()))
    for index, entry in enumerate(candidate_registry(), start=1):
        candidate = str(entry["candidate_id"])
        definition = str(entry["definition"])
        family = str(entry["prior_family"])
        updater = str(entry["updater"])

        prior_rows = priors[(definition, family)]
        candidate_status[candidate] = "ok"
        if updater == "kalman":
            for row in prior_rows.itertuples(index=False):
                noise_row = noise[
                    (definition, family, str(row.unit_role), int(row.season))
                ]
                if noise_row.get("disqualifies"):
                    candidate_status[candidate] = "kalman_noise_fit_failed"
                    break
        if candidate_status[candidate] != "ok":
            progress(
                "tournament_candidate",
                completed=index,
                total=len(candidate_registry()),
                candidate=candidate,
                status=candidate_status[candidate],
            )
            continue

        prior_partitions: dict[int, list[dict[str, Any]]] = {}
        for row in prior_rows.itertuples(index=False):
            prior_partitions.setdefault(int(row.season), []).append(
                {
                    "candidate_id": candidate,
                    "season": int(row.season),
                    "team": str(row.team),
                    "unit_role": str(row.unit_role),
                    "prior_mean": float(row.prior_mean),
                    "prior_variance": float(row.prior_variance),
                    "prior_source": str(row.prior_source),
                    "prior_source_season": row.prior_source_season,
                    "annual_decay_steps": int(row.annual_decay_steps),
                    "fallback_reason": row.fallback_reason,
                }
            )
        for season, rows in prior_partitions.items():
            append("priors", (season,), rows)
        if updater == "kalman":
            noise_partitions: dict[int, list[dict[str, Any]]] = {}
            for (d, f, role, season), noise_row in sorted(noise.items()):
                if d == definition and f == family:
                    noise_partitions.setdefault(int(season), []).append(
                        {
                            "candidate_id": candidate,
                            "season": int(season),
                            "unit_role": role,
                            "q": float(noise_row["q"]),
                            "r": float(noise_row["r"]),
                            "objective": float(noise_row["objective"]),
                            "converged": bool(noise_row["converged"]),
                            "cold_start": bool(noise_row["cold_start"]),
                            "training_seasons": ",".join(
                                map(str, noise_row["training_seasons"])
                            ),
                        }
                    )
            for season, rows in noise_partitions.items():
                append("noise_fits", (season,), rows)

        prior_lookup = {
            (int(row.season), str(row.unit_role), str(row.team)): _VPrior(
                float(row.prior_mean),
                float(row.prior_variance),
                str(row.prior_source),
                row.prior_source_season,
                row.fallback_reason,
            )
            for row in prior_rows.itertuples(index=False)
        }
        streams_by_season: dict[
            tuple[str, str], dict[int, dict[str, list[dict[str, Any]]]]
        ] = {}
        for role in ROLES:
            grouped: dict[int, dict[str, list[dict[str, Any]]]] = {}
            for row in streams[(definition, role)].itertuples(index=False):
                grouped.setdefault(int(row.season), {}).setdefault(
                    str(row.team), []
                ).append(
                    {
                        "game_id": int(row.game_id),
                        "kickoff_utc": row.kickoff_utc,
                        "adjusted_z": float(row.adjusted_z),
                        "exposure": float(row.usable_exposure),
                        "boundary_cutoff": row.boundary_cutoff_utc,
                    }
                )
            streams_by_season[(definition, role)] = grouped

        state_partitions: dict[tuple[int, int], list[dict[str, Any]]] = {}
        team_partitions: dict[tuple[int, int], list[dict[str, Any]]] = {}
        game_states: dict[
            tuple[int, str],
            dict[str, tuple[float, float, float, float, float, int, str | None]],
        ] = {}

        for season in DEVELOPMENT_SEASONS:
            season_games = eligible[eligible["season"].eq(season)].sort_values(
                ["kickoff_utc", "game_id"], kind="mergesort"
            )
            if season_games.empty:
                continue
            scale_table = {
                role: terminal_tables[(definition, role, season)] for role in ROLES
            }
            noise_by_role = {
                role: noise[(definition, family, role, season)] for role in ROLES
            }
            teams = sorted(
                {
                    team
                    for row in season_games.itertuples(index=False)
                    for team in (str(row.home_team), str(row.away_team))
                }
            )
            fcs_history: dict[str, list[tuple[Any, float, float]]] = {
                role: [] for role in ROLES
            }
            for team in teams:
                is_fcs = (int(season), team) not in fbs
                team_games = season_games[
                    season_games["home_team"].eq(team)
                    | season_games["away_team"].eq(team)
                ]
                for role in ROLES:
                    own = (
                        streams_by_season[(definition, role)]
                        .get(season, {})
                        .get(team, [])
                    )
                    own = sorted(
                        own, key=lambda item: (item["kickoff_utc"], item["game_id"])
                    )
                    prior = prior_lookup.get(
                        (season, role, team),
                        _VPrior(0.0, 1.0, "neutral", None, "no_predecessor"),
                    )
                    noise_row = noise_by_role[role]
                    if updater == "kalman" and not noise_row["cold_start"]:
                        state = _VIncremental(
                            prior=prior,
                            k=_K_BY_DEFINITION[definition],
                            half_life=None,
                            q=float(noise_row["q"]),
                            r=float(noise_row["r"]),
                            kalman_mode=True,
                        )
                        fallback: str | None = None
                    else:
                        effective = "exposure" if updater == "kalman" else updater
                        state = _VIncremental(
                            prior=prior,
                            k=_K_BY_DEFINITION[definition],
                            half_life=_HALF_LIFE[effective],
                            q=0.0,
                            r=1.0,
                            kalman_mode=False,
                        )
                        fallback = "kalman_cold_start" if updater == "kalman" else None
                    pending_index = 0
                    for game in team_games.itertuples(index=False):
                        cutoff = pd.Timestamp(game.kickoff_utc)
                        while pending_index < len(own):
                            item = own[pending_index]
                            if pd.Timestamp(item["boundary_cutoff"]) <= cutoff and int(
                                item["game_id"]
                            ) != int(game.game_id):
                                state.assimilate(
                                    item["kickoff_utc"],
                                    item["adjusted_z"],
                                    item["exposure"],
                                )
                                pending_index += 1
                            else:
                                break
                        mean, variance, weight, process, exposure, completed_count = (
                            state.state(cutoff)
                        )
                        role_fallback = fallback
                        if (
                            is_fcs
                            and prior.fallback_reason == "no_predecessor"
                            and completed_count == 0
                        ):
                            pool_mean, pool_variance, pool_reason = _v_fcs_partial_pool(
                                fcs_history[role], cutoff
                            )
                            mean, variance, role_fallback = (
                                pool_mean,
                                pool_variance,
                                pool_reason,
                            )
                            weight, process, exposure = 0.0, 0.0, 0.0
                        table = scale_table[role]
                        state_partitions.setdefault(
                            (int(season), int(game.week)), []
                        ).append(
                            {
                                "candidate_id": candidate,
                                "definition": definition,
                                "season": int(season),
                                "week": int(game.week),
                                "game_id": int(game.game_id),
                                "cutoff_utc": cutoff.isoformat(),
                                "team": team,
                                "unit_role": role,
                                "native_mean": mean * table["scale"] / table["sign"]
                                + table["center"],
                                "rating_mean": mean,
                                "rating_variance": variance,
                                "prior_mean": prior.mean,
                                "prior_variance": prior.variance,
                                "evidence_weight": weight,
                                "process_variance": process,
                                "usable_exposure": exposure,
                                "completed_games": completed_count,
                                "fallback_reason": role_fallback,
                            }
                        )
                        if is_fcs:
                            fcs_history[role].append((cutoff, mean, variance))
                        game_states.setdefault((int(game.game_id), team), {})[role] = (
                            mean,
                            variance,
                            weight,
                            process,
                            exposure,
                            completed_count,
                            role_fallback,
                        )
            for game in season_games.itertuples(index=False):
                for team in (str(game.home_team), str(game.away_team)):
                    roles = game_states.get((int(game.game_id), team))
                    if not roles or set(roles) != set(ROLES):
                        raise IndependentRatingError(
                            f"unexplained missing non-FCS state: {season}/{game.game_id}/{team}"
                        )
                    offense = roles["offense"]
                    defense = roles["defense"]
                    joined = [value for value in (offense[6], defense[6]) if value]
                    team_partitions.setdefault(
                        (int(season), int(game.week)), []
                    ).append(
                        {
                            "candidate_id": candidate,
                            "definition": definition,
                            "season": int(season),
                            "week": int(game.week),
                            "game_id": int(game.game_id),
                            "cutoff_utc": pd.Timestamp(game.kickoff_utc).isoformat(),
                            "team": team,
                            "offense_rating": offense[0],
                            "offense_variance": offense[1],
                            "defense_rating": defense[0],
                            "defense_variance": defense[1],
                            "overall_rating": (offense[0] + defense[0]) / 2.0,
                            "overall_variance": (offense[1] + defense[1]) / 4.0,
                            "fallback_reason": "|".join(joined) if joined else None,
                        }
                    )

        for key, rows in state_partitions.items():
            append("rating_states", key, rows)
        for key, rows in team_partitions.items():
            append("team_states", key, rows)

        team_frame = pd.concat(
            [
                pd.DataFrame.from_records(rows)
                for key in sorted(team_partitions, key=lambda item: tuple(item))
                for rows in [team_partitions[key]]
            ],
            ignore_index=True,
            sort=False,
        )
        predictions = _v_bridge_predictions(
            team_frame,
            games.drop(columns=["home_points", "away_points"]),
            parents.outcomes,
            candidate=candidate,
        )
        prediction_frames.append(predictions)
        for record in predictions.to_dict("records"):
            append(
                "bridge_predictions",
                (int(record["season"]), int(record["week"])),
                [record],
            )
        progress(
            "tournament_candidate",
            completed=index,
            total=len(candidate_registry()),
            candidate=candidate,
            status="ok",
        )

    predictions_all = pd.concat(prediction_frames, ignore_index=True, sort=False)
    valid_predictions = predictions_all[
        predictions_all["candidate_id"].map(candidate_status).eq("ok")
    ]
    validity = {
        candidate: (None if status == "ok" else status)
        for candidate, status in candidate_status.items()
    }
    attribution = _v_selection(valid_predictions, validity=validity)
    selected = str(attribution.loc[attribution["selected"], "candidate_id"].iloc[0])
    append(
        "attribution",
        (),
        attribution.loc[:, list(ATTRIBUTION_COLUMNS)].to_dict("records"),
    )

    result = ReconstructedRating(
        candidate_status=candidate_status,
        selected_candidate=selected,
    )
    selection_payload = {
        "attribution": attribution.loc[:, list(ATTRIBUTION_COLUMNS)].to_dict("records"),
        "selected_candidate": selected,
        "candidate_status": dict(sorted(candidate_status.items())),
    }
    result.selection_sha256 = _json_sha(selection_payload)
    for name in RATING_DATASETS:
        parts = _canonical_parts(name, partitions[name])
        result.parts[name] = parts
        result.row_counts[name] = int(sum(part["row_count"] for part in parts))
        result.records_shas[name] = (
            partitioned_records_sha(parts, _partition_schemas()[name][2])
            if parts
            else _json_sha(
                {
                    "dataset": _partition_schemas()[name][0],
                    "salt": _EMPTY_DATASET_SALT,
                }
            )
        )
    return result


# --------------------------------------------------------------------------
# Stored-artifact comparison and signed verifier manifest
# --------------------------------------------------------------------------


def _compare_partitioned(
    storage: Any,
    *,
    name: str,
    stored_ref: Mapping[str, Any],
    reconstruction: ReconstructedRating,
) -> dict[str, Any]:
    ref = _part_ref(stored_ref, name=name)
    dataset, schema_version, _ = _partition_schemas()[name]
    if ref.dataset != dataset or ref.schema_version != schema_version:
        raise IndependentRatingError(f"stored {name} reference identity mismatch")
    # _stored_parts validates the manifest checksum, logical digest, row
    # counts, ordering, child checksums, child digests, and schemas.
    parts_meta, _ = _stored_parts(storage, ref)
    expected_parts = reconstruction.parts[name]
    stored_summary = [
        {
            "partition": dict(part["partition"]),
            "row_count": int(part["row_count"]),
            "records_sha": str(part["records_sha"]),
        }
        for part in parts_meta
    ]
    expected_summary = [
        {
            "partition": dict(part["partition"]),
            "row_count": int(part["row_count"]),
            "records_sha": str(part["records_sha"]),
        }
        for part in expected_parts
    ]
    if stored_summary != expected_summary:
        raise IndependentRatingError(
            f"independent {name} partition plan differs from stored artifact"
        )
    if (
        ref.records_sha != reconstruction.records_shas[name]
        or ref.row_count != (reconstruction.row_counts[name])
    ):
        raise IndependentRatingError(f"independent {name} dataset digest differs")
    return {
        "row_count": ref.row_count,
        "records_sha256": ref.records_sha,
        "parts": len(expected_parts),
    }


def _compare_compact(
    storage: Any,
    *,
    name: str,
    stored_ref: Mapping[str, Any],
    reconstruction: ReconstructedRating,
) -> dict[str, Any]:
    dataset, schema_version, _ = _partition_schemas()[name]
    ref = _ds_ref(stored_ref, name=name)
    if ref.dataset != dataset or ref.schema_version != schema_version:
        raise IndependentRatingError(f"stored {name} reference identity mismatch")
    try:
        frame = read_dataset(storage, ref)
    except Exception as exc:
        raise IndependentRatingError(
            f"stored {name} dataset is unreadable: {ref.uri}"
        ) from exc
    schema = schema_for(dataset, schema_version)
    validate_frame(frame, schema)
    stored_digest = canonical_frame_digest(frame, columns=schema.required)
    if (
        stored_digest != reconstruction.records_shas[name]
        or len(frame) != reconstruction.row_counts[name]
        or str(stored_ref.get("records_sha")) != stored_digest
        or int(stored_ref.get("row_count", -1)) != len(frame)
    ):
        raise IndependentRatingError(
            f"independent {name} rows differ from the stored artifact"
        )
    return {"row_count": len(frame), "records_sha256": stored_digest}


def verify_rating_artifact(
    *,
    storage: Any,
    manifest: Mapping[str, Any],
    manifest_uri: str,
    measurement_manifest_uri: str,
    repair_manifest_uri: str,
    verifier_code_sha: str,
    progress: Any,
) -> dict[str, Any]:
    """Rebuild the tournament independently and compare every stored output."""
    parents_recorded = manifest.get("parents") or {}
    if (
        parents_recorded.get("measurement_manifest_uri") != measurement_manifest_uri
        or parents_recorded.get("repair_manifest_uri") != repair_manifest_uri
    ):
        raise IndependentRatingError("stored parents differ from the requested URIs")
    measurement_raw = storage.read_bytes(measurement_manifest_uri)
    repair_raw = storage.read_bytes(repair_manifest_uri)
    if hashlib.sha256(measurement_raw).hexdigest() != parents_recorded.get(
        "measurement_manifest_raw_sha256"
    ) or hashlib.sha256(repair_raw).hexdigest() != parents_recorded.get(
        "repair_manifest_raw_sha256"
    ):
        raise IndependentRatingError("parent bytes differ from the sealed checksums")

    from cks_picks_cfb.data.data_first_possession_rating_v1 import verify_parents

    measurement, repair = verify_parents(
        json.loads(measurement_raw), json.loads(repair_raw)
    )
    progress("verifier_parents_started", force=True)
    parents = load_verifier_parents(
        storage=storage,
        measurement=measurement,
        repair=repair,
        progress=progress,
    )
    reconstruction = reconstruct_tournament(parents=parents, progress=progress)

    selection = manifest.get("selection") or {}
    if (
        manifest.get("selected_candidate") != reconstruction.selected_candidate
        or selection.get("selection_sha256") != reconstruction.selection_sha256
        or selection.get("candidate_status")
        != dict(sorted(reconstruction.candidate_status.items()))
        or selection.get("row_counts") != reconstruction.row_counts
        or selection.get("output_records_sha256") != reconstruction.records_shas
    ):
        raise IndependentRatingError(
            "independent selection differs from the retained manifest"
        )

    outputs = manifest.get("output_refs") or {}
    if set(outputs) != set(RATING_DATASETS):
        raise IndependentRatingError("retained manifest lacks complete outputs")
    comparisons: dict[str, Any] = {}
    for name in RATING_DATASETS:
        if _partition_schemas()[name][2]:
            comparisons[name] = _compare_partitioned(
                storage,
                name=name,
                stored_ref=outputs[name],
                reconstruction=reconstruction,
            )
        else:
            comparisons[name] = _compare_compact(
                storage,
                name=name,
                stored_ref=outputs[name],
                reconstruction=reconstruction,
            )

    verifier_manifest = signed_payload(
        {
            "schema_version": VERIFICATION_MANIFEST_SCHEMA,
            "state": "verified",
            "manifest_uri": manifest_uri,
            "retained_manifest_raw_sha256": hashlib.sha256(
                storage.read_bytes(manifest_uri)
            ).hexdigest(),
            "parents": {
                "measurement_manifest_uri": measurement_manifest_uri,
                "repair_manifest_uri": repair_manifest_uri,
            },
            "selected_candidate": reconstruction.selected_candidate,
            "selection_sha256": reconstruction.selection_sha256,
            "output_rows": reconstruction.row_counts,
            "output_records_sha256": reconstruction.records_shas,
            "verifier_code_sha": verifier_code_sha,
            "production_activation_authorized": False,
        }
    )
    verifier_uri = (
        f"{manifest_uri.rsplit('/', 1)[0]}/verification/verifier-manifest.json"
    )
    encoded = json.dumps(
        verifier_manifest, sort_keys=True, separators=(",", ":"), default=str
    ).encode()
    if storage.exists(verifier_uri):
        if storage.read_bytes(verifier_uri) != encoded:
            raise IndependentRatingError(
                "verifier manifest collision; the artifact is already bound to "
                "different verification evidence"
            )
    else:
        storage.write_bytes(encoded, verifier_uri)
    progress("verification_complete", force=True)
    return {
        "status": "verified",
        "manifest_uri": manifest_uri,
        "verifier_manifest_uri": verifier_uri,
        "verifier_manifest_sha256": verifier_manifest["manifest_sha256"],
        "selected_candidate": reconstruction.selected_candidate,
        "selection_sha256": reconstruction.selection_sha256,
        "output_rows": reconstruction.row_counts,
        "output_records_sha256": reconstruction.records_shas,
        "production_activation_authorized": False,
    }
