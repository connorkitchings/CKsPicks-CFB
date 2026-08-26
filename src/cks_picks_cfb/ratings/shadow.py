"""Immutable, Preview-only Phase 4 shadow-operation contracts."""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd
import yaml

from cks_picks_cfb.artifacts import sha256_bytes
from cks_picks_cfb.ratings.contracts import MeasurementContractError
from cks_picks_cfb.ratings.score_models import SCORE_MODEL_DATASET, load_score_model
from cks_picks_cfb.ratings.state_contracts import (
    TeamStateConfig,
    load_team_state_config,
)
from cks_picks_cfb.ratings.states import build_team_states

SHADOW_CONFIG_VERSION = "rating_shadow_operations_v1"
SHADOW_FREEZE_DATASET = "rating_shadow_predictions"
SHADOW_FREEZE_SCHEMA_VERSION = "rating_shadow_freeze_manifest_v1"
SHADOW_PREDICTION_SCHEMA_VERSION = "rating_shadow_predictions_v1"
SHADOW_EVIDENCE_DATASET = "rating_shadow_evidence"
SHADOW_EVIDENCE_SCHEMA_VERSION = "rating_shadow_evidence_v1"
SHADOW_SCORE_REPORT_SCHEMA_VERSION = "rating_shadow_score_report_v1"
ORACLE_TOLERANCE = 1.0e-9
REHEARSAL_CUTOFF_LEAD = timedelta(hours=1)


