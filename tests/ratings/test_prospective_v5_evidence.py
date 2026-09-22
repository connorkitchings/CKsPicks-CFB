from __future__ import annotations

import copy
import hashlib
import json

import pandas as pd
import pytest

from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.ratings import prospective_v5_evidence as runner
from cks_picks_cfb.ratings import prospective_v5_evidence_verification as verifier
from cks_picks_cfb.ratings.prospective_v5_evidence import (
    EVIDENCE_MANIFEST_SCHEMA,
    EVIDENCE_OUTPUT_ROOT,
    EVIDENCE_OUTPUTS,
    _identity,
    _json_bytes,
    apply_evidence,
    build_evidence_outputs,
    preflight_evidence,
)


class MemoryStorage:
    def __init__(self, values: dict[str, bytes] | None = None) -> None:
        self.values = values or {}

    def read_bytes(self, uri: str) -> bytes:
        return self.values[uri]

    def exists(self, uri: str) -> bool:
        return uri in self.values

    def write_bytes(self, payload: bytes, uri: str) -> None:
        self.values[uri] = payload

    def list_files(self, prefix: str) -> list[str]:
        return [uri for uri in self.values if uri.startswith(prefix)]


def _inputs() -> dict[str, object]:
    attempts = pd.DataFrame(
        [
            {
                "candidate": "live-2026",
                "season": 2026,
                "week": 5,
                "run_id": "freeze-1",
                "diagnostic_only": False,
                "readiness_verified": True,
                "readiness_overall": "ready",
                "readiness_blocker": "",
                "first_kickoff": "2026-10-01T23:30:00Z",
                "freeze_completed_at": "2026-10-01T21:00:00Z",
                "declared_games": 55,
                "paired_games": 48,
                "normal_coverage": True,
                "freeze_manifest_sha256": "freeze-sha",
                "freeze_ref": "freeze-ref",
            },
            {
                "candidate": "live-2026",
                "season": 2026,
                "week": 6,
                "run_id": "diagnostic-freeze",
                "diagnostic_only": True,
                "readiness_verified": True,
                "readiness_overall": "ready",
                "readiness_blocker": "",
                "first_kickoff": "2026-10-08T23:30:00Z",
                "freeze_completed_at": "2026-10-08T21:00:00Z",
                "declared_games": 55,
                "paired_games": 48,
                "normal_coverage": True,
                "freeze_manifest_sha256": "diagnostic-sha",
                "freeze_ref": "diagnostic-ref",
            },
        ]
    )
    evaluations = pd.DataFrame(
        [
            {
                "candidate": "live-2026",
                "season": 2026,
                "week": 5,
                "run_id": "freeze-1",
                "outcome_version": "final-v1",
                "score_completed_at": "2026-10-04T12:00:00Z",
                "last_game_completed_at": "2026-10-03T12:00:00Z",
                "outcome_ref": "outcomes-v1",
                "evaluation_ref": "eval-v1",
                "evaluation_manifest_sha256": "score-sha-1",
                "evaluation_verified": True,
                "supersedes_score_manifest_uri": "",
            },
            {
                "candidate": "live-2026",
                "season": 2026,
                "week": 5,
                "run_id": "freeze-1",
                "outcome_version": "corrected-v2",
                "score_completed_at": "2026-10-04T13:00:00Z",
                "last_game_completed_at": "2026-10-03T12:00:00Z",
                "outcome_ref": "outcomes-v2",
                "evaluation_ref": "eval-v2",
                "evaluation_manifest_sha256": "score-sha-2",
                "evaluation_verified": True,
                "supersedes_score_manifest_uri": "score-v1",
            },
        ]
    )
    football = pd.DataFrame(
        [
            {
                "season": 2026,
                "week": 5,
                "game_id": game,
                "target": target,
                "actual": actual,
                "v5_mean": pred,
                "v5_variance": 4.0,
                "v4_mean": v4,
                "completed_game_stage": 1,
                "broader_population": True,
                "paired_population": paired,
            }
            for game, target, actual, pred, v4, paired in (
                (1, "margin", 4.0, 3.0, 5.0, True),
                (1, "total", 44.0, 46.0, 45.0, True),
                (2, "margin", -7.0, -5.0, float("nan"), False),
                (2, "total", 51.0, 49.0, float("nan"), False),
            )
        ]
    )
    empty_quotes = pd.DataFrame()
    return {
        "candidate": "live-2026",
        "attempts": attempts,
        "evaluations": evaluations,
        "football_by_version": {
            "2026-w5:freeze-1:final-v1": football.iloc[:4].copy(),
            "2026-w5:freeze-1:corrected-v2": football.iloc[:4].copy(),
        },
        "football_latest": football,
        "football_quote_population": football,
        "quotes": empty_quotes,
        "quote_cutoff": "2026-10-04T13:00:00Z",
        "quote_raw_sha256": "",
        "parents": [],
        "review": None,
    }


