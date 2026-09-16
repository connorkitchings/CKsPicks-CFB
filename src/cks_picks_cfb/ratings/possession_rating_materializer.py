"""Producer-owned orchestration for the sealed V5-03 possession rating tournament.

The runner owns CLI boundaries and storage construction; this module streams the
exact R6/Repair v2 parents once, constructs every chronological prior and pregame
state for the sealed 60-candidate registry, runs the common bridge and selection
tournament, and records deterministic no-write preflight evidence.  Mathematical
primitives stay in :mod:`possession_ratings` and selection stays in
:mod:`possession_rating_tournament`.

Certified observation construction (bound to the R6 replay): each source game
supplies exactly one adjusted z per team/role/definition, equal to the team's
iteration-four snapshot value at the first certified cutoff boundary where that
game became admissible (kickoff + 6h, strictly later week).  An observation is
usable at a forecast cutoff only when its boundary cutoff is at or before that
cutoff, so later opponent information can never be frozen into earlier states.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from cks_picks_cfb.data.data_first_phase2 import (
    DEVELOPMENT_SEASONS,
    FORBIDDEN_SEASONS,
)
from cks_picks_cfb.data.data_first_phase2d import (
    PHASE3_DATASETS,
    REPLACEMENT_ELIGIBILITY_SCHEMA,
    verify_signed_payload,
)
from cks_picks_cfb.data.data_first_possession_rating_v1 import (
    ATTRIBUTION_COLUMNS,
    DEFINITIONS,
    NOISE_FIT_COLUMNS,
    PREDICTION_COLUMNS,
    PRIOR_COLUMNS,
    PRIOR_FAMILIES,
    RATING_DATASETS,
    RATING_REGISTRY_COLUMNS,
    RATING_STATE_COLUMNS,
    TEAM_STATE_COLUMNS,
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
from cks_picks_cfb.ratings.possession_rating_tournament import (
    bridge_predictions,
    select_candidates,
)
from cks_picks_cfb.ratings.possession_ratings import (
    CONTEXT_BLOCKS,
    RatingPrior,
    analytic_update,
    carryover_prior,
    fit_kalman_noise,
    kalman_step,
    learned_prior,
    standardization,
)

Progress = Callable[..., None]
K_BY_DEFINITION = {"ppp": 8.0, "epa_per_possession": 20.0}
HALF_LIFE_BY_UPDATER: dict[str, float | None] = {
    "exposure": None,
    "half_life_2": 2.0,
    "half_life_4": 4.0,
    "half_life_8": 8.0,
}
CONTEXT_ALIASES: Mapping[str, str] = {
    "recruiting_current": "recruiting_current_points",
    "recruiting_4yr": "recruiting_strict_four_class_average_points",
    "recruiting_trend": "recruiting_current_minus_available_average",
}
VENUE_FALLBACK_REASON = "venue_facts_unavailable_in_certified_parents"
FBS_MINIMUM_SCHEDULED_GAMES = 8
NOISE_FIT_MINIMUM_ROWS = 8
NOISE_FIT_MINIMUM_SEASONS = 2
EMPTY_DATASET_SALT = "data_first_possession_rating_empty_v1"


class PossessionMaterializerError(ValueError):
    """Raised when tournament inputs or construction escape the sealed contract."""


@dataclass(frozen=True)
class DatasetPlan:
    """Ordered immutable output membership for evidence-bound apply."""

    dataset: str
    schema_version: str
    partition_keys: tuple[str, ...]
    parts: tuple[dict[str, Any], ...]
    row_count: int
    records_sha: str

    def as_evidence(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "schema_version": self.schema_version,
            "partition_keys": list(self.partition_keys),
            "row_count": self.row_count,
            "records_sha": self.records_sha,
            "parts": [
                {
                    "partition": dict(part["partition"]),
                    "row_count": int(part["row_count"]),
                    "records_sha": part["records_sha"],
                }
                for part in self.parts
            ],
        }


@dataclass(frozen=True)
class RatingTournamentInputs:
    """Every certified parent fact the tournament is allowed to consume."""

    population: pd.DataFrame
    observations: pd.DataFrame
    snapshots: pd.DataFrame
    terminal: pd.DataFrame
    outcomes: pd.DataFrame
    context: dict[str, pd.DataFrame]
    history_audit: dict[str, Any]
    source_refs: dict[str, Any]
    population_sha256: str


@dataclass(frozen=True)
class RatingTournamentComputation:
    """Complete deterministic tournament result without any R2 write."""

    candidate_status: dict[str, str]
    predictions: pd.DataFrame
    attribution: pd.DataFrame
    selected_candidate: str
    plans: dict[str, DatasetPlan]
    diagnostics: dict[str, Any]
    frames: dict[str, pd.DataFrame] | None = None

    def preflight_evidence(self) -> dict[str, Any]:
        selection_records = self.attribution.loc[:, ATTRIBUTION_COLUMNS].to_dict(
            "records"
        )
        selection_payload = {
            "attribution": selection_records,
            "selected_candidate": self.selected_candidate,
            "candidate_status": dict(sorted(self.candidate_status.items())),
        }
        selection_sha = _json_sha(selection_payload)
        return {
            "candidate_status": dict(sorted(self.candidate_status.items())),
            "selected_candidate": self.selected_candidate,
            "selection_sha256": selection_sha,
            "preflight_plans": {
                name: plan.as_evidence()
                for name, plan in sorted(self.plans.items())
            },
            "row_counts": {
                name: plan.row_count for name, plan in sorted(self.plans.items())
            },
            "output_records_sha256": {
                name: plan.records_sha for name, plan in sorted(self.plans.items())
            },
            "diagnostics": self.diagnostics,
        }


def _json_sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str).encode()
    ).hexdigest()


def _partitioned_ref(value: Mapping[str, Any], *, name: str) -> PartitionedDatasetRef:
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
        raise PossessionMaterializerError(
            f"parent output reference is malformed: {name}"
        ) from exc


def _dataset_ref(value: Mapping[str, Any], *, name: str) -> DatasetRef:
    fields = ("dataset", "version_id", "schema_version", "content_sha", "uri")
    if missing := [item for item in fields if not value.get(item)]:
        raise PossessionMaterializerError(
            f"dataset reference lacks fields: {name} {missing}"
        )
    return DatasetRef(**{item: value[item] for item in fields})


def _manifest_parts(
    storage: Any, ref: PartitionedDatasetRef
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw = storage.read_bytes(ref.uri)
    if hashlib.sha256(raw).hexdigest() != ref.content_sha:
        raise PossessionMaterializerError(
            f"partition manifest checksum mismatch: {ref.dataset}"
        )
    manifest = json.loads(raw)
    if (
        manifest.get("artifact_kind") != PARTITIONED_DATASET_KIND
        or manifest.get("dataset") != ref.dataset
        or manifest.get("schema_version") != ref.schema_version
        or tuple(manifest.get("partition_keys") or ()) != ref.partition_keys
    ):
        raise PossessionMaterializerError(
            f"partition manifest identity mismatch: {ref.dataset}"
        )
    parts = list(manifest.get("parts") or [])
    if partitioned_records_sha(parts, ref.partition_keys) != ref.records_sha:
        raise PossessionMaterializerError(
            f"partition digest mismatch: {ref.dataset}"
        )
    if sum(int(part["row_count"]) for part in parts) != ref.row_count:
        raise PossessionMaterializerError(
            f"partition count mismatch: {ref.dataset}"
        )
    return parts, [part for part in parts if int(part["row_count"]) > 0]


def _read_child(
    storage: Any,
    *,
    dataset: str,
    schema_version: str,
    part: Mapping[str, Any],
) -> pd.DataFrame:
    child = part.get("ref")
    if child is None:
        raise PossessionMaterializerError(
            f"nonempty partition lacks a child reference: {dataset}"
        )
    frame = read_dataset(storage, _dataset_ref(child, name=f"{dataset}:child"))
    schema = schema_for(dataset, schema_version)
    validate_frame(frame, schema)
    if len(frame) != int(part["row_count"]) or canonical_frame_digest(
        frame, columns=schema.required
    ) != str(part["records_sha"]):
        raise PossessionMaterializerError(
            f"child content mismatch: {dataset} {part['partition']}"
        )
    return frame


def _stream_output(
    storage: Any,
    *,
    name: str,
    value: Mapping[str, Any],
    progress: Progress,
) -> pd.DataFrame:
    """Stream a partitioned R6 output once and return its concatenated rows."""
    ref = _partitioned_ref(value, name=name)
    expected_dataset, expected_schema = POSSESSION_DATASETS[name]
    if (
        ref.artifact_kind != PARTITIONED_DATASET_KIND
        or ref.dataset != expected_dataset
        or ref.schema_version != expected_schema
    ):
        raise PossessionMaterializerError(f"R6 output identity mismatch: {name}")
    _, nonempty = _manifest_parts(storage, ref)
    progress(
        "r6_stream_started",
        dataset=name,
        completed=0,
        total=len(nonempty),
        rows=0,
    )
    frames: list[pd.DataFrame] = []
    for index, part in enumerate(nonempty, start=1):
        frames.append(
            _read_child(
                storage,
                dataset=expected_dataset,
                schema_version=expected_schema,
                part=part,
            )
        )
        progress(
            "r6_stream_part",
            dataset=name,
            completed=index,
            total=len(nonempty),
            rows=int(part["row_count"]),
            partition=part["partition"],
    )
    if not frames:
        return pd.DataFrame(columns=schema_for(expected_dataset, expected_schema).required)
    return _concat_frames(
        frames,
        columns=list(schema_for(expected_dataset, expected_schema).required),
    )


def _core_eligibility_refs(
    storage: Any, repair: Mapping[str, Any]
) -> dict[int, dict[str, DatasetRef]]:
    uri = ((repair.get("parents") or {}).get("core_eligibility") or {}).get("uri")
    if not uri:
        raise PossessionMaterializerError(
            "Repair parent lacks core eligibility lineage"
        )
    payload = json.loads(storage.read_bytes(str(uri)))
    if payload.get("schema_version") != REPLACEMENT_ELIGIBILITY_SCHEMA:
        raise PossessionMaterializerError("core eligibility schema mismatch")
    verify_signed_payload(payload, label="core eligibility")
    if (
        payload.get("state") != "eligible"
        or payload.get("production_activation_authorized") is not False
        or tuple(payload.get("development_seasons") or ()) != DEVELOPMENT_SEASONS
        or tuple(payload.get("forbidden_seasons") or ()) != FORBIDDEN_SEASONS
    ):
        raise PossessionMaterializerError(
            "core eligibility is not sealed Preview evidence"
        )
    result: dict[int, dict[str, DatasetRef]] = {}
    for value in payload.get("phase3_input_refs") or []:
        key = (int(value.get("season", -1)), str(value.get("dataset")))
        if value.get("eligible") is not True or key[1] not in PHASE3_DATASETS:
            raise PossessionMaterializerError(
                f"core eligibility rejects source {key}"
            )
        result.setdefault(key[0], {})[key[1]] = _dataset_ref(
            value, name=f"core:{key[0]}:{key[1]}"
        )
    expected = {
        (season, dataset)
        for season in DEVELOPMENT_SEASONS
        for dataset in PHASE3_DATASETS
    }
    seen = {
        (season, dataset) for season, values in result.items() for dataset in values
    }
    if seen != expected or any(
        {"byplay", "game_outcomes"} - set(values) for values in result.values()
    ):
        raise PossessionMaterializerError(
            "core eligibility must provide the exact 70-ref source set"
        )
    return result


def _context_blocks(auxiliary: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Normalize admitted auxiliary rows into the frozen prior feature blocks."""
    required = {"family", "season", "team", "historical_eligible"}
    if not required.issubset(auxiliary.columns):
        raise PossessionMaterializerError("auxiliary source lacks contract columns")
    eligible = auxiliary[auxiliary["historical_eligible"].eq(True)].copy()
    eligible["team"] = eligible["team"].map(canonical_team)
    eligible["season"] = pd.to_numeric(eligible["season"], errors="raise").astype(int)
    if eligible["team"].isna().any():
        raise PossessionMaterializerError("auxiliary team identity is unresolved")
    blocks: dict[str, pd.DataFrame] = {}
    for family, columns in CONTEXT_BLOCKS.items():
        source_columns = [CONTEXT_ALIASES.get(column, column) for column in columns]
        missing = [
            column for column in source_columns if column not in eligible.columns
        ]
        if missing:
            raise PossessionMaterializerError(
                f"auxiliary source lacks admitted columns: {family} {missing}"
            )
        subset = eligible.loc[
            :, ["family", "season", "team", *source_columns]
        ].copy()
        subset = subset[subset["family"].eq(family)]
        subset = subset.rename(columns=dict(zip(source_columns, list(columns))))
        subset = subset.drop_duplicates(["season", "team"], keep=False)
        blocks[family] = subset.loc[:, ["season", "team", *columns]].sort_values(
            ["season", "team"], kind="mergesort"
        )
    return blocks


