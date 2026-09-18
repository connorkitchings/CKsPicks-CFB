"""Focused V5-05C independent shadow verification tests."""

from __future__ import annotations

import ast
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from cks_picks_cfb.data.data_first_shadow_v1 import (
    DIAGNOSTIC_CLASS,
    SHADOW_DATASETS,
    SHADOW_MANIFEST_SCHEMA,
    shadow_identity,
    shadow_manifest,
)
from cks_picks_cfb.data.lake import (
    BuildRequest,
    PartitionedDatasetPart,
    PartitionedDatasetWriter,
    build_dataset_version,
)
from cks_picks_cfb.data.schema_contracts import schema_for
from cks_picks_cfb.forecast.shadow import (
    build_readiness_report,
    check_source_availability,
    plan_freeze,
    score_freeze,
)
from cks_picks_cfb.forecast.shadow_verification import (
    REHEARSAL_MANIFEST_SCHEMA,
    ShadowVerificationError,
    _compare_readiness,
    _reconstruct_readiness,
    _reconstruct_replay,
    verify_shadow_artifact,
    write_verifier_manifest,
)

VERIFIER_PATH = (
    Path(__file__).resolve().parents[1]
    / "src/cks_picks_cfb/forecast/shadow_verification.py"
)
CODE_SHA = "a" * 40
CONFIG_SHA = "b" * 64
CANDIDATE = "forecast-v1-test-candidate"
RUN_ID = "shadow-v1-test-05c"
FREEZE_MANIFEST_URI = "runs/test/freeze-manifest.json"
READINESS_MANIFEST_URI = "runs/test/shadow-manifest.json"
V4_REF_URI = "fixtures/v4.parquet"
AS_OF = datetime(2025, 11, 17, tzinfo=timezone.utc)


class _MemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def write_bytes(self, payload: bytes, uri: str) -> None:
        self.objects[uri] = payload

    def read_bytes(self, uri: str) -> bytes:
        if uri not in self.objects:
            raise FileNotFoundError(uri)
        return self.objects[uri]

    def exists(self, uri: str) -> bool:
        return uri in self.objects

    def list_files(self, prefix: str) -> list[str]:
        return sorted(uri for uri in self.objects if uri.startswith(prefix))


def _write_json(storage: _MemoryStorage, uri: str, payload: Any) -> None:
    storage.write_bytes(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), default=str
        ).encode(),
        uri,
    )


def _schedule(n: int = 45) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "season": 2025,
                "week": 10,
                "game_id": 1000 + i,
                "kickoff_utc": "2025-11-15T16:00:00+00:00",
            }
            for i in range(n)
        ]
    )


def _v4(n: int = 45, mean: float = 4.0) -> pd.DataFrame:
    rows = []
    for i in range(n):
        for target in ("margin", "total"):
            rows.append({"game_id": 1000 + i, "target": target, "mean": mean})
    return pd.DataFrame(rows)


def _diagnostic_v5(
    n: int = 45,
    *,
    interval: float = 19.6,
    candidate: str = CANDIDATE,
) -> pd.DataFrame:
    rows = []
    for i in range(n):
        for target in ("margin", "total"):
            rows.append(
                {
                    "game_id": 1000 + i,
                    "target": target,
                    "mean": 0.0,
                    "variance": 100.0,
                    "interval_lower_95": -interval,
                    "interval_upper_95": interval,
                    "offset": 0.0,
                    "model_ref": candidate,
                    "state_ref": candidate,
                }
            )
    return pd.DataFrame(rows)


def _outcomes(n: int = 45) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "game_id": 1000 + i,
                "actual_margin": 7.0,
                "actual_total": 51.0,
                "last_completion_time": "2025-11-15T20:00:00+00:00",
            }
            for i in range(n)
        ]
    )


def _identity_parents() -> dict[str, str]:
    return {f"parent_{i}": f"value-{i}" for i in range(8)}


def _shadow_identity(run_id: str = RUN_ID, as_of: str = "2025-11-15T14:00:00+00:00"):
    return shadow_identity(
        run_id=run_id,
        as_of=as_of,
        code_sha=CODE_SHA,
        config_sha=CONFIG_SHA,
        parents={
            "forecast_manifest_uri": "parents/forecast.json",
            "forecast_raw_sha256": "1" * 64,
            "rating_manifest_uri": "parents/rating.json",
            "rating_raw_sha256": "2" * 64,
            "measurement_manifest_uri": "parents/measurement.json",
            "measurement_raw_sha256": "3" * 64,
            "repair_manifest_uri": "parents/repair.json",
            "repair_raw_sha256": "4" * 64,
        },
    )


