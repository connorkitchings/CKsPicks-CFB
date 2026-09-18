"""Focused tests for the V5-10a historical-audit harness.

Covers config validation, lineage register, no-write checks, verifier
independence, audit evidence verification, runner gates, and determinism.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
import yaml

from cks_picks_cfb.audit import (
    ELIGIBLE_SEASONS,
    FORBIDDEN_SEASONS,
    PARENT_STAGES,
    PROVISIONAL_SEVERITY,
    SEEDED_FINDINGS,
)
from cks_picks_cfb.audit import checks as audit_checks
from cks_picks_cfb.audit import independence as audit_independence
from cks_picks_cfb.audit import register as audit_register
from cks_picks_cfb.audit import verification as audit_verification
from cks_picks_cfb.data.data_first_phase2d import sha256, signed_payload

ROOT = Path(__file__).resolve().parents[1]
AUDIT_CONFIG = ROOT / "conf/research/data_first_football_v1/historical_audit_v1.yaml"

STAGE_RUN_IDS = {
    "repair": "repair-v2-20260909T1417Z",
    "measurements": "possession-v1-measurements-20260915-18fb0aa-r6",
    "ratings": "possession-v1-ratings-20260917-d029526-cert",
    "forecasts": "forecast-v1-20260917-4600ddd-04b",
}


def _stage_spec(stage: str) -> Mapping[str, Any]:
    for entry in PARENT_STAGES:
        if entry["stage"] == stage:
            return entry
    raise AssertionError(stage)


def _fixture_manifest(
    stage: str,
    *,
    run_id: str | None = None,
    parents: dict[str, Any] | None = None,
    state: Any = "present",
) -> dict[str, Any]:
    spec = _stage_spec(stage)
    refs = {}
    for role, dataset, schema in spec["output_datasets"]:
        refs[role] = {
            "dataset": dataset,
            "version_id": "v-test",
            "schema_version": schema,
            "content_sha": "ab" * 32,
            "uri": f"artifacts/research/fixture/{stage}/{role}.parquet",
        }
    unsigned: dict[str, Any] = {
        "schema_version": spec["manifest_schema"],
        "identity": {
            "run_id": run_id or STAGE_RUN_IDS[stage],
            "environment": "preview",
            "as_of": "2026-09-18T00:00:00Z",
            "code_sha": "c0de" * 10,
            "config_sha": "ca fe".replace(" ", "") * 8,
            "development_seasons": list(ELIGIBLE_SEASONS),
            "forbidden_seasons": list(FORBIDDEN_SEASONS),
        },
        "parents": parents or {},
        "output_refs": refs,
        "output_rows": {role: 100 + index for index, role in enumerate(refs)},
        "production_activation_authorized": False,
    }
    if state == "present":
        unsigned["state"] = spec["state"]
    elif state is not None:
        unsigned["state"] = state
    if stage == "repair":
        unsigned["timing_class"] = "historically_reconstructed"
        unsigned["population"] = {
            "scheduled_games": 8936,
            "forecast_eligible_games": 8935,
            "measurement_usable_games": 8903,
            "measurement_missing_games": 33,
            "population_sha256": "cd" * 32,
        }
    return signed_payload(unsigned)


def _fixture_parents() -> dict[str, dict[str, Any]]:
    uris = {
        stage: f"artifacts/research/fixture/{stage}/manifest.json"
        for stage in STAGE_RUN_IDS
    }
    return {
        "repair": _fixture_manifest("repair", parents={"note": "source eligibility"}),
        "measurements": _fixture_manifest(
            "measurements",
            parents={"repair_manifest_uri": uris["repair"]},
        ),
        "ratings": _fixture_manifest(
            "ratings",
            parents={
                "measurement_manifest_uri": uris["measurements"],
                "repair_manifest_uri": uris["repair"],
            },
        ),
        "forecasts": _fixture_manifest(
            "forecasts",
            parents={
                "rating_manifest_uri": uris["ratings"],
                "measurement_manifest_uri": uris["measurements"],
                "repair_manifest_uri": uris["repair"],
            },
        ),
    }


class _FakeStorage:
    def __init__(
        self, objects: dict[str, bytes], *, missing: set[str] = frozenset()
    ) -> None:
        self.objects = dict(objects)
        self.missing = set(missing)
        self.writes: dict[str, bytes] = {}

    def read_bytes(self, uri: str) -> bytes:
        if uri in self.writes:
            return self.writes[uri]
        if uri in self.objects:
            return self.objects[uri]
        raise FileNotFoundError(uri)

    def exists(self, uri: str) -> bool:
        if uri in self.missing:
            return False
        return uri in self.objects or uri in self.writes

    def write_bytes(self, data: bytes, uri: str) -> None:
        self.writes[uri] = data


def _fixture_storage(manifests: dict[str, dict[str, Any]]) -> _FakeStorage:
    objects: dict[str, bytes] = {}
    for stage, manifest in manifests.items():
        uri = f"artifacts/research/fixture/{stage}/manifest.json"
        objects[uri] = json.dumps(
            manifest, sort_keys=True, separators=(",", ":")
        ).encode()
        for ref in (manifest.get("output_refs") or {}).values():
            objects[ref["uri"]] = b"fixture-dataset-bytes"
    return _FakeStorage(objects)


def _uris(manifests: dict[str, dict[str, Any]]) -> dict[str, str]:
    return {
        stage: f"artifacts/research/fixture/{stage}/manifest.json"
        for stage in manifests
    }


# --- Config -----------------------------------------------------------------


def test_validate_audit_config_accepts_sealed_config() -> None:
    config = audit_register.validate_config(yaml.safe_load(AUDIT_CONFIG.read_bytes()))
    assert config["environment"] == "preview"
    assert set(config["parents"]) == set(STAGE_RUN_IDS)
    assert config["production_activation_authorized"] is False


def test_validate_audit_config_rejects_non_preview() -> None:
    config = yaml.safe_load(AUDIT_CONFIG.read_bytes())
    config["environment"] = "production"
    with pytest.raises(audit_register.AuditError):
        audit_register.validate_config(config)


def test_validate_audit_config_rejects_season_drift() -> None:
    config = yaml.safe_load(AUDIT_CONFIG.read_bytes())
    config["development_seasons"] = [2015, 2016]
    with pytest.raises(audit_register.AuditError):
        audit_register.validate_config(config)


def test_validate_audit_config_rejects_production_flag() -> None:
    config = yaml.safe_load(AUDIT_CONFIG.read_bytes())
    config["production_activation_authorized"] = True
    with pytest.raises(audit_register.AuditError):
        audit_register.validate_config(config)


def test_validate_audit_config_rejects_missing_parent() -> None:
    config = yaml.safe_load(AUDIT_CONFIG.read_bytes())
    del config["parents"]["forecasts"]
    with pytest.raises(audit_register.AuditError):
        audit_register.validate_config(config)


# --- Register ---------------------------------------------------------------


def test_register_row_carries_umbrella_fields() -> None:
    manifest = _fixture_manifest("repair")
    row = audit_register.build_register_row(
        stage="repair",
        manifest_uri="uri://repair",
        manifest=manifest,
        raw_sha256="00" * 32,
    )
    assert row["component"] == "v5-repair"
    assert row["role"] == "audit_parent"
    assert row["canonical_sha256"] == manifest["manifest_sha256"]
    assert row["code_sha"] and row["config_sha"]
    assert row["seasons"] == list(ELIGIBLE_SEASONS)
    assert set(row["outputs"]) == {
        "population",
        "auxiliary",
        "coverage",
        "issues",
        "capture_plan",
    }
    assert row["row_counts"]["population"] == 100
    assert row["declared_permitted_use"] == (
        "repaired reconstructed source/population parent only"
    )


def test_iter_manifest_uris_ignores_output_refs() -> None:
    manifest = _fixture_parents()["forecasts"]
    found = dict(audit_register.iter_manifest_uris(manifest))
    assert found["parents.rating_manifest_uri"].endswith(".json")
    assert found["parents.repair_manifest_uri"].endswith(".json")
    assert all("output" not in key for key in found)


def test_collect_nested_manifests_records_unreadable() -> None:
    manifest = _fixture_parents()["forecasts"]
    storage = _FakeStorage({})
    nested = audit_register.collect_nested_manifests(storage, manifest)
    assert nested
    assert all("error" in record for record in nested.values())


def test_git_helpers_reject_missing_commit(tmp_path: Path) -> None:
    assert audit_register.git_commit_exists("0" * 40, root=tmp_path) is False
    assert audit_register.git_file_sha256("0" * 40, "nope.yaml", root=tmp_path) is None


# --- Checks -----------------------------------------------------------------


def test_signature_check_detects_tampering() -> None:
    manifest = _fixture_parents()["repair"]
    assert audit_checks.check_signature("repair", manifest, "uri")["status"] == "pass"
    tampered = dict(manifest, population={"scheduled_games": 1})
    assert audit_checks.check_signature("repair", tampered, "uri")["status"] == "fail"


def test_identity_check_detects_wrong_run_id() -> None:
    manifest = _fixture_parents()["ratings"]
    good = audit_checks.check_identity(
        "ratings",
        manifest,
        "uri",
        expected_run_id=STAGE_RUN_IDS["ratings"],
        expected_schema=_stage_spec("ratings")["manifest_schema"],
    )
    assert good["status"] == "pass"
    bad = audit_checks.check_identity(
        "ratings",
        manifest,
        "uri",
        expected_run_id="wrong-run",
        expected_schema=_stage_spec("ratings")["manifest_schema"],
    )
    assert bad["status"] == "fail"


def test_parent_links_detect_wrong_uri() -> None:
    manifests = _fixture_parents()
    uris = _uris(manifests)
    raw = {stage: "ff" * 32 for stage in manifests}
    assert all(
        check["status"] == "pass"
        for check in audit_checks.check_parent_links(manifests, uris, raw)
    )
    manifests["forecasts"]["parents"]["repair_manifest_uri"] = "artifacts/wrong.json"
    failed = [
        check
        for check in audit_checks.check_parent_links(manifests, uris, raw)
        if check["status"] == "fail"
    ]
    assert [check["check_id"] for check in failed] == ["parents.forecasts.repair.uri"]


def test_output_refs_detect_missing_and_corrupt() -> None:
    manifests = _fixture_parents()
    storage = _fixture_storage(manifests)
    manifest = manifests["repair"]
    assert (
        audit_checks.check_output_refs("repair", manifest, "uri", storage)["status"]
        == "pass"
    )
    corrupt = json.loads(json.dumps(manifest))
    corrupt["output_refs"]["population"].pop("content_sha")
    assert (
        audit_checks.check_output_refs("repair", corrupt, "uri", storage)["status"]
        == "fail"
    )
    ref_uri = manifest["output_refs"]["population"]["uri"]
    gone = _FakeStorage(storage.objects, missing={ref_uri})
    assert (
        audit_checks.check_output_refs("repair", manifest, "uri", gone)["status"]
        == "fail"
    )


def test_output_refs_detect_role_change() -> None:
    manifests = _fixture_parents()
    storage = _fixture_storage(manifests)
    manifest = json.loads(json.dumps(manifests["forecasts"]))
    manifest["output_refs"].pop("forecast_selection")
    assert (
        audit_checks.check_output_refs("forecasts", manifest, "uri", storage)["status"]
        == "fail"
    )


def test_row_counts_detect_sealed_and_agreement_violations() -> None:
    manifests = _fixture_parents()
    assert audit_checks.check_row_counts("repair", manifests, "uri")["status"] == "pass"
    # Fixture populations agree by construction (both first-role counts).
    assert (
        audit_checks.check_row_counts("measurements", manifests, "uri")["status"]
        == "pass"
    )
    disagree = json.loads(json.dumps(manifests))
    disagree["measurements"]["output_rows"]["population"] += 1
    assert (
        audit_checks.check_row_counts("measurements", disagree, "uri")["status"]
        == "fail"
    )
    resealed = json.loads(json.dumps(manifests))
    resealed["repair"]["population"]["scheduled_games"] = 1
    assert audit_checks.check_row_counts("repair", resealed, "uri")["status"] == "fail"


@pytest.mark.parametrize(
    ("label", "payload", "ok"),
    [
        ("fbs_fbs_2019", {"season": 2019, "week": 12}, True),
        ("fbs_fcs_2021", {"season": 2021, "opponent": "FCS"}, True),
        ("first_season_fallback", {"season": 2015, "fallback": True}, True),
        ("carryover_2019_to_2021", {"seasons": [2019, 2021], "gap": 2}, True),
        (
            "ot_non_offense_categories",
            {"period": "OT", "category": "non-offense"},
            True,
        ),
        ("calibration_chronology", {"residual_seasons": [2017, 2018]}, True),
        ("forbidden_2020", {"season": 2020}, False),
        ("forbidden_2026", {"season": 2026}, False),
        ("nested_2020", {"outer": [{"season": 2020}]}, False),
    ],
)
def test_season_gate_fixtures(label: str, payload: dict[str, Any], ok: bool) -> None:
    manifest = _fixture_manifest("repair")
    manifest = dict(manifest)
    manifest[label] = payload
    result = audit_checks.check_seasons("repair", manifest, "uri")
    assert (result["status"] == "pass") is ok


def test_production_flags_detect_authorization() -> None:
    manifest = _fixture_parents()["forecasts"]
    assert (
        audit_checks.check_production_flags("forecasts", manifest, "uri")["status"]
        == "pass"
    )
    flagged = dict(manifest, production_activation_authorized=True)
    assert (
        audit_checks.check_production_flags("forecasts", flagged, "uri")["status"]
        == "fail"
    )


def test_code_config_check_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = _fixture_parents()["repair"]
    monkeypatch.setattr(audit_checks, "git_commit_exists", lambda commit: False)
    result = audit_checks.check_code_config(
        "repair", manifest, "uri", config_path="conf/x.yaml"
    )
    assert result["status"] == "fail"
    assert "object database" in result["observed"]

    monkeypatch.setattr(audit_checks, "git_commit_exists", lambda commit: True)
    monkeypatch.setattr(audit_checks, "git_file_sha256", lambda commit, path: "ff" * 32)
    mismatch = audit_checks.check_code_config(
        "repair", manifest, "uri", config_path="conf/x.yaml"
    )
    assert mismatch["status"] == "fail"


def test_seeded_findings_are_provisional() -> None:
    findings = audit_checks.seeded_provisional_findings(
        {"audit-structural-001": True, "audit-structural-002": True}
    )
    assert [finding["finding_id"] for finding in findings] == [
        seed["finding_id"] for seed in SEEDED_FINDINGS
    ]
    assert all(finding["severity"] == PROVISIONAL_SEVERITY for finding in findings)
    assert all(finding["condition_confirmed"] for finding in findings)


# --- Independence -----------------------------------------------------------


def test_harness_self_scan_is_clean() -> None:
    results, _ = audit_independence.run_independence_checks()
    harness = next(
        check
        for check in results
        if check["check_id"] == "independence.harness.boundary"
    )
    assert harness["status"] == "pass"


def test_repair_producer_import_condition_confirmed() -> None:
    assert audit_independence.repair_producer_import_present() is True
    results, conditions = audit_independence.run_independence_checks()
    assert conditions["audit-structural-001"] is True
    repair = next(
        check
        for check in results
        if check["check_id"] == "independence.repair.boundary"
    )
    assert repair["status"] == "fail"


def test_forecast_reconstruction_absence_confirmed() -> None:
    assert audit_independence.forecast_reconstruction_absent() is True
    _, conditions = audit_independence.run_independence_checks()
    assert conditions["audit-structural-002"] is True


def test_measurement_and_rating_verifiers_pass_boundary() -> None:
    results, _ = audit_independence.run_independence_checks()
    by_id = {check["check_id"]: check for check in results}
    assert by_id["independence.measurements.boundary"]["status"] == "pass"
    assert by_id["independence.ratings.boundary"]["status"] == "pass"
    assert by_id["independence.forecasts.boundary"]["status"] == "pass"


def test_classify_verifier_requires_both_gates() -> None:
    assert audit_independence.classify_verifier(True, True) == "independent"
    assert audit_independence.classify_verifier(True, False) == "dependent"
    assert audit_independence.classify_verifier(False, True) == "dependent"


def test_false_certification_claim_detected(tmp_path: Path) -> None:
    impostor = tmp_path / "verify_impostor.py"
    impostor.write_text(
        "from scripts.research.run_data_first_forecasts import build_offsets\n"
        "CERTIFIED_INDEPENDENT = True\n"
    )
    violations = audit_independence.scan_imports(
        impostor, ("run_data_first_forecasts",)
    )
    assert violations
    assert audit_independence.classify_verifier(not violations, True) == "dependent"


# --- Verification -----------------------------------------------------------


def _evidence_fixture(**overrides: Any) -> dict[str, Any]:
    evidence = {
        "schema_version": "data_first_historical_audit_evidence_v1",
        "identity": {
            "run_id": "audit-test",
            "environment": "preview",
            "code_sha": "aa" * 20,
            "config_sha": "bb" * 32,
            "parents": {
                stage: {
                    "manifest_uri": f"uri://{stage}",
                    "raw_sha256": _stage_raw(stage),
                }
                for stage in STAGE_RUN_IDS
            },
        },
        "register": [
            {
                "component": f"v5-{stage}",
                "role": "audit_parent",
                "uri": f"uri://{stage}",
                "raw_sha256": _stage_raw(stage),
                "code_sha": "aa" * 20,
                "config_sha": "bb" * 32,
                "seasons": list(ELIGIBLE_SEASONS),
                "parent_identities": {},
                "outputs": {},
                "row_counts": {},
                "declared_permitted_use": "test",
            }
            for stage in STAGE_RUN_IDS
        ],
        "check_results": [
            {
                "check_id": "manifest.repair.signature",
                "layer": "lineage",
                "category": "signature",
                "status": "fail",
                "expected": "signed",
                "observed": "repair verifier imports producer",
                "population": "repair",
                "evidence_refs": ["uri://repair"],
            }
        ],
        "findings": [
            {
                "finding_id": "audit-structural-001",
                "severity": PROVISIONAL_SEVERITY,
                "disposition": PROVISIONAL_SEVERITY,
                "closure_state": "open",
                "affected_stages": ["repair"],
                "evidence": ["scripts/research/verify_data_first_repair_v2.py"],
                "required_action": "10b",
                "closure_criteria": "10b",
            }
        ],
        "gate_evaluation": {
            "upstream_blocker_open": False,
            "forecast_findings_pending": False,
            "contract11_permitted": True,
        },
    }
    evidence.update(overrides)
    return dict(evidence) | {"evidence_sha256": sha256(evidence)}


def _stage_bytes(stage: str) -> bytes:
    return f"fixture-bytes:{stage}".encode()


def _stage_raw(stage: str) -> str:
    return hashlib.sha256(_stage_bytes(stage)).hexdigest()


def _expected_parents() -> dict[str, str]:
    return {stage: f"uri://{stage}" for stage in STAGE_RUN_IDS}


def test_verify_evidence_accepts_provisional_preflight() -> None:
    result = audit_verification.verify_audit_evidence(
        _evidence_fixture(),
        expected_run_id="audit-test",
        expected_code_sha="aa" * 20,
        expected_parents=_expected_parents(),
    )
    assert result["verified"] is True
    assert result["failed_checks"] == ["manifest.repair.signature"]


def test_verify_evidence_rejects_digest_mismatch() -> None:
    evidence = _evidence_fixture()
    evidence["evidence_sha256"] = "00" * 32
    with pytest.raises(audit_verification.AuditVerificationError):
        audit_verification.verify_audit_evidence(
            evidence,
            expected_run_id="audit-test",
            expected_code_sha="aa" * 20,
            expected_parents=_expected_parents(),
        )


def test_verify_evidence_rejects_identity_mismatch() -> None:
    with pytest.raises(audit_verification.AuditVerificationError):
        audit_verification.verify_audit_evidence(
            _evidence_fixture(),
            expected_run_id="other-run",
            expected_code_sha="aa" * 20,
            expected_parents=_expected_parents(),
        )


def test_verify_evidence_rejects_gate_mismatch() -> None:
    evidence = _evidence_fixture(
        gate_evaluation={
            "upstream_blocker_open": True,
            "forecast_findings_pending": False,
            "contract11_permitted": False,
        }
    )
    with pytest.raises(audit_verification.AuditVerificationError):
        audit_verification.verify_audit_evidence(
            evidence,
            expected_run_id="audit-test",
            expected_code_sha="aa" * 20,
            expected_parents=_expected_parents(),
        )


def test_verify_evidence_requires_final_severity_when_published() -> None:
    with pytest.raises(audit_verification.AuditVerificationError):
        audit_verification.verify_audit_evidence(
            _evidence_fixture(),
            expected_run_id="audit-test",
            expected_code_sha="aa" * 20,
            expected_parents=_expected_parents(),
            require_published=True,
        )


def test_evaluate_gate_blocks_upstream_blocker() -> None:
    gate = audit_verification.evaluate_gate(
        [
            {
                "severity": "blocker",
                "disposition": "prohibited_until_closed",
                "closure_state": "open",
                "affected_stages": ["ratings"],
            }
        ]
    )
    assert gate == {
        "upstream_blocker_open": True,
        "forecast_findings_pending": False,
        "contract11_permitted": False,
    }


def test_evaluate_gate_uses_closure_not_disposition() -> None:
    gate = audit_verification.evaluate_gate(
        [
            {
                "severity": "blocker",
                "disposition": "prohibited_until_closed",
                "closure_state": "closed",
                "affected_stages": ["repair"],
            },
            {
                "severity": "info",
                "disposition": "historical_evidence_only",
                "closure_state": "open",
                "affected_stages": ["forecasts"],
            },
        ]
    )
    assert gate["contract11_permitted"] is False  # forecast finding still pending
    assert gate["upstream_blocker_open"] is False  # closed blocker does not block


def _finalized_evidence() -> dict[str, Any]:
    evidence = _evidence_fixture()
    evidence["findings"][0]["severity"] = "blocker"
    evidence["findings"][0]["disposition"] = "prohibited_until_closed"
    evidence["findings"][0]["closure_state"] = "open"
    evidence["gate_evaluation"] = audit_verification.evaluate_gate(evidence["findings"])
    evidence["summaries"] = {"corpus": "full"}
    evidence["check_results"] = [
        {
            "check_id": "manifest.repair.signature",
            "layer": "lineage",
            "category": "signature",
            "status": "pass",
            "expected": "signed",
            "observed": "ok",
            "population": "repair",
            "evidence_refs": ["uri://repair"],
        }
    ]
    unsigned = {k: v for k, v in evidence.items() if k != "evidence_sha256"}
    return dict(evidence) | {"evidence_sha256": sha256(unsigned)}


def test_published_round_trip_through_runner_apply() -> None:
    from scripts.research import run_data_first_historical_audit as runner

    evidence = _finalized_evidence()
    storage = _FakeStorage({})
    prefix = "artifacts/research/data-first-football-v1/audits/historical-foundation-v1/runs/audit-test"
    first = runner.apply(
        storage=storage,
        config={"output_root": "artifacts/research/x"},
        run_id="audit-test",
        evidence=evidence,
        prefix=prefix,
        finalized=True,
    )
    assert first["state"] == "applied"
    repeat = runner.apply(
        storage=storage,
        config={"output_root": "artifacts/research/x"},
        run_id="audit-test",
        evidence=evidence,
        prefix=prefix,
    )
    # Same evidence identity resolves to the stored run: already applied.
    assert repeat["state"] == "already_applied"

    manifest = json.loads(storage.writes[f"{prefix}/audit-manifest.json"])
    assert manifest["production_activation_authorized"] is False
    assert manifest["manifest_sha256"]
    register_doc = json.loads(storage.writes[f"{prefix}/evidence-register.json"])
    checks_doc = json.loads(storage.writes[f"{prefix}/check-results.json"])
    findings_doc = json.loads(storage.writes[f"{prefix}/findings.json"])
    result = audit_verification.verify_published_audit(
        manifest,
        register_doc,
        checks_doc,
        findings_doc,
        expected_run_id="audit-test",
        expected_code_sha="aa" * 20,
        expected_parents=_expected_parents(),
        storage=_FakeStorage(
            {
                row["uri"]: _stage_bytes(row["uri"].rsplit("://", 1)[1])
                for row in register_doc["rows"]
            }
        ),
    )
    assert result["verified"] is True
    assert result["publication_valid"] is True
    assert result["gate_evaluation"]["contract11_permitted"] is False

    # Tampering with published findings after the fact must be detected.
    tampered = json.loads(json.dumps(findings_doc))
    tampered["findings"][0]["severity"] = "info"
    with pytest.raises(audit_verification.AuditVerificationError):
        audit_verification.verify_published_audit(
            manifest,
            register_doc,
            checks_doc,
            tampered,
            expected_run_id="audit-test",
            expected_code_sha="aa" * 20,
            expected_parents=_expected_parents(),
        )

    # --- Runner gates -----------------------------------------------------------def test_runner_rejects_non_preview_environment() -> None:
    from scripts.research import run_data_first_historical_audit as runner

    with pytest.raises(SystemExit):
        runner.main(
            ["--run-id", "x", "--expected-code-sha", "y", "--environment", "production"]
        )


def test_runner_dry_run_requires_evidence_out(monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts.research import run_data_first_historical_audit as runner

    monkeypatch.setattr(runner, "_git_sha", lambda: "sha")
    assert (
        runner.main(
            [
                "--run-id",
                "x",
                "--expected-code-sha",
                "sha",
                "--environment",
                "preview",
                "--as-of",
                "2026-09-18T00:00:00Z",
            ]
        )
        == 1
    )


def test_runner_apply_requires_preflight_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.research import run_data_first_historical_audit as runner

    monkeypatch.setattr(runner, "_git_sha", lambda: "sha")
    assert (
        runner.main(
            [
                "--run-id",
                "x",
                "--expected-code-sha",
                "sha",
                "--environment",
                "preview",
                "--as-of",
                "2026-09-18T00:00:00Z",
                "--apply",
                "--evidence-out",
                "out.json",
            ]
        )
        == 1
    )


# --- Exhaustive traversal ---------------------------------------------------


def _signed_json(payload: dict[str, Any]) -> bytes:
    from cks_picks_cfb.data.data_first_phase2d import signed_payload as _sign

    return json.dumps(_sign(payload), sort_keys=True, separators=(",", ":")).encode()


def test_traversal_is_exhaustive_not_depth_limited() -> None:
    chain = {}
    depth = 8
    for level in range(depth):
        uri = f"artifacts/chain/{level}.json"
        nxt = f"artifacts/chain/{level + 1}.json" if level + 1 < depth else None
        chain[uri] = _signed_json(
            {
                "schema_version": "chain_v1",
                "parents": {"next_uri": nxt} if nxt else {},
                "identity": {},
            }
        )
    root = {"parents": {"next_uri": "artifacts/chain/0.json"}, "identity": {}}
    storage = _FakeStorage(chain)
    collected = audit_register.collect_lineage(storage, root)
    assert len(collected) == depth
    assert all("payload" in record for record in collected.values())


def test_traversal_terminates_on_cycles() -> None:
    storage = _FakeStorage(
        {
            "artifacts/a.json": _signed_json(
                {"parents": {"b_uri": "artifacts/b.json"}, "identity": {}}
            ),
            "artifacts/b.json": _signed_json(
                {"parents": {"a_uri": "artifacts/a.json"}, "identity": {}}
            ),
        }
    )
    collected = audit_register.collect_lineage(
        storage, {"parents": {"a_uri": "artifacts/a.json"}, "identity": {}}
    )
    assert set(collected) == {"artifacts/a.json", "artifacts/b.json"}


def test_traversal_records_unreadable_and_opaque() -> None:
    storage = _FakeStorage(
        {
            "artifacts/ok.json": _signed_json({"parents": {}, "identity": {}}),
            "artifacts/blob.json": b"\x00\x01not-json",
            "artifacts/list.json": b"[1, 2]",
        }
    )
    root = {
        "parents": {
            "ok_uri": "artifacts/ok.json",
            "blob_uri": "artifacts/blob.json",
            "list_uri": "artifacts/list.json",
            "gone_uri": "artifacts/gone.json",
        },
        "identity": {},
    }
    collected = audit_register.collect_lineage(storage, root)
    assert "payload" in collected["artifacts/ok.json"]
    assert collected["artifacts/blob.json"].get("opaque") is True
    assert "error" in collected["artifacts/list.json"]
    assert "error" in collected["artifacts/gone.json"]
    assert (
        audit_register.build_graph({}, collected, {})["nodes"]
        and audit_checks.check_lineage_exhaustive(collected)["status"] == "fail"
    )
    clean = {k: v for k, v in collected.items() if "payload" in v or v.get("opaque")}
    assert audit_checks.check_lineage_exhaustive(clean)["status"] == "pass"


# --- Behavioral matrix ------------------------------------------------------


def test_behavioral_matrix_executes_all_16_cells(tmp_path: Path) -> None:
    from cks_picks_cfb.audit.behavioral import run_behavioral_matrix

    cells = run_behavioral_matrix(tmp_dir=tmp_path)
    assert len(cells) == 16
    assert {(cell["verifier"], cell["case"]) for cell in cells} == {
        (verifier, case)
        for verifier in ("repair", "measurements", "ratings", "forecasts")
        for case in (
            "wrong_parent",
            "missing_dataset",
            "corrupted_output",
            "producer_perturbation",
        )
    }
    for cell in cells:
        for key in (
            "cell_id",
            "verifier",
            "case",
            "method",
            "expected",
            "observed",
            "match",
        ):
            assert cell[key] is not None


def test_behavioral_matrix_is_deterministic(tmp_path: Path) -> None:
    from cks_picks_cfb.audit.behavioral import run_behavioral_matrix

    first = run_behavioral_matrix(tmp_dir=tmp_path / "a")
    second = run_behavioral_matrix(tmp_dir=tmp_path / "b")
    assert first == second


def test_behavioral_mismatches_become_findings() -> None:
    cells = [
        {
            "cell_id": "behavioral.ratings.wrong_parent",
            "verifier": "ratings",
            "case": "wrong_parent",
            "method": "m",
            "expected": "reject",
            "observed": "accepted",
            "match": False,
        },
        {
            "cell_id": "behavioral.ratings.missing_dataset",
            "verifier": "ratings",
            "case": "missing_dataset",
            "method": "m",
            "expected": "reject",
            "observed": "reject",
            "match": True,
        },
    ]
    findings = audit_checks.behavioral_findings(cells)
    assert len(findings) == 1
    finding = findings[0]
    assert finding["finding_id"] == "audit-behavioral-ratings"
    assert finding["severity"] == PROVISIONAL_SEVERITY
    assert finding["closure_state"] == "open"
    assert finding["condition_confirmed"] is True
    assert audit_checks.behavioral_findings([c for c in cells if c["match"]]) == []
    checks = audit_checks.behavioral_cells_to_checks(cells)
    assert [c["status"] for c in checks] == ["fail", "pass"]


# --- Publication hardening --------------------------------------------------


def test_config_rejects_rejected_season_drift() -> None:
    config = yaml.safe_load(AUDIT_CONFIG.read_bytes())
    config["rejected_seasons"] = [2020]
    with pytest.raises(audit_register.AuditError):
        audit_register.validate_config(config)


def test_verify_evidence_rejects_unknown_closure_state() -> None:
    evidence = _evidence_fixture()
    evidence["findings"][0]["closure_state"] = "pending"
    evidence["evidence_sha256"] = sha256(
        {k: v for k, v in evidence.items() if k != "evidence_sha256"}
    )
    with pytest.raises(audit_verification.AuditVerificationError):
        audit_verification.verify_audit_evidence(
            evidence,
            expected_run_id="audit-test",
            expected_code_sha="aa" * 20,
            expected_parents=_expected_parents(),
        )


def test_apply_collision_fails_closed() -> None:
    from scripts.research import run_data_first_historical_audit as runner

    evidence = _finalized_evidence()
    storage = _FakeStorage({})
    prefix = "artifacts/runs/audit-test"
    runner.apply(
        storage=storage,
        config={},
        run_id="audit-test",
        evidence=evidence,
        prefix=prefix,
        finalized=True,
    )
    other = _finalized_evidence()
    other["findings"].append(
        {
            "finding_id": "extra",
            "severity": "info",
            "disposition": "historical_evidence_only",
            "closure_state": "open",
            "affected_stages": [],
            "evidence": [],
            "required_action": "none",
            "closure_criteria": "none",
        }
    )
    other["gate_evaluation"] = audit_verification.evaluate_gate(other["findings"])
    other_unsigned = {k: v for k, v in other.items() if k != "evidence_sha256"}
    other = dict(other) | {"evidence_sha256": sha256(other_unsigned)}
    with pytest.raises(runner.AuditError):
        runner.apply(
            storage=storage,
            config={},
            run_id="audit-test",
            evidence=other,
            prefix=prefix,
            finalized=True,
        )


def test_published_rejects_non_final_manifest() -> None:
    from scripts.research import run_data_first_historical_audit as runner

    evidence = _finalized_evidence()
    storage = _FakeStorage({})
    prefix = "artifacts/runs/audit-test"
    runner.apply(
        storage=storage,
        config={},
        run_id="audit-test",
        evidence=evidence,
        prefix=prefix,
        finalized=False,
    )
    manifest = json.loads(storage.writes[f"{prefix}/audit-manifest.json"])
    assert manifest["finalized"] is False
    with pytest.raises(audit_verification.AuditVerificationError):
        audit_verification.verify_published_audit(
            manifest,
            json.loads(storage.writes[f"{prefix}/evidence-register.json"]),
            json.loads(storage.writes[f"{prefix}/check-results.json"]),
            json.loads(storage.writes[f"{prefix}/findings.json"]),
            expected_run_id="audit-test",
            expected_code_sha="aa" * 20,
            expected_parents=_expected_parents(),
        )


def test_published_rereads_parent_bytes() -> None:
    from scripts.research import run_data_first_historical_audit as runner

    evidence = _finalized_evidence()
    storage = _FakeStorage({})
    prefix = "artifacts/runs/audit-test"
    runner.apply(
        storage=storage,
        config={},
        run_id="audit-test",
        evidence=evidence,
        prefix=prefix,
        finalized=True,
    )
    manifest = json.loads(storage.writes[f"{prefix}/audit-manifest.json"])
    register_doc = json.loads(storage.writes[f"{prefix}/evidence-register.json"])
    checks_doc = json.loads(storage.writes[f"{prefix}/check-results.json"])
    findings_doc = json.loads(storage.writes[f"{prefix}/findings.json"])
    # Register URIs resolve to tampered bytes: reread must detect the change.
    tampered = _FakeStorage({row["uri"]: b"tampered" for row in register_doc["rows"]})
    with pytest.raises(audit_verification.AuditVerificationError):
        audit_verification.verify_published_audit(
            manifest,
            register_doc,
            checks_doc,
            findings_doc,
            expected_run_id="audit-test",
            expected_code_sha="aa" * 20,
            expected_parents=_expected_parents(),
            storage=tampered,
        )


def test_evidence_digest_reconstructs_from_outputs() -> None:
    import hashlib

    from scripts.research import run_data_first_historical_audit as runner

    evidence = _finalized_evidence()
    storage = _FakeStorage({})
    prefix = "artifacts/runs/audit-test"
    runner.apply(
        storage=storage,
        config={},
        run_id="audit-test",
        evidence=evidence,
        prefix=prefix,
        finalized=True,
    )
    manifest = json.loads(storage.writes[f"{prefix}/audit-manifest.json"])
    register_doc = json.loads(storage.writes[f"{prefix}/evidence-register.json"])
    assert manifest["evidence_sha256"] == (
        audit_verification.evidence_digest_for_manifest(
            manifest["identity"], manifest["output_digests"]
        )
    )
    assert (
        manifest["output_digests"]["evidence_register"]
        == hashlib.sha256(audit_verification.canonical_bytes(register_doc)).hexdigest()
    )
