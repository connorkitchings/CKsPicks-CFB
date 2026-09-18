"""Lineage inventory and evidence-register builder (read-only).

Resolves every source/output reference from the four frozen parent manifests
into a parent/output graph, and emits candidate evidence-register rows. Uses
generic storage readers and signing utilities only; never imports producer
computations. Never writes to any backend.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from cks_picks_cfb.audit import (
    ELIGIBLE_SEASONS,
    FORBIDDEN_SEASONS,
    PARENT_STAGES,
    SEALED_REPAIR_POPULATION,
)
from cks_picks_cfb.data.data_first_phase2d import sha256

ROOT = Path(__file__).resolve().parents[3]


class AuditError(ValueError):
    """Raised when audit evidence is incomplete or inconsistent."""


def validate_config(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the Preview-only audit configuration."""
    from cks_picks_cfb.audit import AUDIT_CONFIG_SCHEMA

    if payload.get("schema_version") != AUDIT_CONFIG_SCHEMA:
        raise AuditError("unexpected historical audit config schema")
    if payload.get("environment") != "preview":
        raise AuditError("historical audit config must be Preview-only")
    if tuple(payload.get("development_seasons") or ()) != ELIGIBLE_SEASONS:
        raise AuditError("historical audit development season policy drifted")
    if tuple(payload.get("forbidden_seasons") or ()) != FORBIDDEN_SEASONS:
        raise AuditError("historical audit forbidden season policy drifted")
    parents = payload.get("parents")
    if not isinstance(parents, dict):
        raise AuditError("historical audit config parents are missing")
    stages = {entry["stage"] for entry in PARENT_STAGES}
    if set(parents) != stages:
        raise AuditError("historical audit config must pin all four parents")
    normalized: dict[str, Any] = dict(payload)
    for stage in sorted(stages):
        entry = parents.get(stage)
        if (
            not isinstance(entry, dict)
            or not entry.get("manifest_uri")
            or not entry.get("run_id")
            or not entry.get("config_path")
        ):
            raise AuditError(f"historical audit parent {stage} is incomplete")
    if not payload.get("output_root"):
        raise AuditError("historical audit config output root is missing")
    if payload.get("production_activation_authorized") is not False:
        raise AuditError("historical audit config may not authorize production")
    return normalized


def read_manifest(storage: Any, uri: str) -> tuple[dict[str, Any], str]:
    """Read a manifest URI and return its payload plus raw SHA-256."""
    try:
        raw = storage.read_bytes(uri)
    except Exception as exc:
        raise AuditError(f"audit manifest is unreadable: {uri}") from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AuditError(f"audit manifest is not JSON: {uri}") from exc
    if not isinstance(payload, dict):
        raise AuditError(f"audit manifest is not an object: {uri}")
    return payload, hashlib.sha256(raw).hexdigest()


def iter_manifest_uris(payload: Mapping[str, Any]) -> list[tuple[str, str]]:
    """Collect parent-manifest URIs referenced under parents/identity keys.

    Only values under ``parents`` or ``identity`` mappings whose key ends with
    ``_uri`` and whose value is an ``artifacts/`` JSON path are collected.
    Output dataset refs are never followed here: auditing them is 10b work and
    following them would download row data during the read-only preflight.
    """
    found: list[tuple[str, str]] = []

    def visit(node: Any, section: str | None) -> None:
        if isinstance(node, Mapping):
            for key, value in node.items():
                child_section = section
                if section is None and key in ("parents", "identity"):
                    child_section = str(key)
                if (
                    child_section in ("parents", "identity")
                    and isinstance(key, str)
                    and key.endswith("_uri")
                    and isinstance(value, str)
                    and value.startswith("artifacts/")
                    and value.endswith(".json")
                ):
                    found.append((f"{child_section}.{key}", value))
                visit(value, child_section)
        elif isinstance(node, list):
            for item in node:
                visit(item, section)

    visit(payload, None)
    return found


def collect_nested_manifests(
    storage: Any, payload: Mapping[str, Any], *, max_depth: int = 3
) -> dict[str, dict[str, Any]]:
    """Read recursively referenced parent manifests (metadata only).

    Returns a mapping of manifest URI to ``{"payload": ..., "raw_sha256": ...}``
    or ``{"error": ...}`` when a nested reference cannot be read. Unreadable
    nested evidence becomes a lineage finding in 10b; it never stops the
    top-level inventory.
    """
    collected: dict[str, dict[str, Any]] = {}
    frontier = [uri for _, uri in iter_manifest_uris(payload)]
    depth = 0
    while frontier and depth < max_depth:
        pending = [uri for uri in frontier if uri not in collected]
        frontier = []
        for uri in pending:
            try:
                nested, raw_sha = read_manifest(storage, uri)
            except AuditError as exc:
                collected[uri] = {"error": str(exc)}
                continue
            collected[uri] = {"payload": nested, "raw_sha256": raw_sha}
            frontier.extend(
                child for _, child in iter_manifest_uris(nested) if child != uri
            )
        depth += 1
    return collected