def load_rating_inputs(
    *,
    storage: Any,
    measurement: Mapping[str, Any],
    repair: Mapping[str, Any],
    progress: Progress,
) -> RatingTournamentInputs:
    """Read and validate every certified parent fact with bounded memory."""
    output_refs = measurement.get("output_refs") or {}
    if set(output_refs) != set(POSSESSION_DATASETS):
        raise PossessionMaterializerError("R6 manifest output set changed")

    population = _stream_output(
        storage, name="population", value=output_refs["population"], progress=progress
    ).loc[:, list(POPULATION_COLUMNS)]
    if len(population) != 8936 or int(population["forecast_eligible"].sum()) != 8935:
        raise PossessionMaterializerError("R6 population reconciliation changed")
    if population["season"].isin(FORBIDDEN_SEASONS).any():
        raise PossessionMaterializerError("R6 population contains a forbidden season")

    observations = _stream_output(
        storage,
        name="observations",
        value=output_refs["observations"],
        progress=progress,
    )
    observations = observations[
        observations["measurement_id"].isin(ADJUSTED_MEASUREMENTS)
    ].reset_index(drop=True)

    terminal = _stream_output(
        storage, name="terminal", value=output_refs["terminal"], progress=progress
    )

    snapshots = _stream_output(
        storage, name="snapshots", value=output_refs["snapshots"], progress=progress
    )
    snapshots = snapshots[
        snapshots["adjustment_iteration"].eq(4)
        & snapshots["measurement_id"].isin(ADJUSTED_MEASUREMENTS)
    ].reset_index(drop=True)

    auxiliary_ref = (repair.get("output_refs") or {}).get("auxiliary") or {}
    auxiliary = read_dataset(
        storage, _dataset_ref(auxiliary_ref, name="repair:auxiliary")
    )
    context = _context_blocks(auxiliary)

    refs = _core_eligibility_refs(storage, repair)
    outcome_frames = [
        read_dataset(storage, refs[season]["game_outcomes"])
        for season in sorted(refs)
    ]
    outcomes = pd.concat(outcome_frames, ignore_index=True, sort=False).loc[
        :, ["season", "game_id", "completed", "home_points", "away_points"]
    ]
    for name in ("season", "game_id"):
        outcomes[name] = pd.to_numeric(outcomes[name], errors="raise").astype(int)

    history_audit = _audit_adjusted_history(
        storage=storage,
        value=output_refs["adjusted_history"],
        snapshots=snapshots,
        progress=progress,
    )

    population_records = population.loc[:, list(POPULATION_COLUMNS)].to_dict("records")
    source_refs = {
        "measurement_output_refs": {
            name: {
                "uri": output_refs[name]["uri"],
                "records_sha": output_refs[name]["records_sha"],
                "row_count": int(output_refs[name]["row_count"]),
            }
            for name in sorted(output_refs)
        },
        "history_parts": history_audit["history_parts"],
        "history_rows": history_audit["history_rows"],
    }
    return RatingTournamentInputs(
        population=population,
        observations=observations,
        snapshots=snapshots,
        terminal=terminal,
        outcomes=outcomes,
        context=context,
        history_audit=history_audit,
        source_refs=source_refs,
        population_sha256=_json_sha(population_records),
    )


