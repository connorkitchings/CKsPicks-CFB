"""Focused V5-05C diagnostic rehearsal tests."""

from __future__ import annotations

import argparse
import json

import pandas as pd
import pytest

from cks_picks_cfb.data.data_first_shadow_v1 import (
    DIAGNOSTIC_CLASS,
    SHADOW_REHEARSAL_COLUMNS,
    shadow_identity,
)
from cks_picks_cfb.data.lake import canonical_frame_digest
from cks_picks_cfb.forecast.shadow import plan_freeze, score_freeze
from scripts.research.run_v5_shadow_rehearsal import (
    DEFAULT_CONFIG,
    DEFAULT_FREEZE_TIME,
    DEFAULT_SCORED_AT,
    NEGATIVE_CASES,
    REHEARSAL_MANIFEST_NAME,
    RehearsalRunError,
    _build_rehearsal_record,
    _load_rehearsal_preflight,
    _run_negative_cases,
    _synthetic_v5_predictions,
    apply,
)

CANDIDATE = "forecast-v1-20260917-4600ddd-04b"
RUN_ID = "shadow-v1-test-05c-rehearsal"
CODE_SHA = "a" * 40
CONFIG_SHA = "b" * 64


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


def _config() -> dict:
    return {
        "minimum_paired_games": 40,
        "freeze_hard_lead_seconds": 3600.0,
        "score_stabilization_seconds": 86400.0,
    }


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


def _v4(n: int = 45) -> pd.DataFrame:
    rows = []
    for i in range(n):
        for target in ("margin", "total"):
            rows.append({"game_id": 1000 + i, "target": target, "mean": 4.0})
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


def _chain():
    schedule = _schedule()
    v4 = _v4()
    v5 = _synthetic_v5_predictions(schedule, 2025, 10, CANDIDATE)
    plan = plan_freeze(
        candidate=CANDIDATE,
        season=2025,
        week=10,
        run_id=RUN_ID,
        freeze_time=DEFAULT_FREEZE_TIME,
        schedule=schedule,
        v5_predictions=v5,
        v4_predictions=v4,
        v4_ref_uri="fixtures/v4.parquet",
    )
    score = score_freeze(
        candidate=CANDIDATE,
        season=2025,
        week=10,
        run_id=RUN_ID,
        freeze_record=plan.freeze_record,
        predictions=plan.predictions,
        outcomes=_outcomes(),
        outcome_version="v1",
        scored_at=DEFAULT_SCORED_AT,
    )
    return schedule, v4, plan, score


def test_all_negative_cases_dispose_correctly():
    schedule, v4, plan, score = _chain()
    cases = _run_negative_cases(
        config=_config(),
        schedule=schedule,
        v4=v4,
        outcomes=_outcomes(),
        freeze_plan=plan,
        score_result=score,
        selected_cases=NEGATIVE_CASES,
    )
    assert set(cases) == set(NEGATIVE_CASES)
    for name, case in cases.items():
        assert case["disposition"] == case["expected"], (name, case)


def test_missing_outcome_negative_detects_silent_producer_gap():
    schedule, v4, plan, score = _chain()
    cases = _run_negative_cases(
        config=_config(),
        schedule=schedule,
        v4=v4,
        outcomes=_outcomes(),
        freeze_plan=plan,
        score_result=score,
        selected_cases=("missing_outcome",),
    )
    case = cases["missing_outcome"]
    assert case["disposition"] == "rejected"
    assert "silently scored" in case["detail"]


def test_correction_counts_slate_once():
    schedule, v4, plan, score = _chain()
    cases = _run_negative_cases(
        config=_config(),
        schedule=schedule,
        v4=v4,
        outcomes=_outcomes(),
        freeze_plan=plan,
        score_result=score,
        selected_cases=("correction_version",),
    )
    assert cases["correction_version"]["disposition"] == "counted_once"


