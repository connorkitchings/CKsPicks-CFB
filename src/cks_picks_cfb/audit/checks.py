"""No-write verification harness for parent-manifest evidence.

Every check operates on manifest metadata (signatures, identities, parent
URIs, output references, declared counts, seasons, code/config hashes) and
never downloads row data, so results stay compact. Uses generic storage
readers and signing utilities only; never imports producer computations.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from cks_picks_cfb.audit import (
    ELIGIBLE_SEASONS,
    FORBIDDEN_SEASONS,
    PARENT_STAGES,
    PROVISIONAL_SEVERITY,
    REJECTED_SEASONS,
    SEALED_REPAIR_POPULATION,
    SEEDED_FINDINGS,
)
from cks_picks_cfb.audit.register import git_commit_exists, git_file_sha256
from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload


class AuditCheckError(ValueError):
    """Raised when a check cannot be constructed from malformed evidence."""


def _result(
    check_id: str,
    layer: str,
    category: str,
    status: str,
    expected: Any,
    observed: Any,
    population: str,
    evidence_refs: list[str],
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "layer": layer,
        "category": category,
        "status": status,
        "expected": expected,
        "observed": observed,
        "population": population,
        "evidence_refs": list(evidence_refs),
    }


def check_signature(
    stage: str, manifest: Mapping[str, Any], manifest_uri: str
) -> dict[str, Any]:
    try:
        verify_signed_payload(manifest, label=f"{stage} manifest")
    except ValueError as exc:
        return _result(
            f"manifest.{stage}.signature",
            "lineage",
            "signature",
            "fail",
            "valid manifest_sha256 checksum",
            str(exc),
            f"parent manifest: {stage}",
            [manifest_uri],
        )
    return _result(
        f"manifest.{stage}.signature",
        "lineage",
        "signature",
        "pass",
        "valid manifest_sha256 checksum",
        str(manifest.get("manifest_sha256")),
        f"parent manifest: {stage}",
        [manifest_uri],
    )


def check_identity(
    stage: str,
    manifest: Mapping[str, Any],
    manifest_uri: str,
    *,
    expected_run_id: str,
    expected_schema: str,
) -> dict[str, Any]:
    identity = manifest.get("identity") or {}
    problems: list[str] = []
    if manifest.get("schema_version") != expected_schema:
        problems.append(f"schema_version={manifest.get('schema_version')!r}")
    if identity.get("environment") != "preview":
        problems.append(f"environment={identity.get('environment')!r}")
    if identity.get("run_id") != expected_run_id:
        problems.append(f"run_id={identity.get('run_id')!r}")
    if not identity.get("code_sha"):
        problems.append("code_sha missing")
    if not identity.get("config_sha"):
        problems.append("config_sha missing")
    if tuple(identity.get("development_seasons") or ()) != ELIGIBLE_SEASONS:
        problems.append("development_seasons drifted")
    if tuple(identity.get("forbidden_seasons") or ()) != FORBIDDEN_SEASONS:
        problems.append("forbidden_seasons drifted")
    return _result(
        f"manifest.{stage}.identity",
        "lineage",
        "identity",
        "fail" if problems else "pass",
        f"schema={expected_schema}, environment=preview, run_id={expected_run_id}",
        "ok" if not problems else "; ".join(problems),
        f"parent manifest: {stage}",
        [manifest_uri],
    )


def check_state(
    stage: str,
    manifest: Mapping[str, Any],
    manifest_uri: str,
    *,
    expected_state: str | None,
) -> dict[str, Any]:
    observed = manifest.get("state")
    if expected_state is None:
        return _result(
            f"manifest.{stage}.state",
            "lineage",
            "lifecycle",
            "pass",
            "stateless R6 producer manifest (no lifecycle state field)",
            f"state={observed!r}",
            f"parent manifest: {stage}",
            [manifest_uri],
        )
    return _result(
        f"manifest.{stage}.state",
        "lineage",
        "lifecycle",
        "pass" if observed == expected_state else "fail",
        f"state={expected_state}",
        f"state={observed!r}",
        f"parent manifest: {stage}",
        [manifest_uri],
    )


def check_production_flags(
    stage: str, manifest: Mapping[str, Any], manifest_uri: str
) -> dict[str, Any]:
    problems: list[str] = []
    if manifest.get("production_activation_authorized") is not False:
        problems.append("production_activation_authorized is not false")
    if (
        "model_selection_authorized" in manifest
        and manifest.get("model_selection_authorized") is not False
    ):
        problems.append("model_selection_authorized is not false")
    return _result(
        f"manifest.{stage}.production_flags",
        "lineage",
        "activation",
        "fail" if problems else "pass",
        "production_activation_authorized=false",
        "ok" if not problems else "; ".join(problems),
        f"parent manifest: {stage}",
        [manifest_uri],
    )


def check_parent_links(
    manifests: Mapping[str, Mapping[str, Any]],
    expected_uris: Mapping[str, str],
    raw_shas: Mapping[str, str],
) -> list[dict[str, Any]]:
    """Verify pinned parent URIs and raw checksums agree across manifests."""
    results: list[dict[str, Any]] = []
    # (child stage, parent URI key, parent stage, pinned raw-SHA key)
    links = (
        ("forecasts", "rating_manifest_uri", "ratings", "rating_raw_sha256"),
        (
            "forecasts",
            "measurement_manifest_uri",
            "measurements",
            "measurement_raw_sha256",
        ),
        ("forecasts", "repair_manifest_uri", "repair", "repair_raw_sha256"),
        (
            "ratings",
            "measurement_manifest_uri",
            "measurements",
            "measurement_manifest_raw_sha256",
        ),
        ("ratings", "repair_manifest_uri", "repair", "repair_manifest_raw_sha256"),
        (
            "measurements",
            "repair_manifest_uri",
            "repair",
            "repair_manifest_raw_sha256",
        ),
    )
    for child, key, parent, sha_key in links:
        child_manifest = manifests[child]
        parents = child_manifest.get("parents") or child_manifest.get("identity") or {}
        observed_uri = parents.get(key) or child_manifest.get(key)
        expected_uri = expected_uris[parent]
        child_uri = expected_uris[child]
        ok = observed_uri == expected_uri
        observed = f"{key}={observed_uri!r}"
        pinned_sha = parents.get(sha_key) or child_manifest.get(sha_key)
        if ok and pinned_sha and pinned_sha != raw_shas.get(parent):
            ok = False
            observed += f"; pinned {sha_key} does not match {parent} raw bytes"
        results.append(
            _result(
                f"parents.{child}.{parent}.uri",
                "lineage",
                "parent_uri",
                "pass" if ok else "fail",
                expected_uri,
                observed,
                f"{child} -> {parent}",
                [child_uri, expected_uri],
            )
        )
    return results


def _expected_roles(stage: str) -> dict[str, tuple[str, str]]:
    for entry in PARENT_STAGES:
        if entry["stage"] == stage:
            return {
                role: (dataset, schema)
                for role, dataset, schema in entry["output_datasets"]
            }
    raise AuditCheckError(f"unknown audit stage: {stage}")


def check_output_refs(
    stage: str,
    manifest: Mapping[str, Any],
    manifest_uri: str,
    storage: Any,
    *,
    max_examples: int = 8,
) -> dict[str, Any]:
    """Verify output roles, ref identities, and referenced-object existence.

    Only manifest-level refs and existence probes are used; no dataset bytes
    are downloaded.
    """
    expected = _expected_roles(stage)
    output_refs = manifest.get("output_refs")
    problems: list[str] = []
    if not isinstance(output_refs, dict) or set(output_refs) != set(expected):
        problems.append(
            f"output roles={sorted(output_refs) if isinstance(output_refs, dict) else type(output_refs).__name__!r}"
        )
        return _result(
            f"outputs.{stage}.refs",
            "outputs",
            "output_refs",
            "fail",
            f"roles={sorted(expected)}",
            "; ".join(problems),
            f"parent manifest: {stage}",
            [manifest_uri],
        )
    missing: list[str] = []
    for role in sorted(expected):
        dataset, schema = expected[role]
        ref = output_refs.get(role) or {}
        for key, want in (
            ("dataset", dataset),
            ("schema_version", schema),
        ):
            if ref.get(key) != want:
                problems.append(f"{role}.{key}={ref.get(key)!r}")
        for key in ("version_id", "content_sha", "uri"):
            if not ref.get(key):
                problems.append(f"{role}.{key} missing")
        uri = ref.get("uri")
        if uri:
            try:
                if not storage.exists(uri):
                    missing.append(f"{role}:{uri}")
            except Exception as exc:  # fail closed on unreadable evidence
                problems.append(f"{role} existence probe failed: {exc}")
    problems.extend(missing[:max_examples])
    if len(missing) > max_examples:
        problems.append(f"... plus {len(missing) - max_examples} more missing refs")
    return _result(
        f"outputs.{stage}.refs",
        "outputs",
        "output_refs",
        "fail" if problems else "pass",
        f"roles={sorted(expected)} with dataset/schema identity and existing URIs",
        "ok" if not problems else "; ".join(problems),
        f"parent manifest: {stage}",
        [manifest_uri],
    )


def check_row_counts(
    stage: str, manifests: Mapping[str, Mapping[str, Any]], manifest_uri: str
) -> dict[str, Any]:
    """Verify declared counts are positive and cross-manifest counts agree."""
    manifest = manifests[stage]
    output_rows = manifest.get("output_rows")
    problems: list[str] = []
    if stage in ("repair", "measurements"):
        if not isinstance(output_rows, dict) or not output_rows:
            problems.append("output_rows missing")
        else:
            bad = sorted(
                role
                for role, count in output_rows.items()
                if not isinstance(count, int) or count <= 0
            )
            if bad:
                problems.append(f"non-positive row counts: {bad}")
    if stage == "repair":
        population = manifest.get("population") or {}
        for key, want in SEALED_REPAIR_POPULATION.items():
            if population.get(key) != want:
                problems.append(f"population.{key}={population.get(key)!r}")
    if stage == "measurements":
        repair_rows = (manifests["repair"].get("output_rows") or {}).get("population")
        measurement_rows = (output_rows or {}).get("population")
        if (
            isinstance(repair_rows, int)
            and isinstance(measurement_rows, int)
            and repair_rows != measurement_rows
        ):
            problems.append(
                f"population rows disagree: repair={repair_rows} "
                f"measurements={measurement_rows}"
            )
    observed = (
        "ok"
        if not problems
        else "; ".join(problems) + f" (declared={dict(output_rows or {})})"
    )
    return _result(
        f"outputs.{stage}.row_counts",
        "outputs",
        "row_counts",
        "fail" if problems else "pass",
        "positive declared counts; repair/measurements population agreement",
        observed,
        f"parent manifest: {stage}",
        [manifest_uri],
    )


def _season_ints(node: Any, key: str | None, *, found: list[tuple[str, int]]) -> None:
    # The forbidden-seasons declaration names the excluded season; it is the
    # policy statement, not evidence containing that season.
    if key is not None and key.casefold() == "forbidden_seasons":
        return
    if isinstance(node, Mapping):
        for child_key, value in node.items():
            _season_ints(value, str(child_key), found=found)
    elif isinstance(node, list):
        for item in node:
            _season_ints(item, key, found=found)
    elif (
        isinstance(node, int)
        and not isinstance(node, bool)
        and key is not None
        and "season" in key.casefold()
    ):
        found.append((key, node))


def check_seasons(
    stage: str,
    manifest: Mapping[str, Any],
    manifest_uri: str,
    *,
    rejected: tuple[int, ...] = REJECTED_SEASONS,
) -> dict[str, Any]:
    found: list[tuple[str, int]] = []
    _season_ints(manifest, None, found=found)
    rejected_hits = sorted({(key, year) for key, year in found if year in rejected})
    ineligible = sorted({year for _, year in found if year not in ELIGIBLE_SEASONS})
    problems: list[str] = []
    if rejected_hits:
        problems.append(f"rejected seasons present: {rejected_hits}")
    if ineligible:
        problems.append(f"non-development seasons present: {ineligible}")
    return _result(
        f"population.{stage}.seasons",
        "population",
        "season_gate",
        "fail" if problems else "pass",
        f"only {list(ELIGIBLE_SEASONS)}; never {list(rejected)}",
        "ok" if not problems else "; ".join(problems),
        f"parent manifest: {stage}",
        [manifest_uri],
    )


def check_code_config(
    stage: str,
    manifest: Mapping[str, Any],
    manifest_uri: str,
    *,
    config_path: str,
) -> dict[str, Any]:
    """Verify the recorded commit exists and pins the recorded config bytes."""
    identity = manifest.get("identity") or {}
    code_sha = str(identity.get("code_sha") or "")
    config_sha = str(identity.get("config_sha") or "")
    problems: list[str] = []
    if not git_commit_exists(code_sha):
        problems.append(f"commit {code_sha!r} is absent from the local object database")
        observed = "; ".join(problems)
    else:
        committed = git_file_sha256(code_sha, config_path)
        if committed is None:
            problems.append(f"{config_path} is absent at commit {code_sha[:12]}")
            observed = "; ".join(problems)
        elif committed != config_sha:
            problems.append(
                f"{config_path} hash at commit differs from recorded config_sha"
            )
            observed = "; ".join(problems) + f" (committed={committed})"
        else:
            observed = f"commit present; {config_path} bytes match recorded config_sha"
    return _result(
        f"lineage.{stage}.code_config",
        "lineage",
        "code_config",
        "fail" if problems else "pass",
        "recorded commit present; committed config bytes match recorded config_sha",
        observed,
        f"parent manifest: {stage}",
        [manifest_uri],
    )


def check_lineage_exhaustive(
    nested: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Fail closed when any reachable lineage node is unreadable."""
    unreadable = sorted(
        uri
        for uri, record in nested.items()
        if "payload" not in record and not record.get("opaque")
    )
    opaque = sorted(uri for uri, record in nested.items() if record.get("opaque"))
    observed = (
        f"reachable={len(nested)}, opaque_leaves={len(opaque)}"
        if not unreadable
        else f"unreadable={unreadable[:8]}"
    )
    return _result(
        "lineage.exhaustive",
        "lineage",
        "traversal",
        "fail" if unreadable else "pass",
        "every reachable node decoded or recorded as an opaque leaf",
        observed,
        "recursive parent manifests",
        [],
    )