def test_reports_keep_corrections_linked_and_exclude_diagnostics() -> None:
    outputs = build_evidence_outputs(_inputs())
    ledger = outputs["attempt_ledger"]
    assert ledger["qualifying_slates"] == 1
    assert len(ledger["outcome_dispositions"]) == 3
    assert (
        ledger["outcome_dispositions"][1]["supersedes_score_manifest_uri"] == "score-v1"
    )
    assert ledger["outcome_dispositions"][1]["reason"] == "slate_already_disposed"
    diagnostic = next(
        row for row in ledger["attempts"] if row["run_id"] == "diagnostic-freeze"
    )
    assert diagnostic["diagnostic_only"] is True
    report = outputs["football_report"]["latest_per_freeze_aggregate"]
    assert report["targets"]["margin"]["count"] == 2
    assert report["targets"]["margin"]["v4_count"] == 1
    assert report["targets"]["margin"]["paired_games"] == 1
    assert report["targets"]["margin"]["broader_games"] == 2
    assert outputs["recommendation"]["category"] == "continue_shadowing"


def test_quote_presence_does_not_change_football_or_eligibility() -> None:
    without_quotes = _inputs()
    without_outputs = build_evidence_outputs(without_quotes)
    with_quotes = _inputs()
    with_quotes["quotes"] = pd.DataFrame(
        [
            {
                "game_id": 1,
                "target": "margin",
                "provider": "book-a",
                "quote_id": "q-1",
                "captured_at": "2026-10-01T18:00:00Z",
                "effective_at": "2026-10-01T18:00:00Z",
                "line": -3.5,
            }
        ]
    )
    with_outputs = build_evidence_outputs(with_quotes)
    assert with_outputs["football_report"] == without_outputs["football_report"]
    assert with_outputs["attempt_ledger"] == without_outputs["attempt_ledger"]
    assert with_outputs["quote_diagnostic"]["quote_coverage"]["missing_games"] == 3


