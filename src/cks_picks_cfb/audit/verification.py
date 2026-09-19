"""Independent verification of historical-audit evidence.

Verifier-owned: imports only audit schemas/constants from this package and the
standard library. Never imports the audit runner or check implementations. It
verifies exact parent bytes, output bytes/hashes, manifest-last publication,
internal count/findings consistency, source-reference existence, and
disposition/gate arithmetic. It does not claim to recompute every
football-semantic check.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from cks_picks_cfb.audit import (
    AUDIT_EVIDENCE_SCHEMA,
    AUDIT_MANIFEST_SCHEMA,
    CLOSURE_STATES,
    DISPOSITIONS,
    PROVISIONAL_SEVERITY,
    SEVERITIES,
)


class AuditVerificationError(ValueError):
    """Raised when audit evidence fails independent verification."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str
    ).encode()


def evidence_digest(evidence: Mapping[str, Any]) -> str:
    unsigned = dict(evidence)
    unsigned.pop("evidence_sha256", None)
    return hashlib.sha256(canonical_bytes(unsigned)).hexdigest()


def _require_keys(
    payload: Mapping[str, Any], keys: tuple[str, ...], label: str
) -> None:
    missing = [key for key in keys if payload.get(key) is None]
    if missing:
        raise AuditVerificationError(f"{label} is missing fields: {missing}")