def _build_compact(
    storage: _MemoryStorage, dataset_key: str, frame: pd.DataFrame
) -> dict[str, Any]:
    dataset, schema_version = SHADOW_DATASETS[dataset_key]
    schema = schema_for(dataset, schema_version)
    ref, _ = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset=dataset,
            parent_refs=(),
            code_sha=CODE_SHA,
            config_sha=CONFIG_SHA,
            as_of=AS_OF,
            schema_version=schema_version,
            tier="gold",
        ),
        records=frame.loc[:, list(schema.required)].to_dict("records"),
    )
    return {
        "artifact_kind": "dataset_v1",
        "dataset": ref.dataset,
        "version_id": ref.version_id,
        "schema_version": ref.schema_version,
        "content_sha": ref.content_sha,
        "uri": ref.uri,
        "row_count": len(frame),
    }


def _build_partitioned(
    storage: _MemoryStorage,
    dataset_key: str,
    frame: pd.DataFrame,
    partition: dict[str, Any],
    partition_keys: tuple[str, ...],
) -> dict[str, Any]:
    dataset, schema_version = SHADOW_DATASETS[dataset_key]
    writer = PartitionedDatasetWriter(
        storage,
        build=BuildRequest(
            dataset=dataset,
            parent_refs=(),
            code_sha=CODE_SHA,
            config_sha=CONFIG_SHA,
            as_of=AS_OF,
            schema_version=schema_version,
            tier="gold",
        ),
        partition_keys=partition_keys,
    )
    writer.add(PartitionedDatasetPart(partition=partition, frame=frame.copy()))
    ref = writer.finish()
    return {
        "artifact_kind": ref.artifact_kind,
        "dataset": ref.dataset,
        "version_id": ref.version_id,
        "schema_version": ref.schema_version,
        "content_sha": ref.content_sha,
        "uri": ref.uri,
        "row_count": ref.row_count,
    }