def seeded_provisional_findings(
    conditions: Mapping[str, bool],
) -> list[dict[str, Any]]:
    """Seed confirmed structural conditions as provisional findings.

    Severity and disposition are assigned by 10b; 10a records the confirmed
    condition, affected artifacts, and evidence only.
    """
    findings: list[dict[str, Any]] = []
    for seed in SEEDED_FINDINGS:
        key = seed["finding_id"]
        findings.append(
            {
                "finding_id": key,
                "severity": PROVISIONAL_SEVERITY,
                "disposition": PROVISIONAL_SEVERITY,
                "closure_state": "open",
                "title": seed["title"],
                "description": seed["description"],
                "condition_confirmed": bool(conditions.get(key, False)),
                "affected_stages": list(seed["affected_stages"]),
                "evidence": {
                    "audit-structural-001": [
                        "scripts/research/verify_data_first_repair_v2.py",
                        "scripts/research/run_data_first_repair_v2.py",
                    ],
                    "audit-structural-002": [
                        "src/cks_picks_cfb/forecast/forecast_verification.py",
                    ],
                }[key],
                "permitted_use": "to be determined by 10b",
                "required_action": "10b determines scope, severity, disposition, closure criteria",
                "closure_criteria": "to be determined by 10b",
                "blocking_dependencies": [],
            }
        )
    return findings