def evaluate_gate(findings: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Recompute the Contract 11 entry-gate evaluation from finding closure.

    Contract 11 may begin only when every upstream Repair/measurement/rating
    blocker is closed and every forecast finding is closed or explicitly
    incorporated into Contract 11. Closure state alone drives the gate;
    severity and disposition describe the defect and artifact use.
    """
    upstream_stages = ("repair", "measurements", "ratings")
    upstream_blocker_open = any(
        finding.get("severity") == "blocker"
        and finding.get("closure_state") != "closed"
        and any(
            stage in upstream_stages for stage in (finding.get("affected_stages") or [])
        )
        for finding in findings
    )
    forecast_pending = any(
        "forecasts" in (finding.get("affected_stages") or [])
        and finding.get("closure_state")
        not in ("closed", "incorporated_into_contract_11")
        for finding in findings
    )
    return {
        "upstream_blocker_open": bool(upstream_blocker_open),
        "forecast_findings_pending": bool(forecast_pending),
        "contract11_permitted": bool(
            not upstream_blocker_open and not forecast_pending
        ),
    }


def evidence_digest_for_manifest(
    identity: Mapping[str, Any], output_digests: Mapping[str, Any]
) -> str:
    """Reproducible digest derived from identity and the three evidence docs."""
    return hashlib.sha256(
        canonical_bytes(
            {"identity": dict(identity), "output_digests": dict(output_digests)}
        )
    ).hexdigest()


def verify_audit_evidence(
    evidence: Mapping[str, Any],
    *,
    expected_run_id: str,
    expected_code_sha: str,
    expected_parents: Mapping[str, str],
    storage: Any = None,
    require_published: bool = False,
) -> dict[str, Any]:
    """Independently verify audit evidence bytes and internal consistency."""
    if evidence.get("schema_version") != AUDIT_EVIDENCE_SCHEMA:
        raise AuditVerificationError("unexpected audit evidence schema")
    declared = evidence.get("evidence_sha256")
    if not declared or declared != evidence_digest(evidence):
        raise AuditVerificationError("audit evidence digest mismatch")
    identity = evidence.get("identity") or {}
    _require_keys(
        identity,
        ("run_id", "code_sha", "config_sha", "parents"),
        "audit identity",
    )
    if identity.get("run_id") != expected_run_id:
        raise AuditVerificationError("audit run identity mismatch")
    if identity.get("code_sha") != expected_code_sha:
        raise AuditVerificationError("audit code identity mismatch")
    if identity.get("environment") != "preview":
        raise AuditVerificationError("audit evidence is not Preview evidence")
    observed_parents = identity.get("parents") or {}
    for stage, uri in expected_parents.items():
        if (observed_parents.get(stage) or {}).get("manifest_uri") != uri:
            raise AuditVerificationError(f"audit identity parent mismatch: {stage}")

    register = evidence.get("register")
    if not isinstance(register, list) or not register:
        raise AuditVerificationError("audit evidence register is empty")
    for row in register:
        _require_keys(
            row,
            (
                "component",
                "role",
                "uri",
                "raw_sha256",
                "code_sha",
                "config_sha",
                "seasons",
                "parent_identities",
                "outputs",
                "row_counts",
                "declared_permitted_use",
            ),
            "evidence register row",
        )

    checks = evidence.get("check_results")
    if not isinstance(checks, list) or not checks:
        raise AuditVerificationError("audit check results are empty")
    for check in checks:
        _require_keys(
            check,
            (
                "check_id",
                "layer",
                "category",
                "status",
                "expected",
                "observed",
                "population",
                "evidence_refs",
                "affected_stages",
            ),
            "check result",
        )
        if check.get("status") not in ("pass", "fail"):
            raise AuditVerificationError(
                f"check has an unknown status: {check.get('check_id')}"
            )

    findings = evidence.get("findings")
    if not isinstance(findings, list):
        raise AuditVerificationError("audit findings are missing")
    allowed_severities = set(SEVERITIES)
    allowed_dispositions = set(DISPOSITIONS)
    if not require_published:
        allowed_severities.add(PROVISIONAL_SEVERITY)
        allowed_dispositions.add(PROVISIONAL_SEVERITY)
    for finding in findings:
        _require_keys(
            finding,
            (
                "finding_id",
                "check_id",
                "severity",
                "disposition",
                "closure_state",
                "affected_stages",
                "affected_artifacts",
                "evidence",
                "required_action",
                "closure_criteria",
            ),
            "finding",
        )
        if finding.get("severity") not in allowed_severities:
            raise AuditVerificationError(
                f"finding has an unknown severity: {finding.get('finding_id')}"
            )
        if finding.get("disposition") not in allowed_dispositions:
            raise AuditVerificationError(
                f"finding has an unknown disposition: {finding.get('finding_id')}"
            )
        if finding.get("closure_state") not in CLOSURE_STATES:
            raise AuditVerificationError(
                f"finding has an unknown closure state: {finding.get('finding_id')}"
            )

    recomputed = evaluate_gate([dict(finding) for finding in findings])
    recorded = evidence.get("gate_evaluation") or {}
    if {key: recorded.get(key) for key in recomputed} != recomputed:
        raise AuditVerificationError("audit gate arithmetic does not reconcile")

    if storage is not None:
        missing_refs: list[str] = []
        for row in register:
            uri = row.get("uri")
            if uri and not storage.exists(uri):
                missing_refs.append(str(uri))
        if missing_refs:
            raise AuditVerificationError(
                f"registered source references are missing: {missing_refs[:8]}"
            )

    manifest = evidence.get("audit_manifest")
    if require_published:
        if not isinstance(manifest, dict):
            raise AuditVerificationError("published audit manifest is missing")
        if manifest.get("schema_version") != AUDIT_MANIFEST_SCHEMA:
            raise AuditVerificationError("unexpected audit manifest schema")
        declared_manifest_sha = manifest.get("manifest_sha256")
        unsigned = dict(manifest)
        unsigned.pop("manifest_sha256", None)
        if (
            not declared_manifest_sha
            or declared_manifest_sha
            != hashlib.sha256(canonical_bytes(unsigned)).hexdigest()
        ):
            raise AuditVerificationError("published audit manifest digest mismatch")
        if manifest.get("production_activation_authorized") is not False:
            raise AuditVerificationError("published manifest authorizes production")

    failed = sorted(
        check["check_id"] for check in checks if check.get("status") == "fail"
    )
    return {
        "verified": True,
        "run_id": expected_run_id,
        "evidence_sha256": declared,
        "register_rows": len(register),
        "checks": len(checks),
        "failed_checks": failed,
        "findings": len(findings),
        "gate_evaluation": recomputed,
        "published": require_published,
    }


def _manifest_digest(manifest: Mapping[str, Any]) -> str:
    unsigned = dict(manifest)
    unsigned.pop("manifest_sha256", None)
    return hashlib.sha256(canonical_bytes(unsigned)).hexdigest()


def verify_published_audit(
    manifest: Mapping[str, Any],
    register_doc: Mapping[str, Any],
    checks_doc: Mapping[str, Any],
    findings_doc: Mapping[str, Any],
    *,
    expected_run_id: str,
    expected_code_sha: str,
    expected_parents: Mapping[str, str],
    storage: Any = None,
) -> dict[str, Any]:
    """Verify a published Preview audit prefix and separate two decisions.

    Publication validity (manifest digest, final state, output bytes/hashes,
    reread parent bytes, internal consistency) is required for a legitimate
    publication. The Contract 11 gate (finding closure) is evaluated and
    reported separately: validity never implies Contract 11 permission.
    """
    if manifest.get("schema_version") != AUDIT_MANIFEST_SCHEMA:
        raise AuditVerificationError("unexpected audit manifest schema")
    if manifest.get("finalized") is not True:
        raise AuditVerificationError("published audit manifest is not final")
    declared_manifest_sha = manifest.get("manifest_sha256")
    if not declared_manifest_sha or declared_manifest_sha != _manifest_digest(manifest):
        raise AuditVerificationError("published audit manifest digest mismatch")
    if manifest.get("production_activation_authorized") is not False:
        raise AuditVerificationError("published manifest authorizes production")
    identity = manifest.get("identity") or {}
    _require_keys(identity, ("run_id", "code_sha", "parents"), "audit identity")
    if identity.get("run_id") != expected_run_id:
        raise AuditVerificationError("audit run identity mismatch")
    if identity.get("code_sha") != expected_code_sha:
        raise AuditVerificationError("audit code identity mismatch")
    if identity.get("environment") != "preview":
        raise AuditVerificationError("audit evidence is not Preview evidence")
    observed_parents = identity.get("parents") or {}
    for stage, uri in expected_parents.items():
        if (observed_parents.get(stage) or {}).get("manifest_uri") != uri:
            raise AuditVerificationError(f"audit identity parent mismatch: {stage}")

    observed_digests = {
        "evidence_register": hashlib.sha256(canonical_bytes(register_doc)).hexdigest(),
        "check_results": hashlib.sha256(canonical_bytes(checks_doc)).hexdigest(),
        "findings": hashlib.sha256(canonical_bytes(findings_doc)).hexdigest(),
    }
    if dict(manifest.get("output_digests") or {}) != observed_digests:
        raise AuditVerificationError("published output bytes do not match manifest")
    reconstructed_evidence = evidence_digest_for_manifest(
        manifest.get("identity") or {}, observed_digests
    )
    if manifest.get("evidence_sha256") != reconstructed_evidence:
        raise AuditVerificationError(
            "published evidence digest does not reconstruct from outputs"
        )
    rows = register_doc.get("rows")
    results = checks_doc.get("results")
    findings = findings_doc.get("findings")
    if not isinstance(rows, list) or not rows:
        raise AuditVerificationError("published evidence register is empty")
    if not isinstance(results, list) or not results:
        raise AuditVerificationError("published check results are empty")
    if not isinstance(findings, list):
        raise AuditVerificationError("published findings are missing")
    observed_counts = {
        "register_rows": len(rows),
        "check_results": len(results),
        "findings": len(findings),
    }
    if dict(manifest.get("output_counts") or {}) != observed_counts:
        raise AuditVerificationError("published output counts do not match manifest")

    for row in rows:
        _require_keys(
            row,
            (
                "component",
                "role",
                "uri",
                "raw_sha256",
                "code_sha",
                "config_sha",
                "seasons",
                "parent_identities",
                "outputs",
                "row_counts",
                "declared_permitted_use",
            ),
            "evidence register row",
        )
    for check in results:
        _require_keys(
            check,
            (
                "check_id",
                "layer",
                "category",
                "status",
                "expected",
                "observed",
                "population",
                "evidence_refs",
                "affected_stages",
            ),
            "check result",
        )
        if check.get("status") not in ("pass", "fail"):
            raise AuditVerificationError("check has an unknown status")
    for finding in findings:
        _require_keys(
            finding,
            (
                "finding_id",
                "check_id",
                "severity",
                "disposition",
                "closure_state",
                "affected_stages",
                "affected_artifacts",
                "evidence",
                "required_action",
                "closure_criteria",
            ),
            "finding",
        )
        if finding.get("severity") not in SEVERITIES:
            raise AuditVerificationError("published finding lacks a final severity")
        if finding.get("disposition") not in DISPOSITIONS:
            raise AuditVerificationError("published finding lacks a final disposition")
        if finding.get("closure_state") not in CLOSURE_STATES:
            raise AuditVerificationError("published finding lacks a closure state")

    recomputed = evaluate_gate([dict(finding) for finding in findings])
    if dict(manifest.get("gate_evaluation") or {}) != recomputed:
        raise AuditVerificationError("published gate arithmetic does not reconcile")

    if storage is not None:
        missing_refs = [
            str(row["uri"])
            for row in rows
            if row.get("uri") and not storage.exists(row["uri"])
        ]
        if missing_refs:
            raise AuditVerificationError(
                f"registered source references are missing: {missing_refs[:8]}"
            )
        # Reread and hash the exact parent manifests; the recorded raw
        # hashes must match current bytes.
        recorded_parents = manifest.get("parents") or {}
        for stage, uri in expected_parents.items():
            try:
                parent_raw = storage.read_bytes(uri)
            except Exception as exc:
                raise AuditVerificationError(
                    f"parent manifest unreadable on re-read: {stage}"
                ) from exc
            if hashlib.sha256(parent_raw).hexdigest() != (
                recorded_parents.get(stage) or {}
            ).get("raw_sha256"):
                raise AuditVerificationError(
                    f"parent bytes differ from recorded hash: {stage}"
                )
    return {
        "verified": True,
        "publication_valid": True,
        "run_id": expected_run_id,
        "manifest_sha256": declared_manifest_sha,
        "register_rows": len(rows),
        "checks": len(results),
        "failed_checks": sorted(
            check["check_id"] for check in results if check.get("status") == "fail"
        ),
        "findings": len(findings),
        "gate_evaluation": recomputed,
        "published": True,
    }