def _audit_adjusted_history(
    *,
    storage: Any,
    value: Mapping[str, Any],
    snapshots: pd.DataFrame,
    progress: Progress,
) -> dict[str, Any]:
    """Stream the 24.2M-row history once, validating cutoff chronology."""
    ref = _partitioned_ref(value, name="adjusted_history")
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
    parts, nonempty = _manifest_parts(storage, ref)
    rows_seen = 0
    violations = 0
    value_mismatches = 0
    progress(
        "history_audit_started",
        dataset="adjusted_history",
        completed=0,
        total=len(nonempty),
        rows=0,
    )
    for index, part in enumerate(nonempty, start=1):
        frame = _read_child(
            storage,
            dataset=POSSESSION_DATASETS["adjusted_history"][0],
            schema_version=POSSESSION_DATASETS["adjusted_history"][1],
            part=part,
        )
        available = pd.to_datetime(frame["source_available_utc"], utc=True)
        cutoff = pd.to_datetime(frame["target_week_cutoff_utc"], utc=True)
        strictly_later = (
            available <= cutoff
        ) & frame["source_week"].astype(int).lt(frame["week"].astype(int))
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
            total=len(nonempty),
            rows=rows_seen,
            partition=part["partition"],
        )
    manifest_rows = sum(int(part["row_count"]) for part in parts)
    if rows_seen != manifest_rows or ref.row_count != manifest_rows:
        raise PossessionMaterializerError(
            "adjusted history row counts differ from the certified manifest"
        )
    if violations or value_mismatches:
        raise PossessionMaterializerError(
            "adjusted history violates cutoff chronology or snapshot consistency: "
            f"{violations} availability violations, {value_mismatches} mismatches"
        )
    return {
        "history_parts": len(parts),
        "history_rows": rows_seen,
        "availability_violations": violations,
        "snapshot_value_mismatches": value_mismatches,
    }