def _build_freeze_chain(
    storage: _MemoryStorage,
    *,
    interval: float = 19.6,
    freeze_record_override: dict[str, Any] | None = None,
    scored_at: str = "2025-11-17T00:00:00+00:00",
    evaluation_override: pd.DataFrame | None = None,
    counter_override: pd.DataFrame | None = None,
) -> dict[str, Any]:
    plan = plan_freeze(
        candidate=CANDIDATE,
        season=2025,
        week=10,
        run_id=RUN_ID,
        freeze_time="2025-11-15T14:00:00+00:00",
        schedule=_schedule(),
        v5_predictions=_diagnostic_v5(interval=interval),
        v4_predictions=_v4(),
        v4_ref_uri=V4_REF_URI,
    )
    freeze_record = plan.freeze_record.copy()
    if freeze_record_override:
        for key, value in freeze_record_override.items():
            freeze_record[key] = value
    freeze_ref = _build_compact(storage, "shadow_freeze", freeze_record)
    pred_ref = _build_partitioned(
        storage,
        "shadow_prediction",
        plan.predictions,
        {"season": 2025, "week": 10},
        ("season", "week"),
    )
    _write_json(
        storage,
        READINESS_MANIFEST_URI,
        {"schema_version": SHADOW_MANIFEST_SCHEMA, "state": "frozen"},
    )
    freeze_manifest = {
        "schema_version": "data_first_shadow_freeze_manifest_v1",
        "state": "frozen",
        "identity": _shadow_identity(),
        "parents": {
            "readiness_manifest_uri": READINESS_MANIFEST_URI,
            "v4_prediction_ref_uri": V4_REF_URI,
        },
        "output_refs": {"shadow_freeze": freeze_ref, "shadow_prediction": pred_ref},
        "freeze_summary": {
            "season": 2025,
            "week": 10,
            "freeze_time": plan.freeze_time,
            "lead_seconds": plan.lead_seconds,
            "slate_digest": plan.slate_digest,
            "paired_count": plan.paired_count,
            "broader_count": plan.broader_count,
            "excluded_count": plan.excluded_count,
        },
        "production_activation_authorized": False,
    }
    _write_json(storage, FREEZE_MANIFEST_URI, freeze_manifest)

    score = score_freeze(
        candidate=CANDIDATE,
        season=2025,
        week=10,
        run_id=RUN_ID,
        freeze_record=plan.freeze_record,
        predictions=plan.predictions,
        outcomes=_outcomes(),
        outcome_version="v1",
        scored_at=scored_at,
        freeze_ref=FREEZE_MANIFEST_URI,
    )
    evaluation = (
        evaluation_override.copy()
        if evaluation_override is not None
        else score.evaluation
    )
    eval_ref = _build_partitioned(
        storage,
        "shadow_evaluation",
        evaluation,
        {"season": 2025, "week": 10, "outcome_version": "v1"},
        ("season", "week", "outcome_version"),
    )
    counter = (
        counter_override.copy()
        if counter_override is not None
        else score.counter_record
    )
    counter_ref = _build_compact(storage, "evidence_counter", counter)
    score_manifest_uri = "runs/test/score-manifest.json"
    score_manifest = {
        "schema_version": "data_first_shadow_score_manifest_v1",
        "state": "frozen",
        "identity": _shadow_identity(as_of=scored_at),
        "parents": {
            "freeze_manifest_uri": FREEZE_MANIFEST_URI,
            "outcome_ref_uri": "fixtures/outcomes.parquet",
        },
        "output_refs": {
            "shadow_evaluation": eval_ref,
            "shadow_evidence_counter": counter_ref,
        },
        "score_summary": {
            "season": 2025,
            "week": 10,
            "outcome_version": "v1",
            "qualifying": score.qualifying,
            "reason": score.reason,
            "paired_count": score.paired_count,
            "mae_margin": score.mae_margin,
            "mae_total": score.mae_total,
            "qualifying_slates_total": 1,
        },
        "production_activation_authorized": False,
    }
    _write_json(storage, score_manifest_uri, score_manifest)
    return {
        "freeze_manifest": freeze_manifest,
        "score_manifest": score_manifest,
        "score_manifest_uri": score_manifest_uri,
        "plan": plan,
        "score": score,
    }


# ---------------------------------------------------------------------------
# Import boundary (AST-enforced producer isolation)
# ---------------------------------------------------------------------------

FORBIDDEN_MODULES = {
    "cks_picks_cfb.forecast.shadow",
    "cks_picks_cfb.forecast.offsets",
    "cks_picks_cfb.forecast.heads",
    "cks_picks_cfb.forecast.horizons",
    "cks_picks_cfb.forecast.calibration",
    "cks_picks_cfb.ratings.possession_rating_materializer",
}