def behavioral_cells_to_checks(
    cells: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Convert behavioral matrix cells to check-result records."""
    return [
        _result(
            str(cell["cell_id"]),
            "assurance",
            "behavioral",
            "pass" if cell["match"] else "fail",
            f"expected behavior: {cell['expected']}",
            f"observed behavior: {cell['observed']} (method: {cell['method']})",
            f"{cell['verifier']} verifier / {cell['case']}",
            [],
        )
        for cell in cells
    ]


def behavioral_findings(
    cells: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Convert behavioral mismatches into fully specified provisional findings.

    One finding per verifier with any mismatching cell. A failed assessed
    verifier becomes a finding; it never blocks harness closure.
    """
    mismatched: dict[str, list[Mapping[str, Any]]] = {}
    for cell in cells:
        if not cell["match"]:
            mismatched.setdefault(str(cell["verifier"]), []).append(cell)
    findings: list[dict[str, Any]] = []
    for verifier in sorted(mismatched):
        bad = mismatched[verifier]
        findings.append(
            {
                "finding_id": f"audit-behavioral-{verifier}",
                "severity": PROVISIONAL_SEVERITY,
                "disposition": PROVISIONAL_SEVERITY,
                "closure_state": "open",
                "title": f"{verifier} verifier behavioral mismatch",
                "description": (
                    f"{len(bad)} behavioral case(s) did not match the "
                    "independent-verifier expectation."
                ),
                "condition_confirmed": True,
                "affected_stages": [verifier],
                "evidence": [str(cell["cell_id"]) for cell in bad],
                "cells": [dict(cell) for cell in bad],
                "permitted_use": "to be determined by 10b",
                "required_action": "10b determines scope, severity, disposition, closure criteria",
                "closure_criteria": "to be determined by 10b",
                "blocking_dependencies": [],
            }
        )
    return findings
