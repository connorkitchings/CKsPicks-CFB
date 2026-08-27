"""Candidate-v2 manifest and prospective-policy contracts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

CANDIDATE_V2_MANIFEST_VERSION = "rating_successor_v2_candidate_manifest_v1"
PROSPECTIVE_V2_POLICY_VERSION = "successor_v2_prospective_evidence_v1"


class SuccessorManifestError(ValueError):
    """Raised when a candidate-v2 identity attempts to bypass a sealed gate."""


@dataclass(frozen=True)
class SuccessorV2ProspectivePolicy:
    version: str
    season: int
    first_eligible_week: int
    minimum_games: int
    hard_lead_seconds: int
    stabilization_seconds: int
    required_slates: int
    research_prefix: str


def load_successor_v2_prospective_policy(
    path: str | Path,
) -> SuccessorV2ProspectivePolicy:
    raw = yaml.safe_load(Path(path).read_text())
    if raw.get("prospective_policy_version") != PROSPECTIVE_V2_POLICY_VERSION:
        raise SuccessorManifestError("Unsupported successor-v2 prospective policy")
    if raw.get("candidate_generation") != "v2" or raw.get("season") != 2026:
        raise SuccessorManifestError(
            "Prospective policy must be exclusive to candidate v2 in 2026"
        )
    if raw.get("forbidden_evidence_transfer_from") != "candidate_v1":
        raise SuccessorManifestError("Candidate-v1 evidence transfer must be forbidden")
    if raw.get("allow_retrospective_freeze") is not False:
        raise SuccessorManifestError("Candidate v2 may not allow retrospective freezes")
    values = {
        "first_eligible_week": int(raw["first_eligible_normal_coverage_week"]),
        "minimum_games": int(raw["normal_coverage_min_games"]),
        "hard_lead_seconds": int(raw["hard_lead_seconds"]),
        "stabilization_seconds": int(raw["scoring_stabilization_seconds"]),
        "required_slates": int(raw["required_eligible_slates"]),
    }
    if min(values.values()) <= 0 or values["minimum_games"] < 40:
        raise SuccessorManifestError(
            "Prospective policy has invalid eligibility thresholds"
        )
    prefix = raw.get("research_prefix")
    if not isinstance(prefix, str) or not prefix:
        raise SuccessorManifestError("Prospective policy requires a research prefix")
    return SuccessorV2ProspectivePolicy(
        version=PROSPECTIVE_V2_POLICY_VERSION,
        season=2026,
        research_prefix=prefix.rstrip("/"),
        **values,
    )


def policy_sha256(policy: SuccessorV2ProspectivePolicy) -> str:
    return hashlib.sha256(
        json.dumps(asdict(policy), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def candidate_v2_manifest(
    *,
    code_sha: str,
    history_ref_set_uri: str,
    history_ref_set_sha256: str,
    prior_report_uri: str,
    prior_report_sha256: str,
    update_report_uri: str,
    update_report_sha256: str,
    predictor_report_uri: str,
    predictor_report_sha256: str,
    predictor_gates_passed: bool,
    prediction_ref: Mapping[str, Any],
    policy: SuccessorV2ProspectivePolicy,
) -> dict[str, Any]:
    """Create a candidate-v2 identity only after every R4 gate has passed."""

    if not predictor_gates_passed:
        raise SuccessorManifestError(
            "Candidate v2 cannot freeze after a failed predictor tournament"
        )
    if not code_sha or any(
        not value
        for value in (
            history_ref_set_uri,
            history_ref_set_sha256,
            prior_report_uri,
            prior_report_sha256,
            update_report_uri,
            update_report_sha256,
            predictor_report_uri,
            predictor_report_sha256,
        )
    ):
        raise SuccessorManifestError(
            "Candidate v2 manifest requires complete immutable lineage"
        )
    if not prediction_ref.get("version_id") or not prediction_ref.get("content_sha"):
        raise SuccessorManifestError(
            "Candidate v2 manifest requires an immutable prediction ref"
        )
    return {
        "manifest_version": CANDIDATE_V2_MANIFEST_VERSION,
        "candidate_generation": "v2",
        "code_sha": code_sha,
        "history": {"uri": history_ref_set_uri, "sha256": history_ref_set_sha256},
        "sealed_tournaments": {
            "between_season": {"uri": prior_report_uri, "sha256": prior_report_sha256},
            "within_season": {"uri": update_report_uri, "sha256": update_report_sha256},
            "structured_predictor": {
                "uri": predictor_report_uri,
                "sha256": predictor_report_sha256,
                "all_gates_passed": True,
            },
        },
        "prediction_ref": dict(prediction_ref),
        "prospective_policy": {
            "version": policy.version,
            "sha256": policy_sha256(policy),
        },
        "first_eligible_slate_rule": "first normal-coverage slate frozen after committed candidate-v2 implementation",
        "candidate_v1_evidence_transferred": False,
        "retrospective_freeze_allowed": False,
    }