def test_verifier_import_boundary_ast():
    tree = ast.parse(VERIFIER_PATH.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert node.module not in FORBIDDEN_MODULES, node.module
            assert not node.module.startswith("scripts."), node.module
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in FORBIDDEN_MODULES, alias.name
                assert not alias.name.startswith("scripts."), alias.name


def test_verifier_boundary_catches_producer_perturbation():
    """A producer computing different intervals must not verify."""
    storage = _MemoryStorage()
    _build_freeze_chain(storage, interval=25.0)
    with pytest.raises(ShadowVerificationError, match="stored predictions disagree"):
        verify_shadow_artifact(
            storage,
            manifest_uri=FREEZE_MANIFEST_URI,
            expected_code_sha=CODE_SHA,
            environment="preview",
            sources={"schedule": _schedule(), "v4_predictions": _v4()},
        )


# ---------------------------------------------------------------------------
# Freeze verification
# ---------------------------------------------------------------------------


def test_freeze_chain_verifies():
    storage = _MemoryStorage()
    _build_freeze_chain(storage)
    result = verify_shadow_artifact(
        storage,
        manifest_uri=FREEZE_MANIFEST_URI,
        expected_code_sha=CODE_SHA,
        environment="preview",
        sources={"schedule": _schedule(), "v4_predictions": _v4()},
    )
    assert result["verified"] is True
    assert result["kind"] == "freeze"
    assert result["paired_count"] == 45


def test_freeze_rejects_tampered_record_bytes():
    storage = _MemoryStorage()
    chain = _build_freeze_chain(storage)
    ref = chain["freeze_manifest"]["output_refs"]["shadow_freeze"]
    storage.write_bytes(b"tampered-bytes", ref["uri"])
    with pytest.raises(ShadowVerificationError, match="storage rejected source"):
        verify_shadow_artifact(
            storage,
            manifest_uri=FREEZE_MANIFEST_URI,
            expected_code_sha=CODE_SHA,
            environment="preview",
            sources={"schedule": _schedule(), "v4_predictions": _v4()},
        )


def test_freeze_rejects_perturbed_producer_counts():
    storage = _MemoryStorage()
    _build_freeze_chain(storage, freeze_record_override={"paired_count": 44})
    with pytest.raises(ShadowVerificationError, match="paired count disagrees"):
        verify_shadow_artifact(
            storage,
            manifest_uri=FREEZE_MANIFEST_URI,
            expected_code_sha=CODE_SHA,
            environment="preview",
            sources={"schedule": _schedule(), "v4_predictions": _v4()},
        )


def test_freeze_rejects_wrong_v4_parent():
    storage = _MemoryStorage()
    chain = _build_freeze_chain(storage)
    manifest = dict(chain["freeze_manifest"])
    manifest["parents"] = dict(manifest["parents"])
    manifest["parents"]["v4_prediction_ref_uri"] = "fixtures/other.parquet"
    _write_json(storage, FREEZE_MANIFEST_URI, manifest)
    with pytest.raises(ShadowVerificationError, match="v4 parent disagrees"):
        verify_shadow_artifact(
            storage,
            manifest_uri=FREEZE_MANIFEST_URI,
            expected_code_sha=CODE_SHA,
            environment="preview",
            sources={"schedule": _schedule(), "v4_predictions": _v4()},
        )


def test_freeze_rejects_identity_mismatch():
    storage = _MemoryStorage()
    chain = _build_freeze_chain(storage)
    manifest = dict(chain["freeze_manifest"])
    identity = dict(manifest["identity"])
    identity["code_sha"] = "c" * 40
    manifest["identity"] = identity
    _write_json(storage, FREEZE_MANIFEST_URI, manifest)
    with pytest.raises(ShadowVerificationError, match="code SHA"):
        verify_shadow_artifact(
            storage,
            manifest_uri=FREEZE_MANIFEST_URI,
            expected_code_sha=CODE_SHA,
            environment="preview",
            sources={"schedule": _schedule(), "v4_predictions": _v4()},
        )


def test_freeze_rejects_unknown_schema():
    storage = _MemoryStorage()
    chain = _build_freeze_chain(storage)
    manifest = dict(chain["freeze_manifest"])
    manifest["schema_version"] = "data_first_shadow_unknown_v9"
    _write_json(storage, FREEZE_MANIFEST_URI, manifest)
    with pytest.raises(ShadowVerificationError, match="unknown shadow manifest schema"):
        verify_shadow_artifact(
            storage,
            manifest_uri=FREEZE_MANIFEST_URI,
            expected_code_sha=CODE_SHA,
            environment="preview",
            sources={"schedule": _schedule(), "v4_predictions": _v4()},
        )


def test_freeze_rejects_non_frozen_state():
    storage = _MemoryStorage()
    chain = _build_freeze_chain(storage)
    manifest = dict(chain["freeze_manifest"])
    manifest["state"] = "draft"
    _write_json(storage, FREEZE_MANIFEST_URI, manifest)
    with pytest.raises(ShadowVerificationError, match="not frozen"):
        verify_shadow_artifact(
            storage,
            manifest_uri=FREEZE_MANIFEST_URI,
            expected_code_sha=CODE_SHA,
            environment="preview",
            sources={"schedule": _schedule(), "v4_predictions": _v4()},
        )


# ---------------------------------------------------------------------------
# Score and counter verification
# ---------------------------------------------------------------------------


def test_score_chain_verifies():
    storage = _MemoryStorage()
    chain = _build_freeze_chain(storage)
    result = verify_shadow_artifact(
        storage,
        manifest_uri=chain["score_manifest_uri"],
        expected_code_sha=CODE_SHA,
        environment="preview",
        sources={
            "schedule": _schedule(),
            "v4_predictions": _v4(),
            "outcomes": _outcomes(),
        },
    )
    assert result["verified"] is True
    assert result["kind"] == "score"
    assert result["qualifying_count"] == 1
    assert result["mae_margin"] == pytest.approx(7.0)


def test_score_rejects_stabilization_violation():
    storage = _MemoryStorage()
    chain = _build_freeze_chain(storage)
    manifest = dict(chain["score_manifest"])
    manifest["identity"] = _shadow_identity(as_of="2025-11-15T21:00:00+00:00")
    _write_json(storage, chain["score_manifest_uri"], manifest)
    with pytest.raises(ShadowVerificationError, match="stabilization gate"):
        verify_shadow_artifact(
            storage,
            manifest_uri=chain["score_manifest_uri"],
            expected_code_sha=CODE_SHA,
            environment="preview",
            sources={
                "schedule": _schedule(),
                "v4_predictions": _v4(),
                "outcomes": _outcomes(),
            },
        )


def test_score_rejects_perturbed_evaluation():
    storage = _MemoryStorage()
    chain = _build_freeze_chain(storage)
    evaluation = chain["score"].evaluation.copy()
    evaluation.loc[0, "error"] = evaluation.loc[0, "error"] + 3.0
    # rebuild the chain with the perturbed evaluation stored self-consistently
    _build_freeze_chain(storage, evaluation_override=evaluation)
    with pytest.raises(ShadowVerificationError, match="error"):
        verify_shadow_artifact(
            storage,
            manifest_uri=chain["score_manifest_uri"],
            expected_code_sha=CODE_SHA,
            environment="preview",
            sources={
                "schedule": _schedule(),
                "v4_predictions": _v4(),
                "outcomes": _outcomes(),
            },
        )


def test_counter_rejects_wrong_qualifying_total():
    storage = _MemoryStorage()
    chain = _build_freeze_chain(storage)
    prior_week = pd.DataFrame(
        [
            {
                "candidate": CANDIDATE,
                "season": 2025,
                "week": 9,
                "qualifying": True,
                "reason": "normal_coverage",
                "freeze_ref": "runs/prior/freeze-manifest.json",
                "evaluation_ref": "",
            }
        ]
    )
    counter = pd.concat([prior_week, chain["score"].counter_record], ignore_index=True)
    _build_freeze_chain(storage, counter_override=counter)
    with pytest.raises(ShadowVerificationError, match="qualifying slate total"):
        verify_shadow_artifact(
            storage,
            manifest_uri=chain["score_manifest_uri"],
            expected_code_sha=CODE_SHA,
            environment="preview",
            sources={
                "schedule": _schedule(),
                "v4_predictions": _v4(),
                "outcomes": _outcomes(),
            },
        )


def test_counter_rejects_qualifying_diagnostic_rows():
    storage = _MemoryStorage()
    chain = _build_freeze_chain(storage)
    counter = chain["score"].counter_record.copy()
    counter["reason"] = DIAGNOSTIC_CLASS
    _build_freeze_chain(storage, counter_override=counter)
    with pytest.raises(ShadowVerificationError, match="diagnostic class"):
        verify_shadow_artifact(
            storage,
            manifest_uri=chain["score_manifest_uri"],
            expected_code_sha=CODE_SHA,
            environment="preview",
            sources={
                "schedule": _schedule(),
                "v4_predictions": _v4(),
                "outcomes": _outcomes(),
            },
        )


# ---------------------------------------------------------------------------
# Readiness reconstruction
# ---------------------------------------------------------------------------


def _readiness_sources(*, season_states: bool = True):
    schedule = _schedule()
    schedule["kickoff_utc"] = "2026-09-26T16:00:00+00:00"
    schedule["season"] = 2026
    schedule["week"] = 4
    outcomes = pd.DataFrame(
        [
            {
                "season": 2025,
                "week": 12,
                "game_id": 900,
                "home_points": 21,
                "away_points": 20,
            }
        ]
    )
    scoring = pd.DataFrame([{"season": 2025, "game_id": 900}])
    team_states = pd.DataFrame(
        [{"season": 2026 if season_states else 2015, "team": "t"}]
    )
    priors = pd.DataFrame([{"season": 2026, "team": "t"}])
    return {
        "schedule": schedule,
        "outcomes": outcomes,
        "scoring_events": scoring,
        "team_states": team_states,
        "priors": priors,
    }


def _readiness_chain():
    forecast = {"identity": {"as_of": "2026-09-20T00:00:00Z"}}
    measurement = {"identity": {"as_of": "2026-09-20T00:00:00Z"}}
    rating = {"identity": {"as_of": "2026-09-20T00:00:00Z"}}
    return {"forecast": forecast, "measurement": measurement, "rating": rating}


def _producer_readiness_frame(season_states: bool = True):
    sources = _readiness_sources(season_states=season_states)
    statuses = check_source_availability(
        candidate=CANDIDATE,
        season=2026,
        week=4,
        cutoff="2026-09-20T12:00:00Z",
        forecast={"identity": {"as_of": "2026-09-20T00:00:00Z"}},
        rating_states=sources["team_states"],
        schedule=sources["schedule"],
        outcomes=sources["outcomes"],
        scoring_events=sources["scoring_events"],
        priors=sources["priors"],
        measurement_as_of="2026-09-20T00:00:00Z",
        rating_as_of="2026-09-20T00:00:00Z",
    )
    return build_readiness_report(
        candidate=CANDIDATE, season=2026, week=4, run_id=RUN_ID, statuses=statuses
    )


def test_readiness_reconstruction_matches_producer_when_ready():
    frame, overall = _producer_readiness_frame(season_states=True)
    rebuilt = _reconstruct_readiness(
        cutoff="2026-09-20T12:00:00Z",
        chain=_readiness_chain(),
        stored=frame,
        sources=_readiness_sources(season_states=True),
    )
    assert rebuilt["overall"] == "ready" == overall
    _compare_readiness(frame, rebuilt["frame"], manifest_overall=overall)


def test_readiness_reconstruction_matches_producer_when_blocked():
    frame, overall = _producer_readiness_frame(season_states=False)
    rebuilt = _reconstruct_readiness(
        cutoff="2026-09-20T12:00:00Z",
        chain=_readiness_chain(),
        stored=frame,
        sources=_readiness_sources(season_states=False),
    )
    assert rebuilt["overall"] == "blocked" == overall
    _compare_readiness(frame, rebuilt["frame"], manifest_overall=overall)


def test_readiness_rejects_perturbed_stored_rows():
    frame, overall = _producer_readiness_frame(season_states=True)
    perturbed = frame.copy()
    mask = perturbed["source"].eq("team_states")
    perturbed.loc[mask, "blocked_reason"] = "no team states for 2026"
    with pytest.raises(ShadowVerificationError, match="readiness column"):
        _compare_readiness(
            perturbed,
            _reconstruct_readiness(
                cutoff="2026-09-20T12:00:00Z",
                chain=_readiness_chain(),
                stored=frame,
                sources=_readiness_sources(season_states=True),
            )["frame"],
            manifest_overall=overall,
        )


def test_readiness_manifest_rejects_bad_signature():
    storage = _MemoryStorage()
    manifest = shadow_manifest(
        identity=_shadow_identity(),
        parents={},
        output_refs={"readiness": "ref"},
        readiness_overall="blocked",
    )
    manifest["manifest_sha256"] = "0" * 64
    _write_json(storage, READINESS_MANIFEST_URI, manifest)
    with pytest.raises(ShadowVerificationError, match="checksum mismatch"):
        verify_shadow_artifact(
            storage,
            manifest_uri=READINESS_MANIFEST_URI,
            expected_code_sha=CODE_SHA,
            environment="preview",
        )


# ---------------------------------------------------------------------------
# Replay evidence
# ---------------------------------------------------------------------------


def test_replay_evidence_accepts_valid_digest():
    result = _reconstruct_replay(
        {
            "replay_sha256": "d" * 64,
            "byte_identical": True,
            "perturbation_invariance": True,
        }
    )
    assert result["byte_identical"] is True


def test_replay_evidence_rejects_malformed_digest():
    with pytest.raises(ShadowVerificationError, match="replay digest is malformed"):
        _reconstruct_replay({"replay_sha256": "xyz", "byte_identical": True})


def test_replay_evidence_rejects_failed_perturbation():
    with pytest.raises(ShadowVerificationError, match="perturbation invariance"):
        _reconstruct_replay(
            {"replay_sha256": "d" * 64, "perturbation_invariance": False}
        )


# ---------------------------------------------------------------------------
# Rehearsal verification
# ---------------------------------------------------------------------------


def _rehearsal_chain(
    storage: _MemoryStorage,
    *,
    diagnostic_only: bool = True,
    cases_failed: int = 0,
    replay_block: dict[str, Any] | None = None,
) -> str:
    cases = {
        "timing_violation": {"expected": "rejected", "disposition": "rejected"},
        "population_below_gate": {"expected": "rejected", "disposition": "rejected"},
        "missing_outcome": {"expected": "rejected", "disposition": "rejected"},
        "correction_version": {
            "expected": "counted_once",
            "disposition": "counted_once",
        },
        "immutable_collision": {"expected": "rejected", "disposition": "rejected"},
        "candidate_change_reset": {"expected": "reset", "disposition": "reset"},
        "mainline_positive": {"expected": "passed", "disposition": "passed"},
    }
    uri = "runs/test-rehearsal/rehearsal-manifest.json"
    rehearsal_frame = pd.DataFrame.from_records(
        [
            {
                "candidate": CANDIDATE,
                "run_id": RUN_ID,
                "season_range": "2022-2025",
                "diagnostic_only": diagnostic_only,
                "cases_passed": len(cases) - cases_failed,
                "cases_failed": cases_failed,
                "verifier_ref": "runs/test-rehearsal/verification/verifier-manifest.json",
            }
        ]
    )
    ref = _build_compact(storage, "shadow_rehearsal", rehearsal_frame)
    _write_json(
        storage,
        uri,
        {
            "schema_version": REHEARSAL_MANIFEST_SCHEMA,
            "state": "frozen",
            "identity": _shadow_identity(),
            "replay": replay_block
            or {
                "replay_sha256": "d" * 64,
                "byte_identical": True,
                "perturbation_invariance": True,
            },
            "verification": {
                "verifier_manifest_uri": "runs/test-rehearsal/verification/verifier-manifest.json"
            },
            "rehearsal_cases": cases,
            "output_refs": {"shadow_rehearsal": ref},
            "production_activation_authorized": False,
        },
    )
    return uri


def test_rehearsal_verifies():
    storage = _MemoryStorage()
    uri = _rehearsal_chain(storage)
    result = verify_shadow_artifact(
        storage,
        manifest_uri=uri,
        expected_code_sha=CODE_SHA,
        environment="preview",
    )
    assert result["kind"] == "rehearsal"
    assert result["cases_passed"] == 7
    assert result["cases_failed"] == 0


def test_rehearsal_rejects_non_diagnostic_class():
    storage = _MemoryStorage()
    uri = _rehearsal_chain(storage, diagnostic_only=False)
    with pytest.raises(ShadowVerificationError, match="diagnostic-only"):
        verify_shadow_artifact(
            storage, manifest_uri=uri, expected_code_sha=CODE_SHA, environment="preview"
        )


def test_rehearsal_rejects_case_count_mismatch():
    storage = _MemoryStorage()
    uri = _rehearsal_chain(storage, cases_failed=2)
    with pytest.raises(ShadowVerificationError, match="failure count"):
        verify_shadow_artifact(
            storage, manifest_uri=uri, expected_code_sha=CODE_SHA, environment="preview"
        )


def test_rehearsal_rejects_missing_replay_digest():
    storage = _MemoryStorage()
    uri = _rehearsal_chain(
        storage,
        replay_block={"replay_sha256": None, "byte_identical": None},
    )
    with pytest.raises(ShadowVerificationError, match="replay digest"):
        verify_shadow_artifact(
            storage, manifest_uri=uri, expected_code_sha=CODE_SHA, environment="preview"
        )


# ---------------------------------------------------------------------------
# Verifier manifest
# ---------------------------------------------------------------------------


def test_verifier_manifest_idempotent_and_collision_safe():
    storage = _MemoryStorage()
    payload = {"verified": True, "manifest_uri": FREEZE_MANIFEST_URI}
    uri = write_verifier_manifest(storage, run_prefix="runs/test", payload=payload)
    assert storage.exists(uri)
    again = write_verifier_manifest(storage, run_prefix="runs/test", payload=payload)
    assert again == uri
    with pytest.raises(ShadowVerificationError, match="collision"):
        write_verifier_manifest(
            storage, run_prefix="runs/test", payload={"verified": False}
        )
