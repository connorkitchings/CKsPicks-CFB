#!/usr/bin/env python3
"""V5-10a historical-audit preflight runner (read-only).

Dry run reads the four frozen parent manifests, builds the lineage
inventory, runs manifest and independence checks, and writes candidate
evidence to a local path. It writes nothing to R2. Apply publishes the
versioned audit outputs to the Preview audit prefix; 10a executes
preflights only, and 10b owns the evidence-bound apply.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from cks_picks_cfb.audit import (
    AUDIT_EVIDENCE_SCHEMA,
    AUDIT_IDENTITY_SCHEMA,
    AUDIT_MANIFEST_SCHEMA,
    ELIGIBLE_SEASONS,
    FORBIDDEN_SEASONS,
    PARENT_STAGES,
)
from cks_picks_cfb.audit.behavioral import run_behavioral_matrix
from cks_picks_cfb.audit.checks import (
    behavioral_cells_to_checks,
    behavioral_findings,
    check_code_config,
    check_identity,
    check_lineage_exhaustive,
    check_output_refs,
    check_parent_links,
    check_production_flags,
    check_row_counts,
    check_seasons,
    check_signature,
    check_state,
    seeded_provisional_findings,
)
from cks_picks_cfb.audit.independence import run_independence_checks
from cks_picks_cfb.audit.register import (
    AuditError,
    build_graph,
    build_register_row,
    collect_lineage,
    read_manifest,
    validate_config,
)
from cks_picks_cfb.audit.verification import (
    canonical_bytes,
    evaluate_gate,
    evidence_digest_for_manifest,
)
from cks_picks_cfb.data.data_first_phase2d import sha256
from cks_picks_cfb.data.storage import get_storage

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "conf/research/data_first_football_v1/historical_audit_v1.yaml"


def _git_sha() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def _clean_worktree() -> bool:
    return not subprocess.check_output(
        ["git", "status", "--porcelain=v1"], cwd=ROOT, text=True
    ).strip()


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise AuditError("--as-of must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _config_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _immutable_json(storage: Any, uri: str, payload: Mapping[str, Any]) -> None:
    encoded = canonical_bytes(payload)
    if storage.exists(uri):
        if storage.read_bytes(uri) != encoded:
            raise AuditError(f"immutable object collision at {uri}")
        return
    storage.write_bytes(encoded, uri)


def _expected_schema(stage: str) -> str:
    for entry in PARENT_STAGES:
        if entry["stage"] == stage:
            return str(entry["manifest_schema"])
    raise AuditError(f"unknown audit stage: {stage}")


def _expected_state(stage: str) -> str | None:
    for entry in PARENT_STAGES:
        if entry["stage"] == stage:
            state = entry["state"]
            return None if state is None else str(state)
    raise AuditError(f"unknown audit stage: {stage}")


def preflight(
    *,
    storage: Any,
    config: Mapping[str, Any],
    run_id: str,
    as_of: str,
    code_sha: str,
    config_sha: str,
) -> dict[str, Any]:
    """Run the complete read-only audit preflight and return unsigned evidence."""
    parents_cfg = config["parents"]
    order = ("repair", "measurements", "ratings", "forecasts")
    loaded: dict[str, dict[str, Any]] = {}
    raw_shas: dict[str, str] = {}
    manifest_uris: dict[str, str] = {}
    nested: dict[str, dict[str, Any]] = {}
    for stage in order:
        uri = str(parents_cfg[stage]["manifest_uri"])
        payload, raw_sha = read_manifest(storage, uri)
        loaded[stage] = payload
        raw_shas[stage] = raw_sha
        manifest_uris[stage] = uri
        for nested_uri, record in collect_lineage(storage, payload).items():
            nested.setdefault(nested_uri, record)

    identity = {
        "schema_version": AUDIT_IDENTITY_SCHEMA,
        "run_id": run_id,
        "environment": "preview",
        "as_of": as_of,
        "code_sha": code_sha,
        "config_sha": config_sha,
        "parents": {
            stage: {"manifest_uri": manifest_uris[stage], "raw_sha256": raw_shas[stage]}
            for stage in order
        },
        "development_seasons": list(ELIGIBLE_SEASONS),
        "forbidden_seasons": list(FORBIDDEN_SEASONS),
        "rejected_seasons": list(config["rejected_seasons"]),
    }

    register = [
        build_register_row(
            stage=stage,
            manifest_uri=manifest_uris[stage],
            manifest=loaded[stage],
            raw_sha256=raw_shas[stage],
        )
        for stage in order
    ]
    graph = build_graph(
        {stage: loaded[stage] for stage in order},
        nested,
        manifest_uris,
    )

    check_results: list[dict[str, Any]] = []
    for stage in order:
        uri = manifest_uris[stage]
        check_results.append(check_signature(stage, loaded[stage], uri))
        check_results.append(
            check_identity(
                stage,
                loaded[stage],
                uri,
                expected_run_id=str(parents_cfg[stage]["run_id"]),
                expected_schema=_expected_schema(stage),
            )
        )
        check_results.append(
            check_state(
                stage, loaded[stage], uri, expected_state=_expected_state(stage)
            )
        )
        check_results.append(check_production_flags(stage, loaded[stage], uri))
        check_results.append(check_output_refs(stage, loaded[stage], uri, storage))
        check_results.append(check_row_counts(stage, loaded, uri))
        check_results.append(
            check_seasons(
                stage, loaded[stage], uri, rejected=tuple(config["rejected_seasons"])
            )
        )
        check_results.append(
            check_code_config(
                stage,
                loaded[stage],
                uri,
                config_path=str(parents_cfg[stage]["config_path"]),
            )
        )
    check_results.extend(check_parent_links(loaded, manifest_uris, raw_shas))
    check_results.append(check_lineage_exhaustive(nested))
    independence_results, conditions = run_independence_checks()
    check_results.extend(independence_results)

    with tempfile.TemporaryDirectory(prefix="historical-audit-10a-") as tmp:
        behavioral_cells = run_behavioral_matrix(tmp_dir=Path(tmp))
    check_results.extend(behavioral_cells_to_checks(behavioral_cells))

    findings = seeded_provisional_findings(conditions)
    findings.extend(behavioral_findings(behavioral_cells))
    gate_evaluation = evaluate_gate([dict(finding) for finding in findings])

    return {
        "schema_version": AUDIT_EVIDENCE_SCHEMA,
        "state": "dry_run",
        "identity": identity,
        "register": register,
        "graph": graph,
        "check_results": check_results,
        "findings": findings,
        "gate_evaluation": gate_evaluation,
    }


def _evidence_with_digest(evidence: Mapping[str, Any]) -> dict[str, Any]:
    return dict(evidence) | {"evidence_sha256": sha256(evidence)}


def _load_preflight_evidence(
    path: Path, *, identity: Mapping[str, Any]
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as exc:
        raise AuditError("preflight evidence is unreadable") from exc
    if payload.get("state") != "dry_run" or payload.get("identity") != dict(identity):
        raise AuditError("preflight evidence identity does not match apply")
    if payload.get("evidence_sha256") != sha256(
        {k: v for k, v in payload.items() if k != "evidence_sha256"}
    ):
        raise AuditError("preflight evidence digest does not reconcile")
    return payload


def _audit_manifest(
    *,
    identity: Mapping[str, Any],
    prefix: str,
    evidence_sha256: str,
    digests: Mapping[str, str],
    counts: Mapping[str, int],
    gate_evaluation: Mapping[str, Any],
    finalized: bool,
) -> dict[str, Any]:
    unsigned = {
        "schema_version": AUDIT_MANIFEST_SCHEMA,
        "identity": dict(identity),
        "parents": dict(identity["parents"]),
        "evidence_sha256": evidence_digest_for_manifest(identity, digests),
        "output_refs": {
            "evidence_register": f"{prefix}/evidence-register.json",
            "check_results": f"{prefix}/check-results.json",
            "findings": f"{prefix}/findings.json",
        },
        "output_digests": dict(digests),
        "output_counts": dict(counts),
        "overall_disposition": "candidate-preflight-base"
        if not finalized
        else "audited",
        "gate_evaluation": dict(gate_evaluation),
        "finalized": finalized,
        "production_activation_authorized": False,
    }
    return dict(unsigned) | {
        "manifest_sha256": hashlib.sha256(canonical_bytes(unsigned)).hexdigest()
    }


def apply(
    *,
    storage: Any,
    config: Mapping[str, Any],
    run_id: str,
    evidence: Mapping[str, Any],
    prefix: str,
    finalized: bool = False,
) -> dict[str, Any]:
    """Publish versioned audit outputs to the Preview audit prefix.

    An existing run returns ``already_applied`` only when the complete
    identity, evidence digest, parents, and output hashes match; any
    collision fails closed.
    """
    manifest_uri = f"{prefix}/audit-manifest.json"
    register_payload = {
        "schema_version": evidence["schema_version"],
        "identity": evidence["identity"],
        "rows": evidence["register"],
    }
    checks_payload = {
        "schema_version": evidence["schema_version"],
        "identity": evidence["identity"],
        "results": evidence["check_results"],
    }
    findings_payload = {
        "schema_version": evidence["schema_version"],
        "identity": evidence["identity"],
        "findings": evidence["findings"],
    }
    digests = {
        "evidence_register": sha256(register_payload),
        "check_results": sha256(checks_payload),
        "findings": sha256(findings_payload),
    }
    counts = {
        "register_rows": len(evidence["register"]),
        "check_results": len(evidence["check_results"]),
        "findings": len(evidence["findings"]),
    }
    manifest = _audit_manifest(
        identity=evidence["identity"],
        prefix=prefix,
        evidence_sha256=str(evidence["evidence_sha256"]),
        digests=digests,
        counts=counts,
        gate_evaluation=evidence["gate_evaluation"],
        finalized=finalized,
    )
    if storage.exists(manifest_uri):
        existing = json.loads(storage.read_bytes(manifest_uri))
        if (
            (existing.get("identity") or {}) == dict(evidence["identity"])
            and existing.get("evidence_sha256") == manifest["evidence_sha256"]
            and dict(existing.get("output_digests") or {}) == digests
        ):
            return {
                "state": "already_applied",
                "manifest_uri": manifest_uri,
            }
        raise AuditError("audit run ID already has a different identity")
    # The terminal manifest is written last; its absence keeps any partial
    # prefix permanently ineligible.
    _immutable_json(storage, f"{prefix}/evidence-register.json", register_payload)
    _immutable_json(storage, f"{prefix}/check-results.json", checks_payload)
    _immutable_json(storage, f"{prefix}/findings.json", findings_payload)
    _immutable_json(storage, manifest_uri, manifest)
    return {"state": "applied", "manifest_uri": manifest_uri}


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--environment", required=True, choices=("preview",))
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--repair-manifest-uri", default=None)
    parser.add_argument("--measurement-manifest-uri", default=None)
    parser.add_argument("--rating-manifest-uri", default=None)
    parser.add_argument("--forecast-manifest-uri", default=None)
    parser.add_argument("--evidence-out", default=None)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--preflight-evidence", default=None)
    args = parser.parse_args(argv)

    started = time.monotonic()
    config_path = Path(args.config)
    try:
        config = validate_config(yaml.safe_load(config_path.read_bytes()))
    except (OSError, AuditError) as exc:
        print(f"audit preflight failed: {exc}", file=sys.stderr)
        return 1
    if _git_sha() != args.expected_code_sha:
        print("audit preflight failed: --expected-code-sha must equal committed HEAD")
        return 1
    if bool(args.preflight_evidence) != bool(args.apply):
        print("audit preflight failed: --apply and --preflight-evidence go together")
        return 1
    if args.apply and not _clean_worktree():
        print("audit preflight failed: apply requires a clean committed worktree")
        return 1
    if not args.apply and not args.evidence_out:
        print("audit preflight failed: dry run requires --evidence-out")
        return 1

    overrides = {
        "repair": args.repair_manifest_uri,
        "measurements": args.measurement_manifest_uri,
        "ratings": args.rating_manifest_uri,
        "forecasts": args.forecast_manifest_uri,
    }
    for stage, override in overrides.items():
        if override:
            config["parents"][stage]["manifest_uri"] = override

    as_of = _utc(args.as_of).isoformat().replace("+00:00", "Z")
    storage = get_storage(environment="preview")
    unsigned = preflight(
        storage=storage,
        config=config,
        run_id=args.run_id,
        as_of=as_of,
        code_sha=args.expected_code_sha,
        config_sha=_config_sha(config_path),
    )
    evidence = _evidence_with_digest(unsigned)
    elapsed = round(time.monotonic() - started, 3)

    if not args.apply:
        if elapsed > float(config.get("preflight_timeout_seconds", 3600)):
            print("audit preflight failed: preflight exceeded its runtime cap")
            return 1
        out = Path(args.evidence_out)
        out.write_bytes(canonical_bytes(evidence))
        failed = sorted(
            check["check_id"]
            for check in evidence["check_results"]
            if check["status"] == "fail"
        )
        print(
            json.dumps(
                {
                    "state": "dry_run",
                    "run_id": args.run_id,
                    "evidence_sha256": evidence["evidence_sha256"],
                    "checks": len(evidence["check_results"]),
                    "failed_checks": failed,
                    "findings": len(evidence["findings"]),
                    "elapsed_seconds": elapsed,
                },
                sort_keys=True,
            )
        )
        return 0

    reviewed = _load_preflight_evidence(
        Path(args.preflight_evidence), identity=evidence["identity"]
    )
    if reviewed["evidence_sha256"] != evidence["evidence_sha256"]:
        print("audit apply failed: apply replay differs from reviewed preflight")
        return 1
    if elapsed > float(config.get("apply_timeout_seconds", 600)):
        print("audit apply failed: apply exceeded its runtime cap")
        return 1
    prefix = f"{config['output_root']}/{args.run_id}"
    result = apply(
        storage=storage,
        config=config,
        run_id=args.run_id,
        evidence=evidence,
        prefix=prefix,
    )
    print(json.dumps(result | {"run_id": args.run_id}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
