"""Contract 06 Preview evidence report construction and immutable publication."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping
from typing import Any

import pandas as pd

from cks_picks_cfb.data.data_first_phase2d import signed_payload
from cks_picks_cfb.ratings.prospective_v5 import (
    REQUIRED_SLATES,
    V5EvidenceError,
    derive_eligibility,
    football_metrics,
    quote_diagnostic,
    recommendation,
)
from cks_picks_cfb.ratings.prospective_v5_evidence_sources import (
    EvidenceSourceError,
    collect_verified_sources,
)

EVIDENCE_MANIFEST_SCHEMA = "data_first_v5_prospective_evidence_manifest_v1"
EVIDENCE_OUTPUT_ROOT = (
    "artifacts/research/data-first-football-v1/possession-v1/evidence/runs"
)
EVIDENCE_OUTPUTS = {
    "attempt_ledger": "attempt-ledger.json",
    "football_report": "football-report.json",
    "quote_diagnostic": "quote-diagnostic.json",
    "recommendation": "recommendation.json",
}


class ProspectiveEvidenceError(ValueError):
    """Raised when a Contract 06 report cannot be safely constructed."""


def _json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    ).encode("utf-8")


def _frame_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    return json.loads(frame.to_json(orient="records", date_format="iso"))


def _identity(
    *,
    run_id: str,
    as_of: str,
    expected_code_sha: str,
    config_sha256: str,
    descriptor_sha256: str,
) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", run_id):
        raise ProspectiveEvidenceError("run_id must be a safe immutable URI component")
    timestamp = pd.Timestamp(as_of)
    if timestamp.tzinfo is None:
        raise ProspectiveEvidenceError("as_of must include a timezone")
    identity = {
        "schema_version": "data_first_v5_prospective_evidence_identity_v1",
        "run_id": run_id,
        "environment": "preview",
        "as_of": timestamp.tz_convert("UTC").isoformat(),
        "code_sha": expected_code_sha,
        "config_sha256": config_sha256,
        "input_descriptor_sha256": descriptor_sha256,
    }
    identity["identity_sha256"] = hashlib.sha256(_json_bytes(identity)).hexdigest()
    return identity


def _review_flags(review: Mapping[str, Any] | None) -> dict[str, bool]:
    if review is None:
        return {
            "validity_passed": False,
            "material_regression": False,
            "operational_problem": False,
            "satisfactory_review": False,
        }
    keys = (
        "validity_passed",
        "material_regression",
        "operational_problem",
        "satisfactory_review",
    )
    flags = {key: review.get(key) for key in keys}
    if any(not isinstance(value, bool) for value in flags.values()):
        raise ProspectiveEvidenceError(
            "signed review input must provide four boolean judgments"
        )
    return {key: bool(value) for key, value in flags.items()}


def build_evidence_outputs(inputs: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Build four deterministic, outcome-versioned role payloads."""
    attempts: pd.DataFrame = inputs["attempts"]
    evaluations: pd.DataFrame = inputs["evaluations"]
    if attempts.empty:
        raise ProspectiveEvidenceError("at least one attempted slate must be recorded")
    if evaluations.empty:
        evaluations = pd.DataFrame(
            columns=[
                "candidate",
                "season",
                "week",
                "run_id",
                "outcome_version",
                "score_completed_at",
                "last_game_completed_at",
                "outcome_ref",
                "evaluation_ref",
                "evaluation_manifest_sha256",
                "evaluation_verified",
                "supersedes_score_manifest_uri",
            ]
        )
    football_by_version: Mapping[str, pd.DataFrame] = inputs["football_by_version"]
    latest_football: pd.DataFrame = inputs["football_latest"]
    review = inputs.get("review")
    flags = _review_flags(review)
    ledger = derive_eligibility(
        attempts, evaluations, expected_candidate=str(inputs["candidate"])
    )
    qualifying_slates = int(
        ledger.loc[ledger["qualifying"], ["season", "week"]].drop_duplicates().shape[0]
    )
    ledger_payload = {
        "schema_version": "data_first_v5_evidence_attempt_ledger_v1",
        "candidate": inputs["candidate"],
        "attempts": _frame_records(attempts),
        "outcome_dispositions": _frame_records(ledger),
        "qualifying_slates": qualifying_slates,
        "required_qualifying_slates": REQUIRED_SLATES,
        "count_basis": "distinct candidate-season-week with verified ready freeze and stabilized evaluation",
        "diagnostic_or_unverified_attempts_are_excluded": True,
    }
    versions = {
        version_key: football_metrics(frame)
        for version_key, frame in sorted(football_by_version.items())
    }
    aggregate = football_metrics(latest_football)
    reason_counts = Counter(
        reason
        for value in ledger.get("reason", pd.Series(dtype=str)).astype(str)
        if value
        for reason in value.split(";")
        if reason
    )
    football_payload = {
        "schema_version": "data_first_v5_evidence_football_report_v1",
        "candidate": inputs["candidate"],
        "outcome_version_reports": versions,
        "latest_per_freeze_aggregate": aggregate,
        "attempted_freezes": int(len(attempts)),
        "verified_evaluations": int(
            evaluations.get("evaluation_verified", pd.Series(dtype=bool))
            .astype(bool)
            .sum()
        ),
        "operational_reliability": {
            "attempted_slates": int(len(attempts)),
            "independently_verified_readiness": int(
                attempts.get("readiness_verified", pd.Series(dtype=bool))
                .astype(bool)
                .sum()
            ),
            "independently_verified_freezes": int(
                attempts.get("freeze_manifest_sha256", pd.Series(dtype=str))
                .fillna("")
                .astype(str)
                .ne("")
                .sum()
            ),
            "attempt_dispositions": [
                {
                    "season": int(row.season),
                    "week": int(row.week),
                    "run_id": str(row.run_id),
                    "diagnostic_only": bool(row.diagnostic_only),
                    "readiness": str(row.readiness_overall),
                    "source_blocker": str(row.readiness_blocker or ""),
                }
                for row in attempts.itertuples(index=False)
            ],
        },
        "exclusion_reasons": dict(sorted(reason_counts.items())),
        "review_screens": {
            "target_parity_relative_difference": "1% review screen",
            "season_and_stage_regression": "5% review screen",
            "automatic_promotion": False,
        },
        "independent_season_replication": "one 2026 season; slate-block intervals do not imply multi-season replication",
        "limitations": [
            "V5 parameters and candidate identity are frozen; 2026 outcomes are evaluation only.",
            "V4 comparison is restricted to the exact paired population.",
            "Broader V5 results include completed games with a live forecast and outcome; cancellations without outcomes are excluded and remain visible in slate coverage.",
        ],
    }
    quotes: pd.DataFrame = inputs["quotes"]
    quote_population: pd.DataFrame = inputs["football_quote_population"]
    if not {"game_id", "target"} <= set(quote_population):
        quote_population = pd.DataFrame(columns=["game_id", "target"])
    quote_cutoff = str(inputs.get("quote_cutoff", ""))
    quote_summary = quote_diagnostic(quote_population, quotes, cutoff=quote_cutoff)
    quote_payload = {
        "schema_version": "data_first_v5_evidence_quote_diagnostic_v1",
        "candidate": inputs["candidate"],
        "source_ref": next(
            (
                {"uri": parent["uri"], "raw_sha256": parent["raw_sha256"]}
                for parent in inputs["parents"]
                if parent["role"] == "authentic_quotes"
            ),
            None,
        ),
        "cutoff": quote_summary.get("cutoff", quote_cutoff),
        "declared_population": {
            "game_target_count": quote_summary.get("declared_game_targets", 0),
            "game_ids": sorted(
                int(value)
                for value in quote_population.get(
                    "game_id", pd.Series(dtype=int)
                ).unique()
            ),
        },
        "quote_coverage": quote_summary,
        "authentic_quote_rows": _frame_records(quotes),
        "cannot_change_football_metrics_or_eligibility": True,
    }
    category = recommendation(
        qualifying_slates=qualifying_slates,
        **flags,
    )
    blockers: list[str] = []
    if qualifying_slates < REQUIRED_SLATES:
        blockers.append(
            f"{REQUIRED_SLATES - qualifying_slates} additional qualifying slate(s) required"
        )
    excluded = (
        ledger.loc[~ledger["qualifying"].astype(bool)] if not ledger.empty else ledger
    )
    for row in excluded.itertuples(index=False):
        blockers.append(
            f"{int(row.season)} week {int(row.week)} attempt {row.run_id}: "
            f"{row.reason or 'not qualifying'}"
        )
    if qualifying_slates >= REQUIRED_SLATES and review is None:
        blockers.append("signed Contract 06 review input is missing")
    if qualifying_slates >= REQUIRED_SLATES and not flags["satisfactory_review"]:
        blockers.append(
            "satisfactory football, calibration, coverage, and operations review is not recorded"
        )
    recommendation_payload = {
        "schema_version": "data_first_v5_evidence_recommendation_v1",
        "candidate": inputs["candidate"],
        "category": category,
        "qualifying_slates": qualifying_slates,
        "required_qualifying_slates": REQUIRED_SLATES,
        "status": (
            "continued_shadowing_required"
            if category == "continue_shadowing"
            else "review_recommendation_only"
        ),
        "blockers": blockers,
        "review_flags": flags,
        "review_ref": next(
            (
                {"uri": parent["uri"], "raw_sha256": parent["raw_sha256"]}
                for parent in inputs["parents"]
                if parent["role"] == "recommendation_review"
            ),
            None,
        ),
        "conditional_phase7_only": category == "prepare_phase7",
        "production_activation_authorized": False,
    }
    return {
        "attempt_ledger": ledger_payload,
        "football_report": football_payload,
        "quote_diagnostic": quote_payload,
        "recommendation": recommendation_payload,
    }