def _sha(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def ref_identity(ref: Any) -> dict[str, str]:
    return {
        "dataset": str(ref.dataset),
        "version_id": str(ref.version_id),
        "schema_version": str(ref.schema_version),
        "content_sha": str(ref.content_sha),
        "uri": str(ref.uri),
    }


@dataclass(frozen=True)
class ShadowConfig:
    config_version: str
    research_prefix: str
    candidate: Mapping[str, str]
    rehearsal: Mapping[str, str]
    pace: Mapping[str, Any]
    gates: Mapping[str, Any]
    raw_config: Mapping[str, Any]

    @property
    def design_id(self) -> str:
        return _sha(self.raw_config)

    @property
    def rehearsal_prefix(self) -> str:
        return f"{self.research_prefix}/{self.design_id}/rehearsal"

    @property
    def operations_prefix(self) -> str:
        return f"{self.research_prefix}/{self.design_id}/ops"

    def canonical_week_prefix(self, *, season: int, week: int) -> str:
        return f"{self.operations_prefix}/season={season}/week={week:02d}"


def load_shadow_config(path: str | Path) -> ShadowConfig:
    raw = yaml.safe_load(Path(path).read_text())
    if (
        not isinstance(raw, Mapping)
        or raw.get("shadow_config_version") != SHADOW_CONFIG_VERSION
    ):
        raise MeasurementContractError("Unsupported shadow operations config")
    try:
        config = ShadowConfig(
            config_version=str(raw["shadow_config_version"]),
            research_prefix=str(raw["research_prefix"]).rstrip("/"),
            candidate={str(k): str(v) for k, v in raw["candidate"].items()},
            rehearsal={str(k): str(v) for k, v in raw["rehearsal"].items()},
            pace=dict(raw["pace"]),
            gates=dict(raw["gates"]),
            raw_config=raw,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise MeasurementContractError("Incomplete shadow operations config") from exc
    required_candidate = {
        "candidate_manifest_uri",
        "expected_candidate_sha",
        "expected_code_sha",
        "prediction_design_id",
        "model_ref_uri",
        "expected_model_version",
        "expected_model_sha",
        "predictions_ref_uri",
        "expected_predictions_version",
        "expected_predictions_sha",
        "model_stage",
        "family",
    }
    required_rehearsal = {
        "model_stage",
        "fold_prefix",
        "team_states_ref_uri",
        "expected_team_states_version",
        "expected_team_states_sha",
        "snapshots_ref_uri",
        "expected_snapshots_version",
        "expected_snapshots_sha",
        "terminal_ref_uri",
        "expected_terminal_version",
        "expected_terminal_sha",
        "games_ref_uri",
        "outcomes_ref_uri",
        "v4_ref_uri",
        "season",
        "measurement_config_path",
        "state_config_path",
    }
    if not required_candidate <= set(config.candidate):
        raise MeasurementContractError("Shadow candidate pins are incomplete")
    if not required_rehearsal <= set(config.rehearsal):
        raise MeasurementContractError("Shadow rehearsal pins are incomplete")
    if int(config.rehearsal["season"]) != 2025:
        raise MeasurementContractError("Rehearsal season must remain 2025")
    return config


def prediction_config_for_shadow(
    shadow: ShadowConfig, *, historical_seasons: tuple[int, ...]
) -> Any:
    from cks_picks_cfb.ratings.predictions import PredictionConfig

    return PredictionConfig(
        research_prefix=shadow.research_prefix,
        historical_seasons=historical_seasons,
        evaluation_seasons=(),
        state_inputs={},
        v4_benchmark={},
        pace=dict(shadow.pace),
        gates=dict(shadow.gates),
        raw_config={
            "pace": dict(shadow.pace),
            "historical_seasons": list(historical_seasons),
        },
    )


def _ref(storage, uri: str):
    from cks_picks_cfb.data.lake import DatasetRef

    return DatasetRef(**json.loads(storage.read_bytes(uri).decode()))


def _verify_ref(
    ref: Any, *, version: str, content_sha: str, dataset: str | None = None
) -> None:
    if ref.version_id != version or ref.content_sha != content_sha:
        raise MeasurementContractError(
            "Immutable dataset ref does not match frozen pins"
        )
    if dataset is not None and ref.dataset != dataset:
        raise MeasurementContractError(f"Expected {dataset}, got {ref.dataset}")


def load_frozen_model(storage, shadow: ShadowConfig, *, stage: str):
    """Verify candidate lineage, then reconstruct one exact frozen model stage."""
    from cks_picks_cfb.data.lake import read_dataset, require_dataset

    candidate_bytes = storage.read_bytes(shadow.candidate["candidate_manifest_uri"])
    if sha256_bytes(candidate_bytes) != shadow.candidate["expected_candidate_sha"]:
        raise MeasurementContractError(
            "Candidate manifest does not match frozen checksum"
        )
    candidate = json.loads(candidate_bytes.decode())
    if (
        candidate.get("prediction_design_id")
        != shadow.candidate["prediction_design_id"]
    ):
        raise MeasurementContractError("Candidate design identity does not match pins")
    if candidate.get("code_sha") != shadow.candidate["expected_code_sha"]:
        raise MeasurementContractError("Candidate code identity does not match pins")
    ref = _ref(storage, shadow.candidate["model_ref_uri"])
    _verify_ref(
        ref,
        version=shadow.candidate["expected_model_version"],
        content_sha=shadow.candidate["expected_model_sha"],
        dataset=SCORE_MODEL_DATASET,
    )
    require_dataset(ref, SCORE_MODEL_DATASET)
    rows = read_dataset(storage, ref).query("model_stage == @stage")
    if len(rows) != 1:
        raise MeasurementContractError(
            f"Expected exactly one {stage} model record, found {len(rows)}"
        )
    model = load_score_model(rows.iloc[0].to_dict())
    if model.family != shadow.candidate["family"]:
        raise MeasurementContractError("Frozen model family does not match candidate")
    expected_training = (
        (2021, 2022, 2023, 2024)
        if stage == "locked_confirmation"
        else (2021, 2022, 2023, 2024, 2025)
    )
    if model.training_seasons != expected_training:
        raise MeasurementContractError(
            "Frozen model training chronology does not match stage"
        )
    return model, ref


def load_certified_state_inputs(storage, shadow: ShadowConfig):
    from cks_picks_cfb.data.lake import read_dataset

    values = shadow.rehearsal
    states_ref = _ref(storage, values["team_states_ref_uri"])
    snapshots_ref = _ref(storage, values["snapshots_ref_uri"])
    terminal_ref = _ref(storage, values["terminal_ref_uri"])
    _verify_ref(
        states_ref,
        version=values["expected_team_states_version"],
        content_sha=values["expected_team_states_sha"],
        dataset="rating_team_states",
    )
    _verify_ref(
        snapshots_ref,
        version=values["expected_snapshots_version"],
        content_sha=values["expected_snapshots_sha"],
        dataset="rating_adjusted_measurement_snapshots",
    )
    _verify_ref(
        terminal_ref,
        version=values["expected_terminal_version"],
        content_sha=values["expected_terminal_sha"],
        dataset="rating_adjusted_measurement_terminal_snapshots",
    )
    return (
        states_ref,
        snapshots_ref,
        terminal_ref,
        read_dataset(storage, states_ref),
        read_dataset(storage, snapshots_ref),
        read_dataset(storage, terminal_ref),
    )


def week_cutoff(slate: pd.DataFrame) -> tuple[datetime, datetime, datetime]:
    kickoff = pd.to_datetime(slate["kickoff_utc"], utc=True, errors="coerce")
    if kickoff.isna().any():
        raise MeasurementContractError("Slate contains unparseable kickoff times")
    earliest, latest = kickoff.min().to_pydatetime(), kickoff.max().to_pydatetime()
    return earliest - REHEARSAL_CUTOFF_LEAD, earliest, latest


def validate_freeze_timing(*, as_of: datetime, slate: pd.DataFrame) -> None:
    kickoff = pd.to_datetime(slate["kickoff_utc"], utc=True, errors="coerce")
    if kickoff.isna().any() or pd.Timestamp(as_of) >= kickoff.min():
        raise MeasurementContractError(
            "Freeze as-of must be strictly before earliest kickoff"
        )


def validate_freeze_predictions(
    predictions: pd.DataFrame, *, slate: pd.DataFrame, prospective: bool = True
) -> None:
    if predictions.empty:
        raise MeasurementContractError("Freeze produced no predictions")
    expected = {
        (int(game_id), target)
        for game_id in slate["game_id"]
        for target in ("margin", "total")
    }
    actual = {
        (int(game_id), str(target))
        for game_id, target in predictions[["game_id", "target"]].itertuples(
            index=False
        )
    }
    if actual != expected:
        raise MeasurementContractError(
            "Freeze predictions do not exactly cover the eligible slate"
        )
    columns = [
        "prediction_mean",
        "prediction_sd",
        "score_covariance",
        "home_score_sd",
        "away_score_sd",
    ]
    columns += [
        f"interval_{level}_{side}"
        for level in ("50", "80", "95")
        for side in ("lower", "upper")
    ]
    for column in columns:
        if not np.isfinite(
            pd.to_numeric(predictions[column], errors="coerce").to_numpy(float)
        ).all():
            raise MeasurementContractError(f"Freeze {column} must be finite")
    if (pd.to_numeric(predictions["prediction_sd"]) <= 0).any():
        raise MeasurementContractError("Freeze prediction_sd must be positive")
    for level in ("50", "80", "95"):
        if not (
            predictions[f"interval_{level}_lower"]
            < predictions[f"interval_{level}_upper"]
        ).all():
            raise MeasurementContractError("Freeze intervals must be ordered")
    if prospective and predictions["actual"].notna().any():
        raise MeasurementContractError(
            "Prospective freeze must not carry completed outcomes"
        )


def normal_coverage(scheduled: int, gates: Mapping[str, Any], *, week: int) -> bool:
    return week not in set(gates.get("ineligible_weeks", ())) and scheduled >= int(
        gates["normal_coverage_min_games"]
    )


def canonical_manifest_uri(
    shadow: ShadowConfig, *, season: int, week: int, kind: str
) -> str:
    name = "freeze-manifest.json" if kind == "freeze" else "score-report.json"
    return f"{shadow.canonical_week_prefix(season=season, week=week)}/{name}"


def existing_or_collision(
    storage, uri: str, expected: Mapping[str, Any]
) -> Mapping[str, Any] | None:
    if not storage.exists(uri):
        return None
    found = json.loads(storage.read_bytes(uri).decode())
    for key in ("shadow_design_id", "season", "week", "as_of", "input_identity"):
        if found.get(key) != expected.get(key):
            raise FileExistsError(
                f"Canonical immutable shadow artifact collision: {uri}"
            )
    return found


def immutable_write(storage, uri: str, payload: bytes) -> None:
    if storage.exists(uri):
        if storage.read_bytes(uri) != payload:
            raise FileExistsError(f"Immutable artifact collision: {uri}")
        return
    storage.write_bytes(payload, uri)


def normalize_v4_prediction_run(
    *, manifest: Mapping[str, Any], csv_bytes: bytes, season: int, week: int
) -> pd.DataFrame:
    required = {
        "schema_version",
        "season",
        "week",
        "artifact_sha256",
        "model_bundle_sha256",
        "data_as_of",
    }
    if (
        not required <= set(manifest)
        or manifest["schema_version"] != "prediction_run_v1"
    ):
        raise MeasurementContractError("Unsupported production prediction-run manifest")
    if int(manifest["season"]) != season or int(manifest["week"]) != week:
        raise MeasurementContractError("Production V4 run belongs to another slate")
    if sha256_bytes(csv_bytes) != str(manifest["artifact_sha256"]):
        raise MeasurementContractError("Production V4 CSV checksum mismatch")
    frame = pd.read_csv(io.BytesIO(csv_bytes))
    game_key = (
        "game_id" if "game_id" in frame else "Game ID" if "Game ID" in frame else None
    )
    if game_key is None or not {"Spread Prediction", "Total Prediction"} <= set(frame):
        raise MeasurementContractError(
            "Production V4 CSV lacks required game/target columns"
        )
    game_ids = pd.to_numeric(frame[game_key], errors="coerce")
    if game_ids.isna().any() or game_ids.duplicated().any():
        raise MeasurementContractError("Production V4 CSV game keys are invalid")
    base = pd.DataFrame({"season": season, "game_id": game_ids.astype(int)})
    rows = pd.concat(
        [
            base.assign(
                target="margin",
                v4_prediction=pd.to_numeric(
                    frame["Spread Prediction"], errors="coerce"
                ),
            ),
            base.assign(
                target="total",
                v4_prediction=pd.to_numeric(frame["Total Prediction"], errors="coerce"),
            ),
        ],
        ignore_index=True,
    )
    if rows.v4_prediction.isna().any() or not np.isfinite(rows.v4_prediction).all():
        raise MeasurementContractError("Production V4 predictions must be finite")
    rows["source_kind"] = "production_v4_frozen_run"
    return rows


def score_freeze(
    *,
    freeze_predictions: pd.DataFrame,
    outcomes: pd.DataFrame,
    v4: pd.DataFrame,
    lineage: Mapping[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    required = {"season", "game_id", "completed", "home_points", "away_points"}
    if missing := sorted(required - set(outcomes.columns)):
        raise MeasurementContractError(f"Outcomes missing columns: {missing}")
    completed_flag = outcomes["completed"]
    if completed_flag.dtype != bool:
        completed_flag = (
            completed_flag.astype(str).str.lower().isin(("true", "1", "1.0"))
        )
    completed = outcomes[completed_flag].drop_duplicates(["season", "game_id"])
    base = freeze_predictions[["season", "game_id", "target"]].merge(
        completed[["season", "game_id", "home_points", "away_points"]],
        on=["season", "game_id"],
        how="left",
        validate="many_to_one",
    )
    base["actual"] = np.where(
        base.target.eq("margin"),
        base.home_points - base.away_points,
        base.home_points + base.away_points,
    )
    missing_outcomes = base[base.actual.isna()][["season", "game_id"]].drop_duplicates()
    paired = base.dropna(subset=["actual"]).merge(
        v4[["season", "game_id", "target", "v4_prediction", "source_kind"]],
        on=["season", "game_id", "target"],
        how="left",
        validate="one_to_one",
    )
    unpaired = paired[paired.v4_prediction.isna()][["season", "game_id", "target"]]
    if not missing_outcomes.empty or not unpaired.empty:
        return pd.DataFrame(), {
            "report_schema_version": SHADOW_SCORE_REPORT_SCHEMA_VERSION,
            "complete": False,
            "missing_outcome_games": missing_outcomes.to_dict("records"),
            "unpaired_v4_rows": unpaired.to_dict("records"),
        }
    rows = freeze_predictions.drop(columns=["actual"]).merge(
        paired[
            ["season", "game_id", "target", "actual", "v4_prediction", "source_kind"]
        ],
        on=["season", "game_id", "target"],
        validate="one_to_one",
    )
    for key, value in lineage.items():
        rows[key] = value
    rows["candidate_absolute_error"] = (rows.prediction_mean - rows.actual).abs()
    rows["v4_absolute_error"] = (rows.v4_prediction - rows.actual).abs()
    targets = {}
    for target in ("margin", "total"):
        subset = rows[rows.target.eq(target)]
        targets[target] = {
            "rows": int(len(subset)),
            "candidate_mae": float(subset.candidate_absolute_error.mean()),
            "v4_mae": float(subset.v4_absolute_error.mean()),
            "candidate_bias": float((subset.prediction_mean - subset.actual).mean()),
        }
    return rows, {
        "report_schema_version": SHADOW_SCORE_REPORT_SCHEMA_VERSION,
        "complete": True,
        "scored_rows": int(len(rows)),
        "missing_outcome_games": [],
        "unpaired_v4_rows": [],
        "targets": targets,
    }


def compare_oracle(
    produced: pd.DataFrame, frozen: pd.DataFrame, *, fold_prefix: str
) -> dict[str, Any]:
    subset = frozen[frozen["fold_id"].str.startswith(fold_prefix)].copy()
    if subset.empty:
        raise MeasurementContractError(
            f"No frozen oracle rows for fold prefix {fold_prefix}"
        )
    merged = produced.merge(
        subset,
        on=["season", "game_id", "target"],
        how="outer",
        validate="one_to_one",
        suffixes=("_produced", "_frozen"),
        indicator=True,
    )
    if (merged["_merge"] != "both").any():
        raise MeasurementContractError("Oracle coverage mismatch")
    maximum = 0.0
    for column in (
        "prediction_mean",
        "prediction_sd",
        "interval_50_lower",
        "interval_50_upper",
        "interval_80_lower",
        "interval_80_upper",
        "interval_95_lower",
        "interval_95_upper",
    ):
        delta = np.abs(
            pd.to_numeric(merged[f"{column}_produced"])
            - pd.to_numeric(merged[f"{column}_frozen"])
        )
        if delta.isna().any():
            raise MeasurementContractError(f"Oracle column {column} has null values")
        maximum = max(maximum, float(delta.max()))
    return {
        "rows_compared": int(len(merged)),
        "max_absolute_delta": maximum,
        "tolerance": ORACLE_TOLERANCE,
        "all_checks_passed": maximum <= ORACLE_TOLERANCE,
    }


def assemble_season_states(
    *,
    pregame_snapshots: pd.DataFrame,
    terminal_snapshots: pd.DataFrame,
    state_config_path: str | Path,
    code_sha: str,
    config_sha: str,
    parent_measurement_refs: str,
):
    config: TeamStateConfig = load_team_state_config(state_config_path)
    return build_team_states(
        pregame_snapshots=pregame_snapshots,
        terminal_snapshots=terminal_snapshots,
        config=config,
        code_sha=code_sha,
        config_sha=config_sha,
        parent_measurement_refs=parent_measurement_refs,
    )
