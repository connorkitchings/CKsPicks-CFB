from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from cks_picks_cfb.data.data_first_phase2 import DEVELOPMENT_SEASONS, CaptureRequest
from cks_picks_cfb.data.data_first_phase2c import OUTPUT_DATASETS
from cks_picks_cfb.data.data_first_phase2d import (
    PHASE3_DATASETS,
    REQUIRED_STAGES,
    Phase2dError,
    automation_admission,
    canonical_bytes,
    eligibility_manifest,
    eligibility_role,
    signed_payload,
    strict_coverage_gate,
    validate_certification_inputs,
    verify_signed_payload,
)
from scripts.research.recertify_data_first_phase2d import _capture_timing, _load_config
from scripts.research.verify_phase2d_automation_admission import (
    _verify_capture_manifest,
)


def _coverage_rows() -> list[dict]:
    return [
        {
            "season": season,
            "season_type": season_type,
            "population": population,
            "stage": stage,
            "state": "observed",
            "denominator_count": 100,
            "admitted_count": 100,
            "coverage_rate": 1.0,
        }
        for season in DEVELOPMENT_SEASONS
        for season_type in ("regular", "postseason")
        for population in ("fbs_fbs", "fbs_fcs")
        for stage in REQUIRED_STAGES
    ]


def _inputs() -> list[dict]:
    rows = []
    for season in DEVELOPMENT_SEASONS:
        for dataset in OUTPUT_DATASETS:
            value = f"{season}-{dataset}"
            role, permitted_uses = eligibility_role(dataset)
            rows.append(
                {
                    "season": season,
                    "dataset": dataset,
                    "version_id": value,
                    "schema_version": f"{dataset}_v1",
                    "content_sha": (value.encode().hex() + "0" * 64)[:64],
                    "uri": f"lake/{season}/{dataset}/{value}/data.parquet",
                    "role": role,
                    "permitted_uses": permitted_uses,
                    "eligible": dataset in PHASE3_DATASETS,
                }
            )
    return rows


def _omissions() -> dict:
    plays = [
        {
            "season": DEVELOPMENT_SEASONS[index % len(DEVELOPMENT_SEASONS)],
            "game_id": index + 1,
            "season_type": "regular",
            "reason": "provider_response_omission",
        }
        for index in range(32)
    ]
    return {
        "plays": plays,
        "team_game_stats": [
            {
                "season": 2025,
                "game_id": 100,
                "season_type": "regular",
                "reason": "provider_response_omission",
            }
        ],
        "postseason_omissions": 0,
    }


def _capture(index: int) -> dict:
    return {
        "request_sha": f"request-{index}",
        "capture_id": f"capture-{index}",
        "row_count": 1,
        "captured_at": "2026-09-06T12:00:00+00:00",
        "state": "captured",
    }


class _MemoryStorage:
    def __init__(self, values: dict[str, bytes]):
        self.values = values

    def read_bytes(self, uri: str) -> bytes:
        return self.values[uri]


def test_signed_payload_covers_final_content_once():
    value = signed_payload({"state": "eligible", "run_id": "one"})
    verify_signed_payload(value)
    repaired = signed_payload({**value, "run_id": "two"})
    verify_signed_payload(repaired)
    assert repaired["manifest_sha256"] != value["manifest_sha256"]

    with pytest.raises(Phase2dError, match="checksum mismatch"):
        verify_signed_payload({**repaired, "run_id": "three"})


def test_phase2d_config_is_the_versioned_policy_authority():
    config, digest = _load_config(
        "conf/research/data_first_football_v1/phase2d_audit_v2.yaml"
    )
    assert config["schema_version"] == "data_first_phase2d_audit_v2"
    assert len(digest) == 64


def test_legacy_capture_timing_requires_explicit_historical_profile():
    capture = SimpleNamespace(
        capture_id="capture",
        captured_at=datetime(2026, 8, 31, tzinfo=timezone.utc),
        effective_at=None,
        request={"parameters": {"year": 2015}},
        response_metadata={
            "capture_only": True,
            "capture_profile": "history_source_capture_v2",
        },
    )
    assert _capture_timing(capture) == (
        "historically_reconstructed",
        "history_source_capture_v2",
    )

    capture.response_metadata = {"capture_only": True}
    with pytest.raises(Phase2dError, match="timing is undeclared"):
        _capture_timing(capture)


def test_capture_manifest_requires_exact_request_result_identity():
    requests = []
    results = []
    for index in range(7):
        request = {
            "provider": "cfbd",
            "entity": f"entity-{index}",
            "endpoint": f"Endpoint.method_{index}",
            "parameters": {"year": 2026},
        }
        request_sha = CaptureRequest(**request).request_sha
        requests.append({**request, "request_sha": request_sha})
        results.append({**_capture(index), "request_sha": request_sha})
    manifest = {
        "schema_version": "data_first_phase2_capture_run_v2",
        "environment": "preview",
        "state": "complete",
        "code_sha": "abc",
        "request_count": 7,
        "failed_or_empty_count": 0,
        "requests": requests,
        "results": results,
    }
    storage = _MemoryStorage({"manifest.json": canonical_bytes(manifest)})
    assert _verify_capture_manifest(storage, "manifest.json") == manifest

    bad = {**manifest, "results": [*results[:-1], dict(results[0])]}
    storage = _MemoryStorage({"manifest.json": canonical_bytes(bad)})
    with pytest.raises(Phase2dError, match="request plan"):
        _verify_capture_manifest(storage, "manifest.json")