def build_graph(
    parents: Mapping[str, Mapping[str, Any]],
    nested: Mapping[str, Mapping[str, Any]],
    manifest_uris: Mapping[str, str],
) -> dict[str, Any]:
    """Build the parent/output graph from source eligibility to forecasts."""
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, str]] = []

    def add_node(uri: str, kind: str, stage: str | None = None) -> None:
        if uri not in nodes:
            nodes[uri] = {"uri": uri, "kind": kind}
            if stage is not None:
                nodes[uri]["stage"] = stage

    for stage, manifest in parents.items():
        manifest_uri = manifest_uris[stage]
        add_node(str(manifest_uri), "manifest", stage)
        for _, uri in iter_manifest_uris(manifest):
            add_node(uri, "manifest")
            edges.append({"from": uri, "to": str(manifest_uri), "role": "parent"})
        for role, ref in (manifest.get("output_refs") or {}).items():
            if isinstance(ref, Mapping) and ref.get("uri"):
                ref_uri = str(ref["uri"])
                add_node(ref_uri, "dataset", stage)
                edges.append(
                    {"from": str(manifest_uri), "to": ref_uri, "role": f"output:{role}"}
                )
    for uri, record in nested.items():
        if "payload" in record:
            add_node(uri, "manifest")
    edges.sort(key=lambda edge: (edge["from"], edge["to"], edge["role"]))
    return {
        "nodes": [nodes[uri] for uri in sorted(nodes)],
        "edges": edges,
    }


def declared_permitted_use(stage: str, manifest: Mapping[str, Any]) -> str:
    """Restate the manifest's declared permitted use without interpreting it."""
    activation = manifest.get("production_activation_authorized")
    state = manifest.get("state")
    timing = manifest.get("timing_class")
    if activation is not False:
        return "undeclared (production flag is not false)"
    if stage == "repair":
        return "repaired reconstructed source/population parent only"
    if stage == "measurements":
        return "contract-03 rating input only"
    if stage == "ratings":
        return "contract-04 forecast input only"
    if stage == "forecasts":
        return "historical evidence only (forecast eligibility pending contract 11)"
    return f"undeclared (state={state}, timing={timing})"


def build_register_row(
    *,
    stage: str,
    manifest_uri: str,
    manifest: Mapping[str, Any],
    raw_sha256: str,
) -> dict[str, Any]:
    """Build one candidate evidence-register row for a parent manifest."""
    identity = manifest.get("identity") or {}
    output_refs = manifest.get("output_refs") or {}
    outputs: dict[str, Any] = {}
    for role, ref in output_refs.items():
        if isinstance(ref, Mapping):
            outputs[str(role)] = {
                key: ref.get(key)
                for key in (
                    "dataset",
                    "version_id",
                    "schema_version",
                    "content_sha",
                    "records_sha",
                    "uri",
                )
                if ref.get(key) is not None
            }
    output_rows = manifest.get("output_rows")
    row = {
        "component": f"v5-{stage}",
        "role": "audit_parent",
        "uri": manifest_uri,
        "raw_sha256": raw_sha256,
        "canonical_sha256": manifest.get("manifest_sha256"),
        "code_sha": identity.get("code_sha"),
        "config_sha": identity.get("config_sha"),
        "seasons": list(identity.get("development_seasons") or []),
        "timing_class": manifest.get("timing_class"),
        "parent_identities": {
            key: value for key, value in (manifest.get("parents") or {}).items()
        },
        "outputs": outputs,
        "row_counts": dict(output_rows) if isinstance(output_rows, Mapping) else {},
        "declared_permitted_use": declared_permitted_use(stage, manifest),
    }
    return row


def git_commit_exists(commit: str, *, root: Path = ROOT) -> bool:
    """Check commit presence in the local Git object database (no checkout)."""
    if not commit or len(commit) < 7:
        return False
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def git_file_sha256(commit: str, path: str, *, root: Path = ROOT) -> str | None:
    """Hash a committed path's bytes without touching the worktree."""
    result = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return hashlib.sha256(result.stdout).hexdigest()


def sealed_repair_counts() -> dict[str, int]:
    return dict(SEALED_REPAIR_POPULATION)


def evidence_digest(evidence: Mapping[str, Any]) -> str:
    """Canonical digest of unsigned audit evidence (timing excluded)."""
    return sha256(evidence)
