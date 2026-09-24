"""Verifier-owned reconstruction for the Contract 08 live rating replay.

This module intentionally does not import the live replay producer, the
historical tournament materializer, or their research runners.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.data.data_first_possession_rating_v1 import (
    PRIOR_COLUMNS,
    RATING_DATASETS,
    RATING_STATE_COLUMNS,
    TEAM_STATE_COLUMNS,
)
from cks_picks_cfb.data.data_first_possession_v1 import ROLES
from cks_picks_cfb.data.lake import (
    PartitionedDatasetRef,
    canonical_frame_digest,
    iter_partitioned_dataset,
    partition_order_key,
    partitioned_records_sha,
)
from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame

VERIFICATION_SCHEMA = "data_first_possession_rating_replay_verification_v1"
FROZEN_CANDIDATE = "ppp__rho_0_60__exposure"
OUTPUTS = ("priors", "rating_states", "team_states")
PARTITIONS = {
    "priors": ("season",),
    "rating_states": ("season", "week"),
    "team_states": ("season", "week"),
}


class IndependentReplayError(ValueError):
    """Raised when independent reconstruction or stored evidence differs."""


@dataclass(frozen=True)
class VerifierInputs:
    population: pd.DataFrame
    observations: pd.DataFrame
    snapshots: pd.DataFrame
    historical_terminal: pd.DataFrame


@dataclass(frozen=True)
class ReconstructedReplay:
    frames: dict[str, pd.DataFrame]
    plans: dict[str, dict[str, Any]]
    diagnostics: dict[str, Any]


def _scale(terminal: pd.DataFrame, role: str) -> tuple[float, float, float]:
    rows = terminal[
        terminal["season"].eq(2025)
        & terminal["measurement_id"].eq("ppp")
        & terminal["unit_role"].eq(role)
    ]
    values = pd.to_numeric(rows["adjusted_value"], errors="coerce").dropna()
    if values.empty:
        return 0.0, 1.0, -1.0 if role == "defense" else 1.0
    spread = max(float(values.std(ddof=0)), 0.30)
    if not np.isfinite(spread) or spread <= 0:
        spread = 1.0
    return float(values.mean()), spread, -1.0 if role == "defense" else 1.0


def _games(population: pd.DataFrame) -> pd.DataFrame:
    games = population[
        pd.to_numeric(population["season"], errors="coerce").eq(2026)
        & population["forecast_eligible"].eq(True)
    ].copy()
    if games.empty or not games["timing_class"].eq("live").all():
        raise IndependentReplayError("live population is missing or mistimed")
    if not (
        games["schedule_completed"].eq(True) & games["outcome_valid"].eq(True)
    ).all():
        raise IndependentReplayError("live population contains incomplete games")
    games["week"] = pd.to_numeric(games["week"], errors="raise").astype(int)
    games["game_id"] = pd.to_numeric(games["game_id"], errors="raise").astype(int)
    games["kickoff_utc"] = pd.to_datetime(games["kickoff_utc"], utc=True)
    weeks = sorted(games["week"].unique().tolist())
    if weeks != list(range(weeks[-1] + 1)) or games.duplicated("game_id").any():
        raise IndependentReplayError("live game chronology is not continuous")
    return games.sort_values(["kickoff_utc", "game_id"], kind="mergesort")


def _boundary_map(
    games: pd.DataFrame,
) -> dict[tuple[int, str], tuple[int, pd.Timestamp]]:
    result: dict[tuple[int, str], tuple[int, pd.Timestamp]] = {}
    teams = sorted(
        set(games["home_team"].astype(str)) | set(games["away_team"].astype(str))
    )
    for team in teams:
        schedule = games[
            games["home_team"].eq(team) | games["away_team"].eq(team)
        ].sort_values(["kickoff_utc", "game_id"], kind="mergesort")
        for source in schedule.itertuples(index=False):
            later = schedule[
                schedule["week"].gt(int(source.week))
                & schedule["kickoff_utc"].ge(
                    pd.Timestamp(source.kickoff_utc) + pd.Timedelta(hours=6)
                )
            ]
            if not later.empty:
                target = later.iloc[0]
                result[(int(source.game_id), team)] = (
                    int(target.game_id),
                    pd.Timestamp(target.kickoff_utc),
                )
    return result


def _prior_rows(
    games: pd.DataFrame, terminal: pd.DataFrame
) -> tuple[pd.DataFrame, dict[tuple[str, str], tuple[float, float, str | None]]]:
    teams = sorted(
        set(games["home_team"].astype(str)) | set(games["away_team"].astype(str))
    )
    records: list[dict[str, Any]] = []
    lookup: dict[tuple[str, str], tuple[float, float, str | None]] = {}
    for role in ROLES:
        center, spread, sign = _scale(terminal, role)
        previous = terminal[
            terminal["season"].eq(2025)
            & terminal["measurement_id"].eq("ppp")
            & terminal["unit_role"].eq(role)
        ].copy()
        previous["team"] = previous["team"].astype(str)
        previous = previous.drop_duplicates("team", keep=False).set_index("team")
        for team in teams:
            source_season: int | None = None
            fallback: str | None = "no_predecessor"
            source = "neutral"
            mean, variance = 0.0, 1.0
            if team in previous.index:
                value = float(previous.loc[team, "adjusted_value"])
                exposure = float(previous.loc[team, "primary_exposure"])
                if np.isfinite(value) and np.isfinite(exposure) and exposure > 0:
                    terminal_z = sign * (value - center) / spread
                    old_variance = 1.0 / (1.0 + exposure / 8.0)
                    mean = 0.60 * terminal_z
                    variance = 0.60**2 * old_variance + 1.0 - 0.60**2
                    source, source_season, fallback = "rho_0_60", 2025, None
                else:
                    fallback = "invalid_predecessor"
            records.append(
                {
                    "candidate_id": FROZEN_CANDIDATE,
                    "season": 2026,
                    "team": team,
                    "unit_role": role,
                    "prior_mean": mean,
                    "prior_variance": variance,
                    "prior_source": source,
                    "prior_source_season": source_season,
                    "annual_decay_steps": 1 if source_season else 0,
                    "fallback_reason": fallback,
                }
            )
            lookup[(role, team)] = (mean, variance, fallback)
    frame = pd.DataFrame.from_records(records, columns=list(PRIOR_COLUMNS))
    return frame.sort_values(["unit_role", "team"], kind="mergesort").reset_index(
        drop=True
    ), lookup


def _streams(
    inputs: VerifierInputs,
    boundaries: Mapping[tuple[int, str], tuple[int, pd.Timestamp]],
    scales: Mapping[str, tuple[float, float, float]],
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    if (
        not inputs.observations["timing_class"].eq("live").all()
        or not inputs.snapshots["timing_class"].eq("live").all()
    ):
        raise IndependentReplayError("live evidence timing class changed")
    snapshots = {
        (int(row.as_of_game_id), str(row.team), str(row.unit_role)): float(
            row.adjusted_value
        )
        for row in inputs.snapshots.itertuples(index=False)
        if int(row.season) == 2026
        and str(row.measurement_id) == "ppp"
        and int(row.adjustment_iteration) == 4
        and pd.notna(row.adjusted_value)
    }
    streams: dict[tuple[str, str], list[dict[str, Any]]] = {}
    rows = inputs.observations[
        pd.to_numeric(inputs.observations["season"], errors="coerce").eq(2026)
        & inputs.observations["measurement_id"].eq("ppp")
        & inputs.observations["coverage_status"].eq("observed")
        & pd.to_numeric(inputs.observations["denominator"], errors="coerce").gt(0)
    ]
    for row in rows.itertuples(index=False):
        key = (int(row.game_id), str(row.team))
        if key not in boundaries:
            continue
        target_game, cutoff = boundaries[key]
        value = snapshots.get((target_game, str(row.team), str(row.unit_role)))
        if value is None or not np.isfinite(value):
            continue
        center, spread, sign = scales[str(row.unit_role)]
        streams.setdefault((str(row.unit_role), str(row.team)), []).append(
            {
                "game_id": int(row.game_id),
                "cutoff": cutoff,
                "z": sign * (value - center) / spread,
                "exposure": float(row.denominator),
            }
        )
    return streams


def verify_current_state(
    *,
    population: pd.DataFrame,
    observations: pd.DataFrame,
    snapshots: pd.DataFrame,
    terminal: pd.DataFrame,
    priors: pd.DataFrame,
    historical_terminal: pd.DataFrame,
    current: pd.DataFrame,
    target_week: int,
    target_teams: set[str],
) -> None:
    """Check each as-of state using verifier-owned evidence and Bayes arithmetic."""
    games = population[
        population["season"].eq(2026) & population["forecast_eligible"].eq(True)
    ].copy()
    games["kickoff_utc"] = pd.to_datetime(games["kickoff_utc"], utc=True)
    if games["week"].ge(target_week).any():
        raise IndependentReplayError("as-of verifier received future games")
    boundaries = _boundary_map(games)
    scales = {role: _scale(historical_terminal, role) for role in ROLES}
    streams = _streams(
        VerifierInputs(games, observations, snapshots, historical_terminal),
        boundaries,
        scales,
    )
    candidate = observations[
        observations["season"].eq(2026)
        & observations["measurement_id"].eq("ppp")
        & observations["coverage_status"].eq("observed")
        & pd.to_numeric(observations["denominator"], errors="coerce").gt(0)
    ]
    values = current.set_index("team")
    teams = (
        set(games["home_team"].astype(str))
        | set(games["away_team"].astype(str))
        | target_teams
    )
    if set(values.index) != teams:
        raise IndependentReplayError("as-of verifier team coverage differs")
    for team in sorted(teams):
        estimates: dict[str, tuple[float, float]] = {}
        for role in ROLES:
            prior = priors[priors["team"].eq(team) & priors["unit_role"].eq(role)]
            if len(prior) != 1:
                raise IndependentReplayError("as-of verifier lacks a unique prior")
            p = prior.iloc[0]
            exposure = 0.0
            weighted = 0.0
            for source in candidate[
                candidate["team"].eq(team) & candidate["unit_role"].eq(role)
            ].itertuples(index=False):
                game_id = int(source.game_id)
                if (game_id, team) in boundaries:
                    adjusted = next(
                        (
                            item
                            for item in streams.get((role, team), [])
                            if item["game_id"] == game_id
                        ),
                        None,
                    )
                    if adjusted is None:
                        continue
                    z = float(adjusted["z"])
                else:
                    final = terminal[
                        terminal["season"].eq(2026)
                        & terminal["team"].eq(team)
                        & terminal["unit_role"].eq(role)
                        & terminal["measurement_id"].eq("ppp")
                        & terminal["adjustment_iteration"].eq(4)
                    ]
                    if len(final) != 1:
                        raise IndependentReplayError(
                            "as-of verifier lacks terminal adjustment"
                        )
                    center, spread, sign = scales[role]
                    z = (
                        sign
                        * (float(final.iloc[0]["adjusted_value"]) - center)
                        / spread
                    )
                weight = float(source.denominator)
                exposure += weight
                weighted += weight * z
            precision = 1.0 / float(p["prior_variance"]) + exposure / 8.0
            variance = 1.0 / precision
            mean = variance * (
                float(p["prior_mean"]) / float(p["prior_variance"]) + weighted / 8.0
            )
            estimates[role] = (mean, variance)
            for field, expected in (
                (f"{role}_rating", mean),
                (f"{role}_variance", variance),
            ):
                if not np.isclose(
                    float(values.loc[team, field]), expected, rtol=0, atol=1e-9
                ):
                    raise IndependentReplayError(
                        f"as-of verifier differs for {team} {field}"
                    )
        overall = (estimates["offense"][0] + estimates["defense"][0]) / 2.0
        if not np.isclose(
            float(values.loc[team, "overall_rating"]), overall, rtol=0, atol=1e-9
        ):
            raise IndependentReplayError(
                f"as-of verifier differs for {team} overall rating"
            )
        overall_variance = (estimates["offense"][1] + estimates["defense"][1]) / 4.0
        if not np.isclose(
            float(values.loc[team, "overall_variance"]),
            overall_variance,
            rtol=0,
            atol=1e-9,
        ):
            raise IndependentReplayError(
                f"as-of verifier differs for {team} overall variance"
            )


def _plans(frames: Mapping[str, pd.DataFrame]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for name, frame in frames.items():
        dataset, schema_version = RATING_DATASETS[name]
        schema = schema_for(dataset, schema_version)
        validate_frame(frame, schema)
        keys = PARTITIONS[name]
        parts: list[dict[str, Any]] = []
        for values, part in frame.groupby(list(keys), sort=True, dropna=False):
            grouped = values if isinstance(values, tuple) else (values,)
            partition = {
                key: int(value) if key in {"season", "week"} else value
                for key, value in zip(keys, grouped, strict=True)
            }
            order = list(keys) + [key for key in schema.keys if key not in keys]
            ordered = part.sort_values(order, kind="mergesort")
            parts.append(
                {
                    "partition": partition,
                    "row_count": int(len(ordered)),
                    "records_sha": canonical_frame_digest(
                        ordered, columns=schema.required
                    ),
                }
            )
        parts.sort(key=lambda item: partition_order_key(item["partition"]))
        result[name] = {
            "parts": parts,
            "row_count": int(len(frame)),
            "records_sha": partitioned_records_sha(parts, keys),
        }
    return result


def reconstruct_replay(inputs: VerifierInputs) -> ReconstructedReplay:
    games = _games(inputs.population)
    boundaries = _boundary_map(games)
    priors, prior_lookup = _prior_rows(games, inputs.historical_terminal)
    scales = {role: _scale(inputs.historical_terminal, role) for role in ROLES}
    streams = _streams(inputs, boundaries, scales)
    states: list[dict[str, Any]] = []
    team_states: list[dict[str, Any]] = []
    for game in games.itertuples(index=False):
        cutoff = pd.Timestamp(game.kickoff_utc)
        for team in (str(game.home_team), str(game.away_team)):
            roles: dict[str, tuple[float, float, str | None]] = {}
            for role in ROLES:
                prior_mean, prior_variance, fallback = prior_lookup[(role, team)]
                history = [
                    row
                    for row in streams.get((role, team), [])
                    if row["cutoff"] <= cutoff and row["game_id"] != int(game.game_id)
                ]
                exposure = float(sum(row["exposure"] for row in history))
                weighted = float(sum(row["z"] * row["exposure"] for row in history))
                information = exposure / 8.0
                variance = 1.0 / (1.0 / prior_variance + information)
                mean = variance * (prior_mean / prior_variance + weighted / 8.0)
                weight = information / (1.0 / prior_variance + information)
                center, spread, sign = scales[role]
                states.append(
                    {
                        "candidate_id": FROZEN_CANDIDATE,
                        "definition": "ppp",
                        "season": 2026,
                        "week": int(game.week),
                        "game_id": int(game.game_id),
                        "cutoff_utc": cutoff.isoformat(),
                        "team": team,
                        "unit_role": role,
                        "native_mean": mean * spread / sign + center,
                        "rating_mean": mean,
                        "rating_variance": variance,
                        "prior_mean": prior_mean,
                        "prior_variance": prior_variance,
                        "evidence_weight": weight,
                        "process_variance": 0.0,
                        "usable_exposure": exposure,
                        "completed_games": len(history),
                        "fallback_reason": fallback,
                    }
                )
                roles[role] = (mean, variance, fallback)
            offense, defense = roles["offense"], roles["defense"]
            fallbacks = [value for value in (offense[2], defense[2]) if value]
            team_states.append(
                {
                    "candidate_id": FROZEN_CANDIDATE,
                    "definition": "ppp",
                    "season": 2026,
                    "week": int(game.week),
                    "game_id": int(game.game_id),
                    "cutoff_utc": cutoff.isoformat(),
                    "team": team,
                    "offense_rating": offense[0],
                    "offense_variance": offense[1],
                    "defense_rating": defense[0],
                    "defense_variance": defense[1],
                    "overall_rating": (offense[0] + defense[0]) / 2.0,
                    "overall_variance": (offense[1] + defense[1]) / 4.0,
                    "fallback_reason": ";".join(sorted(set(fallbacks))) or None,
                }
            )
    frames = {
        "priors": priors,
        "rating_states": pd.DataFrame.from_records(
            states, columns=list(RATING_STATE_COLUMNS)
        )
        .sort_values(["week", "game_id", "team", "unit_role"], kind="mergesort")
        .reset_index(drop=True),
        "team_states": pd.DataFrame.from_records(
            team_states, columns=list(TEAM_STATE_COLUMNS)
        )
        .sort_values(["week", "game_id", "team"], kind="mergesort")
        .reset_index(drop=True),
    }
    return ReconstructedReplay(
        frames=frames,
        plans=_plans(frames),
        diagnostics={
            "eligible_games": int(len(games)),
            "weeks": sorted(games["week"].unique().tolist()),
            "source_observations": int(sum(len(value) for value in streams.values())),
        },
    )


def _part_ref(value: Mapping[str, Any]) -> PartitionedDatasetRef:
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


def verify_replay_artifact(
    *,
    storage: Any,
    manifest: Mapping[str, Any],
    manifest_uri: str,
    inputs: VerifierInputs,
    verifier_code_sha: str,
) -> dict[str, Any]:
    reconstruction = reconstruct_replay(inputs)
    outputs = manifest.get("output_refs") or {}
    if set(outputs) != set(OUTPUTS):
        raise IndependentReplayError("replay manifest lacks complete outputs")
    for name in OUTPUTS:
        ref = _part_ref(outputs[name])
        expected_dataset, expected_schema = RATING_DATASETS[name]
        plan = reconstruction.plans[name]
        if (
            ref.dataset != expected_dataset
            or ref.schema_version != expected_schema
            or ref.records_sha != plan["records_sha"]
            or ref.row_count != plan["row_count"]
        ):
            raise IndependentReplayError(f"independent {name} digest differs")
        stored_frames = list(iter_partitioned_dataset(storage, ref))
        stored_parts = json.loads(storage.read_bytes(ref.uri)).get("parts") or []
        stored_summary = [
            {
                "partition": dict(part["partition"]),
                "row_count": int(part["row_count"]),
                "records_sha": str(part["records_sha"]),
            }
            for part in stored_parts
        ]
        if (
            stored_summary != plan["parts"]
            or sum(map(len, stored_frames)) != plan["row_count"]
        ):
            raise IndependentReplayError(f"independent {name} partitions differ")
    rows = {name: value["row_count"] for name, value in reconstruction.plans.items()}
    digests = {
        name: value["records_sha"] for name, value in reconstruction.plans.items()
    }
    if (
        manifest.get("row_counts") != rows
        or manifest.get("output_records_sha256") != digests
    ):
        raise IndependentReplayError("replay manifest summaries differ")
    verifier = signed_payload(
        {
            "schema_version": VERIFICATION_SCHEMA,
            "state": "verified",
            "manifest_uri": manifest_uri,
            "retained_manifest_raw_sha256": hashlib.sha256(
                storage.read_bytes(manifest_uri)
            ).hexdigest(),
            "selected_candidate": FROZEN_CANDIDATE,
            "output_rows": rows,
            "output_records_sha256": digests,
            "diagnostics": reconstruction.diagnostics,
            "verifier_code_sha": verifier_code_sha,
            "production_activation_authorized": False,
        }
    )
    uri = f"{manifest_uri.rsplit('/', 1)[0]}/verification/verifier-manifest.json"
    encoded = json.dumps(
        verifier, sort_keys=True, separators=(",", ":"), default=str
    ).encode()
    if storage.exists(uri):
        if storage.read_bytes(uri) != encoded:
            raise IndependentReplayError("verifier manifest collision")
    else:
        storage.write_bytes(encoded, uri)
    return {
        "status": "verified",
        "verifier_manifest_uri": uri,
        "verifier_manifest_sha256": verifier["manifest_sha256"],
        "output_rows": rows,
        "output_records_sha256": digests,
        "production_activation_authorized": False,
    }