def test_candidate_change_resets_ledger():
    schedule, v4, plan, score = _chain()
    cases = _run_negative_cases(
        config=_config(),
        schedule=schedule,
        v4=v4,
        outcomes=_outcomes(),
        freeze_plan=plan,
        score_result=score,
        selected_cases=("candidate_change_reset",),
    )
    assert cases["candidate_change_reset"]["disposition"] == "reset"


def test_timing_negative_flags_accepted_freeze():
    """If the producer gate were removed, the rehearsal must flag it."""
    schedule, v4, plan, score = _chain()
    config = _config() | {"freeze_hard_lead_seconds": 0.0}
    cases = _run_negative_cases(
        config=config,
        schedule=schedule,
        v4=v4,
        outcomes=_outcomes(),
        freeze_plan=plan,
        score_result=score,
        selected_cases=("timing_violation",),
    )
    assert cases["timing_violation"]["disposition"] == "unexpected"


def test_rehearsal_record_is_permanently_diagnostic():
    cases = {
        "mainline_positive": {
            "expected": "passed",
            "disposition": "passed",
            "detail": "ok",
        },
        "timing_violation": {
            "expected": "rejected",
            "disposition": "rejected",
            "detail": "ok",
        },
    }
    record = _build_rehearsal_record(
        candidate=CANDIDATE,
        run_id=RUN_ID,
        season_range="2024-2025",
        cases=cases,
        verifier_uri=f"runs/{RUN_ID}/verification/verifier-manifest.json",
    )
    assert bool(record["diagnostic_only"].iloc[0]) is True
    assert record["cases_passed"].iloc[0] == 2
    assert record["cases_failed"].iloc[0] == 0
    assert (
        record["verifier_ref"].iloc[0].endswith("verification/verifier-manifest.json")
    )


def test_rehearsal_record_counts_failures():
    cases = {
        "mainline_positive": {
            "expected": "passed",
            "disposition": "passed",
            "detail": "ok",
        },
        "timing_violation": {
            "expected": "rejected",
            "disposition": "unexpected",
            "detail": "gate removed",
        },
    }
    record = _build_rehearsal_record(
        candidate=CANDIDATE,
        run_id=RUN_ID,
        season_range="2024-2025",
        cases=cases,
        verifier_uri="runs/x/verification/verifier-manifest.json",
    )
    assert record["cases_failed"].iloc[0] == 1
    assert record["cases_passed"].iloc[0] == 1