def test_independent_verifier_rejects_report_tampering_even_with_resigned_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _inputs()
    monkeypatch.setattr(
        verifier, "collect_verified_sources", lambda *args, **kwargs: inputs
    )
    descriptor = json.dumps(
        {"schema_version": "data_first_v5_evidence_input_v1"}
    ).encode()
    descriptor_uri = f"{EVIDENCE_OUTPUT_ROOT}/evidence-test/input-descriptor.json"
    config_uri = f"{EVIDENCE_OUTPUT_ROOT}/evidence-test/config.yaml"
    outputs = build_evidence_outputs(inputs)
    config_bytes = b"synthetic-config"
    values: dict[str, bytes] = {
        descriptor_uri: descriptor,
        config_uri: config_bytes,
    }
    refs = {}
    prefix = f"{EVIDENCE_OUTPUT_ROOT}/evidence-test"
    for role, file_name in EVIDENCE_OUTPUTS.items():
        uri = f"{prefix}/{file_name}"
        raw = _json_bytes(outputs[role])
        values[uri] = raw
        refs[role] = {
            "uri": uri,
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
            "byte_count": len(raw),
        }
    identity = _identity(
        run_id="evidence-test",
        as_of="2026-10-04T14:00:00Z",
        expected_code_sha="code-sha",
        config_sha256=hashlib.sha256(config_bytes).hexdigest(),
        descriptor_sha256=hashlib.sha256(descriptor).hexdigest(),
    )
    manifest = signed_payload(
        {
            "schema_version": EVIDENCE_MANIFEST_SCHEMA,
            "state": "frozen",
            "identity": identity,
            "candidate": inputs["candidate"],
            "input_descriptor": {
                "uri": descriptor_uri,
                "raw_sha256": hashlib.sha256(descriptor).hexdigest(),
                "byte_count": len(descriptor),
            },
            "config_ref": {
                "uri": config_uri,
                "raw_sha256": hashlib.sha256(config_bytes).hexdigest(),
                "byte_count": len(config_bytes),
            },
            "parents": [],
            "output_refs": refs,
            "qualifying_slates": outputs["attempt_ledger"]["qualifying_slates"],
            "recommendation": outputs["recommendation"]["category"],
            "production_activation_authorized": False,
        }
    )
    manifest_uri = f"{prefix}/evidence-manifest.json"
    values[manifest_uri] = _json_bytes(manifest)
    storage = MemoryStorage(values)
    result = verifier.verify_evidence_artifact(
        storage, manifest_uri=manifest_uri, expected_code_sha="code-sha"
    )
    assert result["verified"] is True

    report = copy.deepcopy(outputs["football_report"])
    report["latest_per_freeze_aggregate"]["targets"]["margin"]["v5_mae"] = 999.0
    tampered = _json_bytes(report)
    values[refs["football_report"]["uri"]] = tampered
    refs["football_report"]["raw_sha256"] = hashlib.sha256(tampered).hexdigest()
    refs["football_report"]["byte_count"] = len(tampered)
    values[manifest_uri] = _json_bytes(
        signed_payload({**manifest, "output_refs": refs})
    )
    with pytest.raises(
        verifier.EvidenceVerificationError, match="independent reconstruction"
    ):
        verifier.verify_evidence_artifact(
            storage, manifest_uri=manifest_uri, expected_code_sha="code-sha"
        )


def test_synthetic_evidence_apply_is_immutable_and_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _inputs()
    monkeypatch.setattr(
        runner, "collect_verified_sources", lambda *args, **kwargs: inputs
    )
    monkeypatch.setattr(
        verifier, "collect_verified_sources", lambda *args, **kwargs: inputs
    )
    descriptor_bytes = json.dumps(
        {"schema_version": "data_first_v5_evidence_input_v1"}, sort_keys=True
    ).encode()
    descriptor = json.loads(descriptor_bytes)
    config_bytes = b"synthetic-preview-config"
    storage = MemoryStorage()
    preflight = preflight_evidence(
        storage,
        descriptor=descriptor,
        expected_code_sha="code-sha",
        run_id="evidence-apply-test",
        as_of="2026-10-04T14:00:00Z",
        config_bytes=config_bytes,
        descriptor_bytes=descriptor_bytes,
    )
    applied = apply_evidence(
        storage,
        descriptor=descriptor,
        expected_code_sha="code-sha",
        run_id="evidence-apply-test",
        as_of="2026-10-04T14:00:00Z",
        config_bytes=config_bytes,
        descriptor_bytes=descriptor_bytes,
        expected_preflight=preflight,
    )
    assert applied["state"] == "applied"
    initial = dict(storage.values)
    repeated = apply_evidence(
        storage,
        descriptor=descriptor,
        expected_code_sha="code-sha",
        run_id="evidence-apply-test",
        as_of="2026-10-04T14:00:00Z",
        config_bytes=config_bytes,
        descriptor_bytes=descriptor_bytes,
        expected_preflight=preflight,
    )
    assert repeated["state"] == "already_applied"
    assert repeated["verified"] is True
    assert storage.values == initial