def build_boundary_table(population: pd.DataFrame) -> pd.DataFrame:
    """Certified first-inclusion boundary per forecast-eligible game.

    A game's observation boundary is the earliest later-week eligible game whose
    kickoff is at least six hours after the source kickoff, mirroring the R6
    availability policy exactly.  A season's final game has no boundary and can
    therefore never supply a certified within-season observation.
    """
    eligible = population[population["forecast_eligible"]].copy()
    eligible["kickoff_utc"] = pd.to_datetime(eligible["kickoff_utc"], utc=True)
    eligible["available_utc"] = eligible["kickoff_utc"] + pd.Timedelta(hours=6)
    records: list[dict[str, Any]] = []
    for season in DEVELOPMENT_SEASONS:
        season_games = eligible[eligible["season"].eq(season)]
        if season_games.empty:
            continue
        ordered = season_games.sort_values(
            ["kickoff_utc", "game_id"], kind="mergesort"
        )
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
                if boundary_game == int(row.game_id):
                    raise PossessionMaterializerError(
                        "boundary assignment selected the source game itself"
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
    if result.empty:
        raise PossessionMaterializerError("no certified boundaries available")
    if result.duplicated(["season", "game_id"]).any():
        raise PossessionMaterializerError("boundary assignment duplicated a game")
    return result.sort_values(["season", "week", "game_id"], kind="mergesort")


def build_terminal_tables(
    terminal: pd.DataFrame,
) -> dict[tuple[str, str, int], dict[str, Any]]:
    """Per (definition, role, season) center/scale and per-team terminal z."""
    tables: dict[tuple[str, str, int], dict[str, Any]] = {}
    for definition in DEFINITIONS:
        for role in ROLES:
            for season in DEVELOPMENT_SEASONS:
                center, scale = standardization(
                    terminal, season=season, definition=definition, role=role
                )
                rows = terminal[
                    terminal["season"].eq(season)
                    & terminal["measurement_id"].eq(definition)
                    & terminal["unit_role"].eq(role)
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
                    teams[str(row.team)] = (
                        sign * (value - center) / scale,
                        exposure,
                    )
                tables[(definition, role, season)] = {
                    "center": center,
                    "scale": scale,
                    "sign": sign,
                    "teams": teams,
                }
    return tables


def build_observation_streams(
    *,
    inputs: RatingTournamentInputs,
    boundaries: pd.DataFrame,
    terminal_tables: Mapping[tuple[str, str, int], Mapping[str, Any]],
) -> dict[tuple[str, str], pd.DataFrame]:
    """Per (definition, role) chronological certified observation streams.

    Each source game supplies one adjusted z equal to its team's iteration-four
    snapshot value at the game's first certified inclusion boundary, scaled by
    the preceding-season team-equal center/scale with defense sign reversal.
    The observation's information is the game's own usable possession count.
    """
    observations = inputs.observations
    observations = observations[
        observations["coverage_status"].eq("observed")
        & pd.to_numeric(observations["denominator"], errors="coerce").gt(0)
    ].copy()
    observations["kickoff_utc"] = pd.to_datetime(
        observations["kickoff_utc"], utc=True
    )
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
        for row in inputs.snapshots.itertuples(index=False)
        if pd.notna(row.adjusted_value)
    }
    streams: dict[tuple[str, str], pd.DataFrame] = {}
    for definition in DEFINITIONS:
        subset = observations[observations["measurement_id"].eq(definition)].merge(
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
                    (
                        int(row.boundary_game_id),
                        str(row.team),
                        definition,
                        role,
                    )
                )
                if value is None or not np.isfinite(value):
                    z_values.append(float("nan"))
                    continue
                z_values.append(
                    float(
                        table["sign"]
                        * (value - table["center"])
                        / table["scale"]
                    )
                )
            role_rows["adjusted_z"] = z_values
            role_rows = role_rows.dropna(subset=["adjusted_z"]).reset_index(drop=True)
            role_rows["usable_exposure"] = pd.to_numeric(
                role_rows["denominator"], errors="coerce"
            )
            streams[(definition, role)] = role_rows.sort_values(
                ["kickoff_utc", "game_id"], kind="mergesort"
            ).reset_index(drop=True)
    return streams


def _previous_season(season: int) -> int | None:
    earlier = [value for value in DEVELOPMENT_SEASONS if value < season]
    return earlier[-1] if earlier else None


def build_prior_tables(
    *,
    context: Mapping[str, pd.DataFrame],
    terminal_tables: Mapping[tuple[str, str, int], Mapping[str, Any]],
) -> dict[tuple[str, str], pd.DataFrame]:
    """Priors per (definition, prior family) with per-team rows by season."""
    columns = [
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
    labels: dict[tuple[str, str], list[dict[str, Any]]] = {
        (definition, role): []
        for definition in DEFINITIONS
        for role in ROLES
    }
    for definition in DEFINITIONS:
        for role in ROLES:
            for season in DEVELOPMENT_SEASONS:
                table = terminal_tables[(definition, role, season)]
                previous = terminal_tables[(definition, role, _previous_season(season))][
                    "teams"
                ] if _previous_season(season) is not None else {}
                gap = season - _previous_season(season) if previous else 0
                for team, (terminal_z, _) in table["teams"].items():
                    prior_z = previous.get(team)
                    labels[(definition, role)].append(
                        {
                            "season": season,
                            "team": team,
                            "unit_role": role,
                            "terminal_z": terminal_z,
                            "carryover_mean": (
                                (0.60**gap) * prior_z[0] if prior_z else np.nan
                            ),
                        }
                    )
    training_labels = {
        key: pd.DataFrame(rows) for key, rows in labels.items() if rows
    }
    priors: dict[tuple[str, str], pd.DataFrame] = {}
    for definition in DEFINITIONS:
        k = K_BY_DEFINITION[definition]
        for family in PRIOR_FAMILIES:
            records: list[dict[str, Any]] = []
            for role in ROLES:
                training = training_labels.get((definition, role))
                context_frame = context.get(family)
                for season in DEVELOPMENT_SEASONS:
                    # Do not let a context record admitted for a later season
                    # alter an earlier season's fallback attribution.  Earlier
                    # rows remain available to fit chronological learned priors,
                    # while an otherwise empty prefix is equivalent to no
                    # admitted context at all.
                    context_at_season = None
                    if context_frame is not None:
                        available_context = context_frame[
                            context_frame["season"].astype(int).le(season)
                        ]
                        if not available_context.empty:
                            context_at_season = available_context
                    table = terminal_tables[(definition, role, season)]
                    source_season = _previous_season(season)
                    previous = (
                        terminal_tables[(definition, role, source_season)]["teams"]
                        if source_season is not None
                        else {}
                    )
                    gap = season - source_season if source_season else 0
                    teams = sorted(set(table["teams"]) | set(previous))
                    for team in teams:
                        previous_terminal = previous.get(team)
                        if previous_terminal is None:
                            carry = RatingPrior(
                                0.0, 1.0, "neutral", None, "no_predecessor"
                            )
                        else:
                            prev_z, prev_exposure = previous_terminal
                            prev_variance = 1.0 / (1.0 + prev_exposure / k)
                            carry = carryover_prior(
                                RatingPrior(
                                    prev_z,
                                    prev_variance,
                                    "terminal",
                                    source_season,
                                ),
                                gap=gap,
                            )
                        if family == "neutral":
                            prior = RatingPrior(0.0, 1.0, "neutral", None)
                        elif family == "rho_0_60":
                            prior = carry
                        else:
                            prior = learned_prior(
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
                records, columns=columns
            )
    return priors


def fit_noise_tables(
    *,
    streams: Mapping[tuple[str, str], pd.DataFrame],
    priors: Mapping[tuple[str, str], pd.DataFrame],
    progress: Progress,
) -> dict[tuple[str, str, str, int], dict[str, Any]]:
    """Earlier-season-only prior-centered Kalman noise per definition/role/prior."""
    tables: dict[tuple[str, str, str, int], dict[str, Any]] = {}
    total = len(DEFINITIONS) * len(ROLES) * len(PRIOR_FAMILIES) * len(DEVELOPMENT_SEASONS)
    completed = 0
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
                    completed += 1
                    progress(
                        "noise_fit",
                        completed=completed,
                        total=total,
                        definition=definition,
                        role=role,
                        prior_family=family,
                        season=season,
                    )
                    earlier = [value for value in DEVELOPMENT_SEASONS if value < season]
                    rows = [
                        (
                            float(row.adjusted_z)
                            - prior_lookup.get(
                                (int(row.season), str(row.team)), 0.0
                            ),
                            float(row.usable_exposure),
                            7.0,
                        )
                        for row in stream.itertuples(index=False)
                        if int(row.season) in set(earlier)
                        and pd.notna(row.adjusted_z)
                        and float(row.usable_exposure) > 0
                    ]
                    if len(rows) < NOISE_FIT_MINIMUM_ROWS:
                        tables[(definition, family, role, season)] = {
                            "q": 0.0,
                            "r": 1.0,
                            "objective": -1.0,
                            "converged": False,
                            "cold_start": True,
                            "training_seasons": earlier,
                            "disqualifies": False,
                        }
                        continue
                    q, r, objective, converged = fit_kalman_noise(rows)
                    disqualifies = (
                        not converged
                        and len(earlier) >= NOISE_FIT_MINIMUM_SEASONS
                    )
                    tables[(definition, family, role, season)] = {
                        "q": q,
                        "r": r,
                        "objective": objective if converged else -1.0,
                        "converged": converged,
                        "cold_start": not converged,
                        "training_seasons": earlier,
                        "disqualifies": disqualifies,
                    }
    return tables


class _IncrementalState:
    """Exact incremental equivalent of the sealed replay primitives.

    Analytic states pool weighted evidence through :func:`analytic_update`;
    Kalman states advance through the sealed :func:`kalman_step` equations with
    assimilation days measured between source kickoffs and a final advance to
    each forecast cutoff, matching :func:`replay_states` exactly.
    """

    __slots__ = (
        "prior",
        "updater",
        "k",
        "half_life",
        "q",
        "r",
        "weighted_value",
        "weighted_exposure",
        "completed_games",
        "kalman_mean",
        "kalman_variance",
        "kalman_initialized",
        "last_kickoff",
        "process_contribution",
    )

    def __init__(
        self,
        *,
        prior: RatingPrior,
        updater: str,
        k: float,
        half_life: float | None,
        q: float,
        r: float,
    ) -> None:
        self.prior = prior
        self.updater = updater
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
        self.process_contribution = 0.0

    def _decay(self) -> float:
        if self.half_life is None:
            return 1.0
        return 0.5 ** (1.0 / self.half_life)

    def _carrier(self, mean: float, variance: float, process: float):
        from cks_picks_cfb.ratings.possession_ratings import RatingState

        return RatingState(
            mean=mean,
            variance=variance,
            prior_mean=self.prior.mean,
            prior_variance=self.prior.variance,
            evidence_weight=0.0,
            process_variance=process,
            usable_exposure=0.0,
            completed_games=self.completed_games,
        )

    def assimilate(self, kickoff: Any, z: float | None, exposure: float) -> None:
        if self.updater != "kalman":
            usable = z is not None and np.isfinite(z) and exposure > 0
            if usable:
                # Recency ages advance per usable observation, matching the
                # sealed recency convention over admissible usable rows.
                factor = self._decay()
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
            (pd.Timestamp(kickoff) - pd.Timestamp(self.last_kickoff)).total_seconds()
            / 86400.0,
            0.0,
        )
        observation = (
            float(z) if z is not None and np.isfinite(z) and exposure > 0 else None
        )
        state = kalman_step(
            self._carrier(
                self.kalman_mean, self.kalman_variance, self.process_contribution
            ),
            observation=observation,
            exposure=exposure if observation is not None else 0.0,
            elapsed_days=days,
            q=self.q,
            r=self.r,
        )
        self.kalman_mean = state.mean
        self.kalman_variance = state.variance
        self.process_contribution = state.process_variance
        self.completed_games += 1
        self.last_kickoff = kickoff

    def state(self, cutoff: Any) -> tuple[float, float, float, float, float, int]:
        """Pregame state at the cutoff, matching the sealed replay output."""
        if self.updater != "kalman":
            observation = (
                self.weighted_value / self.weighted_exposure
                if self.weighted_exposure > 0
                else None
            )
            state = analytic_update(
                self.prior, observation, self.weighted_exposure, k=self.k
            )
            return (
                state.mean,
                state.variance,
                state.evidence_weight,
                0.0,
                self.weighted_exposure,
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
            (pd.Timestamp(cutoff) - pd.Timestamp(self.last_kickoff)).total_seconds()
            / 86400.0,
            0.0,
        )
        advanced = kalman_step(
            self._carrier(
                self.kalman_mean, self.kalman_variance, self.process_contribution
            ),
            observation=None,
            exposure=0.0,
            elapsed_days=days,
            q=self.q,
            r=self.r,
        )
        return (
            advanced.mean,
            advanced.variance,
            advanced.evidence_weight,
            advanced.process_variance,
            advanced.usable_exposure,
            advanced.completed_games,
        )


def _fbs_universe(population: pd.DataFrame) -> set[tuple[int, str]]:
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
        if count >= FBS_MINIMUM_SCHEDULED_GAMES
    }