def preflight_evidence(
    storage: Any,
    *,
    descriptor: Mapping[str, Any],
    expected_code_sha: str,
    run_id: str,
    as_of: str,
    config_bytes: bytes,
    descriptor_bytes: bytes,
) -> dict[str, Any]:
    try:
        inputs = collect_verified_sources(
            storage, descriptor=descriptor, expected_code_sha=expected_code_sha
        )
        outputs = build_evidence_outputs(inputs)
    except (EvidenceSourceError, V5EvidenceError, ValueError) as exc:
        raise ProspectiveEvidenceError(str(exc)) from exc
    descriptor_sha = hashlib.sha256(descriptor_bytes).hexdigest()
    identity = _identity(
        run_id=run_id,
        as_of=as_of,
        expected_code_sha=expected_code_sha,
        config_sha256=hashlib.sha256(config_bytes).hexdigest(),
        descriptor_sha256=descriptor_sha,
    )
    prefix = f"{EVIDENCE_OUTPUT_ROOT}/{run_id}"
    output_plan = {}
    for name, body in outputs.items():
        raw = _json_bytes(body)
        output_plan[name] = {
            "uri": f"{prefix}/{EVIDENCE_OUTPUTS[name]}",
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
            "byte_count": len(raw),
        }
    parents = sorted(
        inputs["parents"], key=lambda row: (str(row["role"]), str(row["uri"]))
    )
    descriptor_uri = f"{prefix}/input-descriptor.json"
    config_uri = f"{prefix}/config.yaml"
    return {
        "schema_version": "data_first_v5_prospective_evidence_preflight_v1",
        "state": "dry_run",
        "identity": identity,
        "candidate": inputs["candidate"],
        "input_descriptor": {
            "uri": descriptor_uri,
            "raw_sha256": descriptor_sha,
            "byte_count": len(descriptor_bytes),
        },
        "config_ref": {
            "uri": config_uri,
            "raw_sha256": hashlib.sha256(config_bytes).hexdigest(),
            "byte_count": len(config_bytes),
        },
        "parents": parents,
        "output_plan": output_plan,
        "qualifying_slates": outputs["attempt_ledger"]["qualifying_slates"],
        "recommendation": outputs["recommendation"]["category"],
        "production_activation_authorized": False,
    }