def test_certification_inputs_require_exact_unique_membership():
    rows = _inputs()
    validate_certification_inputs(rows)

    with pytest.raises(Phase2dError, match="duplicate certification input"):
        validate_certification_inputs(rows + [dict(rows[0])])
    with pytest.raises(Phase2dError, match="contract mismatch"):
        validate_certification_inputs(rows[:-1])


def test_coverage_requires_complete_contract_and_special_100_percent_gates():
    rows = _coverage_rows()
    assert strict_coverage_gate(rows)["passed"]

    postseason = [dict(row) for row in rows]
    postseason[0]["season_type"] = "postseason"
    postseason[0]["coverage_rate"] = 0.99
    postseason[0]["admitted_count"] = 99
    with pytest.raises(Phase2dError, match="duplicate coverage row"):
        strict_coverage_gate(postseason)

    postseason = [dict(row) for row in rows]
    target = next(
        row
        for row in postseason
        if row["season_type"] == "postseason" and row["stage"] == "plays"
    )
    target["coverage_rate"] = 0.99
    target["admitted_count"] = 99
    assert not strict_coverage_gate(postseason)["passed"]

    outcomes = [dict(row) for row in rows]
    target = next(
        row
        for row in outcomes
        if row["season_type"] == "regular" and row["stage"] == "game_outcomes"
    )
    target["coverage_rate"] = 0.99
    target["admitted_count"] = 99
    assert not strict_coverage_gate(outcomes)["passed"]

    with pytest.raises(Phase2dError, match="coverage contract mismatch"):
        strict_coverage_gate(rows[:-1])


def test_eligibility_rejects_identity_ref_and_omission_drift():
    identity = {"identity_sha256": "identity", "code_sha": "code"}
    inputs = _inputs()
    manifest = eligibility_manifest(
        identity=identity,
        audit={
            "state": "complete",
            "identity": identity,
            "certification_blocking_issue_count": 0,
            "uri": "audit.json",
            "sha256": "audit-raw",
        },
        automation_admission={
            "state": "admitted",
            "verifier_code_sha": "code",
            "uri": "automation.json",
            "sha256": "automation-raw",
        },
        inputs=inputs,
        coverage={"passed": True},
        omissions=_omissions(),
    )
    assert manifest["schema_version"] == "data_first_phase2_eligibility_v3"
    assert len(manifest["phase3_input_refs"]) == 70
    verify_signed_payload(manifest)

    with pytest.raises(Phase2dError, match="identity does not match"):
        eligibility_manifest(
            identity=identity,
            audit={
                "state": "complete",
                "identity": {"identity_sha256": "other"},
                "certification_blocking_issue_count": 0,
                "uri": "audit.json",
                "sha256": "audit-raw",
            },
            automation_admission={
                "state": "admitted",
                "verifier_code_sha": "code",
                "uri": "automation.json",
                "sha256": "automation-raw",
            },
            inputs=inputs,
            coverage={"passed": True},
            omissions=_omissions(),
        )

    bad = _omissions()
    bad["plays"][0]["reason"] = "unknown"
    with pytest.raises(Phase2dError, match="omission reason"):
        eligibility_manifest(
            identity=identity,
            audit={
                "state": "complete",
                "identity": identity,
                "certification_blocking_issue_count": 0,
                "uri": "audit.json",
                "sha256": "audit-raw",
            },
            automation_admission={
                "state": "admitted",
                "verifier_code_sha": "code",
                "uri": "automation.json",
                "sha256": "automation-raw",
            },
            inputs=inputs,
            coverage={"passed": True},
            omissions=bad,
        )


def test_automation_admission_requires_unique_nonempty_timed_remote_evidence():
    remote = {
        "status": "completed",
        "conclusion": "success",
        "event": "workflow_dispatch",
        "workflowName": "Data-first pregame capture",
        "headSha": "abc",
        "url": "https://github.com/o/r/actions/runs/1",
    }
    kwargs = {
        "run_id": "run",
        "code_sha": "abc",
        "capture_manifest_uri": "capture.json",
        "capture_manifest_sha256": "raw-sha",
        "github_run_url": remote["url"],
        "quota": {"monthly_limit": 30_000, "remaining_before": 100},
        "captures": [_capture(index) for index in range(7)],
        "future_kickoff_count": 1,
        "github_run": remote,
        "verifier_code_sha": "verify",
    }
    manifest = automation_admission(**kwargs)
    verify_signed_payload(manifest)

    duplicate = [_capture(index) for index in range(7)]
    duplicate[-1]["capture_id"] = duplicate[0]["capture_id"]
    with pytest.raises(Phase2dError, match="unique nonempty"):
        automation_admission(**{**kwargs, "captures": duplicate})
    with pytest.raises(Phase2dError, match="sufficient recorded quota"):
        automation_admission(**{**kwargs, "quota": {}})
    with pytest.raises(Phase2dError, match="GitHub workflow evidence"):
        automation_admission(
            **{**kwargs, "github_run": {**remote, "headSha": "different"}}
        )