def _completed_counts(population: pd.DataFrame) -> dict[tuple[int, int], dict[str, int]]:
    """Completed prior games per team at each scheduled cutoff."""
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


def _scoreable_games(
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


def compute_tournament(
    *,
    inputs: RatingTournamentInputs,
    progress: Progress,
    retain_frames: bool = False,
) -> RatingTournamentComputation:
    """Run the complete sealed tournament and plan every immutable output."""
    boundaries = build_boundary_table(inputs.population)
    terminal_tables = build_terminal_tables(inputs.terminal)
    streams = build_observation_streams(
        inputs=inputs, boundaries=boundaries, terminal_tables=terminal_tables
    )
    priors = build_prior_tables(
        context=inputs.context, terminal_tables=terminal_tables
    )
    noise = fit_noise_tables(streams=streams, priors=priors, progress=progress)
    fbs = _fbs_universe(inputs.population)
    completed = _completed_counts(inputs.population)
    games = _scoreable_games(
        population=inputs.population,
        outcomes=inputs.outcomes,
        completed=completed,
    )

    chunks: dict[str, dict[tuple[int, ...], list[pd.DataFrame]]] = {
        name: {} for name in RATING_DATASETS
    }
    candidate_status: dict[str, str] = {}
    progress("tournament_started", completed=0, total=len(candidate_registry()))
    for index, entry in enumerate(candidate_registry(), start=1):
        status = _run_candidate(
            entry=entry,
            inputs=inputs,
            boundaries=boundaries,
            streams=streams,
            terminal_tables=terminal_tables,
            priors=priors,
            noise=noise,
            games=games,
            fbs=fbs,
            chunks=chunks,
        )
        candidate_status[entry["candidate_id"]] = status
        progress(
            "tournament_candidate",
            completed=index,
            total=len(candidate_registry()),
            candidate=entry["candidate_id"],
            status=status,
        )

    predictions = _merged_chunks(chunks["bridge_predictions"], list(PREDICTION_COLUMNS))
    valid_predictions = predictions[
        predictions["candidate_id"].map(candidate_status).eq("ok")
    ]
    validity = {
        candidate: (None if status == "ok" else status)
        for candidate, status in candidate_status.items()
    }
    attribution = select_candidates(valid_predictions, validity=validity)
    selected = str(attribution.loc[attribution["selected"], "candidate_id"].iloc[0])

    registry_rows = pd.DataFrame.from_records(
        [
            {
                "candidate_id": entry["candidate_id"],
                "definition": entry["definition"],
                "prior_family": entry["prior_family"],
                "updater": entry["updater"],
                "reference_candidate": entry["reference_candidate"],
                "prior_feature_count": entry["prior_feature_count"],
            }
            for entry in candidate_registry()
        ],
        columns=list(RATING_REGISTRY_COLUMNS),
    )
    plans = {
        "rating_registry": _compact_plan("rating_registry", registry_rows),
        "attribution": _compact_plan("attribution", attribution),
        "priors": _partitioned_plan(
            "priors", chunks["priors"], partition_keys=("season",)
        ),
        "noise_fits": _partitioned_plan(
            "noise_fits", chunks["noise_fits"], partition_keys=("season",)
        ),
        "rating_states": _partitioned_plan(
            "rating_states", chunks["rating_states"], partition_keys=("season", "week")
        ),
        "team_states": _partitioned_plan(
            "team_states", chunks["team_states"], partition_keys=("season", "week")
        ),
        "bridge_predictions": _partitioned_plan(
            "bridge_predictions",
            chunks["bridge_predictions"],
            partition_keys=("season", "week"),
        ),
    }
    diagnostics = {
        "history_audit": inputs.history_audit,
        "population_sha256": inputs.population_sha256,
        "venue_fallback": {
            "reason": VENUE_FALLBACK_REASON,
            "home_host": 1.0,
            "venue_unknown": True,
        },
        "fbs_minimum_scheduled_games": FBS_MINIMUM_SCHEDULED_GAMES,
        "fbs_team_seasons": len(fbs),
        "eligible_games": int(inputs.population["forecast_eligible"].sum()),
        "boundary_games": len(boundaries),
        "scoreable_games": len(games),
        "prediction_rows": len(predictions),
        "candidate_status_counts": {
            status: sum(1 for value in candidate_status.values() if value == status)
            for status in sorted(set(candidate_status.values()))
        },
    }
    return RatingTournamentComputation(
        candidate_status=candidate_status,
        predictions=predictions,
        attribution=attribution,
        selected_candidate=selected,
        plans=plans,
        diagnostics=diagnostics,
        frames=(
            {
                "priors": _merged_chunks(chunks["priors"], list(PRIOR_COLUMNS)),
                "noise_fits": _merged_chunks(
                    chunks["noise_fits"], list(NOISE_FIT_COLUMNS)
                ),
                "rating_states": _merged_chunks(
                    chunks["rating_states"], list(RATING_STATE_COLUMNS)
                ),
                "team_states": _merged_chunks(
                    chunks["team_states"], list(TEAM_STATE_COLUMNS)
                ),
            }
            if retain_frames
            else None
        ),
    )


def _merged_chunks(
    partitions: Mapping[tuple[int, ...], list[pd.DataFrame]], columns: list[str]
) -> pd.DataFrame:
    frames = [
        frame
        for key in sorted(partitions, key=lambda item: tuple(item))
        for frame in partitions[key]
    ]
    return _concat_frames(frames, columns=columns)


def _concat_frames(frames: list[pd.DataFrame], *, columns: list[str]) -> pd.DataFrame:
    """Concatenate contract frames without dtype inference from all-null columns."""
    if not frames:
        return pd.DataFrame(columns=columns)
    normalized = [frame.loc[:, columns].copy() for frame in frames]
    # Optional fields can be entirely null for one candidate and populated for
    # another.  Align their dtype before concatenation so warning-as-error runs
    # do not depend on pandas' deprecated all-null inference behavior.
    for column in columns:
        if any(frame[column].isna().all() for frame in normalized) and any(
            frame[column].notna().any() for frame in normalized
        ):
            for frame in normalized:
                frame[column] = frame[column].astype(object)
    return pd.concat(normalized, ignore_index=True, sort=False)


def _run_candidate(
    *,
    entry: Mapping[str, Any],
    inputs: RatingTournamentInputs,
    boundaries: pd.DataFrame,
    streams: Mapping[tuple[str, str], pd.DataFrame],
    terminal_tables: Mapping[tuple[str, str, int], Mapping[str, Any]],
    priors: Mapping[tuple[str, str], pd.DataFrame],
    noise: Mapping[tuple[str, str, str, int], Mapping[str, Any]],
    games: pd.DataFrame,
    fbs: set[tuple[int, str]],
    chunks: dict[str, dict[tuple[int, ...], list[pd.DataFrame]]],
) -> str:
    candidate = str(entry["candidate_id"])
    definition = str(entry["definition"])
    family = str(entry["prior_family"])
    updater = str(entry["updater"])

    prior_rows = priors[(definition, family)]
    for row in prior_rows.itertuples(index=False):
        if updater != "kalman":
            break
        noise_row = noise[(definition, family, str(row.unit_role), int(row.season))]
        if noise_row.get("disqualifies"):
            return "kalman_noise_fit_failed"

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
    _append_chunks(chunks["priors"], prior_partitions, ("season",))
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
        _append_chunks(chunks["noise_fits"], noise_partitions, ("season",))

    prior_lookup = {
        (int(row.season), str(row.unit_role), str(row.team)): RatingPrior(
            float(row.prior_mean),
            float(row.prior_variance),
            str(row.prior_source),
            row.prior_source_season,
            row.fallback_reason,
        )
        for row in prior_rows.itertuples(index=False)
    }
    streams_by_season: dict[tuple[str, str], dict[int, dict[str, list[dict[str, Any]]]]] = {}
    for definition_name in (definition,):
        for role in ROLES:
            grouped: dict[int, dict[str, list[dict[str, Any]]]] = {}
            for row in streams[(definition_name, role)].itertuples(index=False):
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
            streams_by_season[(definition_name, role)] = grouped

    population = inputs.population
    eligible = population[population["forecast_eligible"]].copy()
    eligible["kickoff_utc"] = pd.to_datetime(eligible["kickoff_utc"], utc=True)

    state_partitions: dict[tuple[int, int], list[dict[str, Any]]] = {}
    team_partitions: dict[tuple[int, int], list[dict[str, Any]]] = {}
    game_states: dict[tuple[int, str], dict[str, tuple[float, float, float, float, float, int, str | None]]] = {}

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
        fcs_history: dict[str, list[tuple[Any, float, float]]] = {role: [] for role in ROLES}
        for team in teams:
            is_fcs = (int(season), team) not in fbs
            team_games = season_games[
                season_games["home_team"].eq(team) | season_games["away_team"].eq(team)
            ]
            for role in ROLES:
                own = streams_by_season[(definition, role)].get(season, {}).get(team, [])
                own = sorted(own, key=lambda item: (item["kickoff_utc"], item["game_id"]))
                prior = prior_lookup.get(
                    (season, role, team),
                    RatingPrior(0.0, 1.0, "neutral", None, "no_predecessor"),
                )
                noise_row = noise_by_role[role]
                if updater == "kalman" and not noise_row["cold_start"]:
                    state = _IncrementalState(
                        prior=prior,
                        updater="kalman",
                        k=K_BY_DEFINITION[definition],
                        half_life=None,
                        q=float(noise_row["q"]),
                        r=float(noise_row["r"]),
                    )
                    fallback: str | None = None
                else:
                    effective = "exposure" if updater == "kalman" else updater
                    state = _IncrementalState(
                        prior=prior,
                        updater=effective,
                        k=K_BY_DEFINITION[definition],
                        half_life=HALF_LIFE_BY_UPDATER[effective],
                        q=0.0,
                        r=1.0,
                    )
                    fallback = "kalman_cold_start" if updater == "kalman" else None
                pending_index = 0
                for game in team_games.itertuples(index=False):
                    cutoff = pd.Timestamp(game.kickoff_utc)
                    while pending_index < len(own):
                        item = own[pending_index]
                        if (
                            pd.Timestamp(item["boundary_cutoff"]) <= cutoff
                            and int(item["game_id"]) != int(game.game_id)
                        ):
                            state.assimilate(
                                item["kickoff_utc"],
                                item["adjusted_z"],
                                item["exposure"],
                            )
                            pending_index += 1
                        else:
                            break
                    mean, variance, weight, process, exposure, completed = state.state(
                        cutoff
                    )
                    role_fallback = fallback
                    if (
                        is_fcs
                        and prior.fallback_reason == "no_predecessor"
                        and completed == 0
                    ):
                        pool_mean, pool_variance, pool_reason = _fcs_partial_pool(
                            fcs_history[role], cutoff
                        )
                        mean, variance, role_fallback = (
                            pool_mean,
                            pool_variance,
                            pool_reason,
                        )
                        weight, process, exposure = 0.0, 0.0, 0.0
                    table = scale_table[role]
                    state_partitions.setdefault((int(season), int(game.week)), []).append(
                        {
                            "candidate_id": candidate,
                            "definition": definition,
                            "season": int(season),
                            "week": int(game.week),
                            "game_id": int(game.game_id),
                            "cutoff_utc": cutoff.isoformat(),
                            "team": team,
                            "unit_role": role,
                            "native_mean": mean * table["scale"] / table["sign"] + table["center"],
                            "rating_mean": mean,
                            "rating_variance": variance,
                            "prior_mean": prior.mean,
                            "prior_variance": prior.variance,
                            "evidence_weight": weight,
                            "process_variance": process,
                            "usable_exposure": exposure,
                            "completed_games": completed,
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
                        completed,
                        role_fallback,
                    )
        for game in season_games.itertuples(index=False):
            for team in (str(game.home_team), str(game.away_team)):
                roles = game_states.get((int(game.game_id), team))
                if not roles or set(roles) != set(ROLES):
                    raise PossessionMaterializerError(
                        "unexplained missing non-FCS state: "
                        f"{season}/{game.game_id}/{team}"
                    )
                offense = roles["offense"]
                defense = roles["defense"]
                team_partitions.setdefault((int(season), int(game.week)), []).append(
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
                        "fallback_reason": _join_fallbacks(offense[6], defense[6]),
                    }
                )

    _append_chunks(chunks["rating_states"], state_partitions, ("season", "week"))
    _append_chunks(chunks["team_states"], team_partitions, ("season", "week"))
    team_frame = _merged_chunks(
        {
            key: [pd.DataFrame.from_records(rows, columns=list(TEAM_STATE_COLUMNS))]
            for key, rows in team_partitions.items()
        },
        list(TEAM_STATE_COLUMNS),
    )
    del game_states
    predictions = bridge_predictions(
        team_frame,
        games.drop(columns=["home_points", "away_points"]),
        inputs.outcomes,
        candidate=candidate,
    )
    prediction_partitions: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for record in predictions.to_dict("records"):
        prediction_partitions.setdefault(
            (int(record["season"]), int(record["week"])), []
        ).append(record)
    _append_chunks(
        chunks["bridge_predictions"], prediction_partitions, ("season", "week")
    )
    return "ok"


def _join_fallbacks(*values: str | None) -> str | None:
    joined = [value for value in values if value]
    return "|".join(joined) if joined else None


def _fcs_partial_pool(
    history: list[tuple[Any, float, float]], cutoff: Any
) -> tuple[float, float, str]:
    """Inherited strictly preceding FCS cohort fallback with conservative variance."""
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
    conservative = max(float(np.sqrt(variance)), max(float(np.sqrt(v)) for _, v in values))
    return mean, conservative**2, "preceding_fcs_partial_pool"


def _append_chunks(
    target: dict[tuple[int, ...], list[pd.DataFrame]],
    partitions: Mapping[int | tuple[int, ...], list[dict[str, Any]]],
    partition_keys: tuple[str, ...],
) -> None:
    """Append rows under the canonical tuple partition representation.

    Season-only producers naturally accumulate under integer keys, while
    multi-key datasets use tuples.  Normalize both shapes before sorting and
    storing so a one-key plan has the same evidence shape as a multi-key plan.
    """
    normalized = [
        ((key,) if isinstance(key, int) else tuple(key), rows)
        for key, rows in partitions.items()
    ]
    for key, rows in sorted(normalized, key=lambda item: item[0]):
        if len(key) != len(partition_keys):
            raise PossessionMaterializerError(
                f"partition key width differs from {partition_keys}: {key}"
            )
        target.setdefault(key, []).append(
            pd.DataFrame.from_records(rows)
        )


def _compact_plan(name: str, frame: pd.DataFrame) -> DatasetPlan:
    dataset, schema_version = RATING_DATASETS[name]
    schema = schema_for(dataset, schema_version)
    validate_frame(frame, schema)
    return DatasetPlan(
        dataset=dataset,
        schema_version=schema_version,
        partition_keys=(),
        parts=(),
        row_count=len(frame),
        records_sha=canonical_frame_digest(frame, columns=schema.required),
    )


def _partitioned_plan(
    name: str,
    partitions: Mapping[tuple[int, ...], list[pd.DataFrame]],
    *,
    partition_keys: tuple[str, ...],
) -> DatasetPlan:
    dataset, schema_version = RATING_DATASETS[name]
    schema = schema_for(dataset, schema_version)
    parts: list[dict[str, Any]] = []
    for key in sorted(partitions, key=lambda item: tuple(item)):
        # Candidate chunks can legitimately have an optional column that is
        # entirely null (for example, a neutral prior's source season).  Build
        # a canonical record frame directly to avoid pandas' deprecated dtype
        # inference during all-null concatenation.
        records = [
            record
            for candidate_frame in partitions[key]
            for record in candidate_frame.loc[:, schema.required].to_dict("records")
        ]
        frame = pd.DataFrame.from_records(records, columns=schema.required)
        if frame.empty:
            continue
        validate_frame(frame, schema)
        for index, partition_name in enumerate(partition_keys):
            if not frame[partition_name].eq(int(key[index])).all():
                raise PossessionMaterializerError(
                    f"{dataset} rows escape partition {key}"
                )
        partition = {
            partition_keys[i]: int(key[i]) for i in range(len(partition_keys))
        }
        parts.append(
            {
                "partition": partition,
                "row_count": int(len(frame)),
                "records_sha": canonical_frame_digest(
                    frame, columns=schema.required
                ),
            }
        )
    if parts and any(
        partition_order_key(part["partition"])
        <= partition_order_key(parts[index - 1]["partition"])
        for index, part in enumerate(parts)
        if index
    ):
        raise PossessionMaterializerError(f"{dataset} parts are not strictly ordered")
    records_sha = (
        partitioned_records_sha(parts, partition_keys)
        if parts
        else _json_sha({"dataset": dataset, "salt": EMPTY_DATASET_SALT})
    )
    return DatasetPlan(
        dataset=dataset,
        schema_version=schema_version,
        partition_keys=partition_keys,
        parts=tuple(parts),
        row_count=int(sum(part["row_count"] for part in parts)),
        records_sha=records_sha,
    )