def apply_evidence(
    storage: Any,
    *,
    descriptor: Mapping[str, Any],
    expected_code_sha: str,
    run_id: str,
    as_of: str,
    config_bytes: bytes,
    descriptor_bytes: bytes,
    expected_preflight: Mapping[str, Any],
) -> dict[str, Any]:
    evidence = preflight_evidence(
        storage,
        descriptor=descriptor,
        expected_code_sha=expected_code_sha,
        run_id=run_id,
        as_of=as_of,
        config_bytes=config_bytes,
        descriptor_bytes=descriptor_bytes,
    )
    if _json_bytes(evidence) != _json_bytes(expected_preflight):
        raise ProspectiveEvidenceError(
            "apply recomputation differs from reviewed preflight"
        )
    prefix = f"{EVIDENCE_OUTPUT_ROOT}/{run_id}"
    manifest_uri = f"{prefix}/evidence-manifest.json"
    if storage.exists(manifest_uri):
        existing, _ = _json_from_storage(storage, manifest_uri)
        if (existing.get("identity") or {}).get("identity_sha256") != evidence[
            "identity"
        ]["identity_sha256"]:
            raise ProspectiveEvidenceError(
                "evidence run ID already has a different identity"
            )
        from cks_picks_cfb.ratings.prospective_v5_evidence_verification import (
            verify_evidence_artifact,
        )

        verification = verify_evidence_artifact(
            storage, manifest_uri=manifest_uri, expected_code_sha=expected_code_sha
        )
        return {
            "state": "already_applied",
            "manifest_uri": manifest_uri,
            "verified": True,
            "verification": verification,
        }
    existing = storage.list_files(prefix)
    if existing:
        raise ProspectiveEvidenceError(
            "evidence run prefix contains partial immutable outputs"
        )
    inputs = collect_verified_sources(
        storage, descriptor=descriptor, expected_code_sha=expected_code_sha
    )
    outputs = build_evidence_outputs(inputs)
    descriptor_uri = str(evidence["input_descriptor"]["uri"])
    _write_immutable(storage, descriptor_uri, descriptor_bytes)
    _write_immutable(storage, str(evidence["config_ref"]["uri"]), config_bytes)
    output_refs = {}
    for name, payload in outputs.items():
        uri = str(evidence["output_plan"][name]["uri"])
        raw = _json_bytes(payload)
        if (
            hashlib.sha256(raw).hexdigest()
            != evidence["output_plan"][name]["raw_sha256"]
        ):
            raise ProspectiveEvidenceError(
                f"output digest changed after preflight: {name}"
            )
        _write_immutable(storage, uri, raw)
        output_refs[name] = {
            "uri": uri,
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
            "byte_count": len(raw),
        }
    manifest = signed_payload(
        {
            "schema_version": EVIDENCE_MANIFEST_SCHEMA,
            "state": "frozen",
            "identity": evidence["identity"],
            "candidate": evidence["candidate"],
            "input_descriptor": evidence["input_descriptor"],
            "config_ref": evidence["config_ref"],
            "parents": evidence["parents"],
            "output_refs": output_refs,
            "qualifying_slates": evidence["qualifying_slates"],
            "recommendation": evidence["recommendation"],
            "production_activation_authorized": False,
        }
    )
    _write_immutable(storage, manifest_uri, _json_bytes(manifest))
    return {
        "state": "applied",
        "manifest_uri": manifest_uri,
        "qualifying_slates": evidence["qualifying_slates"],
        "recommendation": evidence["recommendation"],
        "already_applied": False,
    }


def _json_from_storage(storage: Any, uri: str) -> tuple[dict[str, Any], bytes]:
    raw = storage.read_bytes(uri)
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProspectiveEvidenceError(f"unreadable evidence object: {uri}") from exc
    return value, raw


def _write_immutable(storage: Any, uri: str, raw: bytes) -> None:
    if storage.exists(uri):
        if storage.read_bytes(uri) != raw:
            raise ProspectiveEvidenceError(f"immutable evidence collision at {uri}")
        return
    storage.write_bytes(raw, uri)