def _identity():
    return shadow_identity(
        run_id=RUN_ID,
        as_of="2026-09-18T00:00:00Z",
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


def _cases_all_passing():
    cases = {
        "mainline_positive": {
            "expected": "passed",
            "disposition": "passed",
            "detail": "ok",
        }
    }
    for name in NEGATIVE_CASES:
        expected = (
            "counted_once"
            if name == "correction_version"
            else ("reset" if name == "candidate_change_reset" else "rejected")
        )
        cases[name] = {"expected": expected, "disposition": expected, "detail": "ok"}
    return cases


def _args() -> argparse.Namespace:
    return argparse.Namespace(
        run_id=RUN_ID,
        season_range="2024-2025",
        config=str(DEFAULT_CONFIG),
        as_of="2026-09-18T00:00:00Z",
        readiness_manifest_uri="runs/readiness/shadow-manifest.json",
        freeze_manifest_uri="runs/freeze/freeze-manifest.json",
        v4_prediction_ref_uri="fixtures/v4.parquet",
        slate_ref_uri="fixtures/schedule.parquet",
        outcome_ref_uri="fixtures/outcomes.parquet",
    )


def test_apply_writes_manifest_last_and_is_idempotent(tmp_path):
    storage = _MemoryStorage()
    identity = _identity()
    cases = _cases_all_passing()
    record = _build_rehearsal_record(
        candidate=identity["candidate"],
        run_id=RUN_ID,
        season_range="2024-2025",
        cases=cases,
        verifier_uri=(
            "artifacts/research/data-first-football-v1/possession-v1/shadow/runs/"
            f"{RUN_ID}/verification/verifier-manifest.json"
        ),
    )
    evidence = {
        "state": "dry_run",
        "identity": dict(identity),
        "readiness_overall": "blocked",
        "replay_sha256": "d" * 64,
        "cases": cases,
        "rehearsal_plan": {
            "name": "shadow_rehearsal",
            "partition_keys": [],
            "row_count": len(record),
            "records_sha": canonical_frame_digest(
                record, columns=list(SHADOW_REHEARSAL_COLUMNS)
            ),
        },
    }
    result = apply(storage=storage, args=_args(), identity=identity, evidence=evidence)
    assert result["state"] == "applied"
    prefix = (
        f"artifacts/research/data-first-football-v1/possession-v1/shadow/runs/{RUN_ID}"
    )
    assert storage.exists(f"{prefix}/publication-plan.json")
    assert storage.exists(f"{prefix}/{REHEARSAL_MANIFEST_NAME}")
    manifest = json.loads(storage.read_bytes(f"{prefix}/{REHEARSAL_MANIFEST_NAME}"))
    assert manifest["diagnostic_class"] == DIAGNOSTIC_CLASS
    assert manifest["replay"]["byte_identical"] is True
    assert manifest["verification"]["verifier_manifest_uri"].endswith(
        "verification/verifier-manifest.json"
    )
    assert set(manifest["rehearsal_cases"]) == {"mainline_positive", *NEGATIVE_CASES}

    again = apply(storage=storage, args=_args(), identity=identity, evidence=evidence)
    assert again["state"] == "already_applied"


def test_apply_rejects_partial_prefix():
    storage = _MemoryStorage()
    prefix = (
        f"artifacts/research/data-first-football-v1/possession-v1/shadow/runs/{RUN_ID}"
    )
    storage.write_bytes(b"partial", f"{prefix}/publication-plan.json")
    with pytest.raises(RehearsalRunError, match="permanently ineligible"):
        apply(
            storage=storage,
            args=_args(),
            identity=_identity(),
            evidence={
                "identity": dict(_identity()),
                "readiness_overall": "blocked",
                "replay_sha256": "d" * 64,
                "cases": _cases_all_passing(),
                "rehearsal_plan": {
                    "name": "shadow_rehearsal",
                    "partition_keys": [],
                    "row_count": 1,
                    "records_sha": "e" * 64,
                },
            },
        )


def test_preflight_evidence_rejects_unexpected_dispositions(tmp_path):
    identity = _identity()
    cases = _cases_all_passing() | {
        "timing_violation": {
            "expected": "rejected",
            "disposition": "unexpected",
            "detail": "gate removed",
        }
    }
    payload = {
        "state": "dry_run",
        "identity": dict(identity),
        "readiness_overall": "blocked",
        "replay_sha256": "d" * 64,
        "cases": cases,
        "rehearsal_plan": {
            "name": "shadow_rehearsal",
            "partition_keys": [],
            "row_count": 1,
            "records_sha": "e" * 64,
        },
    }
    path = tmp_path / "preflight.json"
    path.write_bytes(json.dumps(payload).encode())
    with pytest.raises(RehearsalRunError, match="unexpected negative dispositions"):
        _load_rehearsal_preflight(path, identity=identity)


def test_preflight_evidence_rejects_identity_mismatch(tmp_path):
    identity = _identity()
    payload = {
        "state": "dry_run",
        "identity": {"run_id": "other"},
        "cases": {},
        "rehearsal_plan": {"name": "shadow_rehearsal", "records_sha": "e" * 64},
    }
    path = tmp_path / "preflight.json"
    path.write_bytes(json.dumps(payload).encode())
    with pytest.raises(RehearsalRunError, match="identity does not match"):
        _load_rehearsal_preflight(path, identity=identity)
